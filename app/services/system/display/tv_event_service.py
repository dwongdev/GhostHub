"""TV domain event service for Socket.IO broadcasts."""

import logging

from app.constants import TV_EVENTS
from specter import Service, registry

logger = logging.getLogger(__name__)


class TVEventService(Service):
    """Own TV-domain Socket.IO event emission."""

    def __init__(self):
        super().__init__('tv_events')

    def emit_status_update(self, payload, **kwargs):
        return self._emit(TV_EVENTS['TV_STATUS_UPDATE'], payload, **kwargs)

    def emit_error(self, message, *, room=None):
        return self._emit(TV_EVENTS['TV_ERROR'], {'message': message}, room=room)

    def emit_cast_success(self, message, *, room=None):
        return self._emit(TV_EVENTS['CAST_SUCCESS'], {'message': message}, room=room)

    def emit_display_media(self, payload, **kwargs):
        return self._emit(TV_EVENTS['DISPLAY_MEDIA_ON_TV'], payload, **kwargs)

    def emit_request_state(self, payload=None, **kwargs):
        return self._emit(TV_EVENTS['TV_REQUEST_STATE'], payload or {}, **kwargs)

    def emit_request_state_later(self, delay_seconds, payload=None, **kwargs):
        self.spawn_later(
            delay_seconds,
            self.emit_request_state,
            payload or {},
            **kwargs,
        )
        return True

    def emit_playback_control(self, payload, **kwargs):
        return self._emit(TV_EVENTS['TV_PLAYBACK_CONTROL'], payload, **kwargs)

    def emit_playback_state(self, payload, **kwargs):
        return self._emit(TV_EVENTS['TV_PLAYBACK_STATE'], payload, **kwargs)

    def emit_add_subtitle(self, payload, **kwargs):
        return self._emit(TV_EVENTS['TV_ADD_SUBTITLE'], payload, **kwargs)

    def emit_stop_casting(self, payload=None, **kwargs):
        return self._emit(TV_EVENTS['TV_STOP_CASTING'], payload or {}, **kwargs)

    def emit_kiosk_booting(self, payload, *, room=None):
        return self._emit(TV_EVENTS['KIOSK_BOOTING'], payload, room=room)

    def emit_kiosk_boot_complete(self, payload, *, room=None):
        return self._emit(TV_EVENTS['KIOSK_BOOT_COMPLETE'], payload, room=room)

    def emit_kiosk_boot_timeout(self, payload, *, room=None):
        return self._emit(TV_EVENTS['KIOSK_BOOT_TIMEOUT'], payload, room=room)

    def emit_hdmi_status(self, payload):
        return self._emit_dual_namespace(TV_EVENTS['HDMI_STATUS'], payload)

    def emit_kiosk_status(self, payload):
        return self._emit_dual_namespace(TV_EVENTS['KIOSK_STATUS'], payload)

    @staticmethod
    def _socket_transport():
        return registry.require('socket_transport')

    def _emit(self, event_name, payload, **kwargs):
        return self._socket_transport().emit(event_name, payload, **kwargs)

    def _emit_dual_namespace(self, event_name, payload):
        root_ok = self._emit(event_name, payload, namespace='/')
        default_ok = self._emit(event_name, payload)
        return root_ok or default_ok
