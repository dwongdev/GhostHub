"""Admin system management controller built on Specter."""

import gc
import logging
import os
import re
import subprocess
import tempfile

import gevent
import requests
from flask import request

from app.config import Config
from app.services import system_stats_service
from app.services.system.wifi.config_service import get_wifi_config
from app.services.system.wifi.runtime_service import (
    get_wifi_status,
    save_wifi_config,
)
from specter import Controller, Field, Schema, expect_json
from app.utils.auth import admin_required
from app.version import VERSION

logger = logging.getLogger(__name__)


class AdminSystemController(Controller):
    """Own admin system/update/wifi/stats endpoints."""

    name = 'admin_system'
    url_prefix = '/api/admin'

    schemas = {
        'system_update': Schema('admin_system.system_update', {
            'force_update': Field(bool, default=False),
        }, strict=True),
        'wifi_config': Schema('admin_system.wifi_config', {
            'ssid': Field(str),
            'password': Field(str),
            'channel': Field(int),
            'country_code': Field(str),
        }, strict=True),
    }

    def build_routes(self, router):
        @router.route('/system/version-check', methods=['GET'])
        @admin_required
        def version_check():
            """Check GitHub Releases for latest available version."""
            return self.version_check()

        @router.route('/system/update', methods=['POST'])
        @admin_required
        def update_ghosthub():
            """Schedule GhostHub update script execution."""
            return self.update_ghosthub()

        @router.route('/system/restart', methods=['POST'])
        @admin_required
        def restart_ghosthub():
            """Schedule GhostHub service restart."""
            return self.restart_ghosthub()

        @router.route('/hdmi/status', methods=['GET'])
        def hdmi_status():
            """Get HDMI connection and kiosk status."""
            return self.hdmi_status()

        @router.route('/wifi/config', methods=['GET'])
        @admin_required
        def get_wifi_config():
            """Get current WiFi AP configuration."""
            return self.get_wifi_config()

        @router.route('/wifi/config', methods=['POST'])
        @admin_required
        def save_wifi_config():
            """Save WiFi AP configuration."""
            return self.save_wifi_config()

        @router.route('/wifi/status', methods=['GET'])
        @admin_required
        def get_wifi_status():
            """Get WiFi AP status."""
            return self.get_wifi_status()

        @router.route('/system/stats', methods=['GET'])
        @admin_required
        def get_system_stats():
            """Get system statistics for Pi monitoring."""
            return self.get_system_stats()

    def version_check(self):
        """Check GitHub Releases for latest available version."""

        current_version = VERSION
        try:
            release = self._latest_github_release()
            latest_version = self._parse_release_version(release.get("tag_name", ""))
        except Exception as exc:
            logger.error("version-check: GitHub release request failed: %s", exc)
            return {
                'current_version': current_version,
                'latest_version': None,
                'update_available': False,
                'release_url': None,
                'error': 'Could not reach GitHub Releases.',
            }

        try:
            update_available = self._semver_tuple(latest_version) > self._semver_tuple(current_version)
        except ValueError:
            update_available = False

        return {
            'current_version': current_version,
            'latest_version': latest_version,
            'update_available': update_available,
            'release_url': release.get('html_url'),
        }

    def update_ghosthub(self):
        """Schedule GhostHub update script execution."""
        try:
            payload = self.schema('system_update').require(
                request.get_json(silent=True) or {},
            )
            force_update = bool(payload.get('force_update', False))
            script_path = self._resolve_update_script_path()

            if force_update:
                logger.info(
                    "Starting GhostHub update with force update using script: %s",
                    script_path,
                )
            else:
                logger.info("Starting GhostHub update using script: %s", script_path)

            try:
                from app.services.core.sqlite_runtime_service import close_connection

                close_connection()
                gc.collect()
                logger.info("Closed database connections before update")
            except Exception as exc:
                logger.warning("Could not cleanup database connections: %s", exc)

            try:
                cleanup_cmds = [
                    ["sudo", "systemctl", "stop", "ghosthub-update.timer"],
                    ["sudo", "systemctl", "stop", "ghosthub-update.service"],
                    ["sudo", "systemctl", "disable", "ghosthub-update.timer"],
                    ["sudo", "systemctl", "disable", "ghosthub-update.service"],
                    ["sudo", "systemctl", "reset-failed", "ghosthub-update.service"],
                    ["sudo", "rm", "-f", "/etc/systemd/system/ghosthub-update.timer"],
                    ["sudo", "rm", "-f", "/etc/systemd/system/ghosthub-update.service"],
                ]
                greenlets = [
                    self.spawn(subprocess.run, cmd, capture_output=True, timeout=5)
                    for cmd in cleanup_cmds
                ]
                gevent.joinall(greenlets, timeout=10)
                subprocess.run(
                    ["sudo", "systemctl", "daemon-reload"],
                    capture_output=True,
                    timeout=5,
                )
            except Exception as exc:
                logger.debug("Cleanup error (can be ignored): %s", exc)

            systemd_cmd = [
                "sudo",
                "systemd-run",
                "--unit=ghosthub-update",
                "--description=GhostHub Update",
                "--no-block",
                "--on-active=3s",
                "/bin/bash",
                script_path,
                "--no-self-update",
                "--update",
            ]
            if force_update:
                systemd_cmd.append("--force-update")

            result = subprocess.run(
                systemd_cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("Update scheduled via systemd-run: %s", result.stdout)
                return {
                    'success': True,
                    'message': (
                        "Update process scheduled. The system will restart in a few seconds."
                        + (
                            " (Force update enabled - binaries will be refreshed.)"
                            if force_update else ""
                        )
                    ),
                }

            error_msg = result.stderr.strip() or "Unknown error scheduling update"
            logger.error(
                "systemd-run failed (exit %s): %s",
                result.returncode,
                error_msg,
            )
            return {
                'success': False,
                'error': f'Failed to schedule update: {error_msg}',
            }, 500
        except subprocess.TimeoutExpired:
            logger.error("Timeout while scheduling update")
            return {'success': False, 'error': 'Timeout while scheduling update'}, 500
        except Exception as exc:
            logger.error("Error initiating update: %s", exc)
            return {'success': False, 'error': str(exc)}, 500

    def restart_ghosthub(self):
        """Schedule GhostHub service restart."""
        try:
            systemd_cmd = [
                "sudo",
                "systemd-run",
                "--unit=ghosthub-service-restart",
                "--description=GhostHub Service Restart",
                "--no-block",
                "--on-active=2s",
                "/bin/systemctl",
                "restart",
                "ghosthub.service",
            ]

            logger.info("Admin initiated GhostHub service restart.")
            result = subprocess.run(
                systemd_cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("Restart scheduled via systemd-run: %s", result.stdout)
                return {
                    'success': True,
                    'message': (
                        "GhostHub successfully scheduled a restart. "
                        "The system will be back online in about 15-30 seconds."
                    ),
                }

            error_msg = result.stderr.strip() or "Unknown error scheduling restart"
            logger.error(
                "systemd-run restart failed (exit %s): %s",
                result.returncode,
                error_msg,
            )
            if Config.ENV == 'development' or os.name == 'nt':
                return {
                    'success': False,
                    'error': (
                        "Restart not available in this environment. "
                        "Please manually restart the application."
                    ),
                }, 400

            return {
                'success': False,
                'error': f'Failed to schedule restart: {error_msg}',
            }, 500
        except Exception as exc:
            logger.error("Error initiating restart: %s", exc)
            return {'success': False, 'error': str(exc)}, 500

    def hdmi_status(self):
        """Get HDMI connection and kiosk status."""
        try:
            from specter import registry
            status = registry.require('hdmi_runtime_service').get_status()
            return {
                'connected': status['hdmi_connected'],
                'kiosk_running': status['kiosk_running'],
                'casting_active': status['casting_active'],
                'pending_shutdown': status.get('pending_shutdown', False),
                'in_idle_mode': status.get('in_idle_mode', False),
                'in_shutdown_countdown': status.get('in_shutdown_countdown', False),
                'shutdown_remaining': status.get('shutdown_remaining'),
            }
        except Exception as exc:
            logger.error("Error getting HDMI status: %s", exc)
            return {
                'connected': False,
                'kiosk_running': False,
                'error': str(exc),
            }, 500

    def get_wifi_config(self):
        """Get current WiFi AP configuration."""
        try:
            config, error = get_wifi_config()
            if error:
                return {'config': config, 'warning': error}
            return {'config': config}
        except Exception as exc:
            logger.error("Error getting WiFi config: %s", exc)
            return {'error': str(exc)}, 500

    def save_wifi_config(self):
        """Save WiFi AP configuration."""
        try:
            payload = self.schema('wifi_config').require(expect_json())
            if all(
                payload.get(key) is None
                for key in ('ssid', 'password', 'channel', 'country_code')
            ):
                return {
                    'error': (
                        "At least one field (ssid, password, channel, country_code) "
                        "is required"
                    ),
                }, 400

            success, message = save_wifi_config(
                ssid=payload.get('ssid'),
                password=payload.get('password'),
                channel=payload.get('channel'),
                country_code=payload.get('country_code'),
            )
            if success:
                return {'success': True, 'message': message}
            return {'success': False, 'error': message}, 400
        except ValueError as exc:
            return {'error': f'Invalid value: {str(exc)}'}, 400
        except Exception as exc:
            logger.error("Error saving WiFi config: %s", exc)
            return {'error': str(exc)}, 500

    def get_wifi_status(self):
        """Get WiFi AP status."""
        try:
            return get_wifi_status()
        except Exception as exc:
            logger.error("Error getting WiFi status: %s", exc)
            return {'error': str(exc)}, 500

    def get_system_stats(self):
        """Get system statistics for Pi monitoring."""
        try:
            return system_stats_service.get_all_stats()
        except Exception as exc:
            logger.error("Error getting system stats: %s", exc)
            return {'error': str(exc)}, 500

    def _github_repo(self):
        return os.environ.get("GITHUB_REPO", "BleedingXiko/GhostHub").strip("/")

    def _latest_github_release(self):
        response = requests.get(
            f"https://api.github.com/repos/{self._github_repo()}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=8,
            verify=self._ssl_verify(),
        )
        response.raise_for_status()
        return response.json()

    def _parse_release_version(self, tag_name):
        match = re.fullmatch(r"v?([0-9]+\.[0-9]+\.[0-9]+)", tag_name or "")
        if not match:
            raise ValueError(f"Release tag is not semver: {tag_name}")
        return match.group(1)

    def _release_asset_url(self, release, asset_name):
        for asset in release.get("assets", []):
            if asset.get("name") == asset_name and asset.get("browser_download_url"):
                return asset["browser_download_url"]
        tag_name = release.get("tag_name")
        if not tag_name:
            raise ValueError("GitHub release did not include a tag name.")
        return (
            f"https://github.com/{self._github_repo()}/releases/download/"
            f"{tag_name}/{asset_name}"
        )

    def _resolve_update_script_path(self):
        release = self._latest_github_release()
        script_url = self._release_asset_url(release, "install_ghosthub.sh")
        script_path = None

        with requests.get(
            script_url,
            stream=True,
            timeout=20,
            verify=self._ssl_verify(),
        ) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                prefix="ghosthub_install_",
                suffix=".sh",
                dir="/tmp",
            ) as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
                script_path = tmp.name

        first_line = ""
        if os.path.exists(script_path):
            with open(script_path, "rb") as handle:
                first_line = handle.readline().decode("utf-8", errors="replace")
        if not first_line.startswith("#!"):
            raise ValueError("Installer did not look like a script")
        os.chmod(script_path, 0o755)
        return script_path

    def _ssl_verify(self):
        candidates = []
        try:
            import certifi

            candidates.append(certifi.where())
        except Exception:
            pass
        candidates.extend([
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
        ])
        for path in candidates:
            if os.path.isfile(path):
                return path
        return True

    def _semver_tuple(self, version):
        return tuple(int(part) for part in version.split("."))
