"""Library/media event service for shared Socket.IO broadcasts."""

import logging

from app.constants import SOCKET_EVENTS as SE
from specter import Service, registry

logger = logging.getLogger(__name__)


class LibraryEventService(Service):
    """Own library/category update broadcasts."""

    def __init__(self):
        super().__init__('library_events')

    def emit_category_updated(self, payload, **kwargs):
        return self._emit(SE['CATEGORY_UPDATED'], payload, **kwargs)

    def emit_thumbnail_status_update(self, category_id, status, data=None, **kwargs):
        payload = {
            'categoryId': category_id,
            'status': status,
        }
        if data:
            payload.update(data)
        return self._emit(SE['THUMBNAIL_STATUS_UPDATE'], payload, **kwargs)

    @staticmethod
    def _socket_transport():
        return registry.require('socket_transport')

    def _emit(self, event_name, payload, **kwargs):
        return self._socket_transport().emit(event_name, payload, **kwargs)
