"""Specter runtime owner for post-fork worker initialization."""

import logging
import os

from specter import Service, registry

logger = logging.getLogger(__name__)


class WorkerRuntimeService(Service):
    """Coordinate runtime initialization that must happen in worker processes."""

    def __init__(self):
        super().__init__('worker_runtime', {
            'bootstrap_strategy': 'service_start',
            'runtime_initialization_attempted': False,
            'runtime_initialized': False,
            'initialization_reason': None,
            'storage_cleanup_scheduler_started': False,
            'ghoststream_runtime_initialized': False,
            'library_runtime_initialized': False,
            'stale_media_cleanup_initialized': False,
            'tunnel_auto_start_attempted': False,
        })
        self._storage_cleanup_scheduler_started = False
        self.priority = 500

    def on_start(self):
        """Initialize worker-owned runtime dependencies at explicit service boot."""
        self.set_state({
            'runtime_initialization_attempted': True,
        })
        self.initialize_runtime()

    def initialize_runtime(self):
        """Initialize worker-owned runtime dependencies once."""
        if self.state.get('runtime_initialized'):
            return self.get_state()

        app = registry.require('service_manager').app
        should_start, reason = self._should_initialize_runtime(app)
        if not should_start:
            logger.debug("Skipping worker runtime initialization (likely in Gunicorn master process)")
            self.set_state({
                'initialization_reason': reason,
            })
            return self.get_state()

        logger.info("Starting background runtime initialization: %s", reason)

        media_boot = registry.resolve('media_worker_boot')
        media_state = media_boot.initialize_runtime(app) if media_boot else {}
        system_boot = registry.resolve('system_worker_boot')
        system_state = system_boot.initialize_runtime(app) if system_boot else {}
        storage_boot = registry.resolve('storage_worker_boot')
        storage_started = storage_boot.start_runtime() if storage_boot else False
        gs_boot = registry.resolve('ghoststream_worker_boot')
        ghoststream_state = gs_boot.initialize_runtime() if gs_boot else {}

        self._storage_cleanup_scheduler_started = storage_started
        self.set_state({
            'runtime_initialized': True,
            'initialization_reason': reason,
            'storage_cleanup_scheduler_started': storage_started,
            'ghoststream_runtime_initialized': bool(
                ghoststream_state.get('ghoststream_runtime_initialized', False),
            ),
            'library_runtime_initialized': bool(
                media_state.get('library_runtime_initialized', False),
            ),
            'stale_media_cleanup_initialized': bool(
                media_state.get('stale_media_cleanup_initialized', False),
            ),
            'tunnel_auto_start_attempted': bool(
                system_state.get('tunnel_auto_start_attempted', False),
            ),
        })
        return self.get_state()

    def on_stop(self):
        """Stop runtime-owned background work."""
        if self._storage_cleanup_scheduler_started:
            boot_service = registry.resolve('storage_worker_boot')
            if boot_service:
                boot_service.stop_runtime()
            self._storage_cleanup_scheduler_started = False

    @staticmethod
    def _should_initialize_runtime(app):
        """Determine whether the current process should start worker runtimes."""
        if os.environ.get('GHOSTHUB_WORKER_INITIALIZED') == 'true':
            return True, 'Gunicorn worker (post_fork hook)'
        if os.name == 'nt':
            return True, 'Windows development environment'
        if app.debug or os.environ.get('FLASK_ENV') == 'development':
            return True, 'Debug/development mode'
        return False, 'not-in-worker-process'
