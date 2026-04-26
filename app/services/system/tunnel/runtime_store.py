"""Specter-owned runtime store for tunnel lifecycle state."""

from specter import create_store


DEFAULT_ACTIVE_TUNNEL_INFO = {
    "provider": None,
    "status": None,
    "stage": None,
    "message": None,
    "url": None,
    "control_url": None,
    "app_url": None,
    "process": None,
    "local_port": None,
    "qr_code": None,
    "preauth_key": None,
}


tunnel_runtime_store = create_store('tunnel_runtime', {
    'active_tunnel_info': dict(DEFAULT_ACTIVE_TUNNEL_INFO),
    'last_mesh_recovery_attempt': 0.0,
    'mesh_recovery_cooldown_seconds': 60,
    'mesh_recovery_in_progress': False,
    'mesh_connectivity_failures': 0,
    'mesh_watchdog_running': False,
})
