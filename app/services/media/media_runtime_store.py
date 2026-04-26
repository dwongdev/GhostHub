"""Specter-owned runtime store for media session ordering state."""

import time

from specter import create_store


media_runtime_store = create_store('media_runtime', {
    'seen_files_tracker': {},
    'sync_mode_order': {},
    'last_session_cleanup': time.time(),
})
