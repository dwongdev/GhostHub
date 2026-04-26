"""Specter runtime owner for GhostStream lifecycle work."""

import logging

from app.services.ghoststream import ghoststream_service
from specter import Service

logger = logging.getLogger(__name__)


class GhostStreamRuntimeService(Service):
    """Own GhostStream worker-side discovery and socket broadcast callbacks."""

    def __init__(self):
        super().__init__('ghoststream_runtime', {
            'runtime_initialized': False,
            'discovery_started': False,
            'callbacks_registered': False,
        })
        self._progress_callback = self._emit_progress
        self._status_callback = self._emit_status

    def initialize_runtime(self):
        """Initialize GhostStream runtime hooks once per worker process."""
        if self.state.get('runtime_initialized'):
            return self.get_state()

        discovery_started = False
        callbacks_registered = False

        try:
            discovery_started = bool(self.start_discovery())
        except Exception as exc:
            logger.warning("GhostStream auto-discovery failed: %s", exc)

        try:
            ghoststream_service.register_progress_callback(self._progress_callback)
            ghoststream_service.register_status_callback(self._status_callback)
            callbacks_registered = True
        except Exception as exc:
            logger.warning("GhostStream callback registration failed: %s", exc)

        self.set_state({
            'runtime_initialized': True,
            'discovery_started': discovery_started or ghoststream_service.is_discovery_started(),
            'callbacks_registered': callbacks_registered,
        })
        return self.get_state()

    def start_discovery(self):
        """Start GhostStream discovery under Specter lifecycle ownership."""
        started = ghoststream_service.start_discovery(owner=self)
        self.set_state({
            'discovery_started': bool(
                started or ghoststream_service.is_discovery_started(),
            ),
        })
        
        # Start background health-check loop to prune dead servers
        self.spawn(self._health_check_loop, label='ghoststream-health-pruning')
        
        return started

    def _health_check_loop(self):
        """Periodically prune unreachable GhostStream servers."""
        import gevent
        while self.state.get('discovery_started'):
            gevent.sleep(60) # check every minute
            try:
                # This uses the service cleanup_unreachable_servers logic
                # which was previously only called manually by admin
                removed_count = ghoststream_service.cleanup_unreachable_servers()
                if removed_count > 0:
                    logger.info("[GhostHub] Background cleanup removed %d unreachable servers", removed_count)
            except Exception as exc:
                logger.error("[GhostHub] Background health check failed: %s", exc)

    def stop_discovery(self):
        """Stop GhostStream discovery and reflect the runtime state."""
        ghoststream_service.stop_discovery()
        self.set_state({'discovery_started': False})
        return True

    def on_stop(self):
        """Tear down runtime-owned GhostStream background work."""
        try:
            ghoststream_service.unregister_progress_callback(self._progress_callback)
            ghoststream_service.unregister_status_callback(self._status_callback)
        except Exception as exc:
            logger.debug("GhostStream callback teardown skipped: %s", exc)

        try:
            self.stop_discovery()
        except Exception as exc:
            logger.debug("GhostStream discovery stop skipped: %s", exc)

        try:
            ghoststream_service.disconnect_websocket()
        except Exception as exc:
            logger.debug("GhostStream websocket disconnect skipped: %s", exc)

        self.set_state({
            'runtime_initialized': False,
            'discovery_started': False,
            'callbacks_registered': False,
        })

    def _emit_progress(self, job_id, progress_data):
        """Broadcast GhostStream progress updates through Socket.IO."""
        self.registry_require('ghoststream_events').emit_progress({
            'job_id': job_id,
            'progress': progress_data.get('progress', 0),
            'fps': progress_data.get('fps'),
            'speed': progress_data.get('speed'),
            'time': progress_data.get('time'),
        })

    def _emit_status(self, job_id, status):
        """Broadcast GhostStream status changes through Socket.IO."""
        self.registry_require('ghoststream_events').emit_status({
            'job_id': job_id,
            'status': status,
        })

    @staticmethod
    def registry_require(name):
        """Resolve a structural dependency from the Specter registry."""
        from specter import registry

        return registry.require(name)
