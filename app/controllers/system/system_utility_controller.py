"""System utility/controller compatibility endpoints built on Specter."""

import logging
import os

from flask import request

from specter import Controller, registry
from app.utils.auth import admin_required

logger = logging.getLogger(__name__)


class SystemUtilityController(Controller):
    """Own public system info, compatibility aliases, and browse utility routes."""

    name = 'system_utility'
    url_prefix = '/api'

    def build_routes(self, router):
        @router.route('/browse-folders', methods=['GET'])
        def browse_folders():
            """Open folder selection dialog on the server."""
            return self.browse_folders()

        @router.route('/data/clear-all', methods=['POST'])
        @admin_required
        def clear_all_user_data():
            """Delegate user-data clearing to the admin maintenance controller."""
            return registry.require('admin_maintenance').clear_all_user_data()

        @router.route('/system/version', methods=['GET'])
        def get_version():
            """Return the currently installed GhostHub version."""
            from app.version import VERSION

            return {'version': VERSION}

        @router.route('/system/update', methods=['POST'])
        @admin_required
        def update_ghosthub():
            """Delegate update scheduling to the admin system controller."""
            return registry.require('admin_system').update_ghosthub()

        @router.route('/hdmi/status', methods=['GET'])
        def hdmi_status():
            """Delegate HDMI status to the admin system controller."""
            return registry.require('admin_system').hdmi_status()

    def browse_folders(self):
        """Open a folder-selection dialog when available."""
        if os.path.exists('/.dockerenv'):
            logger.info("Running in Docker environment, folder browser not available")
            return {
                'error': 'Folder browser not available in Docker environment',
                'message': 'To add media directories in Docker, mount volumes in docker-compose.yml',
                'docker': True,
            }, 501

        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder_path = filedialog.askdirectory(title="Select Category Folder")
            root.destroy()

            if folder_path:
                logger.info("Folder selected via Tkinter dialog: %s", folder_path)
                return {'path': folder_path}

            logger.info("Folder browser cancelled or no folder selected.")
            return {'path': None}
        except (ImportError, Exception) as exc:
            logger.error("Error opening folder browser: %s", exc)
            return {
                'error': 'Server environment does not support graphical folder browser.',
            }, 501
