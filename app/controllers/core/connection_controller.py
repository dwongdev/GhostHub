"""Global socket connection lifecycle controller built on Specter."""

import logging

import gevent
from gevent.lock import BoundedSemaphore
from flask import request, session as flask_session

from app.constants import SOCKET_EVENTS as SE, TV_EVENTS
from app.services.core import profile_service, session_store
from specter import Controller, registry
from specter.core.controller import _ControllerHandler
from app.utils.auth import (
    get_admin_session_id,
    get_request_session_id,
    is_current_admin_session_with_flag_sync,
)

logger = logging.getLogger(__name__)


class _ConnectionControllerHandler(_ControllerHandler):
    """Controller-backed handler with default socket error subscription."""

    def on_setup(self):
        ingress = registry.resolve('socket_ingress')
        if ingress is not None:
            ingress.subscribe_error_default(
                self._controller.handle_default_error,
                owner=self,
            )
        elif self._socketio is not None:
            self._socketio.on_error_default(self._controller.handle_default_error)


class ConnectionController(Controller):
    """Own connect/disconnect bookkeeping and default error policy."""

    name = 'connection'

    def __init__(self):
        super().__init__()
        self._client_connection_stats = {}
        self._client_stats_lock = BoundedSemaphore(1)

    @staticmethod
    def _transport():
        return registry.require('socket_transport')

    def create_handler(self):
        if self._handler_instance is not None:
            return self._handler_instance

        handler = _ConnectionControllerHandler(
            name=f'{self.name}_events',
            controller=self,
        )
        self.build_events(handler)
        self._handler_instance = handler
        self.own(handler)
        return handler

    def build_events(self, handler):
        handler.on(SE['CONNECT'], self.handle_connect)
        handler.on(SE['DISCONNECT'], self.handle_disconnect)

    def handle_connect(self, auth=None):
        """Initialize connection state and announce current TV status."""
        del auth
        client_id = request.sid
        client_ip = request.remote_addr
        session_id = get_request_session_id()

        if session_store.is_blocked(client_ip):
            logger.warning(
                "Blocked IP %s (Client SID: %s) attempted WebSocket connection. Disconnecting.",
                client_ip,
                client_id,
            )
            self._transport().emit_to_sid(
                SE['YOU_HAVE_BEEN_KICKED'],
                {
                    'message': 'Your IP has been temporarily blocked from this session.',
                },
                client_id,
            )
            self._transport().disconnect(client_id)
            return

        try:
            logger.info(
                "Client connected: %s (IP: %s, Session: %s)",
                client_id,
                client_ip,
                session_id,
            )

            session_store.ensure_admin_release_timers()
            if session_id:
                profile_id = flask_session.get('active_profile_id')
                profile = profile_service.get_profile(profile_id) if profile_id else None
                if profile_id and not profile:
                    flask_session.pop('active_profile_id', None)
                    flask_session.modified = True

                session_store.connect_client(
                    session_id,
                    client_id,
                    client_ip,
                    profile_id=profile.get('id') if profile else None,
                    profile_name=profile.get('name') if profile else None,
                )
                entry = session_store.get_connection(session_id)
                logger.info(
                    "Added to active_connections: %s -> SID count: %s",
                    session_id,
                    len(entry.get('sids', set())) if entry else 0,
                )
                try:
                    session_store.cancel_admin_release_timer(session_id)
                except Exception as exc:
                    logger.error(
                        "Error checking/canceling admin release timer for %s: %s",
                        session_id,
                        exc,
                    )
            else:
                logger.warning("Client %s connected without a session_id cookie.", client_id)

            with self._client_stats_lock:
                self._client_connection_stats[client_id] = {
                    'connect_count': 1,
                    'error_count': 0,
                    'last_error': None,
                }

            tv_controller = registry.require('tv')
            registry.require('tv_events').emit_status_update(
                tv_controller.get_connection_status_payload(),
                room=client_id,
            )

            if is_current_admin_session_with_flag_sync():
                self._transport().join_room('admin', sid=client_id)
                logger.info("Admin client %s joined admin room", client_id)
        except Exception as exc:
            logger.error(
                "Error during client connection for %s (IP: %s): %s",
                client_id,
                client_ip,
                exc,
            )

    def handle_disconnect(self, reason=None):
        """Tear down connection state and release cross-domain runtime state if needed."""
        client_id = request.sid
        session_id = get_request_session_id()

        log_message = f"Client disconnected: {client_id} (Session: {session_id})"
        if reason:
            log_message += f" (Reason: {reason})"
        logger.info(log_message)

        try:
            with self._client_stats_lock:
                self._client_connection_stats.pop(client_id, None)

            if not session_id:
                session_id = session_store.resolve_session_for_sid(client_id)

            cleaned_session = session_store.disconnect_client(
                client_id,
                flask_session_id=session_id,
            )

            if cleaned_session:
                registry.require('sync').remove_session_state(cleaned_session)

            admin_id = get_admin_session_id()
            is_admin = session_id and admin_id is not None and admin_id == session_id
            if is_admin:
                logger.info(
                    "Admin session %s disconnected. Admin role is persistent and will not be auto-released.",
                    session_id,
                )

            registry.require('tv').handle_tv_disconnect(client_id)
        except Exception as exc:
            logger.error(
                "Error during client disconnection for %s (Session: %s): %s",
                client_id,
                session_id,
                exc,
            )

    def handle_default_error(self, exc):
        """Track socket errors and disconnect noisy clients."""
        try:
            client_id = request.sid
            logger.error("SocketIO error for client %s: %s", client_id, exc)

            should_disconnect = False
            with self._client_stats_lock:
                if client_id in self._client_connection_stats:
                    self._client_connection_stats[client_id]['error_count'] += 1
                    self._client_connection_stats[client_id]['last_error'] = str(exc)
                    if self._client_connection_stats[client_id]['error_count'] > 5:
                        should_disconnect = True

            if should_disconnect:
                logger.warning("Too many errors for client %s, disconnecting", client_id)
                self._transport().emit_to_sid(
                    SE['CONNECTION_ERROR'],
                    {'message': 'Too many errors, disconnecting'},
                    client_id,
                )
                gevent.sleep(0.1)
                self._transport().disconnect(client_id)
        except Exception as nested_exc:
            logger.error("Error in error handler: %s", nested_exc)
