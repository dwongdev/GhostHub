"""Configuration controller built on Specter."""

import logging
import time

from flask import jsonify, request, session
from gevent.lock import BoundedSemaphore

from app.config import Config
from app.services import config_service
from app.services.core.runtime_config_service import (
    get_runtime_config_value,
    set_runtime_config_value,
)
from specter import Controller
from app.utils.auth import admin_required, is_current_admin_session

logger = logging.getLogger(__name__)


class ConfigController(Controller):
    """Own configuration and session-password validation endpoints."""

    name = 'config'
    url_prefix = '/api'

    password_attempt_window_seconds = 300
    max_password_attempts_per_window = 10

    def __init__(self):
        super().__init__()
        self._password_attempts_lock = BoundedSemaphore(1)
        self._password_attempts = {}

    def build_routes(self, router):
        @router.route('/config', methods=['GET'])
        def get_config_route():
            """Get the current application configuration."""
            return self.get_config()

        @router.route('/config', methods=['POST'])
        @admin_required
        def save_config_route():
            """Save the application configuration."""
            return self.save_config()

        @router.route('/validate_session_password', methods=['POST'])
        def validate_session_password():
            """Validate the submitted session password."""
            return self.validate_session_password()

    def get_config(self):
        """Get full application configuration plus session/admin flags."""
        config_data, error = config_service.load_config()
        if error:
            logger.warning(
                "Error loading configuration for API response: %s. Serving available config.",
                error,
            )

        config_data['isPasswordProtectionActive'] = bool(
            get_runtime_config_value('SESSION_PASSWORD', ''),
        )
        config_data['is_admin'] = is_current_admin_session()
        return config_data

    def save_config(self):
        """Persist config JSON and apply eligible Python settings live."""
        new_config = request.get_json(silent=True)
        success, message = config_service.save_config(new_config)
        if not success:
            return {'error': message}, 400

        if new_config and 'python_config' in new_config:
            self._apply_live_python_config(new_config['python_config'])

        return {
            'message': message,
            'isPasswordProtectionActive': bool(
                get_runtime_config_value('SESSION_PASSWORD', ''),
            ),
        }, 200

    def validate_session_password(self):
        """Validate the submitted session password with rate limiting."""
        payload = request.get_json(silent=True) or {}
        submitted_password = payload.get('password', '')
        actual_password = get_runtime_config_value('SESSION_PASSWORD', '')

        if not actual_password:
            session['session_password_validated'] = True
            return {
                'valid': True,
                'message': 'No password protection active.',
            }

        client_key = f"{request.remote_addr}:{request.cookies.get('session_id', '')}"
        allowed, retry_after = self._check_password_rate_limit(client_key)
        if not allowed:
            response = jsonify({
                'valid': False,
                'message': 'Too many password attempts. Please try again later.',
                'retry_after_seconds': retry_after,
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(retry_after)
            return response

        if submitted_password == actual_password:
            session['session_password_validated'] = True
            with self._password_attempts_lock:
                self._password_attempts.pop(client_key, None)
            return {'valid': True}

        session['session_password_validated'] = False
        return {'valid': False, 'message': 'Incorrect password.'}

    def _apply_live_python_config(self, python_config):
        """Apply Python config values that do not require a restart."""
        type_converters = {
            'CACHE_EXPIRY': int,
            'DEFAULT_PAGE_SIZE': int,
            'SESSION_EXPIRY': int,
            'SHUFFLE_MEDIA': self._to_bool,
            'WS_RECONNECT_ATTEMPTS': int,
            'WS_RECONNECT_DELAY': int,
            'WS_RECONNECT_FACTOR': float,
            'MEMORY_CLEANUP_INTERVAL': int,
            'MAX_CACHE_SIZE': int,
            'TUNNEL_PROVIDER': str,
            'PINGGY_ACCESS_TOKEN': str,
            'TUNNEL_LOCAL_PORT': int,
            'TUNNEL_AUTO_START': self._to_bool,
            'SESSION_PASSWORD': str,
            'ADMIN_PASSWORD': str,
            'SAVE_VIDEO_PROGRESS': self._to_bool,
            'SAVE_PROGRESS_FOR_HIDDEN_FILES': self._to_bool,
            'ENABLE_SUBTITLES': self._to_bool,
            'ENABLE_TV_SORTING': self._to_bool,
            'ENABLE_CEC_WAKE': self._to_bool,
            'VIDEO_END_BEHAVIOR': str,
            'UPLOAD_RATE_LIMIT_PER_CLIENT': float,
            'UPLOAD_RATE_LIMIT_GLOBAL': float,
            'DOWNLOAD_RATE_LIMIT_PER_CLIENT': float,
            'DOWNLOAD_RATE_LIMIT_GLOBAL': float,
            'STREAM_MAX_DURATION_SECONDS': float,
            'STREAM_READ_TIMEOUT_SECONDS': float,
            'STALE_MEDIA_CLEANUP_INTERVAL': int,
            'STALE_MEDIA_CLEANUP_BATCH_SIZE': int,
            'MAX_CATEGORY_SCAN_DEPTH': int,
            'UI_SETTINGS_MODE': str,
            'AUTO_OPTIMIZE_FOR_HARDWARE': self._to_bool,
            'SESSION_COOKIE_SECURE': str,
        }

        for key, value in python_config.items():
            if key not in type_converters:
                continue

            try:
                if key == 'SESSION_COOKIE_SECURE':
                    mode = str(value).strip().lower()
                    if mode not in ('auto', 'true', 'false'):
                        mode = 'auto'
                    set_runtime_config_value('SESSION_COOKIE_SECURE', mode == 'true')
                    set_runtime_config_value('SESSION_COOKIE_SECURE_MODE', mode)
                    setattr(Config, key, mode == 'true')
                    logger.debug(
                        "Live config updated: SESSION_COOKIE_SECURE_MODE = %s",
                        mode,
                    )
                    continue

                converted = type_converters[key](value)
                set_runtime_config_value(key, converted)
                logger.debug("Live config updated: %s = %s", key, converted)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Failed to convert config value %s=%s: %s",
                    key,
                    value,
                    exc,
                )

        logger.info("Live config updated for %s settings", len(python_config))

    def _prune_password_attempts(self, now):
        """Remove expired password-attempt buckets."""
        expired = [
            key
            for key, value in self._password_attempts.items()
            if now - value.get('first_attempt', 0) > self.password_attempt_window_seconds
        ]
        for key in expired:
            self._password_attempts.pop(key, None)

    def _check_password_rate_limit(self, client_key):
        """Check and increment password validation attempts."""
        now = time.time()
        with self._password_attempts_lock:
            self._prune_password_attempts(now)
            bucket = self._password_attempts.get(client_key)

            if not bucket or now - bucket.get('first_attempt', 0) > self.password_attempt_window_seconds:
                self._password_attempts[client_key] = {'count': 1, 'first_attempt': now}
                return True, 0

            if bucket['count'] >= self.max_password_attempts_per_window:
                retry_after = int(
                    self.password_attempt_window_seconds -
                    (now - bucket['first_attempt'])
                )
                return False, max(retry_after, 1)

            bucket['count'] += 1
            return True, 0

    @staticmethod
    def _to_bool(value):
        """Normalize JSON/string booleans into Python bools."""
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)
