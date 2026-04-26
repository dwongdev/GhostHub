"""Profile CRUD service backed by SQLite."""

import json
import logging
import re
import sqlite3
import time
import uuid

from app.services.core.session_store import clear_connections_for_profile
from app.services.core.sqlite_runtime_service import get_db

logger = logging.getLogger(__name__)

MAX_PROFILE_COUNT = 20
MAX_PROFILE_NAME_LENGTH = 24
PROFILE_NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 -]{0,23}$')
AVATAR_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')
AVATAR_ICON_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{0,39}$')
PROFILE_PREFERENCE_FIELDS = ('theme', 'layout', 'motion')
PROFILE_FEATURE_TOGGLES = (
    'chat',
    'headerBranding',
    'search',
    'syncButton',
)


def get_default_preferences():
    return {
        'theme': None,
        'layout': None,
        'motion': None,
        'features': {
            'chat': None,
            'headerBranding': None,
            'search': None,
            'syncButton': None,
        },
    }


def _normalize_name(name):
    return ' '.join(str(name or '').strip().split())


def _normalize_preference_scalar(value, field_name):
    if value in (None, ''):
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    raise ValueError(f'Profile preference "{field_name}" must be a string or null.')


def _normalize_feature_toggle(value, key):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f'Profile feature preference "{key}" must be true, false, or null.')


def _normalize_preferences(preferences):
    defaults = get_default_preferences()
    if preferences in (None, ''):
        return defaults
    if not isinstance(preferences, dict):
        raise ValueError('Profile preferences must be an object.')

    normalized = get_default_preferences()
    for field_name in PROFILE_PREFERENCE_FIELDS:
        if field_name in preferences:
            normalized[field_name] = _normalize_preference_scalar(
                preferences.get(field_name),
                field_name,
            )

    features = preferences.get('features')
    if features is not None:
        if not isinstance(features, dict):
            raise ValueError('Profile preferences.features must be an object.')
        for key in PROFILE_FEATURE_TOGGLES:
            if key in features:
                normalized['features'][key] = _normalize_feature_toggle(features.get(key), key)

    return normalized


def _merge_preferences(existing_preferences, incoming_preferences):
    merged = _normalize_preferences(existing_preferences)
    incoming = _normalize_preferences(incoming_preferences)

    for field_name in PROFILE_PREFERENCE_FIELDS:
        if field_name in (incoming_preferences or {}):
            merged[field_name] = incoming[field_name]

    incoming_features = (incoming_preferences or {}).get('features')
    if incoming_features is not None:
        for key in PROFILE_FEATURE_TOGGLES:
            if key in incoming_features:
                merged['features'][key] = incoming['features'][key]

    return merged


def _preferences_to_db_value(preferences):
    normalized = _normalize_preferences(preferences)
    if normalized == get_default_preferences():
        return None
    return json.dumps(normalized, sort_keys=True, separators=(',', ':'))


def _preferences_from_db_value(raw_preferences):
    if raw_preferences in (None, ''):
        return get_default_preferences()

    try:
        parsed = json.loads(raw_preferences)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Invalid profile preferences JSON encountered; using defaults")
        return get_default_preferences()

    try:
        return _normalize_preferences(parsed)
    except ValueError:
        logger.warning("Invalid profile preferences payload encountered; using defaults")
        return get_default_preferences()


def _serialize_profile_row(row, *, include_preferences=True):
    if not row:
        return None
    profile = {
        'id': row['id'],
        'name': row['name'],
        'avatar_color': row['avatar_color'],
        'avatar_icon': row['avatar_icon'],
        'created_at': row['created_at'],
        'last_active_at': row['last_active_at'],
    }
    if include_preferences:
        profile['preferences'] = _preferences_from_db_value(row['preferences_json'])
    return profile


def _validate_name(name):
    normalized = _normalize_name(name)
    if not normalized:
        raise ValueError('Profile name is required.')
    if len(normalized) > MAX_PROFILE_NAME_LENGTH:
        raise ValueError('Profile name must be 24 characters or fewer.')
    if not PROFILE_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            'Profile name may only contain letters, numbers, spaces, and hyphens.'
        )
    return normalized


def _validate_avatar_color(avatar_color):
    if avatar_color in (None, ''):
        return None
    value = str(avatar_color).strip()
    if not AVATAR_COLOR_PATTERN.fullmatch(value):
        raise ValueError('Avatar color must be a hex value like #A1B2C3.')
    return value


def _validate_avatar_icon(avatar_icon):
    if avatar_icon in (None, ''):
        return None
    value = str(avatar_icon).strip().lower()
    if not AVATAR_ICON_PATTERN.fullmatch(value):
        raise ValueError('Avatar icon must be a valid avatar library key.')
    return value


def _profile_name_exists(conn, name, *, exclude_profile_id=None):
    query = """
        SELECT id
        FROM profiles
        WHERE lower(name) = lower(?)
    """
    params = [name]
    if exclude_profile_id:
        query += " AND id != ?"
        params.append(str(exclude_profile_id))

    row = conn.execute(query, tuple(params)).fetchone()
    return row is not None


def create_profile(name: str, avatar_color: str = None, avatar_icon: str = None) -> dict:
    """Create and return a new profile."""
    normalized_name = _validate_name(name)
    avatar_color = _validate_avatar_color(avatar_color)
    avatar_icon = _validate_avatar_icon(avatar_icon)
    now = time.time()
    profile_id = str(uuid.uuid4())

    try:
        with get_db() as conn:
            count_row = conn.execute("SELECT COUNT(*) AS count FROM profiles").fetchone()
            if count_row and int(count_row['count']) >= MAX_PROFILE_COUNT:
                raise ValueError(f'Profile limit reached ({MAX_PROFILE_COUNT}).')

            if _profile_name_exists(conn, normalized_name):
                raise ValueError('A profile with that name already exists.')

            conn.execute(
                """
                INSERT INTO profiles (
                    id,
                    name,
                    avatar_color,
                    avatar_icon,
                    preferences_json,
                    created_at,
                    last_active_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    normalized_name,
                    avatar_color,
                    avatar_icon,
                    None,
                    now,
                    now,
                ),
            )

        return get_profile(profile_id)
    except sqlite3.Error as exc:
        logger.error("Error creating profile: %s", exc)
        raise


def update_profile(profile_id: str, *, name=None, avatar_color=None, avatar_icon=None, preferences=None):
    """Update mutable profile fields and return the refreshed record."""
    if not profile_id:
        return None

    updates = {}
    if name is not None:
        updates['name'] = _validate_name(name)
    if avatar_color is not None:
        updates['avatar_color'] = _validate_avatar_color(avatar_color)
    if avatar_icon is not None:
        updates['avatar_icon'] = _validate_avatar_icon(avatar_icon)
    if preferences is not None and not isinstance(preferences, dict):
        raise ValueError('Profile preferences must be an object.')

    if not updates and preferences is None:
        raise ValueError('At least one profile field must be provided.')

    try:
        with get_db() as conn:
            existing_row = conn.execute(
                """
                SELECT id, preferences_json
                FROM profiles
                WHERE id = ?
                LIMIT 1
                """,
                (str(profile_id),),
            ).fetchone()
            if existing_row is None:
                return None

            if (
                'name' in updates and
                _profile_name_exists(conn, updates['name'], exclude_profile_id=profile_id)
            ):
                raise ValueError('A profile with that name already exists.')

            if preferences is not None:
                existing_preferences = _preferences_from_db_value(existing_row['preferences_json'])
                merged_preferences = _merge_preferences(existing_preferences, preferences)
                updates['preferences_json'] = _preferences_to_db_value(merged_preferences)

            assignments = ', '.join(f"{column} = ?" for column in updates.keys())
            params = [*updates.values(), str(profile_id)]
            cursor = conn.execute(
                f"UPDATE profiles SET {assignments} WHERE id = ?",
                tuple(params),
            )
            if cursor.rowcount <= 0:
                return None

        return get_profile(profile_id)
    except sqlite3.Error as exc:
        logger.error("Error updating profile %s: %s", profile_id, exc)
        raise


def list_profiles(*, include_preferences=False) -> list:
    """Return all profiles ordered by most recently active."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, avatar_color, avatar_icon, preferences_json, created_at, last_active_at
                FROM profiles
                ORDER BY last_active_at DESC, name COLLATE NOCASE ASC
                """
            )
            return [
                _serialize_profile_row(row, include_preferences=include_preferences)
                for row in cursor.fetchall()
            ]
    except sqlite3.Error as exc:
        logger.error("Error listing profiles: %s", exc)
        return []


def get_profile(profile_id: str, *, include_preferences=True):
    """Return a profile by id."""
    if not profile_id:
        return None

    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, name, avatar_color, avatar_icon, preferences_json, created_at, last_active_at
                FROM profiles
                WHERE id = ?
                LIMIT 1
                """,
                (str(profile_id),),
            ).fetchone()
            return _serialize_profile_row(row, include_preferences=include_preferences)
    except sqlite3.Error as exc:
        logger.error("Error getting profile %s: %s", profile_id, exc)
        return None


def get_profile_by_name(name: str, *, include_preferences=True):
    """Return a profile by case-insensitive name."""
    normalized_name = _normalize_name(name)
    if not normalized_name:
        return None

    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, name, avatar_color, avatar_icon, preferences_json, created_at, last_active_at
                FROM profiles
                WHERE lower(name) = lower(?)
                LIMIT 1
                """,
                (normalized_name,),
            ).fetchone()
            return _serialize_profile_row(row, include_preferences=include_preferences)
    except sqlite3.Error as exc:
        logger.error("Error getting profile by name %s: %s", normalized_name, exc)
        return None


def delete_profile(profile_id: str) -> bool:
    """Delete a profile and its associated progress rows."""
    if not profile_id:
        return False

    try:
        with get_db() as conn:
            conn.execute(
                "DELETE FROM video_progress WHERE profile_id = ?",
                (str(profile_id),),
            )
            cursor = conn.execute(
                "DELETE FROM profiles WHERE id = ?",
                (str(profile_id),),
            )

        if cursor.rowcount > 0:
            clear_connections_for_profile(profile_id)
            return True
        return False
    except sqlite3.Error as exc:
        logger.error("Error deleting profile %s: %s", profile_id, exc)
        return False


def update_profile_last_active(profile_id: str) -> None:
    """Touch the profile activity timestamp."""
    if not profile_id:
        return

    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE profiles SET last_active_at = ? WHERE id = ?",
                (time.time(), str(profile_id)),
            )
    except sqlite3.Error as exc:
        logger.error("Error updating last_active_at for %s: %s", profile_id, exc)


def rename_profile(profile_id: str, new_name: str):
    """Rename a profile and return the updated record."""
    return update_profile(profile_id, name=new_name)
