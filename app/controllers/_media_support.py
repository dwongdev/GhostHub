"""Shared media path and visibility helpers for GhostHub controllers."""

import logging
import os
from urllib.parse import unquote

from app.services.media import hidden_content_service
from app.services.media import media_index_service
from app.services.media import media_path_service

logger = logging.getLogger(__name__)


class MediaVisibilitySupport:
    """Mixin with media path resolution and hidden-content filtering helpers."""

    def _extract_media_item_identity(self, item):
        category_id = item.get('category_id') or item.get('categoryId')
        rel_path = item.get('name') or item.get('filename') or item.get('rel_path')

        if not rel_path and item.get('url'):
            try:
                url = item.get('url', '')
                if '/media/' in url:
                    after = url.split('/media/', 1)[1]
                    after = after.split('?', 1)[0]
                    parts = after.split('/')
                    if len(parts) >= 2:
                        category_id = category_id or parts[0]
                        rel_path = '/'.join(parts[1:])
            except Exception:
                rel_path = None

        if rel_path:
            try:
                rel_path = unquote(rel_path)
            except Exception:
                pass

        return category_id, rel_path

    def _resolve_media_item_path(self, item):
        category_id, rel_path = self._extract_media_item_identity(item)
        if not category_id or not rel_path:
            return None, category_id

        try:
            rel_path = unquote(rel_path)
        except Exception:
            pass

        try:
            file_path, error = media_path_service.get_media_filepath(category_id, rel_path)
            if not error and file_path:
                return file_path, category_id
        except Exception as exc:
            logger.debug("Media path resolution failed: %s", exc)

        category_path = media_index_service.resolve_category_path_from_id(category_id)
        if category_path:
            return os.path.normpath(os.path.join(category_path, rel_path)), category_id
        return None, category_id

    def _filter_hidden_media_items(self, items, show_hidden=False):
        if show_hidden:
            return items

        filtered = []
        hidden_files_set = hidden_content_service.get_hidden_files_set()

        for item in items:
            category_id, rel_path = self._extract_media_item_identity(item)
            if hidden_content_service.should_block_category_access(category_id, show_hidden=False):
                continue

            file_path, _ = self._resolve_media_item_path(item)
            if file_path and hidden_content_service.is_file_hidden(file_path):
                continue

            if not file_path and rel_path and hidden_files_set:
                rel_norm = os.path.normcase(os.path.normpath(rel_path))
                rel_norm_slash = rel_norm.replace('\\', '/')
                hidden_by_suffix = False
                for hidden_path in hidden_files_set:
                    hp = hidden_path.replace('\\', '/')
                    if hp.endswith('/' + rel_norm_slash):
                        hidden_by_suffix = True
                        break
                if hidden_by_suffix:
                    continue

            filtered.append(item)

        return filtered

    def _media_url_exists(self, media_url, *, show_hidden=False):
        if not media_url:
            return False

        parts = media_url.strip('/').split('/', 2)
        if len(parts) < 3 or parts[0] != 'media':
            return False

        category_id = parts[1]
        filename = unquote(parts[2])
        file_path, error = media_path_service.get_media_filepath(category_id, filename)
        if error or not file_path:
            return False

        if not show_hidden and hidden_content_service.should_block_category_access(
            category_id,
            show_hidden=False,
        ):
            return False

        if not show_hidden and hidden_content_service.is_file_hidden(file_path):
            return False

        return True
