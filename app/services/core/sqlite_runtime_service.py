"""SQLite runtime connection ownership for GhostHub persistence."""

import logging
import os
import sqlite3
from contextlib import contextmanager

import gevent.local

from app.services.core.runtime_config_service import get_runtime_config_value

logger = logging.getLogger(__name__)

DB_FILENAME = 'ghosthub.db'


def get_db_path():
    """Return the current SQLite database path from runtime config."""
    return os.path.join(
        os.path.abspath(get_runtime_config_value('INSTANCE_FOLDER_PATH')),
        DB_FILENAME,
    )


DB_PATH = get_db_path()

_local = gevent.local.local()

PRAGMA_SETTINGS = [
    "PRAGMA foreign_keys=ON",
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA cache_size=-8000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA mmap_size=67108864",
]


def get_connection():
    """Get a greenlet-local SQLite connection."""
    current_db_path = get_db_path()

    if (
        hasattr(_local, 'connection') and
        _local.connection is not None and
        getattr(_local, 'db_path', None) != current_db_path
    ):
        close_connection()

    if not hasattr(_local, 'connection') or _local.connection is None:
        instance_path = os.path.dirname(current_db_path)
        os.makedirs(instance_path, exist_ok=True)

        if os.path.isdir('/tmp/ghosthub_sqlite'):
            os.environ['TMPDIR'] = '/tmp/ghosthub_sqlite'
            os.environ['TEMP'] = '/tmp/ghosthub_sqlite'
            os.environ['TMP'] = '/tmp/ghosthub_sqlite'
            logger.info("Using tmpfs /tmp/ghosthub_sqlite for SQLite temp files")

        _local.connection = sqlite3.connect(
            current_db_path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        _local.connection.row_factory = sqlite3.Row
        _local.db_path = current_db_path

        from app.services.system.system_stats_service import get_hardware_tier

        pragmas = PRAGMA_SETTINGS.copy()
        if get_runtime_config_value('AUTO_OPTIMIZE_FOR_HARDWARE'):
            tier = get_hardware_tier()
            if tier == 'PRO':
                pragmas = [
                    "PRAGMA journal_mode=WAL",
                    "PRAGMA synchronous=NORMAL",
                    "PRAGMA cache_size=-131072",
                    "PRAGMA temp_store=MEMORY",
                    "PRAGMA mmap_size=1073741824",
                ]
                logger.info("Applying PRO tier SQLite optimizations")
            elif tier == 'STANDARD':
                pragmas = [
                    "PRAGMA journal_mode=WAL",
                    "PRAGMA synchronous=NORMAL",
                    "PRAGMA cache_size=-32768",
                    "PRAGMA temp_store=MEMORY",
                    "PRAGMA mmap_size=268435456",
                ]
                logger.info("Applying STANDARD tier SQLite optimizations")
            else:
                logger.info("Applying BASE tier SQLite optimizations")

        for pragma in pragmas:
            try:
                _local.connection.execute(pragma)
            except sqlite3.Error as err:
                logger.warning("Failed to apply %s: %s", pragma, err)

    return _local.connection


@contextmanager
def get_db():
    """Context manager for SQLite operations."""
    conn = get_connection()
    try:
        yield conn
    except sqlite3.Error as err:
        logger.error("Database error: %s", err)
        raise


def close_connection():
    """Close the greenlet-local SQLite connection."""
    if hasattr(_local, 'connection') and _local.connection is not None:
        try:
            _local.connection.close()
        except sqlite3.Error:
            pass
        _local.connection = None
    if hasattr(_local, 'db_path'):
        _local.db_path = None
