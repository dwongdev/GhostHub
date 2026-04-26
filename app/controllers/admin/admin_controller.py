"""Admin runtime controller built on Specter."""

import logging

import gevent
from flask import request, session

from app.constants import SOCKET_EVENTS as SE
from app.services.core import session_store
from app.services.core.runtime_config_service import get_runtime_config_value
from specter import Controller, Field, HTTPError, Schema, expect_json, registry
from app.utils.auth import admin_required, get_request_session_id, is_current_admin_session_with_flag_sync

logger = logging.getLogger(__name__)


class AdminController(Controller):
    """Own admin auth/runtime routes and kick socket ingress."""

    name = 'admin'
    url_prefix = '/api/admin'

    schemas = {
        'claim_admin': Schema('admin.claim_admin', {
            'password': Field(str),
        }),
        'kick_user': Schema('admin.kick_user', {
            'user_sid': Field(str, required=True),
        }, strict=True),
        'socket_kick_user': Schema('admin.socket_kick_user', {
            'target_user_id': Field(
                str,
                required=True,
                validator=lambda value: 0 < len(value) <= 64,
            ),
        }, strict=True),
    }

    def _events(self):
        return registry.require('admin_events')

    def _transport(self):
        return registry.require('socket_transport')

    def build_routes(self, router):
        @router.route(
            '/claim',
            methods=['POST'],
            json_errors='Failed to claim admin role',
        )
        def claim_admin():
            payload = self.schema('claim_admin').require(
                request.get_json(silent=True) or {},
            )
            current_session_id = get_request_session_id()
            if not current_session_id:
                raise HTTPError(
                    'Session not found. Please refresh.',
                    status=400,
                    payload={
                        'success': False,
                        'isAdmin': False,
                        'message': 'Session not found. Please refresh.',
                    },
                )

            active_admin_session = session_store.get_admin_session_id()
            password = payload.get('password')
            admin_password = get_runtime_config_value('ADMIN_PASSWORD', 'admin')

            if (
                active_admin_session and
                active_admin_session != current_session_id
            ):
                if password == admin_password:
                    logger.info(
                        "Admin role reclaimed by session: %s",
                        current_session_id,
                    )
                elif password:
                    raise HTTPError(
                        'Incorrect admin password.',
                        status=401,
                        payload={
                            'success': False,
                            'isAdmin': False,
                            'message': 'Incorrect admin password.',
                        },
                    )
                else:
                    raise HTTPError(
                        'Admin role already claimed by another user.',
                        status=403,
                        payload={
                            'success': False,
                            'isAdmin': False,
                            'message': 'Admin role already claimed by another user.',
                        },
                    )

            session_store.set_admin_session_id(current_session_id)
            session['is_admin'] = True
            session.modified = True
            self._add_session_to_admin_room(current_session_id)
            self._events().emit_status_update(True)

            logger.info("Admin role claimed by session: %s", current_session_id)
            return {
                'success': True,
                'isAdmin': True,
                'message': (
                    'Admin role reclaimed successfully.'
                    if active_admin_session and active_admin_session != current_session_id
                    else 'Admin role claimed successfully.'
                ),
            }

        @router.route(
            '/status',
            methods=['GET'],
            json_errors='Failed to get admin status',
        )
        def admin_status():
            is_admin = is_current_admin_session_with_flag_sync()
            return {
                'isAdmin': is_admin,
                'roleClaimedByAnyone': bool(session_store.get_admin_session_id()),
            }

        @router.route(
            '/release',
            methods=['POST'],
            json_errors='Failed to release admin role',
        )
        @admin_required
        def release_admin():
            current_session_id = get_request_session_id()
            if not session_store.is_admin_session(current_session_id):
                raise HTTPError(
                    'You are not the current admin.',
                    status=400,
                    payload={
                        'success': False,
                        'message': 'You are not the current admin.',
                    },
                )

            session_store.set_admin_session_id(None)
            session['is_admin'] = False
            session.modified = True
            self._remove_session_from_admin_room(current_session_id)
            self._events().emit_status_update(False)

            logger.info("Admin role released by session: %s", current_session_id)
            return {'success': True, 'message': 'Admin role released.'}

        @router.route(
            '/users',
            methods=['GET'],
            json_errors='Failed to list admin users',
        )
        @admin_required
        def list_admin_users():
            users_list = []
            admin_session_id = session_store.get_admin_session_id()

            for flask_session_id, data in session_store.list_connections().items():
                socket_sid = data.get('sid')
                if not socket_sid:
                    session_sids = data.get('sids') or []
                    socket_sid = next(iter(session_sids), None)
                ip_address = data.get('ip', 'N/A')
                if ip_address in ('127.0.0.1', '::1', 'localhost'):
                    continue

                users_list.append({
                    'id': socket_sid,
                    'user_id': data.get('user_id', 'Unknown'),
                    'profile_name': data.get('profile_name'),
                    'session_id': flask_session_id,
                    'ip': ip_address,
                    'isAdmin': flask_session_id == admin_session_id,
                })

            logger.info(
                "Admin %s requested user list. Found %s users.",
                get_request_session_id(),
                len(users_list),
            )
            return users_list

        @router.route(
            '/kick_user',
            methods=['POST'],
            json_errors='Failed to kick user',
        )
        @admin_required
        def kick_admin_user():
            payload = self.schema('kick_user').require(expect_json())
            actor_session_id = get_request_session_id()
            actor_connection = session_store.get_connection(actor_session_id)
            if not actor_connection:
                raise HTTPError(
                    'Admin session not found or inactive. Cannot send kick confirmation.',
                    status=500,
                )

            target_sid = payload['user_sid']
            target_session_id = session_store.resolve_session_for_sid(target_sid)
            target_connection = session_store.get_connection(target_session_id)

            if not target_session_id or not target_connection:
                raise HTTPError(
                    'User not found or already disconnected.',
                    status=404,
                    payload={
                        'success': False,
                        'message': 'User not found or already disconnected.',
                    },
                )

            result = self._kick_target_session(
                actor_session_id=actor_session_id,
                target_session_id=target_session_id,
                target_connection=target_connection,
                kicked_user_sid=target_sid,
            )
            if not result.get('success'):
                status = 400
                if 'not found' in result.get('message', '').lower():
                    status = 404
                raise HTTPError(
                    result.get('message', 'Failed to kick user.'),
                    status=status,
                    payload=result,
                )
            for sid in session_store.list_session_sids(actor_session_id):
                self._events().emit_kick_confirmation(result, room=sid)
            return result

    def build_events(self, handler):
        handler.on(SE['ADMIN_KICK_USER'], self.handle_admin_kick_user)

    def handle_admin_kick_user(self, data):
        """Kick an active user and block their IP."""
        actor_session_id = get_request_session_id()
        actor_socket_sid = request.sid

        if not is_current_admin_session_with_flag_sync():
            return self._emit_socket_error(
                actor_socket_sid,
                'Error: You do not have permission to perform this action.',
            )

        payload = self.schema('socket_kick_user').validate(data or {})
        if not payload.ok:
            return self._emit_socket_error(
                actor_socket_sid,
                'Error: Invalid target user ID format.',
            )

        target_user_id = payload.value['target_user_id']
        target_session_id, target_connection = session_store.find_connection_by_user_id(
            target_user_id,
        )
        if not target_session_id or not target_connection:
            return self._emit_socket_error(
                actor_socket_sid,
                f"Error: User '{target_user_id}' not found or is not currently active.",
            )

        result = self._kick_target_session(
            actor_session_id=actor_session_id,
            target_session_id=target_session_id,
            target_connection=target_connection,
            kicked_user_sid=target_connection.get('sid'),
        )
        self._events().emit_kick_confirmation(result, room=actor_socket_sid)
        return result

    def _add_session_to_admin_room(self, session_id):
        for sid in session_store.list_session_sids(session_id):
            self._transport().join_room('admin', sid=sid, namespace='/')

    def _remove_session_from_admin_room(self, session_id):
        for sid in session_store.list_session_sids(session_id):
            try:
                self._transport().leave_room('admin', sid=sid, namespace='/')
            except Exception as exc:
                logger.warning(
                    "Failed to remove socket %s from admin room: %s",
                    sid,
                    exc,
                )

    def _emit_socket_error(self, actor_socket_sid, message):
        payload = {'success': False, 'message': message}
        self._events().emit_kick_confirmation(payload, room=actor_socket_sid)
        return payload

    def _kick_target_session(
        self,
        *,
        actor_session_id,
        target_session_id,
        target_connection,
        kicked_user_sid,
    ):
        if target_session_id == actor_session_id:
            return {
                'success': False,
                'message': 'Error: You cannot kick yourself.',
            }

        target_ip = target_connection.get('ip')
        target_sids = session_store.list_session_sids(target_session_id)
        if not target_sids:
            return {
                'success': False,
                'message': 'Error: User not found or already disconnected.',
            }

        if target_ip and target_ip != 'N/A':
            session_store.block_ip(target_ip)

        kick_message = (
            'You have been kicked from the session by an administrator. '
            'Your IP has been temporarily blocked.'
        )
        for target_sid in target_sids:
            self._events().emit_kicked(
                {'message': kick_message},
                room=target_sid,
            )

        gevent.sleep(0.1)
        for target_sid in target_sids:
            try:
                self._transport().disconnect(target_sid)
            except Exception as exc:
                logger.warning(
                    "Failed to disconnect kicked SID %s: %s",
                    target_sid,
                    exc,
                )

        logger.info(
            "Admin %s kicked session %s (sids=%s ip=%s)",
            actor_session_id,
            target_session_id,
            target_sids,
            target_ip,
        )

        message = (
            f"User '{target_connection.get('user_id', target_session_id[:8])}' "
            f"(IP: {target_ip}) has been kicked and their IP temporarily blocked."
        )
        return {
            'success': True,
            'message': message,
            'kicked_user_sid': kicked_user_sid,
        }
