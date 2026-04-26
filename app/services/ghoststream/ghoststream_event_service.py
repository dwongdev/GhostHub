"""GhostStream domain event service for Socket.IO broadcasts."""

import logging

from app.constants import SOCKET_EVENTS as SE
from specter import Service, registry

logger = logging.getLogger(__name__)


class GhostStreamEventService(Service):
    """Own GhostStream progress and status emission."""

    def __init__(self):
        super().__init__('ghoststream_events')

    def emit_progress(self, payload, **kwargs):
        return self._emit(SE['GHOSTSTREAM_PROGRESS'], payload, **kwargs)

    def emit_status(self, payload, **kwargs):
        return self._emit(SE['GHOSTSTREAM_STATUS'], payload, **kwargs)

    @staticmethod
    def _socket_transport():
        return registry.require('socket_transport')

    def _emit(self, event_name, payload, **kwargs):
        return self._socket_transport().emit(event_name, payload, **kwargs)
