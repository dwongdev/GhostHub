"""Progress domain event service for Socket.IO broadcasts."""

import logging

from app.constants import SOCKET_EVENTS as SE
from specter import Service, registry

logger = logging.getLogger(__name__)


class ProgressEventService(Service):
    """Own progress-update broadcasts."""

    def __init__(self):
        super().__init__('progress_events')

    def emit_progress_update(self, payload, **kwargs):
        return self._emit(SE['PROGRESS_UPDATE'], payload, **kwargs)

    @staticmethod
    def _socket_transport():
        return registry.require('socket_transport')

    def _emit(self, event_name, payload, **kwargs):
        return self._socket_transport().emit(event_name, payload, **kwargs)
