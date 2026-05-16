"""Hidden-content domain service."""

import logging
import os
import sqlite3
import time

from app.services.core.sqlite_runtime_service import get_db
from app.services.media.media_index_service import bump_category_version_hash
from specter import create_cache

logger = logging.getLogger(__name__)

_hidden_files_cache = create_cache('hidden_files')
_hidden_categories_cache = create_cache('hidden_categories')
_HIDDEN_FILES_OVERFLOW = "OVERFLOW"
_MAX_HIDDEN_FILES_CACHE = 10000


def _normalize_category_id(category_id):
    """Normalize old-style auto category IDs to the current delimiter format."""
    normalized = str(category_id) if category_id is not None else ''
    if normalized.startswith('auto-'):
        normalized = 'auto::' + normalized[5:].replace('-', '::')
    return normalized


def update_hidden_file_path(old_path, new_path):
    """Update a hidden-file record after a rename."""
    try:
        old_path = os.path.normpath(old_path)
        new_path = os.path.normpath(new_path)

        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE hidden_files SET file_path = ?, hidden_at = ? WHERE file_path = ?",
                (str(new_path), time.time(), str(old_path)),
            )

        if cursor.rowcount > 0:
            _invalidate_hidden_files_cache()
            logger.info("Updated hidden file path: %s -> %s", old_path, new_path)
            return True
        return False
    except sqlite3.Error as exc:
        logger.error("Error updating hidden file path: %s", exc)
        return False


def delete_hidden_file_entry(file_path):
    """Delete a hidden-file entry without affecting category visibility."""
    try:
        normalized_path = os.path.normpath(file_path)
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM hidden_files WHERE file_path = ?",
                (str(normalized_path),),
            )

        if cursor.rowcount > 0:
            _invalidate_hidden_files_cache()
            logger.info("Deleted hidden file entry: %s", normalized_path)
            return True
        return False
    except sqlite3.Error as exc:
        logger.error("Error deleting hidden file entry for %s: %s", file_path, exc)
        return False


def _invalidate_hidden_categories_cache():
    """Invalidate the hidden-category cache."""
    _hidden_categories_cache.invalidate()
    logger.debug("Hidden categories cache invalidated")


def invalidate_hidden_content_caches():
    """Invalidate cached hidden category and file state."""
    _hidden_categories_cache.invalidate()
    _hidden_files_cache.invalidate()
    logger.debug("Hidden content caches invalidated")


def get_hidden_categories_set():
    """Return cached hidden category IDs."""
    def factory():
        try:
            with get_db() as conn:
                cursor = conn.execute("SELECT category_id FROM hidden_categories")
                hidden_ids = frozenset(row['category_id'] for row in cursor.fetchall())
                logger.debug(
                    "Hidden categories cache loaded: %s categories",
                    len(hidden_ids),
                )
                return hidden_ids
        except sqlite3.Error as exc:
            logger.error("Error loading hidden categories for cache: %s", exc)
            return frozenset()

    return _hidden_categories_cache.get_or_compute(factory)


def get_all_child_category_ids(parent_category_id):
    """Return all auto child categories under a parent category ID."""
    from app.services.media.category_query_service import get_all_categories_with_details

    try:
        all_categories = get_all_categories_with_details(
            use_cache=True,
            show_hidden=True,
        )
        children = []
        prefix = f"{parent_category_id}::"

        for category in all_categories:
            category_id = category.get('id', '')
            if category_id.startswith(prefix):
                children.append(category_id)

        return children
    except Exception as exc:
        logger.error("Error getting child categories for %s: %s", parent_category_id, exc)
        return []


def _reapply_hidden_file_states(conn, category_ids=None):
    """Re-apply file-level hidden flags after a category visibility change."""
    query = "SELECT file_path, category_id FROM hidden_files"
    params = []

    if category_ids:
        placeholders = ",".join("?" * len(category_ids))
        query += f" WHERE category_id IN ({placeholders})"
        params.extend(category_ids)

    cursor = conn.execute(query, params)
    for row in cursor.fetchall():
        _update_media_index_hidden_state(
            conn,
            os.path.normpath(str(row['file_path'])),
            row['category_id'],
            1,
        )


def _reconcile_media_index_hidden_state(conn, category_ids=None):
    """Rebuild media_index hidden flags from hidden categories/files."""
    if category_ids:
        placeholders = ",".join("?" * len(category_ids))
        conn.execute(
            f"UPDATE media_index SET is_hidden = 0 WHERE category_id IN ({placeholders})",
            category_ids,
        )

        cursor = conn.execute(
            f"SELECT category_id FROM hidden_categories WHERE category_id IN ({placeholders})",
            category_ids,
        )
        hidden_category_ids = [row['category_id'] for row in cursor.fetchall()]
        if hidden_category_ids:
            hidden_placeholders = ",".join("?" * len(hidden_category_ids))
            conn.execute(
                f"UPDATE media_index SET is_hidden = 1 WHERE category_id IN ({hidden_placeholders})",
                hidden_category_ids,
            )

        _reapply_hidden_file_states(conn, category_ids)
        return

    conn.execute("UPDATE media_index SET is_hidden = 0")

    cursor = conn.execute("SELECT category_id FROM hidden_categories")
    hidden_category_ids = [row['category_id'] for row in cursor.fetchall()]
    if hidden_category_ids:
        placeholders = ",".join("?" * len(hidden_category_ids))
        conn.execute(
            f"UPDATE media_index SET is_hidden = 1 WHERE category_id IN ({placeholders})",
            hidden_category_ids,
        )

    _reapply_hidden_file_states(conn)


def hide_category(category_id, admin_session_id=None):
    """Hide a category and all of its discovered children."""
    try:
        normalized_category_id = _normalize_category_id(category_id)
        children = get_all_child_category_ids(normalized_category_id)
        current_time = time.time()
        admin_id = str(admin_session_id) if admin_session_id else None
        data = [(normalized_category_id, current_time, admin_id)]
        data.extend((str(child_id), current_time, admin_id) for child_id in children)

        with get_db() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO hidden_categories
                (category_id, hidden_at, hidden_by)
                VALUES (?, ?, ?)
                """,
                data,
            )

            for cat_id, _, _ in data:
                conn.execute(
                    "UPDATE media_index SET is_hidden = 1 WHERE category_id = ?",
                    (str(cat_id),),
                )

        _invalidate_hidden_categories_cache()
        for cat_id, _, _ in data:
            bump_category_version_hash(str(cat_id))

        total_hidden = len(data)
        logger.info(
            "Category hidden (explicit cascade): %s + %s children by %s",
            normalized_category_id,
            len(children),
            admin_session_id,
        )
        suffix = 'y' if total_hidden == 1 else 'ies'
        return True, f"Hidden {total_hidden} categor{suffix} successfully."
    except sqlite3.Error as exc:
        logger.error("Error hiding category: %s", exc)
        return False, f"Failed to hide category: {str(exc)}"


def unhide_all_categories():
    """Clear all hidden categories."""
    try:
        with get_db() as conn:
            cursor = conn.execute("SELECT category_id FROM hidden_categories")
            hidden_category_ids = [
                row['category_id']
                for row in cursor.fetchall()
                if row['category_id']
            ]
            count = len(hidden_category_ids)
            conn.execute("DELETE FROM hidden_categories")
            _reconcile_media_index_hidden_state(conn)

        _invalidate_hidden_categories_cache()
        for category_id in hidden_category_ids:
            bump_category_version_hash(str(category_id))
        logger.info("Unhid all categories (%s total)", count)
        return True, f"Unhid all categories ({count} total)."
    except sqlite3.Error as exc:
        logger.error("Error unhiding all categories: %s", exc)
        return False, f"Failed to unhide categories: {str(exc)}"


def unhide_category(category_id, cascade=True):
    """Unhide a category, optionally including all children."""
    try:
        normalized_category_id = _normalize_category_id(category_id)
        children = get_all_child_category_ids(normalized_category_id) if cascade else []
        target_ids = [normalized_category_id]
        target_ids.extend(str(child_id) for child_id in children)

        rows_affected = 0
        with get_db() as conn:
            if target_ids:
                batch_size = 500
                for index in range(0, len(target_ids), batch_size):
                    batch = target_ids[index:index + batch_size]
                    placeholders = ','.join('?' * len(batch))
                    cursor = conn.execute(
                        f"DELETE FROM hidden_categories WHERE category_id IN ({placeholders})",
                        batch,
                    )
                    rows_affected += cursor.rowcount
                    _reconcile_media_index_hidden_state(conn, batch)

        if rows_affected > 0:
            _invalidate_hidden_categories_cache()
            for target_id in target_ids:
                bump_category_version_hash(str(target_id))

            children_count = len(children) if cascade else 0
            logger.info(
                "Unhid category: %s%s",
                normalized_category_id,
                f" + {children_count} children" if children_count > 0 else "",
            )
            suffix = 'y' if rows_affected == 1 else 'ies'
            return True, f"Unhidden {rows_affected} categor{suffix} successfully."

        logger.warning(
            "Attempted to unhide category that wasn't hidden: %s",
            normalized_category_id,
        )
        return False, f"Category {normalized_category_id} was not hidden."
    except sqlite3.Error as exc:
        logger.error("Error unhiding category %s: %s", category_id, exc)
        return False, f"Failed to unhide category: {str(exc)}"


def get_hidden_categories_with_details():
    """Return hidden-category rows with metadata."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT category_id, hidden_at, hidden_by
                FROM hidden_categories
                ORDER BY hidden_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        logger.error("Error getting hidden categories with details: %s", exc)
        return []


def is_category_hidden(category_id):
    """Return True when the category is hidden."""
    try:
        return _normalize_category_id(category_id) in get_hidden_categories_set()
    except Exception as exc:
        logger.error("Error checking if category is hidden: %s", exc)
        return False


def get_hidden_category_ids():
    """Return the list of hidden category IDs."""
    try:
        return list(get_hidden_categories_set())
    except Exception as exc:
        logger.error("Error getting hidden categories: %s", exc)
        return []


def should_block_category_access(category_id, show_hidden=False):
    """Return True when a category should be invisible to the caller."""
    if show_hidden:
        return False

    current_id = _normalize_category_id(category_id)
    if is_category_hidden(current_id):
        return True

    for _ in range(10):
        if '::' not in current_id:
            break
        parent_id = current_id.rsplit('::', 1)[0]
        if not parent_id:
            break
        if is_category_hidden(parent_id):
            return True
        current_id = parent_id

    return False


def _invalidate_hidden_files_cache():
    """Invalidate the hidden-file cache."""
    _hidden_files_cache.invalidate()
    logger.debug("Hidden files cache invalidated")


def get_hidden_files_set():
    """Return cached hidden-file paths or overflow sentinel."""
    def factory():
        try:
            with get_db() as conn:
                count_row = conn.execute(
                    "SELECT COUNT(*) as count FROM hidden_files"
                ).fetchone()
                count = count_row['count'] if count_row else 0

                if count > _MAX_HIDDEN_FILES_CACHE:
                    logger.warning(
                        "Hidden files count (%s) exceeds cache limit. Scaling to DB lookups.",
                        count,
                    )
                    return _HIDDEN_FILES_OVERFLOW

                cursor = conn.execute("SELECT file_path FROM hidden_files")
                result = frozenset(
                    os.path.normcase(os.path.normpath(row['file_path']))
                    for row in cursor.fetchall()
                )
                logger.debug("Hidden files cache loaded: %s files", len(result))
                return result
        except sqlite3.Error as exc:
            logger.error("Error loading hidden files for cache: %s", exc)
            return frozenset()

    return _hidden_files_cache.get_or_compute(factory)


def _resolve_category_id_for_file(normalized_path, category_id):
    """Resolve a normalized category ID for a file path when missing."""
    cat_id = _normalize_category_id(category_id)
    if cat_id:
        return cat_id

    try:
        from app.services.storage.storage_path_service import get_category_id_from_path

        return get_category_id_from_path(os.path.dirname(normalized_path))
    except Exception:
        return None


def _update_media_index_hidden_state(conn, normalized_path, category_id, is_hidden):
    """Mirror hidden-file state into media_index."""
    rel_path = None
    if category_id:
        try:
            from app.services.media.category_query_service import get_category_by_id

            category = get_category_by_id(category_id)
            category_path = category.get('path') if category else None
            if category_path:
                rel_path = os.path.relpath(normalized_path, os.path.normpath(category_path))
                rel_path = rel_path.replace('\\', '/').lstrip('/')
        except Exception:
            rel_path = None

    if rel_path:
        conn.execute(
            """
            UPDATE media_index SET is_hidden = ?
            WHERE category_id = ? AND rel_path = ?
            """,
            (is_hidden, str(category_id), rel_path),
        )
        return

    basename = os.path.basename(normalized_path)
    conn.execute(
        """
        UPDATE media_index SET is_hidden = ?
        WHERE rel_path LIKE '%' || ?
        """,
        (is_hidden, basename),
    )


def hide_file(file_path, category_id=None, admin_session_id=None):
    """Hide one file and mirror that state into media_index."""
    try:
        current_time = time.time()
        normalized_path = os.path.normpath(str(file_path))
        admin_id = str(admin_session_id) if admin_session_id else None
        cat_id = _resolve_category_id_for_file(normalized_path, category_id)

        with get_db() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO hidden_files
                (file_path, category_id, hidden_at, hidden_by)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_path, cat_id, current_time, admin_id),
            )
            _update_media_index_hidden_state(conn, normalized_path, cat_id, 1)

        _invalidate_hidden_files_cache()
        bump_category_version_hash(str(cat_id) if cat_id else '')
        return True, f"File hidden successfully: {os.path.basename(file_path)}"
    except sqlite3.Error as exc:
        logger.error("Error hiding file %s: %s", file_path, exc)
        return False, f"Database error: {str(exc)}"


def hide_files_batch(files_list, category_id=None, admin_session_id=None):
    """Hide multiple files in one transaction."""
    try:
        current_time = time.time()
        admin_id = str(admin_session_id) if admin_session_id else None
        cat_id = _normalize_category_id(category_id) if category_id else None
        data = []
        normalized_paths = []

        for file_path in files_list:
            normalized_path = os.path.normpath(str(file_path))
            normalized_paths.append(normalized_path)
            data.append((normalized_path, cat_id, current_time, admin_id))

        if not data:
            return True, "No files to hide.", 0

        with get_db() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO hidden_files
                (file_path, category_id, hidden_at, hidden_by)
                VALUES (?, ?, ?, ?)
                """,
                data,
            )
            for normalized_path in normalized_paths:
                _update_media_index_hidden_state(conn, normalized_path, cat_id, 1)

        _invalidate_hidden_files_cache()
        if cat_id:
            bump_category_version_hash(str(cat_id))

        count = len(data)
        logger.info(
            "Hidden %s files in batch for category %s by %s",
            count,
            category_id,
            admin_session_id,
        )
        return True, f"Hidden {count} files successfully.", count
    except sqlite3.Error as exc:
        logger.error("Error hiding files in batch: %s", exc)
        return False, f"Failed to hide files: {str(exc)}", 0


def unhide_file(file_path):
    """Unhide a single file."""
    try:
        normalized_path = os.path.normpath(str(file_path))
        affected_category_ids = set()

        with get_db() as conn:
            cursor = conn.execute(
                "SELECT category_id FROM hidden_files WHERE file_path = ?",
                (normalized_path,),
            )
            affected_category_ids.update(
                row['category_id']
                for row in cursor.fetchall()
                if row['category_id']
            )
            cursor = conn.execute(
                "DELETE FROM hidden_files WHERE file_path = ?",
                (normalized_path,),
            )
            rows = cursor.rowcount

            if rows == 0:
                cursor = conn.execute(
                    "SELECT category_id FROM hidden_files WHERE file_path = ?",
                    (file_path,),
                )
                affected_category_ids.update(
                    row['category_id']
                    for row in cursor.fetchall()
                    if row['category_id']
                )
                cursor = conn.execute(
                    "DELETE FROM hidden_files WHERE file_path = ?",
                    (file_path,),
                )
                rows = cursor.rowcount

            if rows > 0:
                _reconcile_media_index_hidden_state(
                    conn,
                    list(affected_category_ids) if affected_category_ids else None,
                )

        _invalidate_hidden_files_cache()
        if rows > 0:
            for category_id in affected_category_ids:
                bump_category_version_hash(str(category_id))
            return True, f"File unhidden successfully: {os.path.basename(file_path)}"
        return False, "File was not hidden."
    except sqlite3.Error as exc:
        logger.error("Error unhiding file %s: %s", file_path, exc)
        return False, f"Database error: {str(exc)}"


def unhide_files_batch(file_paths):
    """Unhide multiple files in one transaction."""
    if not file_paths:
        return True, "No files to unhide."

    try:
        normalized_paths = [os.path.normpath(str(path)) for path in file_paths]
        should_invalidate_categories = False
        affected_category_ids = set()
        total_rows_affected = 0
        batch_size = 500

        with get_db() as conn:
            for index in range(0, len(normalized_paths), batch_size):
                batch = normalized_paths[index:index + batch_size]
                placeholders = ','.join('?' * len(batch))
                cursor = conn.execute(
                    f"SELECT DISTINCT category_id FROM hidden_files WHERE file_path IN ({placeholders})",
                    batch,
                )
                category_ids = [
                    row['category_id']
                    for row in cursor.fetchall()
                    if row['category_id']
                ]

                cursor = conn.execute(
                    f"DELETE FROM hidden_files WHERE file_path IN ({placeholders})",
                    batch,
                )
                total_rows_affected += cursor.rowcount

                if category_ids:
                    cat_placeholders = ','.join('?' * len(category_ids))
                    conn.execute(
                        f"DELETE FROM hidden_categories WHERE category_id IN ({cat_placeholders})",
                        category_ids,
                    )
                    should_invalidate_categories = True
                    affected_category_ids.update(category_ids)
                    logger.info("Implicitly unhid %s parent categories", len(category_ids))

            _reconcile_media_index_hidden_state(
                conn,
                list(affected_category_ids) if affected_category_ids else None,
            )

        if should_invalidate_categories:
            _invalidate_hidden_categories_cache()
        if total_rows_affected > 0:
            _invalidate_hidden_files_cache()
        for category_id in affected_category_ids:
            bump_category_version_hash(str(category_id))

        return True, f"Unhidden {total_rows_affected} files."
    except sqlite3.Error as exc:
        logger.error("Error unhiding files batch: %s", exc)
        return False, f"Failed to unhide files: {str(exc)}"


def unhide_all_files():
    """Clear all hidden-file records and visible state flags."""
    try:
        with get_db() as conn:
            cursor = conn.execute("SELECT category_id FROM hidden_files")
            affected_category_ids = {
                row['category_id']
                for row in cursor.fetchall()
                if row['category_id']
            }
            count = len(affected_category_ids)
            cursor = conn.execute("SELECT COUNT(*) as count FROM hidden_files")
            hidden_count = cursor.fetchone()['count']
            conn.execute("DELETE FROM hidden_files")
            _reconcile_media_index_hidden_state(conn)

        _invalidate_hidden_files_cache()
        for category_id in affected_category_ids:
            bump_category_version_hash(str(category_id))
        logger.info("Unhid all files (%s total)", hidden_count)
        return True, f"Unhid all files ({hidden_count} total)."
    except sqlite3.Error as exc:
        logger.error("Error unhiding all files: %s", exc)
        return False, f"Failed to unhide files: {str(exc)}"


def is_file_hidden(file_path):
    """Return True when the file is hidden."""
    try:
        normalized_path = os.path.normpath(str(file_path))
        norm_case_path = os.path.normcase(normalized_path)
        hidden_files = get_hidden_files_set()

        if hidden_files == _HIDDEN_FILES_OVERFLOW:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT 1 FROM hidden_files WHERE file_path = ?",
                    (normalized_path,),
                ).fetchone()
                return row is not None

        if norm_case_path in hidden_files:
            return True

        for part in normalized_path.split(os.sep):
            if part.startswith('.') and part not in ('.', '..'):
                return True

        return False
    except Exception as exc:
        logger.error("Error checking if file is hidden: %s", exc)
        return False


def get_hidden_files_for_category(category_id):
    """Return hidden file paths for one category."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT file_path FROM hidden_files WHERE category_id = ?",
                (str(category_id),),
            )
            return [row['file_path'] for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        logger.error("Error getting hidden files for category: %s", exc)
        return []


def should_block_file_access(file_path, category_id, show_hidden=False):
    """Return True when a file should be invisible to the caller."""
    if show_hidden:
        return False

    if is_file_hidden(file_path):
        return True

    return should_block_category_access(category_id, show_hidden=False)
