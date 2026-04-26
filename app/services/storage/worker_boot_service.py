"""Storage-domain worker boot ownership."""

import logging

from specter import Service, registry

logger = logging.getLogger(__name__)


class StorageWorkerBootService(Service):
    """Own storage-domain worker boot policy."""

    def __init__(self):
        super().__init__('storage_worker_boot')

    def start_runtime(self):
        """Start storage runtimes that should live in worker processes."""
        try:
            state = registry.require('upload_session_runtime').initialize_runtime()
            logger.info("Storage cleanup scheduler started")
            return bool(state.get('runtime_initialized', False))
        except Exception as exc:
            logger.error("Failed to start cleanup scheduler: %s", exc)
            return False

    def stop_runtime(self):
        """Stop storage runtimes owned by worker processes."""
        try:
            registry.require('upload_session_runtime').teardown_runtime()
            return True
        except Exception as exc:
            logger.debug("Storage cleanup scheduler stop skipped: %s", exc)
            return False


def start_storage_worker_runtime():
    """Start storage runtimes through the registered worker boot owner."""
    return registry.require('storage_worker_boot').start_runtime()


def stop_storage_worker_runtime():
    """Stop storage runtimes through the registered worker boot owner."""
    return registry.require('storage_worker_boot').stop_runtime()
