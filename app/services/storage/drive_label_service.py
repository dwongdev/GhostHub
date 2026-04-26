"""Drive label persistence service — maps device keys to user-chosen names."""

import logging
import time
from typing import Dict, Optional

from app.services.core.sqlite_runtime_service import get_db

logger = logging.getLogger(__name__)


def get_drive_label(device_key: str) -> Optional[str]:
    """Return the custom label for *device_key*, or None."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT label FROM drive_labels WHERE device_key = ?",
                (device_key,),
            ).fetchone()
            return row[0] if row else None
    except Exception as exc:
        logger.error("get_drive_label error: %s", exc)
        return None


def set_drive_label(device_key: str, label: str) -> bool:
    """Create or update the label for *device_key*."""
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO drive_labels (device_key, label, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(device_key) DO UPDATE SET label = excluded.label, updated_at = excluded.updated_at",
                (device_key, label, time.time()),
            )
        return True
    except Exception as exc:
        logger.error("set_drive_label error: %s", exc)
        return False


def get_all_drive_labels() -> Dict[str, str]:
    """Return all stored labels as {device_key: label}."""
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT device_key, label FROM drive_labels").fetchall()
            return {row[0]: row[1] for row in rows}
    except Exception as exc:
        logger.error("get_all_drive_labels error: %s", exc)
        return {}


def get_drive_folder_labels() -> Dict[str, str]:
    """Return {folder_name: label} by joining cached drives with stored labels.

    This allows category display names to substitute the user-chosen label
    for the raw filesystem folder name (e.g. "USB-0001" → "My Movies").
    """
    labels = get_all_drive_labels()
    if not labels:
        return {}

    try:
        from app.services.storage import storage_drive_service

        drives = storage_drive_service.get_storage_drives(force_refresh=False)
    except Exception:
        return {}

    result: Dict[str, str] = {}
    for drive in drives:
        device_key = drive.get('device_key')
        if device_key and device_key in labels:
            result[drive['name']] = labels[device_key]
    return result


def delete_drive_label(device_key: str) -> bool:
    """Remove the custom label for *device_key*."""
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM drive_labels WHERE device_key = ?", (device_key,))
        return True
    except Exception as exc:
        logger.error("delete_drive_label error: %s", exc)
        return False
