"""Sync domain controller built on Specter."""

import logging
import time

from flask import request
from werkzeug.exceptions import BadRequest

from specter import Controller, registry
from app.constants import ERROR_MESSAGES, SOCKET_EVENTS as SE, SYNC_ROOM
from app.services.core import session_store, tv_store
from app.utils.auth import get_request_session_id

logger = logging.getLogger(__name__)

SESSION_STATE_EXPIRY = 3600
MAX_SESSION_STATES = 200
MAX_SYNC_CATEGORY_ORDERS = 200
SYNC_ORDER_EXPIRY = 7200


class SyncController(Controller):
    """Composition root for synchronous media casting."""

    name = 'sync'
    url_prefix = '/api/sync'

    @staticmethod
    def _events():
        return registry.require('sync_events')

    @staticmethod
    def _transport():
        return registry.require('socket_transport')

    def on_start(self):
        """Initialize gevent-safe store for sync state."""
        self.store = self.create_store('sync_state', {
            'enabled': False,
            'host_session_id': None,
            'current_media': {
                'category_id': None,
                'file_url': None,
                'index': 0,
                'timestamp': time.time(),
            },
            'playback_state': {
                'is_playing': False,
                'current_time': 0,
                'last_update': time.time(),
            },
            'session_orders': {},
            'order_timestamps': {},
            'session_states': {},
        })

    def build_routes(self, router):
        """Register HTTP endpoints for sync administration."""
        @router.route('/status', methods=['GET'])
        def sync_status():
            return self.get_status()

        @router.route('/toggle', methods=['POST'])
        def toggle_sync_mode():
            data = request.get_json(silent=True) or {}
            enabled = data.get('enabled')
            if enabled is None or not isinstance(enabled, bool):
                raise BadRequest("Invalid request data: 'enabled' (boolean) is required")

            return self.toggle_sync(
                enable=enabled,
                initial_media=data.get('media'),
                session_id=data.get('session_id')
            )

        @router.route('/current', methods=['GET'])
        def get_current_media_route():
            state = self.get_current_media()
            if "error" in state:
                return state, 400
            return state

        @router.route('/update', methods=['POST'])
        def update_current_media_route():
            data = request.get_json(silent=True) or {}
            category_id = data.get('category_id')
            file_url = data.get('file_url')
            index = data.get('index')

            if category_id is None or file_url is None or index is None:
                raise BadRequest("Invalid update data: 'category_id', 'file_url', and 'index' are required")

            try:
                index = int(index)
            except (ValueError, TypeError):
                raise BadRequest("Invalid update data: 'index' must be an integer")

            success, error = self.update_current_media(category_id, file_url, index)
            if not success:
                status_code = 403 if "host" in (error or "") else 400
                return {"error": error}, status_code

            session_id = request.cookies.get('session_id')
            if session_id:
                self.update_session_state(session_id, category_id, index)

            return {"success": True}

    def build_events(self, handler):
        """Register Socket.IO event handlers."""
        handler.on(SE['JOIN_SYNC'], self.handle_join_sync)
        handler.on(SE['LEAVE_SYNC'], self.handle_leave_sync)
        handler.on(SE['SYNC_UPDATE'], self.handle_sync_update_ws)
        handler.on(SE['PLAYBACK_SYNC'], self.handle_playback_sync)
        handler.on(SE['UPDATE_MY_STATE'], self.handle_socket_state_update)
        handler.on(SE['REQUEST_VIEW_INFO'], self.handle_request_view_info)

    # ------------------------------------------------------------------
    # Socket Event Handlers
    # ------------------------------------------------------------------

    def handle_join_sync(self):
        client_id = request.sid
        session_id = get_request_session_id()
        
        if not self.is_sync_enabled():
            self._events().emit_sync_error(ERROR_MESSAGES['SYNC_NOT_ENABLED'], room=client_id)
            return {'status': 'error', 'message': ERROR_MESSAGES['SYNC_NOT_ENABLED']}

        self._transport().join_room(SYNC_ROOM, sid=client_id)
        logger.info("Client %s joined sync room.", client_id)

        current_state = self.get_current_media()
        self._events().emit_sync_state(current_state, room=client_id)
        
        self._events().emit_user_joined({'sid': client_id}, room=SYNC_ROOM, include_self=False)
        return {'status': 'ok'}

    def handle_leave_sync(self):
        client_id = request.sid
        self._transport().leave_room(SYNC_ROOM, sid=client_id)
        logger.info("Client %s left sync room.", client_id)
        self._events().emit_user_left({'sid': client_id}, room=SYNC_ROOM, include_self=False)
        return {'status': 'ok'}

    def handle_sync_update_ws(self, data):
        session_id = get_request_session_id()

        if not self.is_sync_enabled():
            return {'status': 'error', 'message': ERROR_MESSAGES['SYNC_NOT_ENABLED']}

        if session_id != self.get_host_session_id():
            return {'status': 'error', 'message': 'Only host can update sync state'}

        data = data or {}
        category_id = data.get('category_id')
        index = data.get('index')
        file_url = data.get('file_url')

        if category_id is None or index == -1:
            logger.info("Host exiting media viewer, broadcasting to all clients")
            self._events().emit_sync_state({
                'category_id': None, 'file_url': None, 'index': -1,
                'playback_state': self.get_playback_state_for_broadcast()
            }, room=SYNC_ROOM)
            return {'status': 'ok'}

        self.update_current_media(category_id, file_url, index)
        return {'status': 'ok'}

    def handle_playback_sync(self, data):
        client_id = request.sid
        session_id = get_request_session_id()

        if not self.is_sync_enabled():
            self._events().emit_sync_error('Sync mode is not active', room=client_id)
            return {'status': 'error', 'message': 'Sync mode is not active'}

        if session_id != self.get_host_session_id():
            return {'status': 'error', 'message': 'Only host can send playback sync'}

        data = data or {}
        action = data.get('action')
        current_time = data.get('currentTime', 0)
        timestamp = data.get('timestamp', time.time())
        is_playing = data.get('is_playing')

        if action not in ['play', 'pause', 'seek']:
            return {'status': 'error', 'message': 'Invalid playback action'}

        active_playing_state = is_playing if is_playing is not None else (action == 'play')
        self.update_playback_state(active_playing_state, current_time)

        relay_payload = {
            'action': action,
            'currentTime': current_time,
            'timestamp': timestamp,
        }
        if is_playing is not None:
            relay_payload['is_playing'] = is_playing
        if 'category_id' in data:
            relay_payload['category_id'] = data['category_id']
        if 'file_url' in data:
            relay_payload['file_url'] = data['file_url']
        if 'index' in data:
            relay_payload['index'] = data['index']

        self._events().emit_playback_sync(relay_payload, room=SYNC_ROOM, include_self=False)
        return {'status': 'ok'}

    def handle_socket_state_update(self, data):
        """Persist a client's latest browsing state for sync/view sharing."""
        try:
            client_id = request.sid
            session_id = get_request_session_id()
            is_tv = client_id == tv_store.get_tv_sid()

            if not session_id and not is_tv:
                logger.warning(
                    "Client %s tried to update state without session ID.",
                    client_id,
                )
                return

            if not data or 'category_id' not in data or 'index' not in data:
                logger.warning(
                    "Invalid state update data from %s (client %s): Missing fields - %s",
                    session_id,
                    client_id,
                    data,
                )
                return

            category_id = data['category_id']
            index = data['index']
            media_order = data.get('media_order')

            if not isinstance(category_id, str) or not category_id.strip():
                logger.warning(
                    "Invalid category_id in state update from %s: %s",
                    session_id,
                    category_id,
                )
                return

            try:
                index = int(index)
                if index < 0:
                    raise ValueError("Index cannot be negative")
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Invalid index in state update from %s: %s - %s",
                    session_id,
                    index,
                    exc,
                )
                return

            if media_order is not None:
                if (
                    not isinstance(media_order, list) or
                    not all(isinstance(url, str) for url in media_order)
                ):
                    client_identifier = 'TV' if is_tv else session_id
                    logger.warning(
                        "Invalid media_order format in state update from %s: %s",
                        client_identifier,
                        media_order,
                    )
                    media_order = None

            client_identifier = 'TV' if is_tv else session_id
            logger.debug(
                "Updating view state for %s: category=%s, index=%s",
                client_identifier,
                category_id,
                index,
            )

            success = True
            if session_id:
                success = self.update_session_state(
                    session_id,
                    category_id,
                    index,
                    media_order,
                )

            if not success:
                logger.error(
                    "Failed to update session state for session %s",
                    session_id,
                )
                self._transport().emit_to_sid(
                    SE['CHAT_ERROR'],
                    {'message': 'Failed to save your view state'},
                    client_id,
                )
                return

            logger.debug("Successfully updated state for %s", session_id)
        except Exception as exc:
            logger.error("Error handling state update: %s", exc)
            try:
                self._transport().emit_to_sid(
                    SE['CHAT_ERROR'],
                    {'message': 'Failed to update your view state'},
                    client_id,
                )
            except Exception:
                logger.debug("Failed to emit error to client")

    def handle_request_view_info(self, data):
        """Return a target session's current view state."""
        try:
            requesting_client_id = request.sid
            requesting_session_id = get_request_session_id() or 'unknown_requestor'

            if not data or 'target_session_id' not in data:
                logger.warning(
                    "Client %s (Session: %s) sent invalid request_view_info: %s",
                    requesting_client_id,
                    requesting_session_id,
                    data,
                )
                self._events().emit_view_info_response(
                    {'error': 'Invalid request. Missing target_session_id.'},
                    room=requesting_client_id,
                )
                return

            target_session_id = data['target_session_id']
            logger.info(
                "Client %s (Session: %s) requested view info for target session: %s",
                requesting_client_id,
                requesting_session_id,
                target_session_id,
            )

            target_state = self.get_session_state(target_session_id)
            if not target_state:
                logger.info("No state found for target session %s", target_session_id)
                self._events().emit_view_info_response(
                    {
                        'error': (
                            f'Could not find view information for session {target_session_id}. '
                            'User might not be active or sharing.'
                        ),
                    },
                    room=requesting_client_id,
                )
                return

            logger.info(
                "Found state for target session %s: %s",
                target_session_id,
                target_state,
            )

            if 'category_id' not in target_state or 'index' not in target_state:
                logger.warning(
                    "Incomplete state for target session %s: %s",
                    target_session_id,
                    target_state,
                )
                self._events().emit_view_info_response(
                    {
                        'error': (
                            f'View information for session {target_session_id} is incomplete.'
                        ),
                    },
                    room=requesting_client_id,
                )
                return

            category_id = target_state.get('category_id')
            index = target_state.get('index')
            media_order = target_state.get('media_order')

            if (
                not media_order or
                not isinstance(media_order, list) or
                len(media_order) == 0
            ):
                try:
                    from urllib.parse import quote

                    resolved_id = target_state.get('resolved_session_id') or target_session_id
                    from app.services.media import media_session_service
                    filenames = media_session_service.get_session_order(category_id, resolved_id)
                    if filenames:
                        media_order = [
                            f"/media/{category_id}/{quote(name)}"
                            for name in filenames
                        ]
                except Exception as exc:
                    logger.warning(
                        "Could not derive media order for view request %s: %s",
                        target_session_id,
                        exc,
                    )

            if media_order and isinstance(media_order, list):
                if (
                    media_order and
                    isinstance(media_order[0], str) and
                    not media_order[0].startswith('/media/')
                ):
                    try:
                        from urllib.parse import quote

                        media_order = [
                            f"/media/{category_id}/{quote(name)}"
                            for name in media_order
                        ]
                    except Exception:
                        pass

            self._events().emit_view_info_response(
                {
                    'category_id': category_id,
                    'index': index,
                    'media_order': media_order,
                    'target_session_id': target_session_id,
                },
                room=requesting_client_id,
            )
        except Exception as exc:
            logger.error("Error handling request_view_info: %s", exc)
            try:
                self._events().emit_view_info_response(
                    {'error': 'Server error processing your request.'},
                    room=requesting_client_id,
                )
            except Exception:
                logger.debug("Failed to emit error to client")

    # ------------------------------------------------------------------
    # Core Service Logic
    # ------------------------------------------------------------------

    def get_session_id(self):
        """Public alias for backward compatibility with external calls."""
        return get_request_session_id()

    def get_status(self):
        state = self.store.get()
        session_id = get_request_session_id()
        is_host = state['enabled'] and session_id == state['host_session_id']
        return {"active": state['enabled'], "is_host": is_host}

    def toggle_sync(self, enable, initial_media=None, session_id=None):
        if not session_id:
            session_id = get_request_session_id()
        elif session_id.startswith('"'):
            session_id = session_id[1:-1]

        if not session_id:
            logger.error("Cannot toggle sync mode: Session ID missing.")
            return self.get_status()

        action = {'type': None, 'data': None}

        def _toggle(draft):
            host_session_id = draft['host_session_id']
            host_active = False
            if host_session_id:
                host_active = session_store.get_connection(host_session_id) is not None

            should_initialize = False
            if enable:
                if not draft['enabled'] or not host_active or host_session_id == session_id:
                    should_initialize = True

            if should_initialize:
                draft['enabled'] = True
                draft['host_session_id'] = session_id

                if initial_media and all(k in initial_media for k in ["category_id", "file_url", "index"]):
                    new_media = {
                        "category_id": initial_media.get("category_id"),
                        "file_url": initial_media.get("file_url"),
                        "index": initial_media.get("index", 0),
                        "timestamp": time.time(),
                    }
                    draft['current_media'] = new_media
                    cat_id = initial_media.get("category_id")
                    if cat_id:
                        from app.services.media import media_session_service
                        host_order = media_session_service.get_session_order(cat_id, session_id)
                        if host_order:
                            draft['session_orders'][cat_id] = host_order
                            draft['order_timestamps'][cat_id] = time.time()
                else:
                    draft['current_media'] = {
                        "category_id": None, "file_url": None, "index": 0, "timestamp": time.time()
                    }

                action['type'] = 'enabled'
                action['data'] = {
                    "active": True,
                    "host_session_id": session_id,
                    "media": draft['current_media'].copy(),
                }

            elif not enable and draft['enabled']:
                if session_id != host_session_id:
                    action['type'] = 'early_return'
                    return

                draft['enabled'] = False
                draft['host_session_id'] = None
                draft['current_media'] = {
                    "category_id": None, "file_url": None, "index": 0, "timestamp": time.time()
                }
                draft['session_orders'].clear()
                draft['order_timestamps'].clear()
                draft['session_states'].clear()
                action['type'] = 'disabled'

        self.store.update(_toggle)

        if action['type'] == 'early_return':
            return self.get_status()
        elif action['type'] == 'enabled':
            self._events().emit_sync_enabled(action['data'])
        elif action['type'] == 'disabled':
            self._events().emit_sync_disabled({"active": False})

        return self.get_status()

    def get_current_media(self):
        state = self.store.get()
        if not state['enabled']:
            return {"error": "Sync mode not enabled"}
        
        result = state['current_media'].copy()
        result["playback_state"] = state['playback_state'].copy()
        return result

    def update_playback_state(self, is_playing, current_time):
        session_id = get_request_session_id()
        result = [False]

        def _update(draft):
            if not draft['enabled'] or session_id != draft['host_session_id']:
                return
            draft['playback_state'] = {
                "is_playing": is_playing,
                "current_time": current_time,
                "last_update": time.time(),
            }
            result[0] = True

        self.store.update(_update)
        return result[0]

    def update_current_media(self, category_id, file_url, index):
        session_id = get_request_session_id()
        result = {'ok': False, 'error': None, 'emit': None}

        def _update(draft):
            if not draft['enabled']:
                result['error'] = "Sync mode not enabled"
                return
            if session_id != draft['host_session_id']:
                result['error'] = "Only the host can update the current media"
                return

            if draft['current_media'].get('category_id') != category_id:
                from app.services.media import media_session_service
                host_order = media_session_service.get_session_order(category_id, session_id)
                if host_order:
                    draft['session_orders'][category_id] = host_order
                    draft['order_timestamps'][category_id] = time.time()
                    self._prune_sync_orders_locked(draft)

            draft['current_media'] = {
                "category_id": category_id,
                "file_url": file_url,
                "index": index,
                "timestamp": time.time(),
            }
            result['ok'] = True
            result['emit'] = draft['current_media'].copy()

        self.store.update(_update)

        if result['error']:
            return False, result['error']
        if result['emit']:
            self._events().emit_sync_state(result['emit'], room=SYNC_ROOM)
        return True, None

    def is_sync_enabled(self):
        return self.store.get()['enabled']

    def get_host_session_id(self):
        return self.store.get()['host_session_id']

    def get_sync_order(self, category_id):
        result = [None]

        def _update(draft):
            self._prune_sync_orders_locked(draft)
            order = draft['session_orders'].get(category_id)
            if order:
                result[0] = order.copy()

        self.store.update(_update)
        return result[0]

    def update_session_state(self, session_id, category_id, index, media_order=None):
        if not session_id:
            return False

        def _update(draft):
            nonlocal media_order
            existing_state = draft['session_states'].get(session_id, {})
            if media_order is None and existing_state.get('category_id') == category_id:
                media_order = existing_state.get('media_order')

            self._prune_session_states_locked(draft)

            draft['session_states'][session_id] = {
                "category_id": category_id,
                "index": index,
                "media_order": media_order,
                "timestamp": time.time(),
            }

        self.store.update(_update)
        return True

    def get_session_state(self, session_id_or_prefix):
        result = [None]

        def _update(draft):
            self._prune_session_states_locked(draft)

            # Exact session ID match
            s = draft['session_states'].get(session_id_or_prefix)
            if s:
                result[0] = s.copy()
                return

            # Prefix match on session IDs
            if len(session_id_or_prefix) < 16:
                for full_id, sd in draft['session_states'].items():
                    if full_id.startswith(session_id_or_prefix):
                        resolved = sd.copy()
                        resolved['resolved_session_id'] = full_id
                        result[0] = resolved
                        return

            # Profile name / user_id resolution — look up the active
            # connection that matches the given name, then check if that
            # session has a stored view state.
            resolved_sid, _ = session_store.find_connection_by_user_id(
                session_id_or_prefix,
            )
            if resolved_sid:
                s = draft['session_states'].get(resolved_sid)
                if s:
                    resolved = s.copy()
                    resolved['resolved_session_id'] = resolved_sid
                    result[0] = resolved

        self.store.update(_update)
        return result[0]

    def remove_session_state(self, session_id):
        def _update(draft):
            if session_id in draft['session_states']:
                del draft['session_states'][session_id]

        self.store.update(_update)

    def get_playback_state_for_broadcast(self):
        return self.store.get()['playback_state'].copy()

    # ------------------------------------------------------------------
    # Garbage Collection Helpers
    # ------------------------------------------------------------------

    def _prune_session_states_locked(self, state, now=None):
        if now is None:
            now = time.time()

        stale = [sid for sid, sd in state['session_states'].items() if now - sd.get('timestamp', 0) > SESSION_STATE_EXPIRY]
        for sid in stale:
            del state['session_states'][sid]

        while len(state['session_states']) > MAX_SESSION_STATES:
            oldest = min(state['session_states'].items(), key=lambda x: x[1].get('timestamp', 0))[0]
            del state['session_states'][oldest]

    def _prune_sync_orders_locked(self, state, now=None):
        if now is None:
            now = time.time()

        stale = [cid for cid, ts in state['order_timestamps'].items() if now - ts > SYNC_ORDER_EXPIRY]
        for cid in stale:
            del state['order_timestamps'][cid]
            del state['session_orders'][cid]

        while len(state['session_orders']) > MAX_SYNC_CATEGORY_ORDERS:
            oldest = min(state['order_timestamps'].items(), key=lambda x: x[1])[0]
            del state['order_timestamps'][oldest]
            del state['session_orders'][oldest]
