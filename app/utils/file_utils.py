"""
File Utilities
-------------
Utilities for managing category configuration and directory checks.
Now uses SQLite for category storage via the media domain persistence service.
"""
# app/utils/file_utils.py
import os
import logging
import traceback

from app.services.core.runtime_config_service import (
    get_runtime_config_value,
    get_runtime_instance_path,
)

logger = logging.getLogger(__name__)

GHOSTHUB_DIR_NAME = ".ghosthub"


def get_categories_filepath():
    """
    Get absolute path to the categories JSON file.
    DEPRECATED: Categories are now stored in SQLite. This is kept for migration purposes.
    """
    return os.path.join(
        get_runtime_instance_path(),
        os.path.basename(get_runtime_config_value('CATEGORIES_FILE')),
    )


def init_categories_file():
    """
    Create empty categories file if it doesn't exist.
    DEPRECATED: Categories are now stored in SQLite. This is a no-op.
    """
    # No-op: SQLite database is initialized during app startup.
    pass


def load_categories():
    """
    Load manually added categories from storage.
    Now uses SQLite via category_persistence_service for reduced SD card I/O.
    
    Returns list of categories or empty list on error.
    """
    try:
        from app.services.media import category_persistence_service

        categories = category_persistence_service.load_categories()
        logger.info(f"Successfully loaded {len(categories)} categories from SQLite")
        return categories
    except Exception as e:
        logger.error(f"Error loading categories from SQLite: {str(e)}")
        logger.debug(traceback.format_exc())
        return []


def save_categories(categories):
    """
    Save categories to storage.
    Now uses SQLite via category_persistence_service for reduced SD card I/O.
    
    Returns True if successful, False otherwise.
    """
    try:
        from app.services.media import category_persistence_service

        success = category_persistence_service.save_categories_bulk(categories)
        if success:
            logger.info(f"Successfully saved {len(categories)} categories to SQLite")
        return success
    except Exception as e:
        logger.error(f"Error saving categories to SQLite: {str(e)}")
        logger.debug(traceback.format_exc())
        return False


def is_large_directory(category_path, threshold=50, known_file_count=None):
    """
    Check if a directory contains more than the threshold number of media files.
    This is a quick check to determine if async indexing should be used.
    
    Args:
        category_path (str): The path to the category directory.
        threshold (int): The number of files threshold.
        known_file_count (int, optional): Known file count from previous scan.
    Returns:
        bool: True if the directory contains more than threshold media files, False otherwise.
    """
    if threshold <= 0:
        return True

    if known_file_count is not None:
        return known_file_count > threshold

    try:
        # If no valid index, count files directly
        # Import here to avoid circular import
        from app.utils.media_utils import is_media_file
        
        try:
            # Use os.scandir() for constant memory usage and early exit
            count = 0
            with os.scandir(category_path) as it:
                for entry in it:
                    if entry.is_file() and is_media_file(entry.name):
                        count += 1
                        if count > threshold:
                            logger.debug(f"Directory {category_path} exceeded threshold of {threshold}")
                            return True

            logger.debug(f"Found {count} media files in {category_path}")
            return False
        except Exception as list_error:
            logger.error(f"Error listing directory {category_path}: {list_error}")
            return False
    except Exception as e:
        logger.error(f"Error checking directory size for {category_path}: {str(e)}")
        return False  # Default to False on error

# Additional file utilities can be added here
