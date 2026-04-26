"""Specter service to detect a USB sentinel file and reset passwords + admin lock."""

import logging
import os

from app.constants import BUS_EVENTS, SOCKET_EVENTS
from specter import Service, registry

logger = logging.getLogger(__name__)

SENTINEL_FILENAME = '.ghosthub_reset'


class FactoryResetService(Service):
    """Listen for USB mount events and check for the reset sentinel file."""

    def __init__(self):
        super().__init__('factory_reset')

    def on_start(self):
        self.listen(BUS_EVENTS['STORAGE_MOUNT_CHANGED'], self._handle_mount_changed)
        logger.info("FactoryResetService started and listening.")

    def _handle_mount_changed(self, payload: dict):
        mounted_paths = payload.get('mounted_paths') or []
        for mount_path in mounted_paths:
            sentinel = os.path.join(mount_path, SENTINEL_FILENAME)
            if os.path.isfile(sentinel):
                logger.warning(
                    "Factory reset sentinel found on %s — resetting passwords and admin lock.",
                    mount_path,
                )
                self._perform_reset(sentinel)
                return

    def _perform_reset(self, sentinel_path: str):
        """Reset passwords to defaults, clear admin lock, notify clients, remove sentinel."""
        try:
            self._reset_passwords()
            self._clear_admin_lock()
            self._notify_clients()
            self._remove_sentinel(sentinel_path)
            logger.warning("Factory reset completed successfully.")
        except Exception as exc:
            logger.error("Factory reset failed: %s", exc)

    @staticmethod
    def _reset_passwords():
        from app.services.core.config_service import load_config, save_config
        from app.services.core.runtime_config_service import set_runtime_config_value

        # Update runtime config (takes effect immediately without restart)
        set_runtime_config_value('SESSION_PASSWORD', '')
        set_runtime_config_value('ADMIN_PASSWORD', 'admin')

        # Persist to disk
        config_data, _ = load_config()
        config_data['python_config']['SESSION_PASSWORD'] = ''
        config_data['python_config']['ADMIN_PASSWORD'] = 'admin'
        success, msg = save_config(config_data)
        if not success:
            logger.error("Failed to persist password reset: %s", msg)
        else:
            logger.info("Passwords reset to defaults and persisted to config.")

    @staticmethod
    def _clear_admin_lock():
        from app.services.core.session_store import set_admin_session_id

        set_admin_session_id(None)
        logger.info("Admin lock cleared.")

    @staticmethod
    def _notify_clients():
        transport = registry.resolve('socket_transport')
        if transport:
            transport.emit(SOCKET_EVENTS['FACTORY_RESET'], {
                'message': 'Passwords have been reset to defaults. Please reload.',
            })
            logger.info("Factory reset notification emitted to all clients.")

    @staticmethod
    def _remove_sentinel(sentinel_path: str):
        try:
            os.remove(sentinel_path)
            logger.info("Sentinel file removed: %s", sentinel_path)
        except OSError as exc:
            logger.warning(
                "Could not remove sentinel file %s: %s (drive may be read-only)",
                sentinel_path,
                exc,
            )
