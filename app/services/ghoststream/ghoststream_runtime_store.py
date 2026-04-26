"""Specter-owned runtime store for GhostStream shared client state."""

from gevent.lock import BoundedSemaphore

from specter import create_store


ghoststream_runtime_store = create_store('ghoststream_runtime_state', {
    'client': None,
    'load_balancer': None,
    'discovery_started': False,
    'discovery_lock': BoundedSemaphore(1),
    'progress_callbacks': [],
    'status_callbacks': [],
    'last_error': None,
    'active_jobs': {},
    'job_servers': {},
    'server_callback_urls': {},
})
