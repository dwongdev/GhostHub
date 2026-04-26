"""Admin visibility/content control controller built on Specter."""

import logging
import os
import time

from flask import request, session

from app.constants import SOCKET_EVENTS
from app.services.core import session_store
from specter import Controller, Field, Schema, expect_json, registry
from app.utils.auth import admin_required, get_request_session_id, is_current_admin_session

logger = logging.getLogger(__name__)


class AdminVisibilityController(Controller):
    """Own admin content visibility and show-hidden session endpoints."""

    name = 'admin_visibility'
    url_prefix = '/api/admin'

    schemas = {
        'hide_category': Schema('admin_visibility.hide_category', {
            'category_id': Field(str, required=True),
        }, strict=True),
        'show_hidden': Schema('admin_visibility.show_hidden', {
            'duration': Field(int, default=3600),
        }, strict=True),
        'unhide_category': Schema('admin_visibility.unhide_category', {
            'category_id': Field(str),
        }, strict=True),
        'file_visibility': Schema('admin_visibility.file_visibility', {
            'file_path': Field(str, required=True),
            'category_id': Field(str),
        }, strict=True),
        'media_action': Schema('admin_visibility.media_action', {
            'category_id': Field(str, required=True),
            'rel_path': Field(str, required=True),
            'action': Field(
                str,
                required=True,
                choices=('rename', 'hide', 'unhide', 'delete'),
            ),
            'new_name': Field(str),
        }, strict=True),
    }

    def build_routes(self, router):
        @router.route('/categories/hide', methods=['POST'])
        @admin_required
        def hide_category():
            """Hide a category from all users."""
            try:
                from app.services.media.hidden_content_service import (
                    get_all_child_category_ids,
                    hide_category as hidden_hide_category,
                )
                from app.services.media.category_cache_service import (
                    update_cached_category,
                )

                payload = self.schema('hide_category').require(expect_json())
                category_id = self._normalize_category_id(payload['category_id'])
                admin_session_id = get_request_session_id()

                success, message = hidden_hide_category(category_id, admin_session_id)
                if not success:
                    return {'success': False, 'error': message}, 500

                update_cached_category(category_id)
                children = get_all_child_category_ids(category_id)
                for child in children:
                    update_cached_category(child)

                registry.require('library_events').emit_category_updated(
                    {'reason': 'category_hidden', 'category_id': category_id},
                )

                logger.info("Admin %s hid category: %s", admin_session_id, category_id)
                return {'success': True, 'message': message}
            except Exception as exc:
                logger.error("Error hiding category: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/categories/show', methods=['POST'])
        @admin_required
        def show_hidden_categories():
            """Temporarily reveal hidden categories in the current admin session."""
            try:
                payload = self.schema('show_hidden').require(
                    request.get_json(silent=True) or {},
                )
                duration_seconds = max(60, min(payload.get('duration', 3600), 86400))

                session['show_hidden'] = True
                session['show_hidden_timestamp'] = time.time()
                session['show_hidden_duration'] = duration_seconds
                session.modified = True

                admin_session_id = get_request_session_id()
                logger.info(
                    "Admin %s enabled show_hidden for %ss",
                    admin_session_id,
                    duration_seconds,
                )

                self._emit_category_refresh_to_session(
                    admin_session_id,
                    {
                        'reason': 'show_hidden_enabled',
                        'duration_seconds': duration_seconds,
                        'session_only': True,
                        'show_hidden': True,
                    },
                )

                return {
                    'success': True,
                    'message': f'Hidden categories revealed for {duration_seconds} seconds',
                }
            except Exception as exc:
                logger.error("Error showing hidden categories: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/categories/unhide', methods=['POST'])
        @admin_required
        def unhide_categories():
            """Unhide one category or all hidden categories."""
            try:
                from app.services.media.hidden_content_service import (
                    get_all_child_category_ids,
                    unhide_all_categories as hidden_unhide_all,
                    unhide_category as hidden_unhide_category,
                )
                from app.services.media.category_cache_service import (
                    invalidate_cache,
                    update_cached_category,
                )

                payload = self.schema('unhide_category').require(
                    request.get_json(silent=True) or {},
                )
                category_id = payload.get('category_id')
                children = []

                if category_id:
                    children = get_all_child_category_ids(category_id)
                    success, message = hidden_unhide_category(
                        category_id,
                        cascade=True,
                    )
                else:
                    success, message = hidden_unhide_all()

                if not success:
                    return {'success': False, 'error': message}, 500

                if category_id:
                    update_cached_category(category_id)
                    for child in children:
                        update_cached_category(child)
                else:
                    invalidate_cache()

                registry.require('library_events').emit_category_updated(
                    {
                        'reason': 'category_unhidden',
                        'category_id': category_id if category_id else None,
                        'unhide_all': category_id is None,
                    },
                )

                admin_session_id = get_request_session_id()
                logger.info(
                    "Admin %s unhid category: %s",
                    admin_session_id,
                    category_id or 'ALL',
                )
                return {'success': True, 'message': message}
            except Exception as exc:
                logger.error("Error unhiding categories: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/files/hide', methods=['POST'])
        @admin_required
        def hide_file():
            """Hide an individual file."""
            try:
                from app.services.media.hidden_content_service import hide_file as hidden_hide_file

                payload = self.schema('file_visibility').require(expect_json())
                file_path = payload['file_path']
                category_id = payload.get('category_id') or self._resolve_file_category_id(
                    file_path,
                )
                admin_session_id = get_request_session_id()

                success, message = hidden_hide_file(file_path, category_id, admin_session_id)
                if not success:
                    return {'success': False, 'error': message}, 500

                self._refresh_category_cache(category_id)
                self._emit_visibility_change({
                    'type': 'file_hidden',
                    'file_path': file_path,
                    'category_id': category_id,
                })

                logger.info("Admin %s hid file: %s", admin_session_id, file_path)
                return {'success': True, 'message': message}
            except Exception as exc:
                logger.error("Error hiding file: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/files/unhide', methods=['POST'])
        @admin_required
        def unhide_file():
            """Unhide an individual file."""
            try:
                from app.services.media.hidden_content_service import (
                    unhide_category as hidden_unhide_category,
                    unhide_file as hidden_unhide_file,
                )

                payload = self.schema('file_visibility').require(expect_json())
                file_path = payload['file_path']
                category_id = payload.get('category_id')

                success, message = hidden_unhide_file(file_path)
                if not success:
                    return {'success': False, 'error': message}, 500

                if category_id:
                    cat_success, _cat_message = hidden_unhide_category(
                        category_id,
                        cascade=False,
                    )
                    if cat_success:
                        message = f"{message} Parent category unhidden."

                self._refresh_category_cache(category_id)
                self._emit_visibility_change({
                    'type': 'file_unhidden',
                    'file_path': file_path,
                })

                admin_session_id = get_request_session_id()
                logger.info("Admin %s unhid file: %s", admin_session_id, file_path)
                return {'success': True, 'message': message}
            except Exception as exc:
                logger.error("Error unhiding file: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/media/action', methods=['POST'])
        @admin_required
        def media_quick_action():
            """Perform rename/hide/unhide/delete on a media item via rel_path."""
            try:
                from app.services.storage import storage_path_service
                from app.services.storage import storage_media_file_service
                from app.services.media.hidden_content_service import (
                    hide_file as hidden_hide_file,
                    unhide_file as hidden_unhide_file,
                )
                from app.services.media.category_query_service import get_category_by_id

                payload = self.schema('media_action').require(expect_json())
                category_id = payload['category_id']
                rel_path = payload['rel_path']
                action = payload['action']

                category = get_category_by_id(category_id)
                if not category or not category.get('path'):
                    return {'success': False, 'error': 'Category not found'}, 404

                file_path = self._resolve_rel_media_path(category['path'], rel_path)
                if not file_path:
                    return {'success': False, 'error': 'Invalid rel_path'}, 400

                admin_session_id = get_request_session_id()

                if action == 'delete':
                    parent_folder = os.path.dirname(file_path)
                    filename = os.path.basename(file_path)
                    success, message = storage_media_file_service.delete_file(file_path)
                    if not success:
                        return {'success': False, 'error': message}, 400

                    self._emit_visibility_change({
                        'type': 'file_deleted',
                        'file_path': file_path,
                        'filename': filename,
                        'folder': parent_folder,
                    })
                    self._refresh_category_cache(category_id)
                    return {'success': True, 'message': message}

                if action == 'rename':
                    new_name = (payload.get('new_name') or '').strip()
                    if not new_name:
                        return {
                            'success': False,
                            'error': 'new_name is required for rename',
                        }, 400

                    success, message, new_path = storage_media_file_service.rename_file(
                        file_path,
                        new_name,
                    )
                    if not success:
                        return {'success': False, 'error': message}, 400

                    old_url = storage_path_service.get_media_url_from_path(file_path)
                    new_url = (
                        storage_path_service.get_media_url_from_path(new_path)
                        if new_path else None
                    )
                    if old_url and new_url:
                        registry.require('storage_events').emit_file_renamed(
                            {'old_path': old_url, 'new_path': new_url},
                            broadcast=True,
                        )
                    self._refresh_category_cache(category_id)
                    return {
                        'success': True,
                        'message': message,
                        'new_path': new_path,
                        'new_name': os.path.basename(new_path) if new_path else None,
                        'new_url': new_url,
                    }

                if action == 'hide':
                    success, message = hidden_hide_file(
                        file_path,
                        category_id,
                        admin_session_id,
                    )
                    if not success:
                        return {'success': False, 'error': message}, 500
                    self._refresh_category_cache(category_id)
                    self._emit_visibility_change({
                        'type': 'file_hidden',
                        'file_path': file_path,
                        'category_id': category_id,
                    })
                    logger.info(
                        "Admin %s hid file via quick action: %s",
                        admin_session_id,
                        file_path,
                    )
                    return {'success': True, 'message': message}

                success, message = hidden_unhide_file(file_path)
                if not success:
                    return {'success': False, 'error': message}, 500
                self._refresh_category_cache(category_id)
                self._emit_visibility_change({
                    'type': 'file_unhidden',
                    'file_path': file_path,
                })
                logger.info(
                    "Admin %s unhid file via quick action: %s",
                    admin_session_id,
                    file_path,
                )
                return {'success': True, 'message': message}
            except Exception as exc:
                logger.error("Error in media_quick_action: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/categories/show-status', methods=['GET'])
        def get_show_hidden_status():
            """Get current show_hidden session status."""
            try:
                if not is_current_admin_session():
                    return {
                        'active': False,
                        'remaining_seconds': 0,
                        'reason': 'not_admin',
                    }

                show_hidden = session.get('show_hidden', False)
                if not show_hidden:
                    return {
                        'active': False,
                        'remaining_seconds': 0,
                        'reason': 'not_set',
                    }

                timestamp = session.get('show_hidden_timestamp', 0)
                duration = session.get('show_hidden_duration', 3600)
                elapsed = time.time() - timestamp
                remaining = max(0, duration - elapsed)

                if remaining <= 0:
                    session.pop('show_hidden', None)
                    session.pop('show_hidden_timestamp', None)
                    session.pop('show_hidden_duration', None)
                    session.modified = True
                    return {
                        'active': False,
                        'remaining_seconds': 0,
                        'reason': 'expired',
                    }

                return {
                    'active': True,
                    'remaining_seconds': int(remaining),
                    'duration': duration,
                }
            except Exception as exc:
                logger.error("Error getting show_hidden status: %s", exc)
                return {
                    'active': False,
                    'remaining_seconds': 0,
                    'error': str(exc),
                }, 500

        @router.route('/categories/clear-session', methods=['POST'])
        def clear_hidden_session():
            """Clear the current admin session's show_hidden flag."""
            try:
                session.pop('show_hidden', None)
                session.pop('show_hidden_timestamp', None)
                session.pop('show_hidden_duration', None)
                session.modified = True

                admin_session_id = get_request_session_id()
                logger.info("Cleared show_hidden session for: %s", admin_session_id)

                self._emit_category_refresh_to_session(
                    admin_session_id,
                    {
                        'reason': 'show_hidden_disabled',
                        'session_only': True,
                        'show_hidden': False,
                    },
                )

                return {'success': True}
            except Exception as exc:
                logger.error("Error clearing hidden session: %s", exc)
                return {'success': False, 'error': str(exc)}, 500

        @router.route('/categories/hidden', methods=['GET'])
        @admin_required
        def get_hidden_categories():
            """Get all hidden categories with metadata."""
            try:
                from app.services.media.hidden_content_service import (
                    get_hidden_categories_with_details,
                )
                from app.services.media.category_query_service import get_all_categories_with_details

                hidden_items = get_hidden_categories_with_details()
                all_categories = {
                    category['id']: category
                    for category in get_all_categories_with_details(
                        show_hidden=True,
                    )
                }

                enriched_items = []
                for item in hidden_items:
                    category = all_categories.get(item['category_id'])
                    enriched_items.append({
                        'category_id': item['category_id'],
                        'category_name': (
                            category['name']
                            if category else item['category_id']
                        ),
                        'hidden_at': item['hidden_at'],
                        'hidden_by': item['hidden_by'],
                    })

                return {'hidden_categories': enriched_items}
            except Exception as exc:
                logger.error("Error getting hidden categories: %s", exc)
                return {'error': str(exc)}, 500

    def _normalize_category_id(self, category_id):
        if category_id and str(category_id).startswith('auto-'):
            return "auto::" + str(category_id)[5:].replace('-', '::')
        return category_id

    def _emit_category_refresh_to_session(self, session_id, payload):
        for sid in session_store.list_session_sids(session_id):
            registry.require('library_events').emit_category_updated(payload, room=sid)

    def _emit_visibility_change(self, payload):
        registry.require('storage_events').emit_content_visibility_changed(payload)

    def _refresh_category_cache(self, category_id=None):
        from app.services.media.category_cache_service import (
            invalidate_cache,
            update_cached_category,
        )

        if category_id:
            update_cached_category(category_id)
        else:
            invalidate_cache()

    def _resolve_file_category_id(self, file_path):
        from app.services.media.category_query_service import get_all_categories_with_details

        categories = get_all_categories_with_details(use_cache=True)
        best_match = None
        max_len = 0
        normalized_file_path = os.path.normpath(str(file_path))

        for category in categories:
            category_path = category.get('path')
            if not category_path:
                continue
            normalized_category_path = os.path.normpath(category_path)
            if normalized_file_path.startswith(normalized_category_path):
                if len(normalized_category_path) > max_len:
                    max_len = len(normalized_category_path)
                    best_match = category['id']

        return best_match

    def _resolve_rel_media_path(self, category_root, rel_path):
        if not isinstance(rel_path, str) or not rel_path.strip():
            return None
        if os.path.isabs(rel_path):
            return None

        category_root = os.path.realpath(category_root)
        file_path = os.path.realpath(os.path.join(category_root, rel_path))
        if os.path.commonpath([category_root, file_path]) != category_root:
            return None
        return file_path
