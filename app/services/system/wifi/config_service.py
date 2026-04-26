"""WiFi AP config persistence and validation ownership."""

import json
import logging
import os
import re

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.system.platform_service import is_raspberry_pi

logger = logging.getLogger(__name__)

HOSTAPD_CONF_PATH = "/etc/hostapd/hostapd.conf"
INSTANCE_FOLDER = os.path.abspath(get_runtime_config_value('INSTANCE_FOLDER_PATH'))
WIFI_CONFIG_PATH = os.path.join(INSTANCE_FOLDER, 'wifi_config.json')

DEFAULT_WIFI_CONFIG = {
    "ssid": "GhostHub",
    "password": "ghost123",
    "channel": 7,
    "country_code": "US",
}
def get_wifi_config():
    """Get current WiFi AP configuration from persistence or hostapd."""
    try:
        if os.path.exists(WIFI_CONFIG_PATH):
            with open(WIFI_CONFIG_PATH, 'r') as handle:
                config = json.load(handle)
            logger.info("Loaded WiFi config from %s", WIFI_CONFIG_PATH)
            return config, None

        if is_raspberry_pi() and os.path.exists(HOSTAPD_CONF_PATH):
            config = parse_hostapd_conf()
            if config:
                return config, None

        logger.info("Using default WiFi configuration")
        return DEFAULT_WIFI_CONFIG.copy(), None
    except json.JSONDecodeError as err:
        logger.error("Error parsing WiFi config JSON: %s", err)
        return DEFAULT_WIFI_CONFIG.copy(), f"Error parsing config file: {err}"
    except Exception as err:
        logger.error("Error loading WiFi config: %s", err)
        return DEFAULT_WIFI_CONFIG.copy(), str(err)


def parse_hostapd_conf():
    """Parse hostapd.conf and extract current settings."""
    config = DEFAULT_WIFI_CONFIG.copy()
    try:
        with open(HOSTAPD_CONF_PATH, 'r') as handle:
            content = handle.read()

        ssid_match = re.search(r'^ssid=(.+)$', content, re.MULTILINE)
        if ssid_match:
            config['ssid'] = ssid_match.group(1).strip()

        password_match = re.search(r'^wpa_passphrase=(.+)$', content, re.MULTILINE)
        if password_match:
            config['password'] = password_match.group(1).strip()

        channel_match = re.search(r'^channel=(\d+)$', content, re.MULTILINE)
        if channel_match:
            config['channel'] = int(channel_match.group(1))

        country_match = re.search(r'^country_code=(\w+)$', content, re.MULTILINE)
        if country_match:
            config['country_code'] = country_match.group(1).strip()

        logger.info(
            "Parsed hostapd.conf: SSID=%s, channel=%s",
            config['ssid'],
            config['channel'],
        )
        return config
    except Exception as err:
        logger.error("Error parsing hostapd.conf: %s", err)
        return None


def build_updated_wifi_config(ssid=None, password=None, channel=None, country_code=None):
    """Validate user input and return the updated WiFi config payload."""
    current_config, _ = get_wifi_config()

    if ssid is not None:
        if len(ssid) < 1 or len(ssid) > 32:
            return None, "SSID must be 1-32 characters"
        current_config['ssid'] = ssid

    if password is not None:
        if len(password) < 8 or len(password) > 63:
            return None, "Password must be 8-63 characters"
        current_config['password'] = password

    if channel is not None:
        if not (1 <= channel <= 11):
            return None, "Channel must be between 1 and 11"
        current_config['channel'] = channel

    if country_code is not None:
        if len(country_code) != 2:
            return None, "Country code must be 2 characters"
        current_config['country_code'] = country_code.upper()

    return current_config, None


def persist_wifi_config(config):
    """Persist WiFi config in the instance folder."""
    try:
        os.makedirs(INSTANCE_FOLDER, exist_ok=True)
        with open(WIFI_CONFIG_PATH, 'w') as handle:
            json.dump(config, handle, indent=2)
        logger.info("Saved WiFi config to %s", WIFI_CONFIG_PATH)
        return True, None
    except Exception as err:
        logger.error("Error saving WiFi config: %s", err)
        return False, f"Failed to save WiFi config: {str(err)}"
