"""Sync domain event service for Socket.IO broadcasts."""

import logging

from app.constants import SOCKET_EVENTS as SE
from specter import Service, registry

logger = logging.getLogger(__name__)


class SyncEventService(Service):
    """Own sync-domain Socket.IO event emission."""

    def __init__(self):
        super().__init__('sync_events')

    def emit_sync_error(self, message, *, room=None):
        return self._emit(SE['SYNC_ERROR'], {'message': message}, room=room)

    def emit_sync_state(self, payload, **kwargs):
        return self._emit(SE['SYNC_STATE'], payload, **kwargs)

    def emit_user_joined(self, payload, **kwargs):
        return self._emit(SE['USER_JOINED'], payload, **kwargs)

    def emit_user_left(self, payload, **kwargs):
        return self._emit(SE['USER_LEFT'], payload, **kwargs)

    def emit_playback_sync(self, payload, **kwargs):
        return self._emit(SE['PLAYBACK_SYNC'], payload, **kwargs)

    def emit_view_info_response(self, payload, *, room=None):
        return self._emit(SE['VIEW_INFO_RESPONSE'], payload, room=room)

    def emit_sync_enabled(self, payload, **kwargs):
        return self._emit(SE['SYNC_ENABLED'], payload, **kwargs)

    def emit_sync_disabled(self, payload, **kwargs):
        return self._emit(SE['SYNC_DISABLED'], payload, **kwargs)

    @staticmethod
    def _socket_transport():
        return registry.require('socket_transport')

    def _emit(self, event_name, payload, **kwargs):
        return self._socket_transport().emit(event_name, payload, **kwargs)
