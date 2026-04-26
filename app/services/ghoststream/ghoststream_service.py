"""
GhostStream Service
------------------
Flask service wrapper for GhostStream transcoding integration.
Provides synchronous interface for the async GhostStream client.

Now with real-time WebSocket support for efficient progress updates.
"""
import logging
import gevent
import time
import os
from typing import Optional, Dict, List, Any, Callable

from .ghoststream_runtime_store import ghoststream_runtime_store

logger = logging.getLogger(__name__)

# UDP broadcast port for discovery fallback
UDP_DISCOVERY_PORT = 8766
UDP_DISCOVERY_TIMEOUT = 3.0

def _ghoststream_runtime_access(reader):
    """Read GhostStream runtime state atomically."""
    return ghoststream_runtime_store.access(reader)


def _update_ghoststream_runtime(mutator):
    """Mutate GhostStream runtime state atomically."""
    return ghoststream_runtime_store.update(mutator)


def _get_discovery_lock():
    """Return the shared discovery transition lock."""
    return _ghoststream_runtime_access(lambda state: state["discovery_lock"])


def _get_progress_callbacks() -> List[Callable[[str, Dict], None]]:
    """Return a snapshot of registered progress callbacks."""
    return _ghoststream_runtime_access(
        lambda state: list(state.get("progress_callbacks", []))
    )


def _get_status_callbacks() -> List[Callable[[str, str], None]]:
    """Return a snapshot of registered status callbacks."""
    return _ghoststream_runtime_access(
        lambda state: list(state.get("status_callbacks", []))
    )

def _remember_job_server(job_id: str, server_name: Optional[str]) -> None:
    """Record which GhostStream server owns a job."""
    if not job_id or not server_name:
        return

    def mutate(state):
        job_servers = dict(state.get("job_servers", {}))
        job_servers[job_id] = server_name
        state["job_servers"] = job_servers

    _update_ghoststream_runtime(mutate)


def _forget_job_server(job_id: str) -> None:
    """Drop GhostStream server ownership for a job."""
    if not job_id:
        return

    def mutate(state):
        job_servers = dict(state.get("job_servers", {}))
        job_servers.pop(job_id, None)
        state["job_servers"] = job_servers

    _update_ghoststream_runtime(mutate)


def _get_job_server_name(job_id: str) -> Optional[str]:
    """Get the recorded GhostStream server name for a job."""
    return _ghoststream_runtime_access(
        lambda state: state.get("job_servers", {}).get(job_id)
    )


def _resolve_job_server(job_id: str):
    """Resolve the GhostStream server that owns a job."""
    client = _get_client()
    if client is None:
        return None

    server_name = _get_job_server_name(job_id)
    if server_name:
        server = client.get_server(server_name)
        if server is not None:
            return server

    resolved_server = client.resolve_job_server(job_id)
    if resolved_server is not None:
        _remember_job_server(job_id, resolved_server.name)
        return resolved_server

    return None


def get_job_auth_headers(job_id: str) -> Dict[str, str]:
    """Return per-job GhostStream auth headers when available."""
    client = _get_client()
    if client is None:
        return {}

    server = _resolve_job_server(job_id)
    return client.get_job_auth_headers(job_id, server=server)


def track_job(session_id: str, job_id: str, server_name: Optional[str] = None):
    """Track a job for a session (for cleanup when session ends)."""
    def mutate(state):
        active_jobs = {
            sid: set(job_ids)
            for sid, job_ids in state.get("active_jobs", {}).items()
        }
        session_jobs = active_jobs.setdefault(session_id, set())
        session_jobs.add(job_id)
        state["active_jobs"] = active_jobs

    _update_ghoststream_runtime(mutate)
    _remember_job_server(job_id, server_name)
    logger.debug(f"[GhostStream] Tracking job {job_id} for session {session_id}")
    
    # Subscribe to WebSocket updates for this job
    _subscribe_job_ws(job_id)

def untrack_job(session_id: str, job_id: str):
    """Remove job from session tracking."""
    def mutate(state):
        active_jobs = {
            sid: set(job_ids)
            for sid, job_ids in state.get("active_jobs", {}).items()
        }
        session_jobs = active_jobs.get(session_id)
        if session_jobs is None:
            state["active_jobs"] = active_jobs
            return

        session_jobs.discard(job_id)
        if not session_jobs:
            active_jobs.pop(session_id, None)

        state["active_jobs"] = active_jobs

    _update_ghoststream_runtime(mutate)
    _forget_job_server(job_id)
    
    # Unsubscribe from WebSocket updates
    _unsubscribe_job_ws(job_id)

def cleanup_session_jobs(session_id: str):
    """Cancel all active jobs for a session (called on disconnect)."""
    removed_job_ids = {}

    def mutate(state):
        active_jobs = {
            sid: set(job_ids)
            for sid, job_ids in state.get("active_jobs", {}).items()
        }
        removed_job_ids["job_ids"] = set(active_jobs.pop(session_id, set()))
        state["active_jobs"] = active_jobs

    _update_ghoststream_runtime(mutate)
    job_ids = removed_job_ids.get("job_ids", set())
    
    if job_ids:
        logger.info(f"[GhostStream] Cleaning up {len(job_ids)} jobs for session {session_id}")
        for job_id in job_ids:
            try:
                cancel_job(job_id)
            except Exception as e:
                logger.warning(f"[GhostStream] Failed to cancel job {job_id}: {e}")
            finally:
                _forget_job_server(job_id)

def get_session_jobs(session_id: str) -> List[str]:
    """Get all active job IDs for a session."""
    return _ghoststream_runtime_access(
        lambda state: list(state.get("active_jobs", {}).get(session_id, set()))
    )

def _set_last_error(msg: str):
    """Set the last error message."""
    _update_ghoststream_runtime(lambda state: state.update({"last_error": msg}))
    logger.error(f"[GhostStream] {msg}")


# =============================================================================
# WebSocket Integration for Real-Time Updates
# =============================================================================

def _subscribe_job_ws(job_id: str):
    """Subscribe to WebSocket updates for a job."""
    try:
        from . import ghoststream_ws
        ghoststream_ws.subscribe_job(job_id)
    except Exception as e:
        logger.debug(f"[GhostStream WS] Subscribe error: {e}")


def _unsubscribe_job_ws(job_id: str):
    """Unsubscribe from WebSocket updates for a job."""
    try:
        from . import ghoststream_ws
        ghoststream_ws.unsubscribe_job(job_id)
    except Exception as e:
        logger.debug(f"[GhostStream WS] Unsubscribe error: {e}")


def _on_ws_progress(job_id: str, progress_data: Dict):
    """Handle WebSocket progress update - forward to registered callbacks."""
    for callback in _get_progress_callbacks():
        try:
            callback(job_id, progress_data)
        except Exception as e:
            logger.error(f"[GhostStream WS] Progress callback error: {e}")


def _on_ws_status_change(job_id: str, status: str):
    """Handle WebSocket status change - forward to registered callbacks."""
    for callback in _get_status_callbacks():
        try:
            callback(job_id, status)
        except Exception as e:
            logger.error(f"[GhostStream WS] Status callback error: {e}")


def connect_websocket(host: str, port: int) -> bool:
    """
    Connect to GhostStream WebSocket for real-time updates.
    
    Args:
        host: Server hostname/IP
        port: Server port
    
    Returns:
        True if connection initiated
    """
    try:
        from . import ghoststream_ws
        
        success = ghoststream_ws.connect_to_server(
            host, port,
            on_progress=_on_ws_progress,
            on_status_change=_on_ws_status_change
        )
        
        if success:
            logger.info(f"[GhostStream] WebSocket connection initiated to {host}:{port}")
        
        return success
    except ImportError:
        logger.debug("[GhostStream] WebSocket module not available")
        return False
    except Exception as e:
        logger.warning(f"[GhostStream] WebSocket connection failed: {e}")
        return False


def disconnect_websocket():
    """Disconnect from GhostStream WebSocket."""
    try:
        from . import ghoststream_ws
        ghoststream_ws.disconnect()
    except Exception:
        pass


def register_progress_callback(callback: Callable[[str, Dict], None]):
    """
    Register a callback for real-time progress updates.
    
    Args:
        callback: Function(job_id, progress_data) called on progress updates
    """
    def mutate(state):
        callbacks = list(state.get("progress_callbacks", []))
        if callback not in callbacks:
            callbacks.append(callback)
        state["progress_callbacks"] = callbacks

    _update_ghoststream_runtime(mutate)


def unregister_progress_callback(callback: Callable[[str, Dict], None]):
    """Remove a previously registered progress callback."""
    def mutate(state):
        callbacks = [
            registered
            for registered in state.get("progress_callbacks", [])
            if registered != callback
        ]
        state["progress_callbacks"] = callbacks

    _update_ghoststream_runtime(mutate)


def register_status_callback(callback: Callable[[str, str], None]):
    """
    Register a callback for real-time status changes.
    
    Args:
        callback: Function(job_id, status) called on status changes
    """
    def mutate(state):
        callbacks = list(state.get("status_callbacks", []))
        if callback not in callbacks:
            callbacks.append(callback)
        state["status_callbacks"] = callbacks

    _update_ghoststream_runtime(mutate)


def unregister_status_callback(callback: Callable[[str, str], None]):
    """Remove a previously registered status callback."""
    def mutate(state):
        callbacks = [
            registered
            for registered in state.get("status_callbacks", [])
            if registered != callback
        ]
        state["status_callbacks"] = callbacks

    _update_ghoststream_runtime(mutate)


def is_websocket_connected() -> bool:
    """Check if WebSocket is connected for real-time updates."""
    try:
        from . import ghoststream_ws
        return ghoststream_ws.is_connected()
    except Exception:
        return False

def _get_last_error():
    """Get the last error message."""
    return _ghoststream_runtime_access(
        lambda state: state.get("last_error") or "Unknown error"
    )


def _get_client():
    """Get or create the GhostStream client."""
    client = _ghoststream_runtime_access(lambda state: state.get("client"))
    if client is not None:
        return client

    try:
        from ghoststream import ClientConfig, GhostStreamClient

        created_client = GhostStreamClient(config=ClientConfig(client_name="GhostHub"))
    except ImportError as e:
        logger.warning(f"GhostStream client not available: {e}")
        return None

    _update_ghoststream_runtime(
        lambda state: state.update({
            "client": state.get("client") or created_client,
        })
    )
    return _ghoststream_runtime_access(lambda state: state.get("client"))


def _get_load_balancer():
    """Get or create the GhostStream load balancer (shares client with standalone)."""
    load_balancer = _ghoststream_runtime_access(
        lambda state: state.get("load_balancer")
    )
    if load_balancer is not None:
        return load_balancer

    try:
        from ghoststream import GhostStreamLoadBalancer, LoadBalanceStrategy

        shared_client = _get_client()
        created_load_balancer = GhostStreamLoadBalancer(
            strategy=LoadBalanceStrategy.FASTEST,
            client=shared_client
        )
    except ImportError as e:
        logger.warning(f"GhostStream load balancer not available: {e}")
        return None

    _update_ghoststream_runtime(
        lambda state: state.update({
            "load_balancer": state.get("load_balancer") or created_load_balancer,
        })
    )
    return _ghoststream_runtime_access(lambda state: state.get("load_balancer"))


def start_discovery(owner=None):
    """Start mDNS discovery for GhostStream servers with UDP fallback."""
    with _get_discovery_lock():
        if is_discovery_started():
            logger.debug("GhostStream discovery already running")
            return True
        
        client = _get_client()
        if client is None:
            logger.warning("Cannot start discovery - GhostStream client not available (missing httpx or zeroconf?)")
            return False
        
        try:
            # Initialize load balancer FIRST to register callbacks before discovery starts
            lb = _get_load_balancer()
            if lb:
                client.add_callback(lambda event, server: _on_server_discovered(event, server, lb))

            # Start mDNS discovery on the shared client
            client.start_discovery()
            
            _update_ghoststream_runtime(
                lambda state: state.update({"discovery_started": True})
            )
            logger.info("GhostStream mDNS discovery started - listening for _ghoststream._tcp.local.")
            
            # Start UDP broadcast discovery as fallback under the runtime owner.
            if owner is None:
                from specter import registry

                owner = registry.require('ghoststream_runtime')
            owner.spawn(_udp_discovery_loop, label='ghoststream-udp-discovery')
            
            logger.info("GhostStream servers will auto-connect via mDNS, UDP broadcast, or registration")
            return True
        except Exception as e:
            logger.error(f"Failed to start GhostStream discovery: {e}", exc_info=True)
            return False


def _udp_discovery_loop():
    """Background thread for UDP broadcast discovery fallback."""
    import socket
    
    logger.info(f"[GhostStream] Starting UDP discovery on port {UDP_DISCOVERY_PORT}")
    
    while is_discovery_started():
        try:
            # Send broadcast looking for GhostStream servers
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(UDP_DISCOVERY_TIMEOUT)
            
            # Send discovery message
            message = b'GHOSTSTREAM_DISCOVER'
            sock.sendto(message, ('<broadcast>', UDP_DISCOVERY_PORT))
            
            # Wait for responses
            try:
                while True:
                    data, addr = sock.recvfrom(1024)
                    if data.startswith(b'GHOSTSTREAM_ANNOUNCE:'):
                        # Parse response: GHOSTSTREAM_ANNOUNCE:port:version:hw_accels
                        parts = data.decode().split(':')
                        if len(parts) >= 2:
                            port = int(parts[1])
                            version = parts[2] if len(parts) > 2 else ''
                            hw_accels = parts[3].split(',') if len(parts) > 3 else []
                            
                            address = f"{addr[0]}:{port}"
                            client = _get_client()
                            
                            # Check if we already have this server
                            server_name = f"ghoststream_{addr[0].replace('.', '_')}"
                            if client and server_name not in client.servers:
                                logger.info(f"[GhostStream] UDP discovered server at {address}")
                                add_manual_server(address, version=version, hw_accels=hw_accels)
            except socket.timeout:
                pass  # No more responses
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"[GhostStream] UDP discovery error: {e}")
        
        # Wait before next discovery attempt
        gevent.sleep(10)


def _on_server_discovered(event: str, server, lb):
    """Handle server discovery events for load balancer stats."""
    from ghoststream import ServerStats
    if event == "found" and server.name not in lb.server_stats:
        lb.server_stats[server.name] = ServerStats()
        # Connect WebSocket to newly discovered server
        connect_websocket(server.host, server.port)
    elif event == "removed" and server.name in lb.server_stats:
        del lb.server_stats[server.name]


def stop_discovery():
    """Stop mDNS discovery."""
    with _get_discovery_lock():
        client = _get_client()
        if client:
            client.stop_discovery()
        
        _update_ghoststream_runtime(
            lambda state: state.update({"discovery_started": False})
        )
        logger.info("GhostStream discovery stopped")


def is_discovery_started() -> bool:
    """Return whether GhostStream discovery has been started."""
    return _ghoststream_runtime_access(
        lambda state: bool(state.get("discovery_started"))
    )


def add_manual_server(
    address: str,
    name: Optional[str] = None,
    version: Optional[str] = None,
    hw_accels: Optional[List[str]] = None,
    save_to_config: bool = True,
    ghosthub_callback_url: Optional[str] = None
) -> bool:
    """
    Add a manual server address (fallback if mDNS discovery doesn't find it).
    
    Args:
        address: Server address in format "host:port" (e.g., "192.168.4.2:8765")
        name: Optional friendly name for the server
        version: Optional version string
        hw_accels: Optional list of hardware accelerators
        save_to_config: Whether to persist to config file
        ghosthub_callback_url: The URL GhostStream used to reach GhostHub (for source URLs)
    """
    try:
        from ghoststream import GhostStreamServer, ServerStats
        
        host, port = address.split(":")
        server_name = name or f"ghoststream_{host}"
        
        server = GhostStreamServer(
            name=server_name,
            host=host,
            port=int(port),
            version=version or "",
            hw_accels=hw_accels or []
        )
        
        # Add to shared client (used by both standalone and load balancer)
        client = _get_client()
        if client is None:
            logger.error("No GhostStream client available")
            return False
        
        client.servers[server_name] = server
        if client.preferred_server is None:
            client.preferred_server = server_name
        
        # Add stats for load balancer
        lb = _get_load_balancer()
        if lb is not None:
            lb.server_stats[server_name] = ServerStats()
        
        # Store the callback URL if provided
        if ghosthub_callback_url:
            def mutate(state):
                callback_urls = dict(state.get("server_callback_urls", {}))
                callback_urls[server_name] = ghosthub_callback_url
                state["server_callback_urls"] = callback_urls

            _update_ghoststream_runtime(mutate)
            logger.info(f"[GhostStream] Stored callback URL for {server_name}: {ghosthub_callback_url}")

        connect_websocket(server.host, server.port)

        logger.info(f"Added GhostStream server: {address}")
        return True
    except Exception as e:
        logger.error(f"Failed to add manual server {address}: {e}", exc_info=True)
        return False


def get_server_callback_url(server_name: Optional[str] = None) -> Optional[str]:
    """
    Get the GhostHub callback URL for a server.
    
    This is the URL that GhostStream used to reach GhostHub during registration.
    Use this URL for source files so GhostStream can actually fetch them.
    
    Args:
        server_name: Server name, or None for preferred server
    
    Returns:
        The callback URL, or None if not set
    """
    if server_name is None:
        client = _get_client()
        if client and client.preferred_server:
            server_name = client.preferred_server
    
    if server_name:
        return _ghoststream_runtime_access(
            lambda state: state.get("server_callback_urls", {}).get(server_name)
        )
    return None


def remove_server(server_name: str) -> bool:
    """
    Remove a GhostStream server.
    
    Args:
        server_name: Name of the server to remove
    """
    try:
        client = _get_client()
        if client is None:
            return False
        
        if server_name in client.servers:
            del client.servers[server_name]
            
            # Update preferred server if needed
            if client.preferred_server == server_name:
                client.preferred_server = next(iter(client.servers.keys()), None)
            
            # Remove from load balancer stats
            lb = _get_load_balancer()
            if lb and server_name in lb.server_stats:
                del lb.server_stats[server_name]
            
            # Remove callback URL
            def mutate(state):
                callback_urls = dict(state.get("server_callback_urls", {}))
                callback_urls.pop(server_name, None)
                state["server_callback_urls"] = callback_urls

            _update_ghoststream_runtime(mutate)
            
            logger.info(f"[GhostStream] Removed server: {server_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to remove server {server_name}: {e}")
        return False


def cleanup_unreachable_servers() -> int:
    """
    Remove servers that are unreachable.
    Returns the number of servers removed.
    
    Uses a short timeout since this is called on every status check.
    Servers are auto-discovered so we don't persist unreachable ones.
    """
    client = _get_client()
    if client is None:
        return 0
    
    removed = 0
    servers_to_remove = []
    
    for name, server in list(client.servers.items()):
        # Use client's health check (uses pooled connection)
        if not client.health_check(server):
            servers_to_remove.append(name)
            logger.debug(f"[GhostStream] Server {name} unreachable, marking for removal")
    
    for name in servers_to_remove:
        if remove_server(name):
            removed += 1
    
    if removed > 0:
        logger.info(f"[GhostStream] Cleaned up {removed} unreachable server(s)")
    
    return removed


def is_available() -> bool:
    """Check if any GhostStream server is available."""
    client = _get_client()
    return client is not None and client.is_available()


def get_servers() -> List[Dict]:
    """Get list of all discovered/configured servers."""
    client = _get_client()
    if client is None:
        return []
    
    servers = []
    for server in client.get_all_servers():
        servers.append({
            "name": server.name,
            "host": server.host,
            "port": server.port,
            "base_url": server.base_url,
            "version": server.version,
            "hw_accels": server.hw_accels,
            "video_codecs": server.video_codecs,
            "has_hw_accel": server.has_hw_accel,
            "max_jobs": server.max_jobs
        })
    
    return servers


def get_preferred_server() -> Optional[Dict]:
    """Get the currently preferred server."""
    client = _get_client()
    if client is None:
        return None
    
    server = client.get_server()
    if server is None:
        return None
    
    return {
        "name": server.name,
        "host": server.host,
        "port": server.port,
        "base_url": server.base_url,
        "has_hw_accel": server.has_hw_accel
    }


def health_check(server_name: Optional[str] = None) -> bool:
    """Check if a server is healthy (synchronous)."""
    client = _get_client()
    if client is None:
        return False
    
    server = client.get_server(server_name) if server_name else client.get_server()
    return client.health_check(server)


def get_capabilities(server_name: Optional[str] = None) -> Optional[Dict]:
    """Get server capabilities (synchronous)."""
    client = _get_client()
    if client is None:
        return None
    
    server = client.get_server(server_name) if server_name else client.get_server()
    return client.get_capabilities(server)


def transcode(
    source: str,
    mode: str = "stream",
    format: str = "hls",
    video_codec: str = "h264",
    audio_codec: str = "aac",
    resolution: str = "original",
    bitrate: str = "auto",
    hw_accel: str = "auto",
    start_time: float = 0,
    use_load_balancer: bool = None,  # None = auto-detect based on server count
    # New options
    tone_map: bool = True,
    two_pass: bool = False,
    max_audio_channels: int = 2,
    abr: bool = False,
    session_id: str = None,
    subtitles: Optional[List[Dict]] = None
) -> Optional[Dict]:
    """
    Start a transcoding job (synchronous - gevent compatible).
    
    Args:
        source: URL of the source video
        mode: "stream" (single HLS), "abr" (adaptive bitrate), or "batch"
        format: Output format (hls, mp4, webm, mkv)
        video_codec: Video codec (h264, h265, vp9, av1, copy)
        audio_codec: Audio codec (aac, opus, mp3, copy)
        resolution: Target resolution (4k, 1080p, 720p, 480p, original)
        bitrate: Target bitrate ("auto" or specific like "8M")
        hw_accel: Hardware acceleration ("auto", "nvenc", "qsv", "software")
        start_time: Start position in seconds
        use_load_balancer: Whether to use load balancing (None = auto-detect)
        tone_map: Convert HDR to SDR automatically (default True)
        two_pass: Use two-pass encoding for batch mode
        max_audio_channels: Max audio channels (2=stereo, 6=5.1)
        subtitles: List of subtitle track dictionaries to mux into HLS
    """
    logger.info(f"[GhostStream] Transcode request: source={source[:100]}..., mode={mode}, resolution={resolution}")
    if subtitles:
        logger.info(f"[GhostStream] Including {len(subtitles)} subtitle tracks")
    
    client = _get_client()
    if client is None:
        return {"error": "GhostStream not configured. Install dependency: pip install ghoststream"}
    
    if len(client.servers) == 0:
        return {"error": "No GhostStream servers found. Add a server in Settings."}
    
    # Auto-detect load balancing: use it when we have 2+ servers
    if use_load_balancer is None:
        use_load_balancer = len(client.servers) >= 2
        if use_load_balancer:
            logger.info(f"[GhostStream] Auto-enabling load balancing ({len(client.servers)} servers detected)")
    
    # If ABR is enabled, switch mode to "abr" for adaptive bitrate streaming
    effective_mode = "abr" if abr else mode
    
    # Select server using load balancer or direct
    selected_server = None
    if use_load_balancer:
        lb = _get_load_balancer()
        if lb:
            # Use load balancer's sync-compatible selection
            from ghoststream import ServerStats
            # Get healthy servers
            healthy_servers = [
                (name, server) for name, server in client.servers.items()
                if name in lb.server_stats and lb.server_stats[name].is_healthy
            ]
            if not healthy_servers:
                healthy_servers = [(name, server) for name, server in client.servers.items()]
            
            if healthy_servers:
                # Use FASTEST strategy: prefer HW accel, then least busy
                hw_servers = [(n, s) for n, s in healthy_servers if s.has_hw_accel]
                if hw_servers:
                    # Pick least busy HW server
                    best = min(hw_servers, key=lambda x: lb.server_stats[x[0]].active_jobs)
                    selected_server = best[1]
                    logger.info(f"[GhostStream] Load balancer selected: {best[0]} (HW accel, {lb.server_stats[best[0]].active_jobs} jobs)")
                else:
                    # Pick least busy software server
                    best = min(healthy_servers, key=lambda x: lb.server_stats[x[0]].active_jobs)
                    selected_server = best[1]
                    logger.info(f"[GhostStream] Load balancer selected: {best[0]} ({lb.server_stats[best[0]].active_jobs} jobs)")
    
    # Use client's sync method with connection pooling and retry logic
    if selected_server is None:
        selected_server = client.get_server()

    job = client.transcode(
        source=source,
        mode=effective_mode,
        format=format,
        video_codec=video_codec,
        audio_codec=audio_codec,
        resolution=resolution,
        bitrate=bitrate,
        hw_accel=hw_accel,
        start_time=start_time,
        tone_map=tone_map,
        two_pass=two_pass,
        max_audio_channels=max_audio_channels,
        session_id=session_id,
        server=selected_server
    )
    
    if job is None:
        return {"error": "Transcode request failed"}
    
    # Check for error status
    if job.status.value == "error":
        _set_last_error(job.error_message or "Unknown error")
        return {"error": job.error_message or "Transcode failed"}
    
    job_id = job.job_id
    logger.info(f"[GhostStream] Job created: {job_id}")
    logger.info(f"[GhostStream] Raw response stream_url: {job.stream_url}")
    logger.info(f"[GhostStream] Raw response status: {job.status.value}")
    
    # Track which server handled this job
    server_name = None
    if selected_server:
        for name, srv in client.servers.items():
            if srv.host == selected_server.host and srv.port == selected_server.port:
                server_name = name
                # Update load balancer stats
                lb = _get_load_balancer()
                if lb and name in lb.server_stats:
                    lb.server_stats[name].active_jobs += 1
                break
    
    # Track job for session cleanup and WebSocket subscription
    if session_id and job_id and job_id != "error":
        track_job(session_id, job_id, server_name=server_name)
    elif job_id and job_id != "error":
        _remember_job_server(job_id, server_name)
        _subscribe_job_ws(job_id)
    
    # Convert stream_url to use GhostHub proxy - browsers can't access GhostStream directly
    stream_url = _convert_to_proxy_url(job.stream_url)
    logger.info(f"[GhostStream] Stream URL: {job.stream_url} -> proxy: {stream_url}")
    
    return {
        "job_id": job_id,
        "status": job.status.value,
        "progress": job.progress,
        "stream_url": stream_url,
        "download_url": job.download_url,
        "hw_accel_used": job.hw_accel_used,
        "server_name": server_name,
        "server_host": selected_server.host if selected_server else None
    }


def get_job_status(job_id: str) -> Optional[Dict]:
    """Get the status of a transcoding job (synchronous)."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return None

    server = _resolve_job_server(job_id)
    job = client.get_job_status(job_id, server) if server else client.get_job_status(job_id)
    if job is None:
        return None
    
    logger.debug(f"[GhostStream] Job status: {job.job_id} -> {job.status.value}")
    
    # Convert stream_url to use GhostHub proxy
    stream_url = _convert_to_proxy_url(job.stream_url)
    
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress,
        "stream_url": stream_url,
        "download_url": job.download_url,
        "error_message": job.error_message,
        "hw_accel_used": job.hw_accel_used
    }


def cancel_job(job_id: str) -> bool:
    """Cancel a transcoding job (synchronous)."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return False

    server = _resolve_job_server(job_id)
    success = client.cancel_job(job_id, server) if server else client.cancel_job(job_id)
    if success:
        _forget_job_server(job_id)
    return success


def cancel_all_jobs() -> int:
    """Cancel all active transcoding jobs on all servers (synchronous)."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return 0
    
    cancelled = 0
    
    for server in client.servers.values():
        try:
            # Get all jobs using the pooled client
            response = client._request_with_retry(
                "GET",
                f"{server.base_url}/api/transcode/jobs"
            )
            
            if response.status_code == 200:
                jobs = response.json().get("jobs", [])
                for job in jobs:
                    if job.get("status") in ["queued", "processing"]:
                        if client.cancel_job(job["job_id"], server):
                            cancelled += 1
        except Exception as e:
            logger.warning(f"[GhostStream] Failed to cancel jobs on {server.name}: {e}")
    
    # Also clear local tracking
    _update_ghoststream_runtime(
        lambda state: state.update({"active_jobs": {}, "job_servers": {}})
    )
    
    logger.info(f"[GhostStream] Cancelled {cancelled} jobs")
    return cancelled


def delete_job(job_id: str) -> bool:
    """Delete a transcoding job and clean up its temp files (synchronous)."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return False

    server = _resolve_job_server(job_id)
    success = client.delete_job(job_id, server) if server else client.delete_job(job_id)
    if success:
        _forget_job_server(job_id)
    return success


def get_cleanup_stats() -> Optional[Dict]:
    """Get cleanup statistics from GhostStream server."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return None
    
    server = client.get_server()
    if not server:
        return None
    
    try:
        response = client._request_with_retry(
            "GET",
            f"{server.base_url}/api/cleanup/stats"
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"[GhostStream] Failed to get cleanup stats: {e}")
    
    return None


def run_cleanup() -> Optional[Dict]:
    """Manually trigger cleanup on GhostStream server."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return None
    
    server = client.get_server()
    if not server:
        return None
    
    try:
        response = client._request_with_retry(
            "POST",
            f"{server.base_url}/api/cleanup/run"
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"[GhostStream] Failed to run cleanup: {e}")
    
    return None


def wait_for_ready(job_id: str, timeout: float = 60) -> Optional[Dict]:
    """Wait for a job to be ready for streaming (synchronous)."""
    start = time.time()
    while time.time() - start < timeout:
        status = get_job_status(job_id)
        if status:
            if status["status"] in ("ready", "error", "cancelled"):
                return status
        gevent.sleep(1)

    return None


def get_status_summary() -> Dict:
    """Get a summary of GhostStream status for the UI.
    
    FAST: Returns immediately with current server list.
    Cleanup happens in background, not blocking the UI.
    """
    client = _get_client()
    lb = _get_load_balancer()
    
    if client is None:
        return {
            "available": False,
            "reason": "GhostStream client not installed (missing ghoststream package)",
            "servers": [],
            "discovery_started": False
        }
    
    # DON'T block on cleanup - just return what we have
    # Unreachable servers will be cleaned up when actually used (transcode fails)
    # This makes the status check instant instead of 10+ seconds
    
    servers = get_servers()
    preferred = get_preferred_server()
    
    # Skip capabilities fetch - it's slow and not needed for status display
    # User can get capabilities separately if needed
    
    # Get load balancer stats (local, fast)
    lb_stats = None
    if lb:
        lb_stats = lb.get_server_stats()
    
    return {
        "available": len(servers) > 0,  # Fast check - just see if we have servers
        "discovery_started": is_discovery_started(),
        "server_count": len(servers),
        "servers": servers,
        "preferred_server": preferred,
        "capabilities": None,  # Skipped for speed
        "load_balancer_stats": lb_stats
    }


def _convert_to_proxy_url(stream_url: Optional[str]) -> Optional[str]:
    """
    Convert a direct GhostStream stream URL to use GhostHub's proxy.
    
    This is critical for HLS playback - browsers can't access GhostStream directly
    due to CORS/network issues, so we proxy through GhostHub.
    
    Args:
        stream_url: Direct GhostStream URL like "http://192.168.4.2:8765/stream/job123/master.m3u8"
    
    Returns:
        Proxy URL like "/api/ghoststream/stream/job123/master.m3u8"
    """
    if not stream_url:
        return None
    
    import re
    # Match pattern: http://host:port/stream/job_id/filename
    match = re.search(r'/stream/([^/]+)/(.+)$', stream_url)
    if match:
        job_id = match.group(1)
        filename = match.group(2)
        proxy_url = f"/api/ghoststream/stream/{job_id}/{filename}"
        logger.debug(f"[GhostStream] Converted {stream_url} -> {proxy_url}")
        return proxy_url
    
    # If pattern doesn't match, return original (shouldn't happen)
    logger.warning(f"[GhostStream] Could not convert stream URL to proxy: {stream_url}")
    return stream_url


def get_stream_proxy_target(job_id: str, filename: str) -> Optional[str]:
    """Get the upstream GhostStream stream URL for a proxied HLS asset."""
    client = _get_client()
    if client is None or len(client.servers) == 0:
        return None

    server = _resolve_job_server(job_id)
    if server is None:
        server = next(iter(client.servers.values()))
    return f"http://{server.host}:{server.port}/stream/{job_id}/{filename}"


def build_source_url(category_id: str, filename: str, ghosthub_base_url: str) -> str:
    """
    Build a source URL that GhostStream can access.
    
    Args:
        category_id: The category ID
        filename: The media filename
        ghosthub_base_url: GhostHub's base URL accessible from GhostStream
                          (e.g., "http://192.168.4.1:5000")
    
    Returns:
        Full URL for the media file
    """
    from urllib.parse import quote
    return f"{ghosthub_base_url}/media/{category_id}/{quote(filename)}"
