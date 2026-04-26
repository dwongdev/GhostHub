"""Recycle-bin and storage-cleanup workflows for storage domains."""

import logging
import os
import shutil
from typing import Tuple

from app.services.storage.storage_drive_service import (
    get_storage_drives,
    get_storage_drives_fresh,
)
from app.services.storage.storage_io_service import is_path_within

logger = logging.getLogger(__name__)

RECYCLE_BIN_NAMES = frozenset([
    '$RECYCLE.BIN',
    '$Recycle.Bin',
    'RECYCLER',
    '.Trashes',
    '#recycle',
    '@Recycle',
])

RECYCLE_BIN_NAMES_LOWER = frozenset([
    '$recycle.bin',
    'recycler',
])


def cleanup_recycle_bins():
    """Clear recycle-bin contents from active storage drives."""
    cleaned_count = 0
    bytes_freed = 0

    try:
        drives = get_storage_drives(force_refresh=False)
        if not drives:
            drives = get_storage_drives_fresh()

        for drive in drives:
            drive_path = drive.get('path')
            if not drive_path or not os.path.isdir(drive_path):
                continue

            try:
                with os.scandir(drive_path) as entries:
                    for entry in entries:
                        if not entry.is_dir():
                            continue

                        is_recycle = (
                            entry.name in RECYCLE_BIN_NAMES
                            or entry.name.lower() in RECYCLE_BIN_NAMES_LOWER
                        )
                        if not is_recycle:
                            continue

                        count, size = _clear_recycle_bin_contents(entry.path)
                        cleaned_count += count
                        bytes_freed += size
            except (PermissionError, OSError) as exc:
                logger.debug("Cannot scan drive %s: %s", drive_path, exc)

        if cleaned_count > 0:
            mb_freed = bytes_freed / (1024 * 1024)
            logger.info(
                "Cleaned %s items from recycle bins, freed %.1fMB",
                cleaned_count,
                mb_freed,
            )
    except Exception as exc:
        logger.error("Error cleaning recycle bins: %s", exc)


def _clear_recycle_bin_contents(recycle_bin_path: str) -> Tuple[int, int]:
    """Delete recycle-bin contents while keeping the recycle-bin folder itself."""
    items_deleted = 0
    bytes_freed = 0

    try:
        with os.scandir(recycle_bin_path) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        logger.debug(
                            "Skipping symlink in recycle bin cleanup: %s",
                            entry.path,
                        )
                        continue
                    if not is_path_within(recycle_bin_path, entry.path):
                        logger.warning(
                            "Skipping out-of-scope recycle bin entry: %s",
                            entry.path,
                        )
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        folder_size = _get_folder_size(entry.path)
                        shutil.rmtree(entry.path)
                        bytes_freed += folder_size
                        items_deleted += 1
                        logger.debug("Removed recycle bin folder: %s", entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        file_size = entry.stat().st_size
                        os.remove(entry.path)
                        bytes_freed += file_size
                        items_deleted += 1
                        logger.debug("Removed recycle bin file: %s", entry.path)
                except (PermissionError, OSError) as exc:
                    logger.debug("Cannot remove %s: %s", entry.path, exc)
    except (PermissionError, OSError) as exc:
        logger.debug("Cannot access recycle bin %s: %s", recycle_bin_path, exc)

    return items_deleted, bytes_freed


def _get_folder_size(folder_path: str) -> int:
    """Return the recursive size of a folder in bytes."""
    total_size = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total_size
