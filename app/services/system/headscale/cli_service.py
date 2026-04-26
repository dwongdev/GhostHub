"""Headscale binary, path, and CLI command ownership."""

import json
import logging
import os
import shutil
import subprocess
from typing import Tuple

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None


def _find_app_root():
    """Find the GhostHub app root directory reliably."""
    # First check the standard Pi install location - this is the most reliable
    if os.path.exists("/home/ghost/ghosthub"):
        return "/home/ghost/ghosthub"
    
    # Then check for requirements.txt in typical locations
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if (
            os.path.exists(os.path.join(current, "main.py"))
            or os.path.exists(os.path.join(current, "requirements.txt"))
            or os.path.exists(os.path.join(current, "static"))
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    while True:
        parent = os.path.dirname(current)
        if parent == current:
            return current
        current = parent


APP_ROOT = _find_app_root()
INSTANCE_DIR = os.path.join(APP_ROOT, "instance", "headscale")
HS_CONFIG = os.path.join(INSTANCE_DIR, "config.yaml")
HS_DB_DIR = "/var/lib/headscale"
HS_DB = os.path.join(HS_DB_DIR, "db.sqlite")
HS_SOCKET = "/var/run/headscale/headscale.sock"
HS_SERVICE_NAME = "ghosthub-headscale"
DEFAULT_DERP_MAP_PATH = os.path.join(INSTANCE_DIR, "derpmap.json")
DEFAULT_DERP_REGION = {
    "regionID": 999,
    "regionCode": "ghosthub",
    "regionName": "GhostHub Local DERP",
    "avoid": False,
    "nodes": [
        {
            "name": "ghosthub-derp-1",
            "regionID": 999,
            "hostName": "127.0.0.1",
            "ipv4": "127.0.0.1",
            "stunPort": 3478,
            "derpPort": 3478,
            "stunOnly": False,
        }
    ],
}

HS_BINARY = None


def ensure_local_derp_map(path: str) -> bool:
    """Ensure a local DERP map exists to avoid external dependencies."""
    if os.path.exists(path):
        return True

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        derp_map = {"regions": {"999": DEFAULT_DERP_REGION}}
        with open(path, "w") as derp_file:
            json.dump(derp_map, derp_file, indent=2)
        logger.info("Created local DERP map at %s", path)
        return True
    except Exception as err:
        logger.error("Failed to create local DERP map at %s: %s", path, err)
        return False


def _find_headscale_binary():
    """Find headscale binary in common locations."""
    app_binary = os.path.join(APP_ROOT, "headscale")
    if _ensure_executable_file(app_binary):
        return app_binary

    try:
        system_binary = shutil.which("headscale")
        if _ensure_executable_file(system_binary):
            return system_binary
    except (AttributeError, OSError):
        pass

    for path in (
        "/usr/local/bin/headscale",
        "/usr/bin/headscale",
        "/home/ghost/ghosthub/headscale",
    ):
        if _ensure_executable_file(path):
            return path

    return None


def get_headscale_binary():
    """Get headscale binary path with lazy evaluation."""
    global HS_BINARY
    if HS_BINARY is None or not _is_executable_file(HS_BINARY):
        HS_BINARY = _find_headscale_binary()
    return HS_BINARY


def _is_executable_file(path):
    """Return True only for executable files, never directories."""
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def _ensure_executable_file(path):
    """Return True for executable files, attempting to repair missing exec bits."""
    if not path or not os.path.isfile(path):
        return False
    if os.access(path, os.X_OK):
        return True

    try:
        current_mode = os.stat(path).st_mode
        os.chmod(path, current_mode | 0o111)
    except OSError as err:
        logger.warning("Failed to restore execute bits on %s: %s", path, err)
        return False

    return os.access(path, os.X_OK)


def run_hs_command(args: list) -> Tuple[bool, str]:
    """Run a Headscale CLI command with sudo for socket access."""
    hs_binary = get_headscale_binary()
    if not hs_binary or not os.path.exists(hs_binary):
        return False, "Headscale binary not found."

    try:
        cmd = ["sudo", hs_binary] + args + ["--config", HS_CONFIG]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
        )
        stdout, stderr = proc.communicate(timeout=30)
        if proc.returncode == 0:
            return True, stdout.strip()
        logger.error("Headscale command failed: %s", stderr)
        return False, stderr.strip()
    except subprocess.TimeoutExpired:
        proc.kill()
        logger.error("Headscale command timed out: %s", " ".join(args))
        return False, "Command timed out"
    except Exception as err:
        logger.error("Headscale command error: %s", err)
        return False, str(err)
