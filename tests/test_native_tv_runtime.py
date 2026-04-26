"""Tests for the native TV runtime bootstrap path."""


def test_ghosthub_runtime_init_uses_local_socketio_alias():
    """The kiosk runtime should import socketio into a local alias inside __init__."""
    from app.services.system.display.native_tv_runtime import GhostHubRuntime

    assert "_socketio" in GhostHubRuntime.__init__.__code__.co_varnames
