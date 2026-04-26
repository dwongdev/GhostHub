"""Specter-owned runtime store for category discovery/cache state."""

from specter import create_store


category_runtime_store = create_store('category_runtime', {
    'category_cache': [],
    'last_cache_update': 0,
    'dir_mtime_cache': {},
    'last_content_check': 0,
})
