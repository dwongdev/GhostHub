"""Headscale mesh and Tailscale connectivity ownership."""

import logging
import os
import socket
import subprocess
from typing import Dict, Optional

import gevent

from app.services.system.headscale.access_service import generate_preauth_key
from app.services.system.headscale.cli_service import (
    HS_CONFIG,
    HS_SERVICE_NAME,
    run_hs_command,
    yaml,
)

logger = logging.getLogger(__name__)


def get_remote_server_url(pi_ip: Optional[str] = None) -> Optional[str]:
    """Return the Pi's mesh-reachable Headscale control URL."""
    mesh_ip = pi_ip or get_pi_tailscale_ip()
    if mesh_ip:
        return f"http://{mesh_ip}:8080"
    return None


def update_dns_record():
    """Update mesh app DNS records to point at the Pi's real Tailscale IP."""
    if yaml is None:
        logger.error("PyYAML module not available for DNS updates")
        return False
    try:
        logger.info("Waiting for Tailscale IP assignment...")
        pi_ip = None
        for attempt in range(6):
            gevent.sleep(0.3)
            pi_ip = get_pi_tailscale_ip()
            if pi_ip:
                logger.info("Got Tailscale IP: %s", pi_ip)
                break
            logger.info("Attempt %s/6: Waiting for Tailscale IP...", attempt + 1)

        if not pi_ip:
            logger.error("Could not get Pi's Tailscale IP after multiple attempts")
            return False

        with open(HS_CONFIG, 'r') as config_file:
            config = yaml.safe_load(config_file) or {}

        if 'dns_config' not in config:
            config['dns_config'] = {}

        current_records = config['dns_config'].get('extra_records', [])
        desired_records = {
            'ghosthub.mesh.local': {"name": "ghosthub.mesh.local", "type": "A", "value": pi_ip},
            'ghosthub': {"name": "ghosthub", "type": "A", "value": pi_ip},
        }

        updated_records = []
        seen_names = set()
        changed = False
        for record in current_records:
            name = record.get('name')
            if name in desired_records:
                desired = desired_records[name]
                updated_records.append(desired)
                seen_names.add(name)
                if record != desired:
                    changed = True
            else:
                updated_records.append(record)

        for name, desired in desired_records.items():
            if name not in seen_names:
                updated_records.append(desired)
                changed = True

        if not changed:
            logger.info("Headscale DNS already synced to %s", pi_ip)
            return True

        config['dns_config']['extra_records'] = updated_records

        with open(HS_CONFIG, 'w') as config_file:
            yaml.dump(config, config_file, default_flow_style=False)

        reload_success = False
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "reload", HS_SERVICE_NAME],
                check=False,
                timeout=2,
            )
            reload_success = result.returncode == 0
            if reload_success:
                logger.info("Headscale config reloaded")
        except Exception as err:
            logger.warning("Headscale reload failed: %s", err)

        if not reload_success:
            try:
                subprocess.run(
                    ["sudo", "systemctl", "restart", HS_SERVICE_NAME],
                    check=False,
                    timeout=10,
                )
                reload_success = is_hs_running()
                if reload_success:
                    logger.info("Headscale restarted to apply DNS changes")
            except Exception as err:
                logger.warning("Headscale restart failed after DNS update: %s", err)

        return reload_success
    except Exception as err:
        logger.error("Failed to update DNS record: %s", err)
        return False


def is_hs_running() -> bool:
    """Check if a Headscale process is listening on the local mesh port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            return sock.connect_ex(('127.0.0.1', 8080)) == 0
    except Exception:
        return False


def is_hs_healthy() -> bool:
    """Check if Headscale is running and responding to API calls."""
    if not is_hs_running():
        return False
    try:
        success, _ = run_hs_command(["users", "list"])
        return success
    except Exception:
        return False


def get_pi_tailscale_ip() -> Optional[str]:
    """Get the Pi's Tailscale IPv4 address."""
    try:
        proc = subprocess.Popen(
            ["tailscale", "ip", "-4"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
        )
        stdout, stderr = proc.communicate(timeout=5)
        if proc.returncode == 0:
            ip = stdout.strip()
            if ip and ip.startswith('100.'):
                logger.info("Found Tailscale IP: %s", ip)
                return ip
            logger.debug("Tailscale returned non-100.x IP or empty: '%s'", ip)
        else:
            logger.debug("Tailscale ip command failed with code %s: %s", proc.returncode, stderr)
    except Exception as err:
        logger.debug("Error getting Tailscale IP: %s", err)
    return None


def verify_tailscale_connectivity() -> bool:
    """Verify Tailscale is connected and has assigned the Pi an IP."""
    try:
        status_data = _get_tailscale_status()
        backend_state = status_data.get("BackendState")
        if backend_state == "Running":
            pi_ip = get_pi_tailscale_ip()
            if pi_ip:
                logger.info("Tailscale connectivity verified: %s, IP: %s", backend_state, pi_ip)
                return True
            logger.warning("Tailscale state is %s but no IP assigned", backend_state)
        else:
            logger.warning("Tailscale backend state: %s", backend_state)
    except Exception as err:
        logger.error("Error checking Tailscale connectivity: %s", err)
    return False


def join_pi_to_mesh(progress_cb=None):
    """Have the Pi join its own Headscale mesh network so it's remotely reachable.

    Args:
        progress_cb: Optional ``(stage, message)`` callable for granular status.
    """
    def _progress(message):
        if progress_cb:
            progress_cb("joining", message)

    try:
        ts_check = subprocess.run(["which", "tailscale"], capture_output=True, text=True, timeout=5)
        if ts_check.returncode != 0:
            logger.warning("Tailscale client not installed - Pi won't be reachable via mesh")
            return False

        server_url = None
        if os.path.exists(HS_CONFIG) and yaml is not None:
            try:
                with open(HS_CONFIG, 'r') as config_file:
                    config = yaml.safe_load(config_file)
                    server_url = config.get('server_url')
            except Exception:
                pass

        if not server_url:
            logger.error("Could not determine Headscale server URL")
            return False

        _progress("Checking Tailscale status...")
        status_data = _get_tailscale_status()
        backend_state = status_data.get("BackendState")
        login_server = status_data.get("LoginServer", "")
        pi_ip = get_pi_tailscale_ip()
        already_connected = backend_state == "Running" and pi_ip
        expected_login_servers = {"http://127.0.0.1:8080", server_url}

        if already_connected:
            if login_server and login_server not in expected_login_servers:
                logger.warning(
                    "Tailscale is Running with IP %s but login server differs (%s). Keeping current session to avoid disruption.",
                    pi_ip,
                    login_server,
                )
            else:
                logger.info("Tailscale already connected with valid login server; skipping re-auth.")
            update_dns_record()
            return True

        if backend_state == "Running" and not pi_ip:
            _progress("Waiting for Tailscale IP assignment...")
            logger.warning("Tailscale backend is Running but no IP yet; waiting before re-auth.")
            for _ in range(4):
                gevent.sleep(1)
                pi_ip = get_pi_tailscale_ip()
                if pi_ip:
                    logger.info("Tailscale IP became available without re-auth: %s", pi_ip)
                    update_dns_record()
                    return True

        should_clear_auth = backend_state in {"NeedsLogin", "Stopped", "NoState", ""}
        if should_clear_auth:
            _progress("Clearing stale auth state...")
            logger.info(
                "Clearing Tailscale auth state before joining mesh (backend state: %s)",
                backend_state,
            )
            proc = subprocess.Popen(
                ["sudo", "tailscale", "logout"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
            )
            stdout, _ = proc.communicate(timeout=15)
            logger.debug("Logout result: %s", stdout)
            gevent.sleep(1)

        success, output = run_hs_command(["users", "create", "ghosthub"])
        if not success and "already exists" not in output:
            logger.warning("Could not create user ghosthub, may already exist: %s", output)

        _progress("Waiting for Headscale API...")
        logger.info("Waiting for Headscale API to be ready...")
        api_ready = False
        for api_check in range(5):
            gevent.sleep(0.5)
            if is_hs_healthy():
                logger.info("Headscale API ready after %.1fs", (api_check + 1) * 0.5)
                api_ready = True
                break
        if not api_ready:
            logger.warning(
                "Headscale API not responding, attempting preauth key generation anyway...",
            )

        _progress("Generating mesh preauth key...")
        preauth_key = None
        for attempt in range(3):
            preauth_key = generate_preauth_key(user="ghosthub")
            if preauth_key:
                logger.info("Preauth key generated successfully on attempt %s", attempt + 1)
                break
            wait_time = 1
            logger.warning(
                "Preauth key generation attempt %s/3 failed, retrying in %ss...",
                attempt + 1,
                wait_time,
            )
            gevent.sleep(wait_time)

        if not preauth_key:
            logger.error("Failed to generate preauth key for Pi to join mesh after 3 attempts")
            logger.error("Check Headscale logs for details")
            return False

        _progress("Connecting Pi to mesh network...")
        join_server_url = "http://127.0.0.1:8080"
        up_cmd = [
            "sudo", "tailscale", "up",
            "--login-server", join_server_url,
            "--authkey", preauth_key,
            "--hostname", "ghosthub",
            "--accept-routes=false",
            "--accept-dns=false",
        ]
        if should_clear_auth:
            up_cmd.append("--force-reauth")

        proc = subprocess.Popen(
            up_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
        )
        stdout, stderr = proc.communicate(timeout=45)
        if proc.returncode != 0:
            logger.error("Failed to join mesh. Return code: %s", proc.returncode)
            logger.error("Stderr: %s", stderr)
            logger.error("Stdout: %s", stdout)
            return False

        logger.info("Tailscale up command succeeded")
        status_proc = subprocess.Popen(
            ["tailscale", "status"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
        )
        status_stdout, _ = status_proc.communicate(timeout=10)
        logger.info("Tailscale status after 'up': %s", status_stdout)

        _progress("Verifying mesh IP assignment...")
        for verify_attempt in range(8):
            gevent.sleep(1)
            pi_ip = get_pi_tailscale_ip()
            if pi_ip:
                logger.info("Pi successfully joined mesh network with IP: %s", pi_ip)
                dns_success = update_dns_record()
                if dns_success:
                    logger.info("DNS updated successfully - ghosthub.mesh.local is ready")
                return True
            logger.info(
                "Verification attempt %s/8: Waiting for IP assignment...",
                verify_attempt + 1,
            )

        logger.error("Tailscale up succeeded but Pi did not receive an IP address")
        status_proc = subprocess.Popen(
            ["tailscale", "status"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
        )
        status_stdout, _ = status_proc.communicate(timeout=10)
        logger.error("Final Tailscale status: %s", status_stdout)
        return False
    except Exception as err:
        logger.error("Error joining Pi to mesh: %s", err)
        return False


def manual_dns_update():
    """Manually trigger DNS update for ghosthub.mesh.local."""
    logger.info("Manual DNS update triggered")
    return update_dns_record()


def _get_tailscale_status() -> Dict:
    """Fetch Tailscale status data as JSON."""
    try:
        proc = subprocess.Popen(
            ["tailscale", "status", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
        )
        stdout, stderr = proc.communicate(timeout=10)
        if proc.returncode == 0 and stdout.strip():
            import json

            return json.loads(stdout)
        if stderr:
            logger.debug("Tailscale status error output: %s", stderr)
    except Exception as err:
        logger.debug("Error fetching Tailscale status: %s", err)
    return {}
