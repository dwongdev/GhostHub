"""Headscale node, preauth, and client-access ownership."""

import base64
import io
import json
import logging
from typing import Dict, List, Optional, Tuple

from app.services.system.headscale.cli_service import run_hs_command

logger = logging.getLogger(__name__)


def generate_preauth_key(user: str = None, tags: list = None) -> Optional[str]:
    """Generate a pre-auth key for joining clients with dynamic user support."""
    del tags
    if user is None:
        user = "local"

    success, output = run_hs_command(
        ["preauthkeys", "create", "-u", user, "--reusable", "--expiration", "24h"],
    )
    if success:
        return output
    return None


def generate_tailscale_qr_code(server_url: str, preauth_key: str) -> Optional[str]:
    """Generate a QR code the Tailscale app can scan for a custom server login."""
    try:
        import qrcode
    except ImportError:
        logger.warning("qrcode module not available")
        return None

    if not server_url or not preauth_key:
        return None

    qr_data = f"tailscale://login?server={server_url}&key={preauth_key}"
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as err:
        logger.error("Error generating Tailscale QR code: %s", err)
        return None


def delete_node(node_id: int) -> Tuple[bool, str]:
    """Delete a node from Headscale and ensure it's fully disconnected."""
    success, message = run_hs_command(["nodes", "delete", "-i", str(node_id), "--force"])
    if success:
        logger.info("Successfully deleted node %s from Headscale mesh", node_id)
    else:
        logger.error("Failed to delete node %s: %s", node_id, message)
    return success, message


def get_all_nodes() -> List[Dict]:
    """Get all mesh nodes including offline ones."""
    success, output = run_hs_command(["nodes", "list", "-o", "json"])
    if not success:
        return []
    try:
        return json.loads(output)
    except Exception:
        return []


def get_nodes() -> List[Dict]:
    """Get actually connected nodes."""
    all_nodes = get_all_nodes()
    connected_nodes = []
    for node in all_nodes:
        if node.get('online', False) and node.get('ip_addresses'):
            connected_nodes.append(node)
    return connected_nodes


def register_node(node_key: str, user: str = "local") -> Tuple[bool, str]:
    """Register a pending node by its node key."""
    key = node_key.strip()
    if not key.startswith("nodekey:") and not key.startswith("mkey:"):
        key = f"nodekey:{key}"
    return run_hs_command(["nodes", "register", "--user", user, "--key", key])


def get_pending_nodes() -> List[str]:
    """Pending node registration requests are not exposed by Headscale today."""
    return []


def generate_client_preauth_key(client_info: dict = None) -> Tuple[str, str]:
    """Generate a preauth key for a client with a stable shared Headscale user."""
    username = "local"
    if client_info:
        device_type = client_info.get('device_type', 'unknown')
        platform = client_info.get('platform', 'unknown')
        tags = [f"device:{device_type}", f"platform:{platform}"]
    else:
        tags = ["device:client"]

    preauth_key = generate_preauth_key(user=username, tags=tags)
    if preauth_key:
        return username, preauth_key
    return None, None


def register_node_from_url(registration_input: str, user: str = "local") -> Tuple[bool, str]:
    """Register a node from pasted user input or a copied registration URL."""
    try:
        raw = registration_input.strip()
        if "nodekey:" in raw:
            key = "nodekey:" + raw.split("nodekey:")[1].split()[0].split("?")[0].split("/")[0]
        elif "mkey:" in raw:
            key = "mkey:" + raw.split("mkey:")[1].split()[0].split("?")[0].split("/")[0]
        else:
            key = raw.split()[0]
        return register_node(key, user=user)
    except Exception as err:
        return False, f"Failed to parse key: {str(err)}"
