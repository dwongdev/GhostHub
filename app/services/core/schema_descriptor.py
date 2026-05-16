"""Single source of truth for SQLite schema and portable user-data metadata."""

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 15
NO_DEFAULT = object()


@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False
    default: Any = NO_DEFAULT
    required_for_import: bool = False


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_table: str
    ref_column: str
    on_delete: str = ''


@dataclass(frozen=True)
class TableDef:
    columns: list[Column]
    export: bool = False
    import_order: int = 999
    composite_pk: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)


@dataclass(frozen=True)
class AddColumn:
    table: str
    column: str


TABLES = {
    'schema_info': TableDef(
        columns=[
            Column('key', 'TEXT', primary_key=True),
            Column('value', 'TEXT', not_null=True),
        ],
    ),
    'categories': TableDef(
        export=True,
        import_order=2,
        columns=[
            Column('id', 'TEXT', primary_key=True, required_for_import=True),
            Column('name', 'TEXT', not_null=True, required_for_import=True),
            Column('path', 'TEXT', not_null=True, unique=True, required_for_import=True),
            Column('is_manual', 'INTEGER', not_null=True, default=0),
            Column('version_hash', 'TEXT'),
            Column('created_at', 'REAL', not_null=True, default=0),
            Column('updated_at', 'REAL', not_null=True, default=0),
        ],
    ),
    'profiles': TableDef(
        export=True,
        import_order=1,
        columns=[
            Column('id', 'TEXT', primary_key=True, required_for_import=True),
            Column('name', 'TEXT', not_null=True, unique=True, required_for_import=True),
            Column('avatar_color', 'TEXT', default=None),
            Column('avatar_icon', 'TEXT', default=None),
            Column('preferences_json', 'TEXT', default=None),
            Column('created_at', 'REAL', not_null=True, default=0),
            Column('last_active_at', 'REAL', not_null=True, default=0),
        ],
    ),
    'video_progress': TableDef(
        export=True,
        import_order=6,
        composite_pk=['video_path', 'profile_id'],
        foreign_keys=[
            ForeignKey('profile_id', 'profiles', 'id', on_delete='CASCADE'),
        ],
        columns=[
            Column('video_path', 'TEXT', not_null=True, required_for_import=True),
            Column('profile_id', 'TEXT', not_null=True, required_for_import=True),
            Column('category_id', 'TEXT'),
            Column('video_timestamp', 'REAL'),
            Column('video_duration', 'REAL'),
            Column('thumbnail_url', 'TEXT'),
            Column('last_watched', 'REAL', not_null=True, default=0),
            Column('updated_at', 'REAL', not_null=True, default=0),
        ],
    ),
    'hidden_categories': TableDef(
        export=True,
        import_order=4,
        columns=[
            Column('category_id', 'TEXT', primary_key=True, required_for_import=True),
            Column('hidden_at', 'REAL', not_null=True, default=0),
            Column('hidden_by', 'TEXT'),
        ],
    ),
    'hidden_files': TableDef(
        export=True,
        import_order=5,
        columns=[
            Column('file_path', 'TEXT', primary_key=True, required_for_import=True),
            Column('category_id', 'TEXT'),
            Column('hidden_at', 'REAL', not_null=True, default=0),
            Column('hidden_by', 'TEXT'),
        ],
    ),
    'file_path_aliases': TableDef(
        columns=[
            Column('old_path', 'TEXT', primary_key=True),
            Column('new_path', 'TEXT', not_null=True),
            Column('renamed_at', 'REAL', not_null=True, default=0),
        ],
    ),
    'media_index': TableDef(
        columns=[
            Column('id', 'TEXT', primary_key=True),
            Column('category_id', 'TEXT', not_null=True),
            Column('rel_path', 'TEXT', not_null=True),
            Column('parent_path', 'TEXT', not_null=True),
            Column('name', 'TEXT', not_null=True),
            Column('size', 'INTEGER', not_null=True),
            Column('mtime', 'REAL', not_null=True),
            Column('hash', 'TEXT', not_null=True),
            Column('type', 'TEXT', not_null=True),
            Column('is_hidden', 'INTEGER', not_null=True, default=0),
            Column('created_at', 'REAL', not_null=True),
            Column('updated_at', 'REAL', not_null=True),
        ],
    ),
    'drive_labels': TableDef(
        export=True,
        import_order=3,
        columns=[
            Column('device_key', 'TEXT', primary_key=True, required_for_import=True),
            Column('label', 'TEXT', not_null=True, required_for_import=True),
            Column('updated_at', 'REAL', not_null=True, default=0),
        ],
    ),
}

MIGRATIONS: dict[int, list[AddColumn]] = {}

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_categories_path ON categories(path);
CREATE INDEX IF NOT EXISTS idx_categories_is_manual ON categories(is_manual);
CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_video_progress_category ON video_progress(category_id);
CREATE INDEX IF NOT EXISTS idx_video_progress_last_watched ON video_progress(last_watched DESC);
CREATE INDEX IF NOT EXISTS idx_video_progress_profile ON video_progress(profile_id);
CREATE INDEX IF NOT EXISTS idx_hidden_files_category ON hidden_files(category_id);
CREATE INDEX IF NOT EXISTS idx_file_path_aliases_renamed_at ON file_path_aliases(renamed_at DESC);
CREATE INDEX IF NOT EXISTS idx_video_progress_cat_timestamp ON video_progress(category_id, video_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_video_progress_profile_cat ON video_progress(profile_id, category_id);
CREATE INDEX IF NOT EXISTS idx_media_index_category_id ON media_index(category_id);
CREATE INDEX IF NOT EXISTS idx_media_index_parent_path ON media_index(category_id, parent_path);
CREATE INDEX IF NOT EXISTS idx_media_index_mtime ON media_index(mtime DESC);
CREATE INDEX IF NOT EXISTS idx_media_index_name ON media_index(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_media_index_type ON media_index(type);
CREATE INDEX IF NOT EXISTS idx_media_index_hidden ON media_index(is_hidden);
CREATE INDEX IF NOT EXISTS idx_media_index_category_rel_path ON media_index(category_id, rel_path);
CREATE INDEX IF NOT EXISTS idx_media_index_cat_hidden_name ON media_index(category_id, is_hidden, name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_media_index_cat_hidden_parent_name ON media_index(category_id, is_hidden, parent_path, name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_media_index_cat_hidden_mtime ON media_index(category_id, is_hidden, mtime DESC);
"""


def get_export_tables() -> dict[str, list[str]]:
    """Return exportable table names mapped to ordered column names."""
    return {
        name: [column.name for column in table.columns]
        for name, table in TABLES.items()
        if table.export
    }


def get_table_defaults(table: str) -> dict[str, Any]:
    """Return import defaults for non-required columns with schema defaults."""
    return {
        column.name: column.default
        for column in TABLES[table].columns
        if not column.required_for_import and column.default is not NO_DEFAULT
    }


def get_required_columns(table: str) -> set[str]:
    """Return columns required to be present and non-empty in imported rows."""
    return {
        column.name
        for column in TABLES[table].columns
        if column.required_for_import
    }


def get_import_order() -> list[str]:
    """Return export table names ordered for foreign-key aware imports."""
    return [
        name
        for name, _table in sorted(
            ((name, table) for name, table in TABLES.items() if table.export),
            key=lambda item: item[1].import_order,
        )
    ]


def get_create_tables_sql() -> str:
    """Generate full CREATE TABLE IF NOT EXISTS SQL for all tables and indexes."""
    statements = [_create_table_sql(name, table) for name, table in TABLES.items()]
    statements.append(INDEXES_SQL.strip())
    return '\n\n'.join(statements) + '\n'


def get_add_column_sql(table: str, column: str) -> str:
    """Return the SQL fragment used by ALTER TABLE ADD COLUMN."""
    return _column_sql(_find_column(table, column))


def apply_migrations_to_rows(tables: dict, from_version: int) -> None:
    """Apply descriptor ADD COLUMN migrations to imported table row payloads."""
    for version in sorted(MIGRATIONS):
        if version <= from_version or version > SCHEMA_VERSION:
            continue
        for step in MIGRATIONS[version]:
            if not isinstance(step, AddColumn):
                continue
            column = _find_column(step.table, step.column)
            default = None if column.default is NO_DEFAULT else column.default
            for row in tables.get(step.table, []):
                row.setdefault(step.column, default)


def has_migration_path(from_version: int) -> bool:
    """Return whether descriptor migrations cover every version to current."""
    if from_version >= SCHEMA_VERSION:
        return False
    return all(
        version in MIGRATIONS
        for version in range(from_version + 1, SCHEMA_VERSION + 1)
    )


def _create_table_sql(name: str, table: TableDef) -> str:
    if table.composite_pk:
        for column in table.columns:
            if column.primary_key:
                raise ValueError(
                    f"Table '{name}' defines both composite_pk and column-level "
                    f"primary_key on '{column.name}' — use one or the other."
                )
    definitions = [_column_sql(column) for column in table.columns]
    if table.composite_pk:
        definitions.append(f"PRIMARY KEY ({', '.join(table.composite_pk)})")
    for foreign_key in table.foreign_keys:
        clause = (
            f"FOREIGN KEY ({foreign_key.column}) "
            f"REFERENCES {foreign_key.ref_table}({foreign_key.ref_column})"
        )
        if foreign_key.on_delete:
            clause += f" ON DELETE {foreign_key.on_delete}"
        definitions.append(clause)

    body = ',\n    '.join(definitions)
    return f"CREATE TABLE IF NOT EXISTS {name} (\n    {body}\n);"


def _column_sql(column: Column) -> str:
    parts = [column.name, column.sql_type]
    if column.primary_key:
        parts.append('PRIMARY KEY')
    if column.not_null:
        parts.append('NOT NULL')
    if column.unique:
        parts.append('UNIQUE')
    if column.default is not NO_DEFAULT:
        parts.extend(['DEFAULT', _format_default(column.default)])
    return ' '.join(parts)


def _format_default(value: Any) -> str:
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _find_column(table: str, column: str) -> Column:
    for candidate in TABLES[table].columns:
        if candidate.name == column:
            return candidate
    raise KeyError(f'Unknown schema column {table}.{column}')
