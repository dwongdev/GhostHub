"""Process-backed tunnel lifecycle ownership."""

import logging
import subprocess

from app.services.system.tunnel.state_service import (
    get_active_tunnel_info,
    replace_active_tunnel_info,
)
from app.services.system.tunnel.url_capture_service import capture_process_tunnel_url

logger = logging.getLogger(__name__)


def get_running_process_tunnel():
    """Return active tunnel info when a process-backed tunnel is still running."""
    active_info = get_active_tunnel_info()
    process = active_info.get("process")
    if process and process.poll() is None:
        return active_info
    return None


def register_process_tunnel(provider, process, local_port):
    """Claim tunnel runtime ownership for a running process-backed tunnel."""
    replace_active_tunnel_info({
        "provider": provider,
        "process": process,
        "url": None,
        "local_port": local_port,
    })
    capture_process_tunnel_url(provider, process)
    logger.info("%s tunnel process started", provider.capitalize())


def stop_process_tunnel():
    """Terminate an active process-backed tunnel and reset state."""
    active_info = get_active_tunnel_info()
    provider = active_info.get("provider", "Unknown")
    process = active_info.get("process")

    if not process:
        logger.info("No active tunnel process found to stop")
        return {"status": "success", "message": "No active tunnel to stop."}

    if process.poll() is None:
        logger.info("Terminating %s tunnel process (PID: %s)", provider, process.pid)
        try:
            process.terminate()
            process.wait(timeout=5)
            logger.info("%s tunnel terminated gracefully", provider)
        except subprocess.TimeoutExpired:
            logger.warning("%s tunnel did not terminate gracefully, killing process", provider)
            process.kill()
            logger.info("%s tunnel process killed", provider)
        except Exception as err:
            logger.error("Error terminating %s tunnel: %s", provider, err)
    else:
        logger.info("%s tunnel process already stopped", provider)

    replace_active_tunnel_info()
    return {"status": "success", "message": f"{provider} tunnel stopped."}


def get_process_tunnel_status():
    """Return status for the active process-backed tunnel."""
    active_info = get_active_tunnel_info()
    process = active_info.get("process")
    if process and process.poll() is None:
        return {
            "status": "running",
            "provider": active_info.get("provider"),
            "url": active_info.get("url"),
            "local_port": active_info.get("local_port"),
        }

    if active_info.get("provider"):
        logger.info("Detected stopped tunnel, cleaning up state")
        stop_process_tunnel()

    return {
        "status": "stopped",
        "provider": None,
        "url": None,
        "local_port": None,
    }
