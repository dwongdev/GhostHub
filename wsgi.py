#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
-----------------------------
Initializes the Flask application for production deployment via Gunicorn.
It assumes the 'production' configuration will be used.

IMPORTANT: Monkey patching must happen before any imports, but should
only be called once. GeventWebSocketWorker calls patch_all() in init_process(),
but only if we let it. We check first to avoid double patching.

See: https://github.com/gevent/gevent/issues/1149 (patch_all not idempotent)
"""

# CRITICAL: Only patch if not already patched (avoid double patching issues)
from gevent import monkey
if not monkey.is_module_patched('socket'):
    monkey.patch_all()

import os
import faulthandler
from app.utils.server_utils import initialize_app

# Emit Python stack traces on fatal signals (SIGSEGV/SIGABRT) for crash triage.
if not faulthandler.is_enabled():
    faulthandler.enable(all_threads=True)

# Set the config name explicitly for Gunicorn environment
# Gunicorn doesn't typically read the FLASK_CONFIG env var in the same way
# as the direct script execution might.
config_name = 'production'
port = int(os.getenv('PORT', 5000)) # Port might still be relevant for app internals

# Initialize the Flask application instance
app = initialize_app(config_name, port)

# Gunicorn will look for this 'app' variable by default
