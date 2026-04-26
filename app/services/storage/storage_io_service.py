"""Shared storage I/O and formatting helpers."""

import os
import tempfile

import gevent


def get_file_io_pool():
    """Return gevent's shared threadpool for blocking file I/O."""
    return gevent.get_hub().threadpool


def is_path_within(base_path: str, target_path: str) -> bool:
    """Return True when target_path resolves inside base_path."""
    try:
        base_real = os.path.realpath(base_path)
        target_real = os.path.realpath(target_path)
        return os.path.commonpath([base_real, target_real]) == base_real
    except Exception:
        return False


def is_path_writable(path: str) -> bool:
    """
    Validate write access using an actual write probe.

    os.access() can be stale or misleading for removable media and ACL-backed mounts.
    """
    if not path or not os.path.isdir(path):
        return False

    probe_path = None
    try:
        fd, probe_path = tempfile.mkstemp(prefix=".ghosthub_write_test_", dir=path)
        os.close(fd)
        os.remove(probe_path)
        return True
    except (PermissionError, OSError):
        return False
    finally:
        if probe_path and os.path.exists(probe_path):
            try:
                os.remove(probe_path)
            except Exception:
                pass


def format_bytes(size: int) -> str:
    """Format bytes to a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
