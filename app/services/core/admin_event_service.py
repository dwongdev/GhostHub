"""Admin-domain socket event service."""

import logging

from app.constants import SOCKET_EVENTS as SE
from specter import Service, registry

logger = logging.getLogger(__name__)


class AdminEventService(Service):
    """Own admin-domain Socket.IO event emission."""

    def __init__(self):
        super().__init__('admin_events')

    def emit_status_update(self, claimed):
        return self._emit(
            SE['ADMIN_STATUS_UPDATE'],
            {'roleClaimedByAnyone': claimed},
        )

    def emit_kick_confirmation(self, payload, *, room=None):
        return self._emit(SE['ADMIN_KICK_CONFIRMATION'], payload, room=room)

    def emit_kicked(self, payload, *, room=None):
        return self._emit(SE['YOU_HAVE_BEEN_KICKED'], payload, room=room)

    @staticmethod
    def _socketio():
        manager = registry.require('service_manager')
        return manager.socketio

    def _emit(self, event_name, payload, **kwargs):
        try:
            self._socketio().emit(event_name, payload, **kwargs)
            return True
        except Exception as exc:
            logger.warning("Failed to emit admin event %s: %s", event_name, exc)
            return False
