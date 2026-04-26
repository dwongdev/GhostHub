"""Specter-owned runtime store for HDMI and kiosk lifecycle state."""

from specter import create_store

hdmi_runtime_store = create_store('hdmi_runtime', {
    'runtime_initialized': False,
    'monitoring_active': False,
    'connected': False,
    'kiosk_running': False,
    'casting_active': False,
    'idle_greenlet': None,
    'countdown_greenlet': None,
    'shutdown_start_time': None,
    'shutdown_duration': None,
    'in_idle_mode': False,
    'in_shutdown_countdown': False,
})
