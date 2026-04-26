"""Database schema/bootstrap ownership for app startup."""

import logging
import os
import sqlite3
import time
import uuid

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.core.database_schema_service import (
    CREATE_TABLES_SQL,
    SCHEMA_VERSION,
)
from app.services.core.sqlite_runtime_service import (
    get_db,
    get_db_path,
)

logger = logging.getLogger(__name__)
LEGACY_SCHEMA_VERSION = 11
PROFILE_PREFERENCES_SCHEMA_VERSION = 12
PROFILE_AVATAR_ICON_SCHEMA_VERSION = 13
VIDEO_PROGRESS_FOREIGN_KEY_SCHEMA_VERSION = 14
LEGACY_PROGRESS_PROFILE_NAME = 'Imported Progress'


def ensure_database_ready():
    """Create/update schema metadata for the current SQLite backend."""
    _ensure_instance_folder()

    with get_db() as conn:
        _ensure_schema_info_table(conn)
        current_version = _read_schema_version(conn)

        if _table_exists(conn, 'video_progress') and not _column_exists(conn, 'video_progress', 'profile_id'):
            _migrate_legacy_video_progress_schema(conn)
            current_version = SCHEMA_VERSION

        conn.executescript(CREATE_TABLES_SQL)

        if current_version is None:
            _set_schema_version(conn, SCHEMA_VERSION)
            logger.info("Database initialized with schema version %s", SCHEMA_VERSION)
        else:
            if current_version in (
                LEGACY_SCHEMA_VERSION,
                PROFILE_PREFERENCES_SCHEMA_VERSION,
                PROFILE_AVATAR_ICON_SCHEMA_VERSION,
                VIDEO_PROGRESS_FOREIGN_KEY_SCHEMA_VERSION,
            ):
                if (
                    current_version <= PROFILE_PREFERENCES_SCHEMA_VERSION and
                    not _column_exists(conn, 'profiles', 'preferences_json')
                ):
                    _add_profile_preferences_column(conn)
                if (
                    current_version <= PROFILE_AVATAR_ICON_SCHEMA_VERSION and
                    not _column_exists(conn, 'profiles', 'avatar_icon')
                ):
                    _add_profile_avatar_icon_column(conn)
                if not _video_progress_has_profile_foreign_key(conn):
                    _rebuild_video_progress_table_with_foreign_key(conn)
                _set_schema_version(conn, SCHEMA_VERSION)
                logger.info(
                    "Database schema version upgraded from %s to %s",
                    current_version,
                    SCHEMA_VERSION,
                )
            elif current_version == SCHEMA_VERSION:
                if not _video_progress_has_profile_foreign_key(conn):
                    _rebuild_video_progress_table_with_foreign_key(conn)
                    logger.info(
                        "Rebuilt video_progress table to restore profile foreign key enforcement",
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


def _video_progress_has_profile_foreign_key(conn):
    if not _table_exists(conn, 'video_progress'):
        return False

    rows = conn.execute("PRAGMA foreign_key_list(video_progress)").fetchall()
    return any(
        row['from'] == 'profile_id' and
        row['table'] == 'profiles' and
        str(row['on_delete']).upper() == 'CASCADE'
        for row in rows
    )


def _migrate_legacy_video_progress_schema(conn):
    """Upgrade legacy per-video progress schema to profile-aware rows."""
    logger.info("Migrating legacy video_progress schema to version %s", SCHEMA_VERSION)

    conn.execute("BEGIN IMMEDIATE")
    try:
        backup_table = 'video_progress_v11_backup'
        if _table_exists(conn, backup_table):
            conn.execute(f"DROP TABLE {backup_table}")

        conn.execute("ALTER TABLE video_progress RENAME TO video_progress_v11_backup")
        _create_profiles_table(conn)
        _create_video_progress_table(conn)

        legacy_count_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM {backup_table}"
        ).fetchone()
        legacy_row_count = int(legacy_count_row['count']) if legacy_count_row else 0

        if legacy_row_count > 0:
            profile_id = _create_imported_progress_profile(conn)
            conn.execute(
                f"""
                INSERT INTO video_progress (
                    video_path,
                    profile_id,
                    category_id,
                    video_timestamp,
                    video_duration,
                    thumbnail_url,
                    last_watched,
                    updated_at
                )
                SELECT
                    video_path,
                    ?,
                    category_id,
                    video_timestamp,
                    video_duration,
                    thumbnail_url,
                    last_watched,
                    updated_at
                FROM {backup_table}
                """,
                (profile_id,),
            )
            logger.info(
                "Migrated %s legacy progress rows into imported profile %s",
                legacy_row_count,
                profile_id,
            )

        conn.execute(f"DROP TABLE {backup_table}")
        _set_schema_version(conn, SCHEMA_VERSION)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _create_profiles_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            avatar_color TEXT DEFAULT NULL,
            avatar_icon TEXT DEFAULT NULL,
            preferences_json TEXT DEFAULT NULL,
            created_at REAL NOT NULL DEFAULT 0,
            last_active_at REAL NOT NULL DEFAULT 0
        )
        """
    )


def _add_profile_preferences_column(conn):
    logger.info("Adding preferences_json column to profiles table")
    conn.execute(
        "ALTER TABLE profiles ADD COLUMN preferences_json TEXT DEFAULT NULL"
    )


def _add_profile_avatar_icon_column(conn):
    logger.info("Adding avatar_icon column to profiles table")
    conn.execute(
        "ALTER TABLE profiles ADD COLUMN avatar_icon TEXT DEFAULT NULL"
    )


def _create_video_progress_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS video_progress (
            video_path TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            category_id TEXT,
            video_timestamp REAL,
            video_duration REAL,
            thumbnail_url TEXT,
            last_watched REAL NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            PRIMARY KEY (video_path, profile_id)
        )
        """
    )


def _rebuild_video_progress_table_with_foreign_key(conn):
    """Rebuild video_progress so SQLite enforces profile ownership."""
    logger.info(
        "Rebuilding video_progress table to enforce profiles(id) foreign key",
    )

    conn.execute("BEGIN IMMEDIATE")
    try:
        backup_table = 'video_progress_v14_backup'
        if _table_exists(conn, backup_table):
            conn.execute(f"DROP TABLE {backup_table}")

        conn.execute("ALTER TABLE video_progress RENAME TO video_progress_v14_backup")
        _create_video_progress_table(conn)

        source_count_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM {backup_table}"
        ).fetchone()
        source_count = int(source_count_row['count']) if source_count_row else 0

        conn.execute(
            f"""
            INSERT INTO video_progress (
                video_path,
                profile_id,
                category_id,
                video_timestamp,
                video_duration,
                thumbnail_url,
                last_watched,
                updated_at
            )
            SELECT
                backup.video_path,
                backup.profile_id,
                backup.category_id,
                backup.video_timestamp,
                backup.video_duration,
                backup.thumbnail_url,
                backup.last_watched,
                backup.updated_at
            FROM {backup_table} AS backup
            WHERE EXISTS (
                SELECT 1
                FROM profiles
                WHERE profiles.id = backup.profile_id
            )
            """
        )

        preserved_count_row = conn.execute(
            "SELECT COUNT(*) AS count FROM video_progress"
        ).fetchone()
        preserved_count = int(preserved_count_row['count']) if preserved_count_row else 0

        conn.execute(f"DROP TABLE {backup_table}")
        conn.execute("COMMIT")

        dropped_count = max(0, source_count - preserved_count)
        if dropped_count:
            logger.warning(
                "Dropped %s orphaned video_progress rows during foreign key rebuild",
                dropped_count,
            )
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _create_imported_progress_profile(conn):
    now = time.time()
    suffix = 1
    name = LEGACY_PROGRESS_PROFILE_NAME

    while True:
        row = conn.execute(
            "SELECT id FROM profiles WHERE lower(name) = lower(?) LIMIT 1",
            (name,),
        ).fetchone()
        if row is None:
            break
        suffix += 1
        name = f"{LEGACY_PROGRESS_PROFILE_NAME} {suffix}"

    profile_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO profiles (id, name, avatar_color, created_at, last_active_at)
        VALUES (?, ?, NULL, ?, ?)
        """,
        (profile_id, name, now, now),
    )
    return profile_id
