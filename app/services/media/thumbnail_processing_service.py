"""Thumbnail-processing helpers for indexing and library runtime flows."""

import logging
import os

from specter import registry
from app.utils.media_utils import (
    IMAGE_THUMBNAIL_MIN_SIZE,
    get_media_type,
)

logger = logging.getLogger(__name__)


def _require_thumbnail_runtime():
    return registry.require('thumbnail_runtime')


def _should_enqueue_thumbnail(
    category_path,
    file_meta,
    force_refresh,
    existing_thumbnails=None,
):
    """Return True when an image/video thumbnail should be generated."""
    filename = file_meta.get('name', '')
    if not filename:
        return False

    from app.utils.media_utils import THUMBNAIL_DIR_NAME, get_thumbnail_filename

    thumbnail_dir = os.path.join(category_path, ".ghosthub", THUMBNAIL_DIR_NAME)
    thumbnail_filename = get_thumbnail_filename(filename)
    thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
    abs_path = os.path.join(category_path, filename)

    exists = (
        thumbnail_filename in existing_thumbnails
        if existing_thumbnails is not None
        else os.path.exists(thumbnail_path)
    )
    if not exists:
        from app.utils.media_utils import should_retry_thumbnail

        return should_retry_thumbnail(thumbnail_path, abs_path)

    if force_refresh:
        media_mtime = file_meta.get('mtime')
        if media_mtime is None:
            try:
                media_mtime = os.path.getmtime(abs_path)
            except OSError:
                return False

        try:
            thumb_mtime = os.path.getmtime(thumbnail_path)
            if media_mtime <= thumb_mtime:
                return False
        except OSError:
            pass

        from app.utils.media_utils import should_retry_thumbnail

        return should_retry_thumbnail(thumbnail_path, abs_path)

    return False


def process_category_thumbnails(
    category_path,
    all_files_metadata,
    category_id,
    force_refresh=False,
    wait_for_slot=False,
    max_wait_seconds=300,
):
    """Queue thumbnail generation for media in a category."""
    image_count = 0
    video_count = 0
    thumbnails_queued = 0
    to_enqueue = []

    from app.utils.media_utils import THUMBNAIL_DIR_NAME

    thumbnail_dir = os.path.join(category_path, ".ghosthub", THUMBNAIL_DIR_NAME)
    existing_thumbnails = set()
    if os.path.isdir(thumbnail_dir):
        try:
            with os.scandir(thumbnail_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        existing_thumbnails.add(entry.name)
        except OSError:
            pass

    for file_meta in all_files_metadata:
        filename = file_meta.get('name', '')
        media_type = get_media_type(filename)

        if media_type == 'image':
            image_count += 1
            if file_meta.get('size', 0) >= IMAGE_THUMBNAIL_MIN_SIZE:
                if _should_enqueue_thumbnail(
                    category_path,
                    file_meta,
                    force_refresh,
                    existing_thumbnails=existing_thumbnails,
                ):
                    to_enqueue.append(file_meta)
        elif media_type == 'video':
            video_count += 1
            if _should_enqueue_thumbnail(
                category_path,
                file_meta,
                force_refresh,
                existing_thumbnails=existing_thumbnails,
            ):
                to_enqueue.append(file_meta)

    if to_enqueue:
        runtime = _require_thumbnail_runtime()
        runtime.start_thumbnail_batch(category_id, len(to_enqueue))

        try:
            for file_meta in to_enqueue:
                queued = runtime.queue_thumbnail(
                    category_path,
                    category_id,
                    file_meta,
                    force_refresh=force_refresh,
                    wait_for_slot=wait_for_slot,
                    max_wait_seconds=max_wait_seconds,
                    check_exists=False,
                )
                if queued:
                    thumbnails_queued += 1
        finally:
            runtime.finish_thumbnail_batch(category_id)

    logger.info(
        "Processed category thumbnails for %s: %s images, %s videos, %s queued",
        category_id,
        image_count,
        video_count,
        thumbnails_queued,
    )
    return image_count, video_count, thumbnails_queued


def process_category_thumbnails_smart(
    category_path,
    all_files_metadata,
    category_id,
    force_refresh=False,
    files_to_process=None,
    wait_for_slot=False,
    max_wait_seconds=300,
):
    """Queue thumbnails only for media that still need them."""
    from app.utils.media_utils import THUMBNAIL_DIR_NAME, get_thumbnail_filename

    stats = {'checked': 0, 'queued': 0, 'skipped': 0, 'existing': 0}
    to_enqueue = []

    thumbnail_dir = os.path.join(category_path, ".ghosthub", THUMBNAIL_DIR_NAME)
    existing_thumbnails = set()
    thumbnail_dir_exists = os.path.isdir(thumbnail_dir)
    if thumbnail_dir_exists:
        try:
            with os.scandir(thumbnail_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        existing_thumbnails.add(entry.name)
        except OSError:
            pass

    files_to_check = files_to_process if files_to_process is not None else all_files_metadata

    for item in files_to_check:
        file_meta = {'name': item} if isinstance(item, str) else item
        filename = file_meta.get('name', '')
        if not filename:
            continue

        file_type = get_media_type(filename)
        if file_type not in ('video', 'image'):
            continue

        if file_type == 'image':
            file_size = file_meta.get('size', 0)
            if not file_size:
                try:
                    file_size = os.path.getsize(os.path.join(category_path, filename))
                except OSError:
                    file_size = 0
            if file_size < IMAGE_THUMBNAIL_MIN_SIZE:
                continue

        stats['checked'] += 1

        thumb_filename = get_thumbnail_filename(filename)
        thumb_exists = thumb_filename in existing_thumbnails if thumbnail_dir_exists else False
        should_enqueue = _should_enqueue_thumbnail(
            category_path,
            file_meta,
            force_refresh,
            existing_thumbnails=existing_thumbnails if thumbnail_dir_exists else set(),
        )
        if should_enqueue:
            to_enqueue.append(file_meta)
        elif thumb_exists:
            stats['existing'] += 1
        else:
            stats['skipped'] += 1

    if to_enqueue:
        runtime = _require_thumbnail_runtime()
        runtime.start_thumbnail_batch(category_id, len(to_enqueue))
        try:
            for file_meta in to_enqueue:
                queued = runtime.queue_thumbnail(
                    category_path,
                    category_id,
                    file_meta,
                    force_refresh=force_refresh,
                    wait_for_slot=wait_for_slot,
                    max_wait_seconds=max_wait_seconds,
                    check_exists=False,
                )
                if queued:
                    stats['queued'] += 1
        finally:
            runtime.finish_thumbnail_batch(category_id)

    return stats
