"""Headscale bootstrap preparation ownership."""

import logging
import os

from app.services.system.headscale.cli_service import HS_DB, INSTANCE_DIR

logger = logging.getLogger(__name__)


def reset_database_if_needed():
    """Reset the Headscale database when missing or corrupted."""
    db_needs_reset = not os.path.exists(HS_DB)

    if os.path.exists(HS_DB):
        try:
            import sqlite3

            conn = sqlite3.connect(HS_DB)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            conn.close()
            logger.info("Database file is valid: %s", HS_DB)
        except Exception as err:
            logger.warning("Database corrupted, resetting: %s", err)
            db_needs_reset = True
    else:
        logger.info("No existing database - starting fresh")

    if not db_needs_reset:
        return True

    try:
        os.remove(HS_DB)
        for ext in ('-wal', '-shm'):
            wal_file = HS_DB + ext
            if os.path.exists(wal_file):
                os.remove(wal_file)
        return True
    except Exception as err:
        logger.error("Failed to remove old database: %s", err)
        return False


def ensure_instance_writable():
    """Ensure the Headscale instance directory is writable."""
    if not os.path.exists(INSTANCE_DIR):
        return True

    try:
        test_file = os.path.join(INSTANCE_DIR, ".write_test")
        with open(test_file, 'w') as temp_file:
            temp_file.write("test")
        os.remove(test_file)
        return True
    except Exception as err:
        logger.error("Instance directory not writable: %s", err)
        return False
