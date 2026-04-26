"""Storage/content event service for Socket.IO broadcasts."""

import logging

from app.constants import SOCKET_EVENTS
from specter import Service, registry

logger = logging.getLogger(__name__)


class StorageEventService(Service):
    """Own storage/content visibility and file-update broadcasts."""

    def __init__(self):
        super().__init__('storage_events')

    def emit_content_visibility_changed(self, payload, **kwargs):
        return self._emit(SOCKET_EVENTS['CONTENT_VISIBILITY_CHANGED'], payload, **kwargs)

    def emit_usb_mounts_changed(self, payload=None, **kwargs):
        return self._emit(SOCKET_EVENTS['USB_MOUNTS_CHANGED'], payload or {}, **kwargs)

    def emit_file_renamed(self, payload, **kwargs):
        return self._emit(SOCKET_EVENTS['FILE_RENAMED'], payload, **kwargs)

    @staticmethod
    def _socket_transport():
        return registry.require('socket_transport')

    def _emit(self, event_name, payload, **kwargs):
        return self._socket_transport().emit(event_name, payload, **kwargs)
