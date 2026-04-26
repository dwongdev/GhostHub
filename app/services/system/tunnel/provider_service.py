"""Tunnel provider command ownership for Cloudflare and Pinggy."""

import logging
import subprocess
import sys

import gevent
from app.services.system.tunnel.url_capture_service import collect_process_output_lines

from app.services.system.tunnel.binary_service import (
    ensure_pinggy_ssh_key,
    find_cloudflared_path,
)
from app.services.system.tunnel.process_service import (
    get_process_tunnel_status,
    get_running_process_tunnel,
    register_process_tunnel,
    stop_process_tunnel,
)
from app.services.system.tunnel.state_service import replace_active_tunnel_info

logger = logging.getLogger(__name__)


def _read_process_startup_output(process, output_lines):
    """Capture any remaining startup output after a fast process exit."""
    lines = list(output_lines or [])

    try:
        stdout, stderr = process.communicate(timeout=1)
    except Exception:
        stdout, stderr = '', ''

    for chunk in (stdout, stderr):
        if not chunk:
            continue
        for line in chunk.splitlines():
            line = line.strip()
            if line and line not in lines:
                lines.append(line)

    return "\n".join(lines)


def start_cloudflare_tunnel(cloudflared_path, port):
    """Start a Cloudflare tunnel for the requested local port."""
    active_info = get_running_process_tunnel()
    if active_info:
        return {
            "status": "error",
            "message": (
                f"Another tunnel ({active_info.get('provider', 'unknown')}) is already running."
            ),
        }

    if not cloudflared_path:
        logger.warning("cloudflared executable not found.")
        return {"status": "error", "message": "cloudflared executable not found."}

    try:
        logger.info("Starting Cloudflare Tunnel for port %s", port)
        command = [
            cloudflared_path,
            "tunnel",
            "--url",
            f"http://localhost:{port}/",
            "--loglevel",
            "info",
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            close_fds=True,
        )

        output_lines = []
        collect_process_output_lines(process, output_lines, label_prefix='Cloudflare')
        gevent.sleep(2)

        current_output = "\n".join(output_lines)
        if process.poll() is not None:
            current_output = _read_process_startup_output(process, output_lines)
            logger.error("Cloudflare tunnel exited during startup: %s", current_output or 'no output')
            replace_active_tunnel_info()
            message = current_output or "cloudflared exited during startup."
            return {"status": "error", "message": message}

        register_process_tunnel("cloudflare", process, port)
        return {
            "status": "success",
            "message": "Cloudflare Tunnel starting. URL will be available shortly.",
        }
    except Exception as err:
        logger.error("Error starting Cloudflare Tunnel: %s", err)
        replace_active_tunnel_info()
        return {"status": "error", "message": f"Error starting Cloudflare Tunnel: {err}"}


def start_pinggy_tunnel(port, token):
    """Start a Pinggy tunnel for the requested local port."""
    active_info = get_running_process_tunnel()
    if active_info:
        return {
            "status": "error",
            "message": (
                f"Another tunnel ({active_info.get('provider', 'unknown')}) is already running."
            ),
        }

    if not token:
        logger.warning("No Pinggy access token provided")
        return {"status": "error", "message": "Pinggy token is required."}

    try:
        logger.info("Starting Pinggy Tunnel for port %s", port)
        ensure_pinggy_ssh_key()
        command = [
            "ssh", "-p", "443",
            f"-R0:127.0.0.1:{port}",
            "-L4300:127.0.0.1:4300",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            f"{token}@pro.pinggy.io",
        ]
        logger.info("Executing Pinggy SSH tunnel command")

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            close_fds=True,
            creationflags=creation_flags,
        )

        error_patterns = [
            "Permission denied",
            "Connection refused",
            "Could not resolve hostname",
            "Authentication failed",
        ]
        output_lines = []

        collect_process_output_lines(process, output_lines, label_prefix='Pinggy')
        gevent.sleep(3)

        current_output = "\n".join(output_lines)
        for pattern in error_patterns:
            if pattern.lower() in current_output.lower():
                pinggy_error = f"Pinggy error: '{pattern}' detected."
                if process.poll() is None:
                    process.terminate()
                logger.error(pinggy_error)
                return {"status": "error", "message": pinggy_error}

        register_process_tunnel("pinggy", process, port)
        return {
            "status": "success",
            "message": "Pinggy Tunnel starting. URL will be available shortly.",
        }
    except FileNotFoundError:
        logger.error("SSH client not found")
        return {
            "status": "error",
            "message": "'ssh' command not found. Make sure SSH client is installed and in your PATH.",
        }
    except Exception as err:
        logger.error("Error starting Pinggy Tunnel: %s", err)
        if 'process' in locals() and process:
            process.kill()
        replace_active_tunnel_info()
        return {"status": "error", "message": f"Error starting Pinggy Tunnel: {err}"}
