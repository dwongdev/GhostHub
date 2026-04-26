"""SQLite schema metadata for GhostHub persistence."""

SCHEMA_VERSION = 15

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    is_manual INTEGER NOT NULL DEFAULT 0,
    version_hash TEXT,
    created_at REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    avatar_color TEXT DEFAULT NULL,
    avatar_icon TEXT DEFAULT NULL,
    preferences_json TEXT DEFAULT NULL,
    created_at REAL NOT NULL DEFAULT 0,
    last_active_at REAL NOT NULL DEFAULT 0
);

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
);

CREATE TABLE IF NOT EXISTS hidden_categories (
    category_id TEXT PRIMARY KEY,
    hidden_at REAL NOT NULL DEFAULT 0,
    hidden_by TEXT
);

CREATE TABLE IF NOT EXISTS hidden_files (
    file_path TEXT PRIMARY KEY,
    category_id TEXT,
    hidden_at REAL NOT NULL DEFAULT 0,
    hidden_by TEXT
);

CREATE TABLE IF NOT EXISTS file_path_aliases (
    old_path TEXT PRIMARY KEY,
    new_path TEXT NOT NULL,
    renamed_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS media_index (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    parent_path TEXT NOT NULL,
    name TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    hash TEXT NOT NULL,
    type TEXT NOT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

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

CREATE TABLE IF NOT EXISTS drive_labels (
    device_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    updated_at REAL NOT NULL DEFAULT 0
);
"""
