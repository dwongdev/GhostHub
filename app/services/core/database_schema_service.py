"""SQLite schema metadata for GhostHub persistence."""

from app.services.core.schema_descriptor import SCHEMA_VERSION, get_create_tables_sql

CREATE_TABLES_SQL = get_create_tables_sql()

__all__ = ['SCHEMA_VERSION', 'CREATE_TABLES_SQL']
