"""Persistent manual-category storage for the media domain."""

import logging
import os
import sqlite3
import time

from app.services.core.sqlite_runtime_service import get_db

logger = logging.getLogger(__name__)


def load_categories():
    """Load manually added categories from persistent storage."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, path FROM categories
                WHERE is_manual = 1
                ORDER BY created_at DESC
                """
            )
            return [
                {
                    'id': row['id'],
                    'name': row['name'],
                    'path': row['path'],
                }
                for row in cursor.fetchall()
            ]
    except sqlite3.Error as exc:
        logger.error("Error loading categories: %s", exc)
        return []


def save_category(category_id, name, path):
    """Persist a single manual category."""
    try:
        current_time = time.time()
        with get_db() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO categories
                (id, name, path, is_manual, created_at, updated_at)
                VALUES (?, ?, ?, 1, COALESCE((SELECT created_at FROM categories WHERE id = ?), ?), ?)
                """,
                (category_id, name, path, category_id, current_time, current_time),
            )
        logger.info("Saved category: %s (%s)", name, category_id)
        return True
    except sqlite3.Error as exc:
        logger.error("Error saving category: %s", exc)
        return False


def delete_category(category_id):
    """Delete a single manual category."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM categories WHERE id = ? AND is_manual = 1",
                (category_id,),
            )
            if cursor.rowcount > 0:
                logger.info("Deleted category: %s", category_id)
                return True
            logger.warning("Category not found for deletion: %s", category_id)
            return False
    except sqlite3.Error as exc:
        logger.error("Error deleting category: %s", exc)
        return False


def category_exists_by_path(path):
    """Check whether a manual category already exists at a path."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM categories WHERE path = ? LIMIT 1",
                (path,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as exc:
        logger.error("Error checking category exists: %s", exc)
        return False


def save_categories_bulk(categories):
    """Replace the manual category list in persistent storage."""
    try:
        current_time = time.time()
        with get_db() as conn:
            conn.execute("DELETE FROM categories WHERE is_manual = 1")
            for category in categories:
                if not isinstance(category, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO categories (id, name, path, is_manual, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (
                        category.get('id'),
                        category.get('name'),
                        category.get('path'),
                        current_time,
                        current_time,
                    ),
                )
        logger.info("Saved %s categories in bulk", len(categories))
        return True
    except sqlite3.Error as exc:
        logger.error("Error saving categories in bulk: %s", exc)
        return False


def delete_categories_by_path_prefix(path_prefix):
    """Delete persisted categories whose paths live under a filesystem prefix."""
    try:
        normalized_prefix = os.path.normpath(str(path_prefix))
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM categories WHERE path LIKE ?",
                (normalized_prefix + '%',),
            )
            if cursor.rowcount > 0:
                logger.info(
                    "Deleted %s categories under path prefix %s",
                    cursor.rowcount,
                    normalized_prefix,
                )
            return cursor.rowcount
    except sqlite3.Error as exc:
        logger.error(
            "Error deleting categories by path prefix %s: %s",
            path_prefix,
            exc,
        )
        return 0
