"""Specter-owned socket transport controls for rooms and disconnects."""

import logging

from specter import Service, registry

logger = logging.getLogger(__name__)


class SocketTransportService(Service):
    """Own low-level Socket.IO room membership and disconnect operations."""

    def __init__(self):
        super().__init__('socket_transport')

    @staticmethod
    def _socketio():
        manager = registry.require('service_manager')
        return manager.socketio

    def emit(self, event_name, payload, **kwargs):
        """Emit a Socket.IO event with centralized logging/failure handling."""
        try:
            self._socketio().emit(event_name, payload, **kwargs)
            return True
        except Exception as exc:
            logger.warning(
                "Failed to emit socket transport event %s: %s",
                event_name,
                exc,
            )
            return False

    def emit_to_sid(self, event_name, payload, sid, **kwargs):
        """Emit a Socket.IO event directly to a socket SID."""
        return self.emit(event_name, payload, room=sid, **kwargs)

    def join_room(self, room, *, sid, namespace='/'):
        """Add a socket SID to a named room."""
        try:
            self._socketio().server.enter_room(sid, room, namespace=namespace)
            return True
        except Exception as exc:
            logger.warning(
                "Failed to join room %s for sid %s: %s",
                room,
                sid,
                exc,
            )
            return False

    def leave_room(self, room, *, sid, namespace='/'):
        """Remove a socket SID from a named room."""
        try:
            self._socketio().server.leave_room(sid, room, namespace=namespace)
            return True
        except Exception as exc:
            logger.warning(
                "Failed to leave room %s for sid %s: %s",
                room,
                sid,
                exc,
            )
            return False

    def disconnect(self, sid, *, namespace='/'):
        """Disconnect a socket SID from the active namespace."""
        try:
            self._socketio().server.disconnect(sid, namespace=namespace)
            return True
        except Exception as exc:
            logger.warning("Failed to disconnect sid %s: %s", sid, exc)
            return False
