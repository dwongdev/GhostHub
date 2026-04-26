"""Specter Store for managing active chunked upload sessions."""

from gevent.lock import BoundedSemaphore
from specter import create_store

upload_sessions_store = create_store('upload_sessions', {
    'active_uploads': {},  # Dict[str, Dict] active chunked upload sessions
    'upload_lock': BoundedSemaphore(1),  # gevent-aware lock for critical sections
})
