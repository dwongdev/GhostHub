"""Specter-owned runtime store for shared media-sort state."""

from specter import create_store


sort_runtime_store = create_store('sort_runtime', {
    'shared_shuffle_cache': {},
})
