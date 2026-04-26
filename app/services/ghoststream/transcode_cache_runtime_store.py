"""Specter-owned runtime store for GhostStream transcode cache cleanup."""

from specter import create_store


transcode_cache_runtime_store = create_store('transcode_cache_runtime', {
    'cleanup_running': False,
    'cleanup_category_paths': [],
    'cleanup_max_age_days': 30,
    'cleanup_max_size_gb': 50,
    'cleanup_interval': 3600,
})
