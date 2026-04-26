"""Headscale process/systemctl ownership."""

import logging
import os
import subprocess
import time

import gevent

from app.services.system.headscale.cli_service import HS_CONFIG, HS_SERVICE_NAME, INSTANCE_DIR
from app.services.system.headscale.connectivity_service import is_hs_running

logger = logging.getLogger(__name__)


def stop_running_service():
    """Stop the Headscale systemd service if it is currently running."""
    try:
        subprocess.run(["sudo", "systemctl", "stop", HS_SERVICE_NAME], check=False)
        return True
    except Exception:
        return False


def restart_service():
    """Restart the Headscale systemd service."""
    subprocess.run(["sudo", "systemctl", "restart", HS_SERVICE_NAME], check=True)
    return True


def stop_service():
    """Stop the Headscale service and bring down the local Tailscale client."""
    try:
        subprocess.run(["sudo", "tailscale", "down"], check=False, capture_output=True, timeout=2)
        subprocess.run(["sudo", "systemctl", "stop", HS_SERVICE_NAME], check=False, timeout=3)
        return True, "Headscale stopped."
    except subprocess.TimeoutExpired:
        subprocess.run(["sudo", "systemctl", "kill", HS_SERVICE_NAME], check=False)
        return True, "Headscale stopped (forced)."
    except Exception as err:
        return False, str(err)


def wait_for_running(max_wait=30):
    """Wait for Headscale to start accepting connections."""
    start_wait = time.time()
    logger.info("Waiting for Headscale to start...")
    while time.time() - start_wait < max_wait:
        if is_hs_running():
            logger.info("Headscale started after %ss", int(time.time() - start_wait))
            return True, None
        gevent.sleep(1)

    return False, get_recent_log_snippet()


def ensure_default_users(hs_binary):
    """Ensure the default Headscale users exist, waiting for API readiness."""
    from app.services.system.headscale.connectivity_service import is_hs_healthy
    for _ in range(10):
        if is_hs_healthy():
            break
        gevent.sleep(0.5)
    logger.info("Ensuring headscale users exist...")
    subprocess.run(["sudo", hs_binary, "users", "create", "ghosthub", "--config", HS_CONFIG], check=False)
    subprocess.run(["sudo", hs_binary, "users", "create", "local", "--config", HS_CONFIG], check=False)
    return True


def repair_instance_permissions():
    """Repair instance directory ownership/permissions when local writes fail."""
    subprocess.run(["sudo", "chown", "-R", "ghost:ghost", INSTANCE_DIR], check=False)
    subprocess.run(["sudo", "chmod", "-R", "755", INSTANCE_DIR], check=False)
    return True


def get_recent_log_snippet():
    """Return a short tail of the Headscale log for startup failure reporting."""
    try:
        log_path = os.path.join(INSTANCE_DIR, "headscale.log")
        if os.path.exists(log_path):
            with open(log_path, "r") as log_file:
                lines = log_file.readlines()
                return " ".join([line.strip() for line in lines[-5:]])
    except Exception:
        pass
    return ""
