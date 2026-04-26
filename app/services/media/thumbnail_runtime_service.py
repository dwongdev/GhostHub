"""Specter-owned thumbnail queue, worker, and status runtime."""

import gc
import logging
import os
import time
import traceback
from collections import deque
from itertools import islice
from urllib.parse import quote

import gevent
import psutil
from gevent.lock import BoundedSemaphore, RLock as GeventRLock
from gevent.queue import Empty, Full, JoinableQueue

from specter import Service, registry
from app.utils.media_utils import (
    GC_THRESHOLD,
    IMAGE_THUMBNAIL_MIN_SIZE,
    THUMBNAIL_SIZE_PI,
    generate_image_thumbnail,
    generate_thumbnail,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT_TASKS = 2
GC_INTERVAL = 60
STALE_CATEGORY_STATUS_SECONDS = 30
CATEGORY_PRIORITY_BOOST_SECONDS = 90
THUMBNAIL_INDEX_BATCH_SIZE = 500


class PerformanceMonitor:
    """Track recent thumbnail processing rates for lightweight diagnostics."""

    def __init__(self, window_size=10):
        self.window_size = window_size
        self.tasks_processed = 0
        self.task_times = []
        self.start_time = time.time()

    def record_task(self, duration):
        self.tasks_processed += 1
        self.task_times.append(duration)
        if len(self.task_times) > self.window_size:
            self.task_times.pop(0)

    def get_tasks_per_minute(self):
        elapsed_minutes = (time.time() - self.start_time) / 60
        return self.tasks_processed / max(1, elapsed_minutes)


def get_max_queue_size():
    """Get tier-aware max thumbnail queue size."""
    try:
        from app.services.core.runtime_config_service import get_runtime_config_value

        if not get_runtime_config_value('AUTO_OPTIMIZE_FOR_HARDWARE', True):
            return 500

        from app.services.system.system_stats_service import get_hardware_tier

        tier = get_hardware_tier()
        if tier == 'PRO':
            return 5000
        if tier == 'STANDARD':
            return 2000
        return 500
    except Exception:
        return 500


def get_max_concurrent_tasks():
    """Get tier-aware concurrent thumbnail worker count."""
    try:
        from app.services.core.runtime_config_service import get_runtime_config_value

        if not get_runtime_config_value('AUTO_OPTIMIZE_FOR_HARDWARE', True):
            return DEFAULT_MAX_CONCURRENT_TASKS

        from app.services.system.system_stats_service import get_hardware_tier

        tier = get_hardware_tier()
        if tier == 'PRO':
            return 8
        if tier == 'STANDARD':
            return 4
        return DEFAULT_MAX_CONCURRENT_TASKS
    except Exception:
        return DEFAULT_MAX_CONCURRENT_TASKS


def _build_task_key(category_id, rel_path, force_refresh):
    """Build a normalized task key to prevent duplicate enqueues."""
    normalized_path = os.path.normcase(os.path.normpath(rel_path or ''))
    normalized_path = normalized_path.replace(os.sep, '/')
    return f"{category_id}|{normalized_path}|{int(bool(force_refresh))}"


class ThumbnailRuntimeService(Service):
    """Own thumbnail queueing, background workers, and status tracking."""

    def __init__(self):
        super().__init__(
            'thumbnail_runtime',
            initial_state={
                'queue_size': 0,
                'active_tasks': 0,
                'worker_count': get_max_concurrent_tasks(),
                'thumbnail_paused': False,
            },
        )
        self._thumbnail_queue_maxsize = get_max_queue_size()
        self._thumbnail_queue = JoinableQueue(maxsize=self._thumbnail_queue_maxsize)
        self._thumbnail_priority_queue = deque()
        self._thumbnail_state_lock = BoundedSemaphore(1)
        self._thumbnail_queue_lock = GeventRLock()
        self._thumbnail_processing_categories = set()
        self._thumbnail_category_stats = {}
        self._queued_thumbnail_task_keys = set()
        self._thumbnail_category_priority_boosts = {}
        self._thumbnail_active_tasks = 0
        self._thumbnail_paused = False
        self._thumbnail_gc_at = time.time()
        self._thumbnail_perf = PerformanceMonitor()
        self._thumbnail_worker_count = get_max_concurrent_tasks()
        self._thumbnail_task_semaphore = BoundedSemaphore(self._thumbnail_worker_count)

    def on_start(self):
        for index in range(self._thumbnail_worker_count):
            self.spawn(
                self._thumbnail_worker_loop,
                label=f'thumbnail-worker-{index + 1}',
            )

    def ensure_workers(self):
        """Ensure thumbnail workers are active."""
        self._thumbnail_paused = False
        self.set_state({'thumbnail_paused': False})

    def start_thumbnail_batch(self, category_id, total):
        """Initialize thumbnail progress tracking for a category batch."""
        if not category_id:
            return

        with self._thumbnail_state_lock:
            stats = self._thumbnail_category_stats.setdefault(
                category_id,
                {
                    'total': 0,
                    'processed': 0,
                    'success': 0,
                    'failed': 0,
                    'videoCount': 0,
                    'dropped': 0,
                    'batch_mode': True,
                    'last_update_ts': time.time(),
                },
            )
            stats['total'] = total
            stats['processed'] = 0
            stats['success'] = 0
            stats['failed'] = 0
            stats['videoCount'] = total
            stats['dropped'] = 0
            stats['batch_mode'] = True
            stats['last_update_ts'] = time.time()
            self._thumbnail_processing_categories.add(category_id)

    def finish_thumbnail_batch(self, category_id):
        """Mark thumbnail enqueuing complete for a category batch."""
        if not category_id:
            return

        is_complete = False
        final_payload = None
        with self._thumbnail_state_lock:
            stats = self._thumbnail_category_stats.get(category_id)
            if stats is not None:
                stats['batch_mode'] = False
                if stats['processed'] >= stats['total']:
                    is_complete = True
                    denominator = max(stats.get('videoCount', 0), stats['total'])
                    progress = 100 if denominator > 0 else 0
                    final_payload = {
                        'status': 'complete',
                        'total': stats['total'],
                        'processed': stats['processed'],
                        'progress': progress,
                        'success': stats['success'],
                        'failed': stats['failed'],
                    }
                    self._thumbnail_processing_categories.discard(category_id)
                    del self._thumbnail_category_stats[category_id]

        if is_complete:
            registry.require('library_events').emit_thumbnail_status_update(
                category_id,
                'complete',
                final_payload,
            )

    def queue_thumbnail(
        self,
        category_path,
        category_id,
        file_meta,
        *,
        force_refresh=False,
        wait_for_slot=False,
        max_wait_seconds=300,
        check_exists=True,
        priority='auto',
    ):
        """Queue thumbnail generation for a single media file."""
        task_payload = self._prepare_task_payload(
            category_path,
            category_id,
            file_meta,
            force_refresh=force_refresh,
            check_exists=check_exists,
        )
        if task_payload is None:
            return False

        task_key = task_payload['task_key']

        wait_started = time.monotonic()
        while True:
            with self._thumbnail_queue_lock:
                self._prune_thumbnail_priority_boosts()
                if task_key in self._queued_thumbnail_task_keys:
                    return False
                if self._get_total_queue_size_locked() < self._thumbnail_queue_maxsize:
                    queue_priority = self._resolve_queue_priority(priority, category_id)
                    task_payload['_queue_origin'] = 'priority' if queue_priority == 'front' else 'regular'
                    try:
                        if queue_priority == 'front':
                            self._thumbnail_priority_queue.append(task_payload)
                        else:
                            self._thumbnail_queue.put_nowait(task_payload)
                        self._queued_thumbnail_task_keys.add(task_key)
                        self.set_state({'queue_size': self._get_total_queue_size_locked()})
                        break
                    except Full:
                        pass

            if not wait_for_slot:
                self._record_thumbnail_drop(category_id)
                return False

            if max_wait_seconds is not None:
                elapsed = time.monotonic() - wait_started
                if elapsed >= float(max_wait_seconds):
                    self._record_thumbnail_drop(category_id)
                    logger.warning(
                        "Timed out waiting for thumbnail queue slot after %.1fs for %s",
                        elapsed,
                        category_id,
                    )
                    return False

            gevent.sleep(0.05)

        should_emit_generating = False
        with self._thumbnail_state_lock:
            stats = self._thumbnail_category_stats.get(category_id)
            should_emit_generating = (
                stats is not None and stats.get('total', 0) <= 5
            )
            if category_id not in self._thumbnail_processing_categories:
                self._thumbnail_processing_categories.add(category_id)
                should_emit_generating = True

        if should_emit_generating:
            registry.require('library_events').emit_thumbnail_status_update(
                category_id,
                'generating',
                self.get_thumbnail_status(category_id),
            )

        return True

    def prioritize_media_slice(
        self,
        media_items,
        *,
        boost_seconds=CATEGORY_PRIORITY_BOOST_SECONDS,
        force_refresh=False,
    ):
        """Prioritize thumbnails for client-visible media without affecting indexing order."""
        if not media_items:
            return {'queued': 0, 'promoted': 0, 'reordered': 0, 'skipped': 0}

        from app.services.media.category_query_service import get_category_by_id

        category_cache = {}
        prepared_tasks = []

        for item in media_items:
            if not isinstance(item, dict):
                continue

            category_id = item.get('categoryId') or item.get('category_id')
            if not category_id:
                continue

            category = category_cache.get(category_id)
            if category is None:
                category = get_category_by_id(category_id)
                category_cache[category_id] = category

            category_path = (category or {}).get('path')
            if not category_path:
                continue

            task_payload = self._prepare_task_payload(
                category_path,
                category_id,
                item,
                force_refresh=force_refresh,
                check_exists=True,
            )
            if task_payload is not None:
                prepared_tasks.append(task_payload)

        if not prepared_tasks:
            return {'queued': 0, 'promoted': 0, 'reordered': 0, 'skipped': 0}

        now = time.time()
        expires_at = now + max(1, int(boost_seconds or CATEGORY_PRIORITY_BOOST_SECONDS))
        queued = 0
        promoted = 0
        reordered = 0
        skipped = 0

        with self._thumbnail_queue_lock:
            self._prune_thumbnail_priority_boosts(now)

            for task_payload in prepared_tasks:
                category_id = task_payload.get('category_id')
                if category_id:
                    self._thumbnail_category_priority_boosts[category_id] = max(
                        float(self._thumbnail_category_priority_boosts.get(category_id, 0.0)),
                        expires_at,
                    )

            regular_queue = self._thumbnail_queue.queue
            front_tasks = []

            for task_payload in prepared_tasks:
                task_key = task_payload.get('task_key')
                if not task_key:
                    skipped += 1
                    continue

                existing_priority_task = self._find_task_by_key(self._thumbnail_priority_queue, task_key)
                if existing_priority_task is not None:
                    try:
                        self._thumbnail_priority_queue.remove(existing_priority_task)
                    except ValueError:
                        pass
                    front_tasks.append(existing_priority_task)
                    reordered += 1
                    continue

                existing_regular_task = self._find_task_by_key(regular_queue, task_key)
                if existing_regular_task is not None:
                    try:
                        regular_queue.remove(existing_regular_task)
                    except ValueError:
                        skipped += 1
                        continue
                    front_tasks.append(existing_regular_task)
                    promoted += 1
                    continue

                if task_key in self._queued_thumbnail_task_keys:
                    skipped += 1
                    continue

                if self._get_total_queue_size_locked() + len(front_tasks) >= self._thumbnail_queue_maxsize:
                    skipped += 1
                    continue

                priority_task = dict(task_payload)
                priority_task['_queue_origin'] = 'priority'
                front_tasks.append(priority_task)
                self._queued_thumbnail_task_keys.add(task_key)
                queued += 1

            for task in reversed(front_tasks):
                self._thumbnail_priority_queue.appendleft(task)

            self.set_state({'queue_size': self._get_total_queue_size_locked()})

        return {
            'queued': queued,
            'promoted': promoted,
            'reordered': reordered,
            'skipped': skipped,
        }

    def get_thumbnail_status(self, category_id):
        """Return thumbnail generation status for a category."""
        with self._thumbnail_state_lock:
            stats = self._thumbnail_category_stats.get(category_id)
            if stats is not None:
                if (
                    not stats.get('batch_mode', False)
                    and stats.get('processed', 0) < stats.get('total', 0)
                ):
                    now = time.time()
                    age_seconds = now - float(stats.get('last_update_ts', now))
                    has_pending_queue_work = self._category_has_pending_thumbnail_work(category_id)
                    no_active_workers = self._thumbnail_active_tasks <= 0
                    should_clear_immediately = no_active_workers and not has_pending_queue_work
                    if should_clear_immediately or (
                        age_seconds > STALE_CATEGORY_STATUS_SECONDS and not has_pending_queue_work
                    ):
                        self._thumbnail_processing_categories.discard(category_id)
                        del self._thumbnail_category_stats[category_id]
                        return {
                            'status': 'idle',
                            'total': 0,
                            'processed': 0,
                            'progress': 100,
                        }

                denominator = max(stats.get('videoCount', 0), stats['total'])
                progress = 0
                if denominator > 0:
                    progress = min(100, int((stats['processed'] / denominator) * 100))

                return {
                    'status': 'pending' if stats['processed'] == 0 else 'generating',
                    'total': stats['total'],
                    'processed': stats['processed'],
                    'progress': progress,
                    'success': stats['success'],
                    'failed': stats['failed'],
                    'videoCount': stats.get('videoCount', 0),
                }

            if category_id in self._thumbnail_processing_categories:
                has_pending_queue_work = self._category_has_pending_thumbnail_work(category_id)
                if not has_pending_queue_work and self._thumbnail_active_tasks <= 0:
                    self._thumbnail_processing_categories.discard(category_id)
                    return {
                        'status': 'idle',
                        'total': 0,
                        'processed': 0,
                        'progress': 100,
                    }
                return {
                    'status': 'pending',
                    'total': 0,
                    'processed': 0,
                    'progress': 0,
                }

        return {
            'status': 'idle',
            'total': 0,
            'processed': 0,
            'progress': 100,
        }

    def regenerate_category_from_index(
        self,
        category_path,
        category_id,
        *,
        force_refresh=True,
        batch_size=THUMBNAIL_INDEX_BATCH_SIZE,
    ):
        """Requeue thumbnail generation for indexed media in a category."""
        if not category_path or not category_id:
            return {'checked': 0, 'queued': 0, 'skipped': 0}

        total_candidates = 0
        for row in self._iter_indexed_media_rows(category_id, batch_size=batch_size):
            if self._build_indexed_file_meta(row) is not None:
                total_candidates += 1

        if total_candidates <= 0:
            return {'checked': 0, 'queued': 0, 'skipped': 0}

        checked = 0
        queued = 0
        skipped = 0
        self.start_thumbnail_batch(category_id, total_candidates)

        try:
            for row in self._iter_indexed_media_rows(category_id, batch_size=batch_size):
                file_meta = self._build_indexed_file_meta(row)
                if file_meta is None:
                    continue

                checked += 1
                was_queued = self.queue_thumbnail(
                    category_path,
                    category_id,
                    file_meta,
                    force_refresh=force_refresh,
                    wait_for_slot=True,
                    max_wait_seconds=None,
                    check_exists=False,
                )
                if was_queued:
                    queued += 1
                else:
                    skipped += 1
        finally:
            self.finish_thumbnail_batch(category_id)

        return {
            'checked': checked,
            'queued': queued,
            'skipped': skipped,
        }

    def quiesce_thumbnail_runtime(self, *, timeout_seconds=8, clear_queue=True):
        """Pause thumbnail workers and optionally drain pending work."""
        self._thumbnail_paused = True
        self.set_state({'thumbnail_paused': True})

        deadline = time.monotonic() + max(0.1, float(timeout_seconds or 8))
        while time.monotonic() < deadline:
            with self._thumbnail_state_lock:
                if self._thumbnail_active_tasks <= 0:
                    break
            gevent.sleep(0.05)

        drained = 0
        if clear_queue:
            with self._thumbnail_queue_lock:
                while self._thumbnail_priority_queue:
                    task = self._thumbnail_priority_queue.popleft()
                    task_key = task.get('task_key') if isinstance(task, dict) else None
                    if task_key:
                        self._queued_thumbnail_task_keys.discard(task_key)
                    if isinstance(task, dict) and task.get('_queue_origin') == 'regular':
                        try:
                            self._thumbnail_queue.task_done()
                        except Exception:
                            pass
                    drained += 1
                while True:
                    try:
                        task = self._thumbnail_queue.get_nowait()
                        task_key = task.get('task_key') if isinstance(task, dict) else None
                        if task_key:
                            self._queued_thumbnail_task_keys.discard(task_key)
                        self._thumbnail_queue.task_done()
                        drained += 1
                    except Empty:
                        break
                    except Exception:
                        break

                self._queued_thumbnail_task_keys.clear()
                self._thumbnail_category_priority_boosts.clear()

        with self._thumbnail_state_lock:
            idle = self._thumbnail_active_tasks <= 0
            self._thumbnail_processing_categories.clear()
            self._thumbnail_category_stats.clear()

        self.set_state({
            'queue_size': self._thumbnail_queue.qsize(),
            'active_tasks': self._thumbnail_active_tasks,
        })
        return {
            'drained_tasks': drained,
            'idle': idle,
        }

    def on_stop(self):
        try:
            self.quiesce_thumbnail_runtime(timeout_seconds=2, clear_queue=True)
        except Exception as exc:
            logger.warning("Thumbnail runtime shutdown quiesce failed: %s", exc)

    def _thumbnail_worker_loop(self):
        while self.running:
            if self._thumbnail_paused:
                gevent.sleep(0.05)
                continue

            if not self._check_thumbnail_system_resources():
                gevent.sleep(5)
                continue

            try:
                task = self._get_next_thumbnail_task(timeout=0.5)
            except Empty:
                continue

            self.set_state({'queue_size': self._get_total_queue_size()})

            try:
                with self._thumbnail_task_semaphore:
                    with self._thumbnail_state_lock:
                        self._thumbnail_active_tasks += 1
                        active_tasks = self._thumbnail_active_tasks
                    self.set_state({'active_tasks': active_tasks})
                    started_at = time.time()
                    self._process_thumbnail_task(task)
                    self._thumbnail_perf.record_task(time.time() - started_at)
            except Exception as exc:
                logger.error("Thumbnail worker error: %s", exc)
                logger.debug(traceback.format_exc())
            finally:
                task_key = task.get('task_key') if isinstance(task, dict) else None
                if task_key:
                    with self._thumbnail_queue_lock:
                        self._queued_thumbnail_task_keys.discard(task_key)
                with self._thumbnail_state_lock:
                    self._thumbnail_active_tasks = max(0, self._thumbnail_active_tasks - 1)
                    active_tasks = self._thumbnail_active_tasks
                try:
                    if isinstance(task, dict) and task.get('_queue_origin') != 'priority':
                        self._thumbnail_queue.task_done()
                except Exception:
                    pass
                self.set_state({
                    'queue_size': self._get_total_queue_size(),
                    'active_tasks': active_tasks,
                })
                if time.time() - self._thumbnail_gc_at > GC_INTERVAL:
                    gc.collect()
                    self._thumbnail_gc_at = time.time()

    def _process_thumbnail_task(self, task):
        category_path = task.get('category_path')
        file_meta = task.get('file_meta') or {}
        category_id = task.get('category_id')
        force_refresh = bool(task.get('force_refresh', False))
        rel_path = file_meta.get('path', file_meta.get('name', ''))
        filename = rel_path
        abs_path = os.path.join(category_path, rel_path)

        try:
            manager = registry.require('service_manager')
            app = getattr(manager, 'app', None)
            if app is None:
                raise RuntimeError('Flask app is not available for thumbnail runtime')

            with app.app_context():
                if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
                    logger.warning("Media file not found at path: %s", abs_path)
                    self._update_thumbnail_category_stats(
                        category_id,
                        success=False,
                        filename=filename,
                    )
                    return

                ghosthub_dir = os.path.join(category_path, '.ghosthub')
                thumbnail_dir = os.path.join(ghosthub_dir, 'thumbnails')
                try:
                    os.makedirs(ghosthub_dir, exist_ok=True)
                    os.makedirs(thumbnail_dir, exist_ok=True)
                except Exception as exc:
                    logger.error("Failed to prepare thumbnail directories for %s: %s", abs_path, exc)
                    self._update_thumbnail_category_stats(
                        category_id,
                        success=False,
                        filename=filename,
                    )
                    return

                from app.utils.media_utils import get_media_type, get_thumbnail_filename, get_thumbnail_url

                thumbnail_path = os.path.join(
                    thumbnail_dir,
                    get_thumbnail_filename(filename),
                )
                if get_media_type(filename) == 'image':
                    success = generate_image_thumbnail(
                        abs_path,
                        thumbnail_path,
                        size=THUMBNAIL_SIZE_PI,
                    )
                else:
                    success = generate_thumbnail(
                        abs_path,
                        thumbnail_path,
                        force_refresh=force_refresh,
                        size=THUMBNAIL_SIZE_PI,
                    )

                thumbnail_url = None
                media_url = None
                if success:
                    thumbnail_url = get_thumbnail_url(category_id, filename)
                    media_url = f"/media/{category_id}/{quote(filename)}"

                self._update_thumbnail_category_stats(
                    category_id,
                    success=success,
                    thumbnail_url=thumbnail_url,
                    media_url=media_url,
                    filename=filename,
                )
        except Exception as exc:
            logger.error("Failed to process thumbnail for %s: %s", filename, exc)
            logger.debug(traceback.format_exc())
            self._update_thumbnail_category_stats(
                category_id,
                success=False,
                filename=filename,
            )

    def _update_thumbnail_category_stats(
        self,
        category_id,
        *,
        success=True,
        thumbnail_url=None,
        media_url=None,
        filename=None,
    ):
        payload = None
        is_complete = False
        final_total = 0
        final_processed = 0

        with self._thumbnail_state_lock:
            stats = self._thumbnail_category_stats.get(category_id)
            if stats is None:
                return

            stats['processed'] += 1
            stats['last_update_ts'] = time.time()
            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1

            denominator = max(stats.get('videoCount', 0), stats['total'])
            progress_percent = 0
            if denominator > 0:
                progress_percent = min(100, int((stats['processed'] / denominator) * 100))

            chunk_size = 5 if denominator < 100 else (25 if denominator < 1000 else 100)
            chunk_reached = stats['processed'] % chunk_size == 0
            is_final_item = (
                not stats.get('batch_mode', False) and
                stats['processed'] >= stats['total']
            )
            percent_changed = (
                (progress_percent // 5) !=
                (stats.get('last_emitted_percent', -1) // 5)
            )
            should_emit_progress = (
                stats['processed'] <= 5 or
                is_final_item or
                percent_changed or
                chunk_reached
            )
            should_emit_thumbnail = success and thumbnail_url
            actual_status = 'pending' if stats['processed'] == 0 else 'generating'

            if should_emit_progress or should_emit_thumbnail:
                payload = {
                    'total': stats['total'],
                    'processed': stats['processed'],
                    'success': stats['success'],
                    'failed': stats['failed'],
                    'videoCount': stats.get('videoCount', 0),
                    'progress': progress_percent,
                    'color': (
                        'green' if progress_percent > 70 else
                        'yellow' if progress_percent > 30 else
                        'orange'
                    ),
                    'status': actual_status,
                }
                if should_emit_progress:
                    stats['last_emitted_percent'] = progress_percent
                if should_emit_thumbnail:
                    payload['thumbnail_url'] = thumbnail_url
                    payload['media_url'] = media_url
                    payload['filename'] = filename

            is_complete = (
                not stats.get('batch_mode', False) and
                stats['processed'] >= stats['total']
            )
            final_total = stats['total']
            final_processed = stats['processed']
            if is_complete:
                self._thumbnail_processing_categories.discard(category_id)
                del self._thumbnail_category_stats[category_id]

        if payload:
            registry.require('library_events').emit_thumbnail_status_update(
                category_id,
                payload.get('status', 'generating'),
                payload,
            )

        if is_complete:
            registry.require('library_events').emit_thumbnail_status_update(
                category_id,
                'complete',
                {
                    'progress': 100,
                    'status': 'complete',
                    'total': final_total,
                    'processed': final_processed,
                },
            )

    def _record_thumbnail_drop(self, category_id):
        with self._thumbnail_state_lock:
            stats = self._thumbnail_category_stats.setdefault(
                category_id,
                {
                    'total': 0,
                    'processed': 0,
                    'success': 0,
                    'failed': 0,
                    'videoCount': 0,
                    'dropped': 0,
                    'batch_mode': False,
                    'last_update_ts': time.time(),
                },
            )
            stats['dropped'] += 1
            stats['total'] = max(0, stats['total'] - 1)
            return stats['dropped']

    def _check_thumbnail_system_resources(self):
        try:
            mem = psutil.virtual_memory()
            if mem.available < GC_THRESHOLD:
                gc.collect()
        except Exception:
            pass
        return True

    def _category_has_pending_thumbnail_work(self, category_id):
        try:
            with self._thumbnail_queue_lock:
                if any(
                    isinstance(task, dict) and task.get('category_id') == category_id
                    for task in self._thumbnail_priority_queue
                ):
                    return True
                return any(
                    isinstance(task, dict) and task.get('category_id') == category_id
                    for task in islice(self._thumbnail_queue.queue, 500)
                )
        except Exception:
            return True

    def _prepare_task_payload(
        self,
        category_path,
        category_id,
        file_meta,
        *,
        force_refresh=False,
        check_exists=True,
    ):
        if not category_path or not category_id or not file_meta:
            return None

        if isinstance(file_meta, str):
            file_meta = {
                'name': file_meta,
                'path': file_meta,
            }

        if not isinstance(file_meta, dict):
            return None

        from app.utils.media_utils import get_media_type, get_thumbnail_filename, should_retry_thumbnail

        rel_path = file_meta.get('path', file_meta.get('name', ''))
        if not rel_path:
            return None

        abs_path = os.path.join(category_path, rel_path)
        media_type = get_media_type(rel_path)
        if media_type == 'image':
            try:
                if os.path.getsize(abs_path) < IMAGE_THUMBNAIL_MIN_SIZE:
                    return None
            except OSError:
                return None
        elif media_type != 'video':
            return None

        if not force_refresh and check_exists:
            try:
                thumbnail_filename = get_thumbnail_filename(rel_path)
                thumbnail_path = os.path.join(
                    category_path,
                    '.ghosthub',
                    'thumbnails',
                    thumbnail_filename,
                )
                if os.path.exists(thumbnail_path):
                    return None
                if not should_retry_thumbnail(thumbnail_path, abs_path):
                    return None
            except Exception as exc:
                logger.debug("Thumbnail preflight check failed for %s: %s", rel_path, exc)
        elif check_exists:
            try:
                thumbnail_filename = get_thumbnail_filename(rel_path)
                thumbnail_path = os.path.join(
                    category_path,
                    '.ghosthub',
                    'thumbnails',
                    thumbnail_filename,
                )
                if os.path.exists(thumbnail_path):
                    media_mtime = file_meta.get('mtime')
                    if media_mtime is None:
                        media_mtime = os.path.getmtime(abs_path)
                    thumb_mtime = os.path.getmtime(thumbnail_path)
                    if float(media_mtime or 0) <= float(thumb_mtime or 0):
                        return None
                if not should_retry_thumbnail(thumbnail_path, abs_path):
                    return None
            except Exception as exc:
                logger.debug("Thumbnail force-refresh preflight failed for %s: %s", rel_path, exc)

        task_key = _build_task_key(category_id, rel_path, force_refresh)
        return {
            'category_path': category_path,
            'file_meta': file_meta,
            'category_id': category_id,
            'force_refresh': force_refresh,
            'task_key': task_key,
        }

    def _iter_indexed_media_rows(self, category_id, *, batch_size=THUMBNAIL_INDEX_BATCH_SIZE):
        from app.services.media import media_index_service

        safe_batch_size = max(1, int(batch_size or THUMBNAIL_INDEX_BATCH_SIZE))
        offset = 0
        while True:
            rows = media_index_service.get_paginated_media(
                category_id=category_id,
                subfolder='__all__',
                sort_by='name',
                sort_order='ASC',
                limit=safe_batch_size,
                offset=offset,
                filter_type='all',
                show_hidden=True,
                deduplicate_by_hash=False,
                columns=['rel_path', 'size', 'mtime', 'type'],
            )
            if not rows:
                break

            for row in rows:
                yield row

            if len(rows) < safe_batch_size:
                break
            offset += len(rows)

    def _build_indexed_file_meta(self, row):
        if not isinstance(row, dict):
            return None

        rel_path = row.get('rel_path') or row.get('name')
        if not rel_path:
            return None

        media_type = row.get('type')
        if media_type not in ('video', 'image'):
            return None

        size = int(row.get('size') or 0)
        if media_type == 'image' and size < IMAGE_THUMBNAIL_MIN_SIZE:
            return None

        return {
            'name': rel_path,
            'path': rel_path,
            'size': size,
            'mtime': row.get('mtime', 0),
            'type': media_type,
        }

    def _get_total_queue_size_locked(self):
        return len(self._thumbnail_priority_queue) + self._thumbnail_queue.qsize()

    def _get_total_queue_size(self):
        with self._thumbnail_queue_lock:
            return self._get_total_queue_size_locked()

    def _resolve_queue_priority(self, priority, category_id):
        if priority == 'front':
            return 'front'
        if priority == 'normal':
            return 'normal'
        if category_id and self._category_has_priority_boost(category_id):
            return 'front'
        return 'normal'

    def _category_has_priority_boost(self, category_id, now=None):
        if not category_id:
            return False
        self._prune_thumbnail_priority_boosts(now)
        return float(self._thumbnail_category_priority_boosts.get(category_id, 0.0)) > time.time()

    def _prune_thumbnail_priority_boosts(self, now=None):
        current_time = float(now if now is not None else time.time())
        expired = [
            category_id
            for category_id, expires_at in self._thumbnail_category_priority_boosts.items()
            if float(expires_at) <= current_time
        ]
        for category_id in expired:
            self._thumbnail_category_priority_boosts.pop(category_id, None)

    def _get_next_thumbnail_task(self, timeout=0.5):
        deadline = time.monotonic() + max(0.05, float(timeout or 0.5))
        while self.running:
            with self._thumbnail_queue_lock:
                if self._thumbnail_priority_queue:
                    return self._thumbnail_priority_queue.popleft()

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Empty()

            try:
                return self._thumbnail_queue.get(timeout=min(0.1, remaining))
            except Empty:
                continue

        raise Empty()

    @staticmethod
    def _find_task_by_key(task_queue, task_key):
        for task in task_queue:
            if isinstance(task, dict) and task.get('task_key') == task_key:
                return task
        return None
