"""Specter-owned runtime store for storage/mount detection state."""

from specter import create_store


storage_runtime_store = create_store('storage_runtime', {
    'last_mount_snapshot': None,
    'last_mount_hash': None,
    'mount_change_detected': False,
    'drive_cache': [],
    'drive_scan_in_progress': False,
    'monitoring': False,
})
