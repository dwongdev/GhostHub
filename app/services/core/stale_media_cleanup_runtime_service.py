"""Specter runtime owner for periodic stale media-index cleanup."""

import logging

from specter import Service

logger = logging.getLogger(__name__)


class StaleMediaCleanupRuntimeService(Service):
    """Own periodic filesystem validation passes for `media_index` rows."""

    def __init__(self):
        super().__init__('stale_media_cleanup_runtime', {
            'runtime_initialized': False,
            'batch_size': 0,
            'cleanup_interval_seconds': 0,
            'initial_delay_seconds': 0,
            'periodic_cleanup_enabled': False,
        })
        self._batch_size = 0

    def initialize_runtime(
        self,
        *,
        initial_delay_seconds=10,
        cleanup_interval_seconds=21600,
        batch_size=5000,
    ):
        """Initialize stale media cleanup scheduling once per worker."""
        if self.state.get('runtime_initialized'):
            return self.get_state()

        cleanup_interval_seconds = int(cleanup_interval_seconds)
        batch_size = max(1, int(batch_size))
        initial_delay_seconds = max(0, int(initial_delay_seconds))
        periodic_enabled = cleanup_interval_seconds > 0

        self._batch_size = batch_size
        if periodic_enabled:
            if initial_delay_seconds > 0:
                self.spawn_later(
                    initial_delay_seconds,
                    self._run_cleanup_pass,
                    label='initial_stale_media_cleanup',
                )
            else:
                self.spawn(self._run_cleanup_pass, label='initial_stale_media_cleanup')
            self.interval(self._run_cleanup_pass, cleanup_interval_seconds)
            logger.info(
                "Started stale media cleanup runtime (interval=%ss, batch=%s)",
                cleanup_interval_seconds,
                batch_size,
            )
        else:
            logger.info("Stale media cleanup runtime disabled by config")

        self.set_state({
            'runtime_initialized': True,
            'batch_size': batch_size,
            'cleanup_interval_seconds': cleanup_interval_seconds,
            'initial_delay_seconds': initial_delay_seconds,
            'periodic_cleanup_enabled': periodic_enabled,
        })
        return self.get_state()

    def _run_cleanup_pass(self):
        """Run a single bounded stale media cleanup pass."""
        from app.services.media import media_index_service

        try:
            deleted = media_index_service.cleanup_stale_media_index_entries(
                self._batch_size,
            )
            if deleted > 0:
                logger.info("Periodic stale media cleanup deleted %s rows", deleted)
        except Exception as exc:
            logger.warning("Periodic stale media cleanup failed: %s", exc)
