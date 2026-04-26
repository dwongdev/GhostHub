"""Category visibility filtering ownership."""

import logging

from app.services.media.hidden_content_service import should_block_category_access

logger = logging.getLogger(__name__)


def filter_hidden_categories(categories, show_hidden=False):
    """Filter out hidden categories unless show_hidden is True."""
    if show_hidden:
        return categories

    filtered = []
    for category in categories:
        category_id = category.get("id", "")
        if should_block_category_access(category_id, show_hidden=False):
            continue
        filtered.append(category)

    logger.debug(
        "Filtered %s hidden categories (including children)",
        len(categories) - len(filtered),
    )
    return filtered
