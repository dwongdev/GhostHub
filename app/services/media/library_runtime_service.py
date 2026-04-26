"""Specter coordinator for cross-runtime library orchestration."""

from specter import Service, registry


class LibraryRuntimeService(Service):
    """Coordinate cross-runtime library flows without acting as a generic facade."""

    def __init__(self):
        super().__init__('library_runtime')

    def initialize_runtime(self, *, initial_delay_seconds=60, scan_interval_seconds=0):
        """Initialize thumbnail and indexing runtimes once."""
        registry.require('thumbnail_runtime').ensure_workers()
        indexing_state = registry.require('indexing_runtime').initialize_runtime(
            initial_delay_seconds=initial_delay_seconds,
            scan_interval_seconds=scan_interval_seconds,
        )
        return {
            'runtime_initialized': bool(indexing_state.get('runtime_initialized', False)),
            'periodic_scan_enabled': bool(indexing_state.get('periodic_scan_enabled', False)),
            'scan_interval_seconds': int(indexing_state.get('scan_interval_seconds', 0) or 0),
        }

    def quiesce_for_reindex(self, *, timeout_seconds=8, clear_queue=True):
        """Pause thumbnail and indexing workers ahead of a full reindex."""
        thumbnail_state = registry.require('thumbnail_runtime').quiesce_thumbnail_runtime(
            timeout_seconds=timeout_seconds,
            clear_queue=clear_queue,
        )
        indexer_state = registry.require('indexing_runtime').quiesce_indexing(
            timeout_seconds=timeout_seconds,
            clear_queue=clear_queue,
        )
        return {
            'thumbnail': thumbnail_state,
            'indexer': indexer_state,
        }

    def start_background_reindex(
        self,
        categories,
        *,
        active_mounts=None,
        generate_thumbnails=True,
    ):
        """Kick off background reindex through the dedicated indexing runtime."""
        registry.require('thumbnail_runtime').ensure_workers()
        return registry.require('indexing_runtime').start_background_reindex(
            categories,
            active_mounts=active_mounts,
            generate_thumbnails=generate_thumbnails,
        )
