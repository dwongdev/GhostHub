"""Live application of persisted Python config values."""

import logging

from app.config import Config
from app.services.core.runtime_config_service import set_runtime_config_value

logger = logging.getLogger(__name__)


def apply_live_python_config(python_config):
    """Apply Python config values that do not require a restart."""
    if not isinstance(python_config, dict):
        return

    type_converters = {
        'CACHE_EXPIRY': int,
        'DEFAULT_PAGE_SIZE': int,
        'SESSION_EXPIRY': int,
        'SHUFFLE_MEDIA': _to_bool,
        'WS_RECONNECT_ATTEMPTS': int,
        'WS_RECONNECT_DELAY': int,
        'WS_RECONNECT_FACTOR': float,
        'MEMORY_CLEANUP_INTERVAL': int,
        'MAX_CACHE_SIZE': int,
        'TUNNEL_PROVIDER': str,
        'PINGGY_ACCESS_TOKEN': str,
        'TUNNEL_LOCAL_PORT': int,
        'TUNNEL_AUTO_START': _to_bool,
        'SESSION_PASSWORD': str,
        'ADMIN_PASSWORD': str,
        'SAVE_VIDEO_PROGRESS': _to_bool,
        'SAVE_PROGRESS_FOR_HIDDEN_FILES': _to_bool,
        'ENABLE_SUBTITLES': _to_bool,
        'ENABLE_TV_SORTING': _to_bool,
        'ENABLE_CEC_WAKE': _to_bool,
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
        'AUTO_OPTIMIZE_FOR_HARDWARE': _to_bool,
        'SESSION_COOKIE_SECURE': str,
    }

    applied_count = 0
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
                applied_count += 1
                logger.debug(
                    "Live config updated: SESSION_COOKIE_SECURE_MODE = %s",
                    mode,
                )
                continue

            converted = type_converters[key](value)
            set_runtime_config_value(key, converted)
            applied_count += 1
            logger.debug("Live config updated: %s = %s", key, converted)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Failed to convert config value %s=%s: %s",
                key,
                value,
                exc,
            )

    logger.info("Live config updated for %s settings", applied_count)


def _to_bool(value):
    """Normalize JSON/string booleans into Python bools."""
    if isinstance(value, str):
        return value.lower() == 'true'
    return bool(value)
