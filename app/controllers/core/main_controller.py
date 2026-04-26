"""Main page controller built on Specter."""

import logging
import os

from flask import render_template, send_from_directory

from app.services import config_service
from app.services.core.runtime_config_service import get_runtime_static_folder
from specter import Controller

logger = logging.getLogger(__name__)


class MainController(Controller):
    """Own primary web page ingress."""

    name = 'core_main_page'
    url_prefix = ''

    def build_routes(self, router):
        """Register HTTP endpoints for the main web interface."""
        router.route('/', methods=['GET'])(self.index)
        router.route('/ragot', methods=['GET'])(self.ragot_lab)

    def index(self):
        """Render the main category listing page."""
        logger.info("Serving index page.")
        config_data, _ = config_service.load_config()
        ui_config = config_data.get('javascript_config', {}).get('ui', {})
        initial_theme = ui_config.get('theme', 'dark')
        initial_layout = ui_config.get('layout', 'streaming')
        initial_features = ui_config.get('features', {})
        return render_template(
            'index.html',
            initial_theme=initial_theme,
            initial_layout=initial_layout,
            initial_features=initial_features,
        )

    def ragot_lab(self):
        """Render the RAGOT framework lab page."""
        logger.info("Serving RAGOT Lab page.")
        lab_dir = os.path.join(get_runtime_static_folder(), 'js', 'ragot', 'lab')
        return send_from_directory(lab_dir, 'index.html')
