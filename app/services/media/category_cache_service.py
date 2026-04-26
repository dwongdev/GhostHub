"""Category cache ownership and change-detection helpers."""

import logging
import os
import stat
import time

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.media import media_index_service
from app.services.media.category_runtime_store import category_runtime_store

logger = logging.getLogger(__name__)

CATEGORY_CACHE_TTL = 86400


def _category_runtime_access(reader):
    """Read category runtime cache state under the Specter store lock."""
    return category_runtime_store.access(reader)


def _update_category_runtime(mutator):
    """Mutate category runtime cache state through the Specter-owned store."""
    return category_runtime_store.update(mutator)


def invalidate_cache():
    """Invalidate the entire category cache."""
    def _reset_cache(draft):
        draft['category_cache'] = []
        draft['last_cache_update'] = 0
        draft['dir_mtime_cache'] = {}

    _update_category_runtime(_reset_cache)
    logger.info("Category cache invalidated")


def invalidate_cache_for_category(category_path):
    """Invalidate cache state for a single category path."""
    normalized_path = os.path.normpath(category_path)

    def _invalidate_path(draft):
        category_cache = draft.setdefault('category_cache', [])
        dir_mtime_cache = draft.setdefault('dir_mtime_cache', {})

        for path in [category_path, normalized_path]:
            if path in dir_mtime_cache:
                del dir_mtime_cache[path]
                logger.info("Invalidated dir mtime cache for: %s", path)

        parent = normalized_path
        while parent and parent != "/" and len(parent) > 3:
            parent = os.path.dirname(parent)
            if parent in dir_mtime_cache:
                del dir_mtime_cache[parent]

        if category_cache:
            original_count = len(category_cache)
            draft['category_cache'] = [
                category
                for category in category_cache
                if os.path.normpath(category.get("path", "")) != normalized_path
            ]
            if len(draft['category_cache']) < original_count:
                draft['last_cache_update'] = 0
                logger.info("Removed category from cache for path: %s", normalized_path)

    _update_category_runtime(_invalidate_path)
    logger.info("Category cache invalidated for path: %s", normalized_path)


def update_cached_category(category_id):
    """Refresh one cached category using current media-index summary data."""
    # Fetch data outside the store lock to avoid deadlock
    try:
        summaries = media_index_service.get_all_category_media_summaries(show_hidden=True)
        summary = summaries.get(category_id)
    except Exception as exc:
        logger.error("Failed to fetch summaries for category %s: %s", category_id, exc)
        return

    thumbnail_url = None
    new_count = 0
    new_contains_video = False
    new_path_mtime = None
    cached_path = None

    if summary:
        new_count = int(summary.get("count", 0) or 0)
        new_contains_video = bool(summary.get("contains_video", False))
        if new_count > 0:
            image_rel = summary.get("image_rel_path")
            video_rel = summary.get("video_rel_path")
            if image_rel:
                from app.utils.media_utils import get_thumbnail_url
                thumbnail_url = get_thumbnail_url(category_id, image_rel)
            elif video_rel:
                from app.utils.media_utils import get_thumbnail_url
                thumbnail_url = get_thumbnail_url(category_id, video_rel)

    # Get path for mtime update (read from store briefly)
    cached_path = _category_runtime_access(
        lambda state: next(
            (cat.get("path") for cat in state.get('category_cache', [])
             if cat.get("id") == category_id),
            None,
        )
    )
    if cached_path:
        try:
            new_path_mtime = os.stat(cached_path).st_mtime
        except OSError:
            pass

    # Now update the store (briefly — no I/O inside mutator)
    def _apply_update(draft):
        category_cache = draft.setdefault('category_cache', [])
        if not category_cache:
            return
        for index, cached_cat in enumerate(category_cache):
            if cached_cat.get("id") != category_id:
                continue
            if new_count > 0:
                category_cache[index]["mediaCount"] = new_count
                category_cache[index]["containsVideo"] = new_contains_video
                if thumbnail_url:
                    category_cache[index]["thumbnailUrl"] = thumbnail_url
            if new_path_mtime is not None and cached_path:
                draft.setdefault('dir_mtime_cache', {})[cached_path] = new_path_mtime
            logger.info(
                "Surgically updated cache for category: %s (count: %s)",
                category_id,
                new_count,
            )
            break

    _update_category_runtime(_apply_update)


def get_cache_timestamp():
    """Return the timestamp of the last cache update."""
    return _category_runtime_access(
        lambda state: state.get('last_cache_update', 0),
    )


def get_cached_categories(max_age_seconds=CATEGORY_CACHE_TTL):
    """Return a copy of cached categories when the cache is still fresh."""
    current_time = int(time.time())
    return _category_runtime_access(
        lambda state: (
            list(state.get('category_cache', []))
            if (
                state.get('category_cache')
                and state.get('last_cache_update', 0) > 0
                and (current_time - state.get('last_cache_update', 0)) < max_age_seconds
            )
            else None
        ),
    )


def store_cached_categories(categories, timestamp):
    """Replace cached category payloads and set the cache timestamp."""
    def _cache_categories(draft):
        draft['category_cache'] = list(categories)
        draft['last_cache_update'] = timestamp

    _update_category_runtime(_cache_categories)


def has_cached_categories():
    """Return True when cached category payloads exist."""
    return _category_runtime_access(
        lambda state: bool(state.get('category_cache')),
    )


def check_content_changes() -> bool:
    """Invalidate the cache when cached category directories change on disk."""
    current_time = time.time()
    check_interval = get_runtime_config_value("CONTENT_CHECK_INTERVAL", 10)

    # Read state under lock (briefly — no I/O here)
    state_snapshot = _category_runtime_access(lambda state: {
        'last_content_check': state.get('last_content_check', 0),
        'category_cache': list(state.get('category_cache', [])),
        'dir_mtime_cache': dict(state.get('dir_mtime_cache', {})),
    })

    if current_time - state_snapshot['last_content_check'] < check_interval:
        return False

    category_cache = state_snapshot['category_cache']
    if not category_cache:
        def _stamp_check_time(draft):
            draft['last_content_check'] = current_time
        _update_category_runtime(_stamp_check_time)
        return False

    # Perform all filesystem I/O without holding the store lock
    dir_mtime_cache = state_snapshot['dir_mtime_cache']
    changed_path = None
    new_mtimes = {}

    for category in category_cache:
        path = category.get("path", "")
        if not path:
            continue
        try:
            st = os.stat(path)
            if not stat.S_ISDIR(st.st_mode):
                continue
            current_mtime = st.st_mtime
            cached_mtime = dir_mtime_cache.get(path)
            new_mtimes[path] = current_mtime
            if cached_mtime is not None and current_mtime != cached_mtime:
                logger.info("Category cache invalidated: Content changed in %s", path)
                changed_path = path
                break
        except OSError:
            continue

    # Update store state (briefly — no I/O here)
    if changed_path is not None:
        def _invalidate(draft):
            if current_time - draft.get('last_content_check', 0) < check_interval:
                return
            draft['category_cache'] = []
            draft['last_cache_update'] = 0
            draft['dir_mtime_cache'] = {}
            draft['last_content_check'] = current_time
        _update_category_runtime(_invalidate)
        return True

    def _update_mtimes(draft):
        if current_time - draft.get('last_content_check', 0) < check_interval:
            return
        draft['last_content_check'] = current_time
        mtime_cache = draft.setdefault('dir_mtime_cache', {})
        mtime_cache.update(new_mtimes)
    _update_category_runtime(_update_mtimes)
    return False


def _check_dir_mtime_changed(path: str) -> bool:
    """Return True when a directory's mtime changed since the last cache probe.

    NOTE: Do NOT call this from inside a store mutator — it accesses the store
    internally and would deadlock on the BoundedSemaphore. Use check_content_changes()
    which correctly separates I/O from store access.
    """
    try:
        st = os.stat(path)
        if not stat.S_ISDIR(st.st_mode):
            return False

        current_mtime = st.st_mtime
        cached_mtime = _category_runtime_access(
            lambda state: state.get('dir_mtime_cache', {}).get(path),
        )

        if cached_mtime is None:
            _update_category_runtime(
                lambda draft: draft.setdefault('dir_mtime_cache', {}).__setitem__(
                    path,
                    current_mtime,
                ),
            )
            return False

        if current_mtime != cached_mtime:
            _update_category_runtime(
                lambda draft: draft.setdefault('dir_mtime_cache', {}).__setitem__(
                    path,
                    current_mtime,
                ),
            )
            logger.info("Directory content changed: %s", path)
            return True

        return False
    except (OSError, ImportError):
        return False
