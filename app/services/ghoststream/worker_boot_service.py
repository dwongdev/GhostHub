"""GhostStream-domain worker boot ownership."""

import logging

from specter import Service, registry

logger = logging.getLogger(__name__)


class GhostStreamWorkerBootService(Service):
    """Own GhostStream-domain worker boot policy."""

    def __init__(self):
        super().__init__('ghoststream_worker_boot')

    def initialize_runtime(self):
        """Initialize the GhostStream runtime inside worker processes."""
        try:
            state = registry.require('ghoststream_runtime').initialize_runtime()
            logger.info("GhostStream runtime initialized in worker process")
            return {
                'ghoststream_runtime_initialized': bool(
                    state.get('runtime_initialized', False),
                ),
            }
        except Exception as exc:
            logger.warning("GhostStream runtime initialization failed: %s", exc)
            return {
                'ghoststream_runtime_initialized': False,
            }


def initialize_ghoststream_worker_runtime():
    """Initialize GhostStream through the registered worker boot owner."""
    return registry.require('ghoststream_worker_boot').initialize_runtime()
