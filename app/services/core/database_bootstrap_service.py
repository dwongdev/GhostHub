"""Database schema/bootstrap ownership for app startup."""

import logging
import os

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.core.database_schema_service import (
    CREATE_TABLES_SQL,
    SCHEMA_VERSION,
)
from app.services.core.schema_descriptor import (
    MIGRATIONS,
    AddColumn,
    get_add_column_sql,
    has_migration_path,
)
from app.services.core.sqlite_runtime_service import (
    get_db,
    get_db_path,
)

logger = logging.getLogger(__name__)


def ensure_database_ready():
    """Create/update schema metadata for the current SQLite backend."""
    _ensure_instance_folder()

    with get_db() as conn:
        _ensure_schema_info_table(conn)
        current_version = _read_schema_version(conn)

        conn.executescript(CREATE_TABLES_SQL)

        if current_version is None:
            _set_schema_version(conn, SCHEMA_VERSION)
            logger.info("Database initialized with schema version %s", SCHEMA_VERSION)
        else:
            if current_version == SCHEMA_VERSION:
                pass
            elif current_version < SCHEMA_VERSION and has_migration_path(current_version):
                _apply_descriptor_migrations(conn, current_version)
                _set_schema_version(conn, SCHEMA_VERSION)
                logger.info(
                    "Database schema version upgraded from %s to %s",
                    current_version,
                    SCHEMA_VERSION,
                )
            elif current_version != SCHEMA_VERSION:
                raise RuntimeError(
                    "Unsupported database schema version "
                    f"{current_version}; expected {SCHEMA_VERSION}. "
                    "Migrations are not supported for this release."
                )

    logger.info("Database ready at %s", get_db_path())


def _ensure_instance_folder():
    """Ensure the instance folder exists before opening SQLite."""
    instance_path = os.path.abspath(get_runtime_config_value('INSTANCE_FOLDER_PATH'))
    os.makedirs(instance_path, exist_ok=True)


def _ensure_schema_info_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_info (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _read_schema_version(conn):
    row = conn.execute(
        "SELECT value FROM schema_info WHERE key = 'version'",
    ).fetchone()
    return int(row['value']) if row else None


def _set_schema_version(conn, version):
    conn.execute(
        "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
        ('version', str(version)),
    )


def _apply_descriptor_migrations(conn, current_version):
    for version in sorted(MIGRATIONS):
        if version <= current_version or version > SCHEMA_VERSION:
            continue
        for step in MIGRATIONS[version]:
            if isinstance(step, AddColumn):
                _add_column_if_missing(conn, step.table, step.column)


def _table_exists(conn, table_name):
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn, table_name, column_name):
    if not _table_exists(conn, table_name):
        return False

    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row['name'] == column_name for row in rows)


def _add_column_if_missing(conn, table_name, column_name):
    if _column_exists(conn, table_name, column_name):
        return

    logger.info("Adding %s column to %s table", column_name, table_name)
    conn.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {get_add_column_sql(table_name, column_name)}"
    )

