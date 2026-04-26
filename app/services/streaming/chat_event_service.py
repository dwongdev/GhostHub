"""Chat-domain socket event service."""

import logging

from app.constants import SOCKET_EVENTS as SE
from specter import Service, registry

logger = logging.getLogger(__name__)


class ChatEventService(Service):
    """Own chat-domain Socket.IO event emission."""

    def __init__(self):
        super().__init__('chat_events')

    def emit_notification(self, payload, **kwargs):
        return self._emit(SE['CHAT_NOTIFICATION'], payload, **kwargs)

    def emit_message(self, payload, **kwargs):
        return self._emit(SE['CHAT_MESSAGE'], payload, **kwargs)

    def emit_command(self, payload, **kwargs):
        return self._emit(SE['COMMAND'], payload, **kwargs)

    def emit_error(self, message, *, room=None):
        return self._emit(SE['CHAT_ERROR'], {'message': message}, room=room)

    @staticmethod
    def _socketio():
        manager = registry.require('service_manager')
        return manager.socketio

    def _emit(self, event_name, payload, **kwargs):
        try:
            self._socketio().emit(event_name, payload, **kwargs)
            return True
        except Exception as exc:
            logger.warning("Failed to emit chat event %s: %s", event_name, exc)
            return False
