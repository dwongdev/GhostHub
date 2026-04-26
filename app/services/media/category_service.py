"""Category mutation ownership."""

# app/services/category_service.py
import os
import uuid
import logging
import traceback
from app.services.media import category_persistence_service

logger = logging.getLogger(__name__)


class CategoryService:
    """Service for managing manual category mutation."""

    @staticmethod
    def add_category(name, path):
        """
        Add a new category with validation.

        Returns (new_category, error_message) tuple.
        """
        if not name or not path:
            return None, "Category name and path are required."

        # Basic path validation (more robust validation might be needed)
        if not os.path.exists(path):
            logger.warning(f"Attempting to add category with non-existent path: {path}")
            # Allow adding but log warning - adjust if strict validation is needed
        elif not os.path.isdir(path):
            logger.error(
                f"Attempting to add category where path is not a directory: {path}"
            )
            return None, "The specified path is not a directory."

        logger.info(f"Attempting to add category: Name='{name}', Path='{path}'")
        categories = category_persistence_service.load_categories()

        # Check for duplicate path
        if any(c.get("path") == path for c in categories):
            logger.warning(f"Attempt to add category with duplicate path: {path}")
            return None, "A category with this path already exists."

        # Check for duplicate name (optional, decide if names must be unique)
        # if any(c.get('name') == name for c in categories):
        #     logger.warning(f"Attempt to add category with duplicate name: {name}")
        #     return None, "A category with this name already exists."

        new_category = {"id": str(uuid.uuid4()), "name": name, "path": path}
        categories.append(new_category)

        if category_persistence_service.save_categories_bulk(categories):
            logger.info(
                f"Successfully added category: ID={new_category['id']}, Name='{name}'"
            )
            return new_category, None
        else:
            logger.error(
                f"Failed to save categories after attempting to add: Name='{name}'"
            )
            return None, "Failed to save the new category."

    @staticmethod
    def delete_category(category_id):
        """
        Delete a category by ID.

        Returns (success, error_message) tuple.
        """
        logger.info(f"Attempting to delete category with ID: {category_id}")
        categories = category_persistence_service.load_categories()
        original_count = len(categories)
        categories = [c for c in categories if c.get("id") != category_id]

        if len(categories) == original_count:
            logger.warning(f"Category with ID {category_id} not found for deletion.")
            return False, "Category not found"

        # Optionally clear related cache entries here if caching is implemented at this level

        if category_persistence_service.save_categories_bulk(categories):
            logger.info(f"Successfully deleted category with ID: {category_id}")
            return True, None
        else:
            logger.error(f"Failed to save categories after deleting ID: {category_id}")
            return False, "Failed to save categories after deletion"
