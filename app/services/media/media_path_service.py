"""Media file path validation and resolution helpers."""

import logging
import os

from app.services.media.category_query_service import get_category_by_id

logger = logging.getLogger(__name__)


def get_media_filepath(category_id, filename):
    """
    Resolve a category-relative media path to a readable file on disk.

    Returns a `(filepath, error_message)` tuple.
    """
    category = get_category_by_id(category_id)
    if not category:
        return None, "Category not found."

    if not filename:
        return None, "Filename cannot be empty."

    if '..' in filename or filename.startswith('/'):
        logger.warning("Potential directory traversal attempt blocked: %s", filename)
        return None, "Invalid filename."

    try:
        full_path = os.path.normpath(os.path.join(category['path'], filename))
    except Exception as path_error:
        logger.error(
            "Error constructing path for category %s, filename %s: %s",
            category_id,
            filename,
            path_error,
        )
        return None, "Error constructing file path."

    try:
        base_dir = os.path.realpath(category['path'])
        target_file = os.path.realpath(full_path)
        if not target_file.startswith(base_dir):
            logger.error(
                "Security Alert: Path traversal detected. Base='%s' Target='%s'",
                base_dir,
                target_file,
            )
            return None, "Access denied."
    except Exception as security_check_error:
        logger.error(
            "Error during security path validation for %s/%s: %s",
            category_id,
            filename,
            security_check_error,
        )
        return None, "File path validation failed."

    if not os.path.exists(target_file):
        logger.warning("Media file not found at path: %s", target_file)
        return None, "File not found."
    if not os.path.isfile(target_file):
        logger.warning("Path exists but is not a file: %s", target_file)
        return None, "Path is not a file."
    if not os.access(target_file, os.R_OK):
        logger.warning("File exists but is not readable: %s", target_file)
        return None, "File not readable."

    logger.info("Validated media file path: %s", target_file)
    return target_file, None
