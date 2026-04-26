"""Unified system tunnel orchestration seam."""

import logging

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.system.headscale.connectivity_service import manual_dns_update
import app.services.system.network_detection_service as network_detection_service
from app.services.system.tunnel.binary_service import find_cloudflared_path
from app.services.system.tunnel.mesh_service import (
    get_mesh_tunnel_status,
    remove_mesh_node,
    start_mesh_tunnel,
    stop_mesh_tunnel,
)
from app.services.system.tunnel.process_service import (
    get_process_tunnel_status,
    stop_process_tunnel,
)
from app.services.system.tunnel.provider_service import (
    start_cloudflare_tunnel,
    start_pinggy_tunnel,
)
from app.services.system.tunnel.state_service import get_active_tunnel_info

logger = logging.getLogger(__name__)


def start_tunnel(
    provider,
    *,
    local_port=None,
    pinggy_token=None,
    wait_for_network=True,
):
    """Start the requested tunnel provider through the tunnel domain seams."""
    provider_name = str(provider or '').strip().lower()
    if not provider_name or provider_name == 'none':
        return {'status': 'error', 'message': 'No tunnel provider specified.'}, 400

    resolved_port = int(
        local_port if local_port is not None
        else get_runtime_config_value('TUNNEL_LOCAL_PORT', 5000),
    )

    if wait_for_network:
        logger.info("Checking eth0 readiness before starting %s tunnel...", provider_name)
        if not network_detection_service.wait_for_eth0(timeout=1):
            logger.info("eth0 not immediately ready; tunnel will use whatever IP is available")

    if provider_name == 'cloudflare':
        cloudflared_path = find_cloudflared_path()
        if not cloudflared_path:
            return {'status': 'error', 'message': 'cloudflared executable not found.'}, 500
        return start_cloudflare_tunnel(cloudflared_path, resolved_port)

    if provider_name == 'pinggy':
        token = pinggy_token or get_runtime_config_value('PINGGY_ACCESS_TOKEN')
        if not token:
            return {
                'status': 'error',
                'message': 'Pinggy access token not provided or configured.',
            }, 400
        return start_pinggy_tunnel(resolved_port, token)

    if provider_name == 'mesh':
        return start_mesh_tunnel()

    return {
        'status': 'error',
        'message': f'Unsupported tunnel provider: {provider_name}',
    }, 400


def stop_tunnel():
    """Stop the currently active tunnel."""
    if get_active_tunnel_info().get('provider') == 'mesh':
        return stop_mesh_tunnel()
    return stop_process_tunnel()


def get_tunnel_status():
    """Return status for the active tunnel."""
    active_info = get_active_tunnel_info()
    if active_info.get('provider') == 'mesh':
        return get_mesh_tunnel_status()
    return get_process_tunnel_status()


def remove_tunnel_node(node_id):
    """Remove a mesh node through the mesh tunnel seam."""
    return remove_mesh_node(node_id)


def update_tunnel_dns():
    """Manually trigger mesh DNS update."""
    return manual_dns_update()
