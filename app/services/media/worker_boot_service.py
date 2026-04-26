"""Media-domain worker boot ownership."""

import logging

from specter import Service, registry

logger = logging.getLogger(__name__)


class MediaWorkerBootService(Service):
    """Own media-domain worker boot policy."""

    def __init__(self):
        super().__init__('media_worker_boot')
        self.priority = 200

    def initialize_runtime(self, app):
        """Initialize media runtimes that should start in worker processes."""
        result = {
            'library_runtime_initialized': False,
            'stale_media_cleanup_initialized': False,
            'subtitle_cleanup_completed': False,
        }

        try:
            state = registry.require('library_runtime').initialize_runtime(
                initial_delay_seconds=60,
                scan_interval_seconds=app.config.get(
                    'LIBRARY_SCAN_INTERVAL',
                    600,
                ),
            )
            result['library_runtime_initialized'] = bool(
                state.get('runtime_initialized', False),
            )
            logger.info("Library runtime initialized")
        except Exception as exc:
            logger.error("Failed to initialize library runtime: %s", exc)

        try:
            state = registry.require('stale_media_cleanup_runtime').initialize_runtime(
                initial_delay_seconds=10,
                cleanup_interval_seconds=app.config.get(
                    'STALE_MEDIA_CLEANUP_INTERVAL',
                    21600,
                ),
                batch_size=app.config.get(
                    'STALE_MEDIA_CLEANUP_BATCH_SIZE',
                    5000,
                ),
            )
            result['stale_media_cleanup_initialized'] = bool(
                state.get('runtime_initialized', False),
            )
        except Exception as exc:
            logger.warning("Failed to initialize periodic stale media cleanup: %s", exc)

        try:
            from app.services.media import subtitle_service

            subtitle_service.cleanup_old_cache(max_age_days=30)
            result['subtitle_cleanup_completed'] = True
            logger.info("Deferred subtitle cleanup completed in worker process")
        except Exception as exc:
            logger.warning("Subtitle cleanup failed: %s", exc)

        return result


def initialize_media_worker_runtime(app):
    """Initialize media runtimes through the registered worker boot owner."""
    return registry.require('media_worker_boot').initialize_runtime(app)
