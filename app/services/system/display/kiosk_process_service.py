"""Kiosk process control ownership."""

import logging
import subprocess

import gevent

from app.services.system.display.hdmi_detection_service import wake_tv_via_cec

logger = logging.getLogger(__name__)


def check_kiosk_status():
    """Return True when the kiosk service is active."""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', '--quiet', 'ghosthub-kiosk'],
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def start_kiosk(*, cec_enabled=False):
    """Start the kiosk service."""
    logger.info("[KIOSK] Starting GhostHub Kiosk service...")
    if check_kiosk_status():
        logger.info("[KIOSK] Service already running")
        return True

    try:
        cec_attempted = wake_tv_via_cec(cec_enabled)
        if cec_attempted:
            logger.info("[KIOSK] CEC wake command sent, waiting 5s...")
            gevent.sleep(5)

        logger.info("[KIOSK] Executing: sudo systemctl start ghosthub-kiosk")
        result = subprocess.run(
            ['sudo', 'systemctl', 'start', 'ghosthub-kiosk'],
            check=False,
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.error(
                "[KIOSK] Start failed (code %s): %s",
                result.returncode,
                result.stderr.decode().strip(),
            )
            try:
                status_res = subprocess.run(
                    ['systemctl', 'status', 'ghosthub-kiosk'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                logger.error("[KIOSK] Detailed status:\n%s", status_res.stdout)
            except Exception:
                pass

        gevent.sleep(2)
        kiosk_running = check_kiosk_status()
        if kiosk_running:
            logger.info("[KIOSK] Service started successfully")
            return True

        logger.error("[KIOSK] Service failed to reach 'active' state")
        return False
    except Exception as err:
        logger.error("[KIOSK] Unexpected error starting service: %s", err)
        return False


def stop_kiosk():
    """Stop the kiosk service."""
    try:
        logger.info("[KIOSK] Stopping GhostHub Kiosk service...")
        result = subprocess.run(
            ['sudo', 'systemctl', 'stop', 'ghosthub-kiosk'],
            check=False,
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning(
                "[KIOSK] Stop command returned code %s: %s",
                result.returncode,
                result.stderr.decode().strip(),
            )

        kiosk_running = check_kiosk_status()
        if not kiosk_running:
            logger.info("[KIOSK] Service stopped successfully")
            return True

        logger.error("[KIOSK] Service still 'active' after stop command")
        return False
    except Exception as err:
        logger.error("[KIOSK] Unexpected error stopping service: %s", err)
        return False


def restart_kiosk():
    """Restart the kiosk service after HDMI reconnect or runtime recovery."""
    try:
        logger.info("[KIOSK] Restarting GhostHub Kiosk service...")
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'ghosthub-kiosk'],
            check=False,
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning(
                "[KIOSK] Restart command returned code %s: %s",
                result.returncode,
                result.stderr.decode().strip(),
            )
        return check_kiosk_status()
    except Exception as err:
        logger.error("[KIOSK] Unexpected error restarting service: %s", err)
        return False
