"""Specter service for safe app-factory startup work."""

import logging
import os

from specter import Service, registry

logger = logging.getLogger(__name__)


class AppStartupService(Service):
    """Own safe one-time startup work for the Flask app factory."""

    def __init__(self):
        super().__init__('app_startup', {
            'instance_path_ready': False,
            'admin_lock_configured': False,
            'database_initialized': False,
            'startup_cleanup_completed': False,
            'wifi_sync_attempted': False,
        })
        self.priority = 10

    def on_start(self):
        """Run startup tasks that are safe during app boot."""
        app = registry.require('service_manager').app
        startup_state = {
            'instance_path_ready': False,
            'admin_lock_configured': False,
            'database_initialized': False,
            'startup_cleanup_completed': False,
            'wifi_sync_attempted': False,
        }

        with app.app_context():
            startup_state['instance_path_ready'] = True  # handled in install_specter
            startup_state['admin_lock_configured'] = self._configure_admin_lock(app)
            startup_state['database_initialized'] = True  # handled in install_specter
            startup_state['wifi_sync_attempted'] = self._sync_wifi_config()

        self.set_state(startup_state)
        self.spawn_later(
            1,
            self._run_startup_cleanup_task,
            app,
            label='startup-cleanup',
        )

    def _run_startup_cleanup_task(self, app):
        """Run startup cleanup after the boot sequence has progressed."""
        with app.app_context():
            self.set_state({
                'startup_cleanup_completed': self._run_startup_cleanup(),
            })

    @staticmethod
    def _ensure_instance_path(app):
        """Ensure the instance directory exists."""
        try:
            os.makedirs(app.instance_path, exist_ok=True)
            logger.info("Instance folder ensured at: %s", app.instance_path)
            return True
        except OSError as exc:
            logger.error("Could not create instance folder at %s: %s", app.instance_path, exc)
            return False

    @staticmethod
    def _configure_admin_lock(app):
        """Configure the shared admin-session lock path."""
        try:
            from app.services.core import session_store

            session_store.configure_admin_lock(app.instance_path)
            return True
        except Exception as exc:
            logger.error("Failed to configure admin lock: %s", exc)
            return False

    @staticmethod
    def _initialize_database():
        """Initialize SQLite persistence."""
        try:
            from app.services.core.database_bootstrap_service import ensure_database_ready

            ensure_database_ready()
            logger.info("SQLite database initialized successfully")
            return True
        except Exception as exc:
            logger.error("Failed to initialize SQLite database: %s", exc)
            return False

    @staticmethod
    def _run_startup_cleanup():
        """Clean stale media-index data for missing/unmounted media roots."""
        try:
            from app.services.media import media_index_service
            from app.services.media.category_query_service import get_all_categories_with_details
            from app.services.storage.storage_drive_service import get_current_mount_paths_fresh

            current_mounts = get_current_mount_paths_fresh()
            logger.info(
                "Startup cleanup: Found %s mounted drives: %s",
                len(current_mounts),
                current_mounts,
            )

            media_index_service.cleanup_media_index_for_unmounted_paths(current_mounts)

            deleted = media_index_service.cleanup_media_index_by_category_path_check()
            if deleted > 0:
                logger.warning(
                    "Startup cleanup DELETED %s stale media_index entries from unmounted drives",
                    deleted,
                )

            all_categories = get_all_categories_with_details(
                use_cache=False,
                show_hidden=True,
            )
            valid_ids = [category['id'] for category in all_categories]
            media_index_service.cleanup_orphaned_media_index(valid_ids)

            logger.info("Startup cleanup complete")
            return True
        except Exception as exc:
            logger.warning("Startup cleanup failed: %s", exc)
            return False

    @staticmethod
    def _sync_wifi_config():
        """Sync persisted WiFi AP configuration to the host system."""
        try:
            from app.services.system.wifi.runtime_service import sync_wifi_config_on_boot

            sync_wifi_config_on_boot()
            return True
        except Exception as exc:
            logger.warning("WiFi config sync skipped: %s", exc)
            return False
