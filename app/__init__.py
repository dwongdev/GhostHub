"""
Application Factory
-----------------
Flask application initialization and configuration.
"""
import logging

from flask import Flask

from .app_bootstrap import (
    configure_flask_app,
    configure_root_logging,
    create_socketio,
    install_specter,
    log_app_creation,
)
from .config import config_by_name

configure_root_logging()

logger = logging.getLogger(__name__)
socketio = create_socketio()

def create_app(config_name='default'):
    """
    Create and configure Flask application instance.
    Returns the configured Flask app with Specter installed.
    """
    app = Flask(
        __name__,
        static_folder=config_by_name[config_name].STATIC_FOLDER,
        template_folder=config_by_name[config_name].TEMPLATE_FOLDER,
        instance_path=config_by_name[config_name].INSTANCE_FOLDER_PATH,
        instance_relative_config=True,
    )
    configure_flask_app(app, config_name)

    socketio.init_app(app)
    install_specter(app, socketio)
    log_app_creation(logger, app, config_name)

    return app
