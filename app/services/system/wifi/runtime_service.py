"""WiFi AP runtime/application ownership."""

import logging
import os
import re
import subprocess

import gevent

from app.services.system.wifi.config_service import (
    HOSTAPD_CONF_PATH,
    build_updated_wifi_config,
    get_wifi_config,
    is_raspberry_pi,
    parse_hostapd_conf,
    persist_wifi_config,
)

logger = logging.getLogger(__name__)


def save_wifi_config(ssid=None, password=None, channel=None, country_code=None):
    """Persist WiFi config and apply it to the host AP runtime when appropriate."""
    config, error = build_updated_wifi_config(
        ssid=ssid,
        password=password,
        channel=channel,
        country_code=country_code,
    )
    if error:
        return False, error

    success, save_error = persist_wifi_config(config)
    if not success:
        return False, save_error

    if is_raspberry_pi():
        success, message = apply_wifi_config(config)
        if not success:
            return False, message
        return True, "WiFi configuration saved and applied. Network will restart shortly."

    return True, "WiFi configuration saved. Changes will apply on next Pi boot."


def apply_wifi_config(config):
    """Apply WiFi AP configuration to system files and restart services."""
    if os.environ.get('GHOSTHUB_TESTING') == 'true' and os.environ.get('GHOSTHUB_SKIP_WIFI_MOCK') != 'true':
        return True, "Mocked for testing"
    try:
        if not os.path.exists(HOSTAPD_CONF_PATH):
            return False, "hostapd.conf not found. Is AP mode set up?"

        with open(HOSTAPD_CONF_PATH, 'r') as handle:
            content = handle.read()

        content = re.sub(r'^ssid=.*$', f"ssid={config['ssid']}", content, flags=re.MULTILINE)
        content = re.sub(
            r'^wpa_passphrase=.*$',
            f"wpa_passphrase={config['password']}",
            content,
            flags=re.MULTILINE,
        )
        content = re.sub(r'^channel=.*$', f"channel={config['channel']}", content, flags=re.MULTILINE)

        if re.search(r'^country_code=', content, re.MULTILINE):
            content = re.sub(
                r'^country_code=.*$',
                f"country_code={config['country_code']}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content = re.sub(
                r'^(interface=.*)$',
                f"\\1\ncountry_code={config['country_code']}",
                content,
                flags=re.MULTILINE,
            )

        temp_file = '/tmp/hostapd_temp.conf'
        with open(temp_file, 'w') as handle:
            handle.write(content)

        logger.info(
            "Writing hostapd.conf with SSID=%s, channel=%s",
            config['ssid'],
            config['channel'],
        )

        result = subprocess.run(
            ['sudo', '-n', 'cp', temp_file, HOSTAPD_CONF_PATH],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.error("Failed to update hostapd.conf: %s", result.stderr)
            return False, f"Failed to update hostapd.conf: {result.stderr}"

        try:
            with open(HOSTAPD_CONF_PATH, 'r') as handle:
                verify_content = handle.read()
            if config['ssid'] not in verify_content or config['password'] not in verify_content:
                return False, "Failed to verify hostapd.conf was updated correctly"
        except Exception as err:
            logger.warning("Could not verify hostapd.conf: %s", err)

        os.remove(temp_file)

        reconfigure_result = subprocess.run(
            ['sudo', '-n', 'hostapd_cli', 'reconfigure'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if reconfigure_result.returncode == 0 and 'OK' in reconfigure_result.stdout:
            subprocess.run(
                ['sudo', '-n', 'systemctl', 'restart', 'dnsmasq'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return True, "WiFi configuration applied. Devices should reconnect with new credentials."

        logger.warning(
            "hostapd_cli reconfigure failed: %s, falling back to full restart",
            reconfigure_result.stderr,
        )

        subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'hostapd'], capture_output=True, timeout=10)
        subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'dnsmasq'], capture_output=True, timeout=10)
        subprocess.run(['sudo', '-n', 'ip', 'addr', 'flush', 'dev', 'wlan0'], capture_output=True, timeout=10)
        subprocess.run(['sudo', '-n', 'ip', 'link', 'set', 'wlan0', 'down'], capture_output=True, timeout=10)
        gevent.sleep(2)
        subprocess.run(['sudo', '-n', 'ip', 'link', 'set', 'wlan0', 'up'], capture_output=True, timeout=10)
        subprocess.run(['sudo', '-n', 'ip', 'addr', 'add', '192.168.4.1/24', 'dev', 'wlan0'], capture_output=True, timeout=10)
        gevent.sleep(2)

        start_result = subprocess.run(
            ['sudo', '-n', 'systemctl', 'start', 'hostapd'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if start_result.returncode != 0:
            logger.error("Failed to start hostapd: %s", start_result.stderr)
            return False, f"Config saved but failed to start hostapd: {start_result.stderr}"

        gevent.sleep(2)
        subprocess.run(['sudo', '-n', 'systemctl', 'start', 'dnsmasq'], capture_output=True, timeout=10)

        status_result = subprocess.run(
            ['sudo', '-n', 'systemctl', 'is-active', 'hostapd'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if 'active' not in status_result.stdout:
            return False, "hostapd failed to start. Check system logs."

        logger.info("WiFi AP configuration applied successfully")
        return True, "WiFi configuration applied. Devices must forget the old network and reconnect with new credentials."
    except subprocess.TimeoutExpired:
        logger.error("Timeout while applying WiFi config")
        return False, "Timeout while restarting WiFi service"
    except PermissionError as err:
        logger.error("Permission error applying WiFi config: %s", err)
        return False, "Permission denied. GhostHub service may need sudo privileges."
    except Exception as err:
        logger.error("Error applying WiFi config: %s", err)
        return False, f"Failed to apply WiFi config: {str(err)}"


def get_wifi_status():
    """Get current WiFi AP runtime status."""
    status = {
        'is_raspberry_pi': is_raspberry_pi(),
        'ap_mode_available': False,
        'hostapd_running': False,
        'connected_clients': 0,
    }

    if not is_raspberry_pi():
        status['message'] = "Not running on Raspberry Pi"
        return status

    try:
        status['ap_mode_available'] = os.path.exists(HOSTAPD_CONF_PATH)
        result = subprocess.run(
            ['systemctl', 'is-active', 'hostapd'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status['hostapd_running'] = result.stdout.strip() == 'active'

        if status['hostapd_running']:
            try:
                result = subprocess.run(
                    ['iw', 'dev', 'wlan0', 'station', 'dump'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    status['connected_clients'] = result.stdout.count('Station')
            except Exception:
                pass

        return status
    except Exception as err:
        logger.error("Error getting WiFi status: %s", err)
        status['error'] = str(err)
        return status


def sync_wifi_config_on_boot():
    """Sync persisted WiFi config to hostapd.conf on boot."""
    if not is_raspberry_pi():
        return
    from app.services.system.wifi.config_service import WIFI_CONFIG_PATH

    if not os.path.exists(WIFI_CONFIG_PATH):
        logger.info("No persistent WiFi config found, using system defaults")
        return

    try:
        saved_config, _ = get_wifi_config()
        current_config = parse_hostapd_conf()
        if current_config and (
            current_config.get('ssid') != saved_config.get('ssid')
            or current_config.get('password') != saved_config.get('password')
            or current_config.get('channel') != saved_config.get('channel')
        ):
            logger.info("Syncing saved WiFi config to hostapd.conf...")
            success, message = apply_wifi_config(saved_config)
            if success:
                logger.info("WiFi config synced successfully on boot")
            else:
                logger.warning("Failed to sync WiFi config on boot: %s", message)
        else:
            logger.info("WiFi config already in sync")
    except Exception as err:
        logger.error("Error syncing WiFi config on boot: %s", err)
