"""
GhostStream WebSocket Client
----------------------------
Real-time WebSocket connection to GhostStream for efficient progress updates.
Uses job subscriptions to minimize traffic and handles heartbeat automatically.
"""

import asyncio
import json
import logging
import gevent
from gevent.lock import BoundedSemaphore
from gevent.event import Event as GeventEvent
import time
from typing import Optional, Dict, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from specter import registry

logger = logging.getLogger(__name__)

# Try to import websockets, fall back gracefully if not available
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("websockets package not installed - GhostStream real-time updates disabled")


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class GhostStreamWSClient:
    """
    WebSocket client for real-time GhostStream progress updates.
    
    Features:
    - Auto-reconnection with exponential backoff
    - Job subscription filtering (only receive updates for subscribed jobs)
    - Automatic ping/pong heartbeat handling
    - Thread-safe job subscription management
    - Callbacks for progress/status updates
    """
    
    server_url: str = ""
    state: ConnectionState = ConnectionState.DISCONNECTED
    subscribed_jobs: Set[str] = field(default_factory=set)
    
    # Callbacks
    on_progress: Optional[Callable[[str, Dict], None]] = None
    on_status_change: Optional[Callable[[str, str], None]] = None
    on_connect: Optional[Callable[[], None]] = None
    on_disconnect: Optional[Callable[[], None]] = None
    
    # Internal state
    _ws: Any = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread = None
    _stop_event: GeventEvent = field(default_factory=GeventEvent)
    _lock: BoundedSemaphore = field(default_factory=lambda: BoundedSemaphore(1))
    _reconnect_delay: float = 1.0
    _max_reconnect_delay: float = 30.0
    _last_pong: float = field(default_factory=time.time)
    
    def __post_init__(self):
        # Already initialized by dataclass defaults, but ensuring fresh instances
        self._stop_event = GeventEvent()  # gevent-aware event
        self._lock = BoundedSemaphore(1)  # gevent-aware lock
        self.subscribed_jobs = set()
    
    def connect(self, server_host: str, server_port: int, owner=None) -> bool:
        """
        Connect to a GhostStream server's WebSocket endpoint.
        Runs under a Specter-owned greenlet.
        """
        if not HAS_WEBSOCKETS:
            logger.warning("[GhostStream WS] websockets package not installed")
            return False
        
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            logger.debug("[GhostStream WS] Already connected/connecting")
            return True
        
        self.server_url = f"ws://{server_host}:{server_port}/ws/progress"
        self._stop_event.clear()

        owner = owner or registry.require('ghoststream_runtime')
        self._thread = owner.spawn(self._run_loop, label='ghoststream-ws-loop')

        logger.info(f"[GhostStream WS] Connecting to {self.server_url}")
        return True
    
    def disconnect(self):
        """Disconnect from WebSocket server."""
        self._stop_event.set()
        self.state = ConnectionState.DISCONNECTED
        
        if self._thread and not self._thread.dead:
            gevent.joinall([self._thread], timeout=2.0)
            if not self._thread.dead:
                self._thread.kill()
        
        self._thread = None
        self._ws = None
        logger.info("[GhostStream WS] Disconnected")
    
    def subscribe_job(self, job_id: str):
        """Subscribe to updates for a specific job."""
        with self._lock:
            self.subscribed_jobs.add(job_id)
        
        # Send subscribe message if connected
        if self.state == ConnectionState.CONNECTED and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe([job_id]),
                self._loop
            )
        
        logger.debug(f"[GhostStream WS] Subscribed to job {job_id}")
    
    def unsubscribe_job(self, job_id: str):
        """Unsubscribe from updates for a specific job."""
        with self._lock:
            self.subscribed_jobs.discard(job_id)
        
        # Send unsubscribe message if connected
        if self.state == ConnectionState.CONNECTED and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_unsubscribe([job_id]),
                self._loop
            )
        
        logger.debug(f"[GhostStream WS] Unsubscribed from job {job_id}")
    
    def _run_loop(self):
        """Run the async event loop in background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._connection_loop())
        except Exception as e:
            logger.error(f"[GhostStream WS] Event loop error: {e}")
        finally:
            self._loop.close()
            self._loop = None
    
    async def _connection_loop(self):
        """Main connection loop with auto-reconnection."""
        while not self._stop_event.is_set():
            try:
                self.state = ConnectionState.CONNECTING
                
                async with websockets.connect(
                    self.server_url,
                    ping_interval=None,  # We handle pings manually
                    close_timeout=5
                ) as ws:
                    self._ws = ws
                    self.state = ConnectionState.CONNECTED
                    self._reconnect_delay = 1.0  # Reset backoff on successful connect
                    self._last_pong = time.time()
                    
                    logger.info(f"[GhostStream WS] Connected to {self.server_url}")
                    
                    # Notify callback
                    if self.on_connect:
                        try:
                            self.on_connect()
                        except Exception as e:
                            logger.error(f"[GhostStream WS] on_connect callback error: {e}")
                    
                    # Re-subscribe to all tracked jobs
                    with self._lock:
                        if self.subscribed_jobs:
                            await self._send_subscribe(list(self.subscribed_jobs))
                    
                    # Start message handler
                    await self._message_loop(ws)
                    
            except ConnectionClosed as e:
                logger.warning(f"[GhostStream WS] Connection closed: {e}")
            except Exception as e:
                logger.warning(f"[GhostStream WS] Connection error: {e}")
            
            # Handle disconnect
            self._ws = None
            if self.state != ConnectionState.DISCONNECTED:
                self.state = ConnectionState.RECONNECTING
                
                if self.on_disconnect:
                    try:
                        self.on_disconnect()
                    except Exception as e:
                        logger.error(f"[GhostStream WS] on_disconnect callback error: {e}")
            
            # Wait before reconnecting (with exponential backoff)
            if not self._stop_event.is_set():
                logger.info(f"[GhostStream WS] Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
    
    async def _message_loop(self, ws):
        """Handle incoming WebSocket messages."""
        try:
            async for message in ws:
                if self._stop_event.is_set():
                    break
                
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    if msg_type == "ping":
                        # Respond to server ping
                        await ws.send(json.dumps({"type": "pong", "ts": time.time()}))
                        
                    elif msg_type == "pong":
                        # Server responded to our ping
                        self._last_pong = time.time()
                        
                    elif msg_type == "progress":
                        # Job progress update
                        job_id = data.get("job_id")
                        progress_data = data.get("data", {})
                        
                        if self.on_progress:
                            try:
                                self.on_progress(job_id, progress_data)
                            except Exception as e:
                                logger.error(f"[GhostStream WS] on_progress callback error: {e}")
                        
                    elif msg_type == "status_change":
                        # Job status change
                        job_id = data.get("job_id")
                        status = data.get("data", {}).get("status")
                        
                        if self.on_status_change:
                            try:
                                self.on_status_change(job_id, status)
                            except Exception as e:
                                logger.error(f"[GhostStream WS] on_status_change callback error: {e}")
                        
                        # Auto-unsubscribe from completed jobs
                        if status in ("ready", "error", "cancelled"):
                            with self._lock:
                                self.subscribed_jobs.discard(job_id)
                                
                except json.JSONDecodeError:
                    logger.debug(f"[GhostStream WS] Invalid JSON: {message[:100]}")
                except Exception as e:
                    logger.error(f"[GhostStream WS] Message handling error: {e}")
                    
        except ConnectionClosed:
            raise
        except Exception as e:
            logger.error(f"[GhostStream WS] Message loop error: {e}")
    
    async def _send_subscribe(self, job_ids: list):
        """Send subscribe message to server."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "type": "subscribe",
                    "job_ids": job_ids
                }))
                logger.debug(f"[GhostStream WS] Sent subscribe for {len(job_ids)} jobs")
            except Exception as e:
                logger.error(f"[GhostStream WS] Failed to send subscribe: {e}")
    
    async def _send_unsubscribe(self, job_ids: list):
        """Send unsubscribe message to server."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "type": "unsubscribe",
                    "job_ids": job_ids
                }))
            except Exception as e:
                logger.error(f"[GhostStream WS] Failed to send unsubscribe: {e}")


def get_ws_client() -> Optional[GhostStreamWSClient]:
    """Get the global WebSocket client instance."""
    from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

    if not HAS_WEBSOCKETS:
        return None

    lock = ghoststream_runtime_store.access(lambda state: state["discovery_lock"])
    with lock:
        client = ghoststream_runtime_store.get('client')
        if client is None:
            client = GhostStreamWSClient()
            ghoststream_runtime_store.set({'client': client})
        return client


def connect_to_server(host: str, port: int, 
                      on_progress: Callable[[str, Dict], None] = None,
                      on_status_change: Callable[[str, str], None] = None,
                      owner=None) -> bool:
    """
    Connect to a GhostStream server's WebSocket endpoint.
    
    Args:
        host: Server hostname/IP
        port: Server port
        on_progress: Callback for progress updates (job_id, progress_data)
        on_status_change: Callback for status changes (job_id, status)
    
    Returns:
        True if connection initiated successfully
    """
    client = get_ws_client()
    if client is None:
        return False
    
    client.on_progress = on_progress
    client.on_status_change = on_status_change
    
    return client.connect(host, port, owner=owner)


def disconnect():
    """Disconnect from GhostStream WebSocket."""
    client = get_ws_client()
    if client:
        client.disconnect()


def subscribe_job(job_id: str):
    """Subscribe to real-time updates for a job."""
    client = get_ws_client()
    if client:
        client.subscribe_job(job_id)


def unsubscribe_job(job_id: str):
    """Unsubscribe from updates for a job."""
    client = get_ws_client()
    if client:
        client.unsubscribe_job(job_id)


def is_connected() -> bool:
    """Check if WebSocket is connected."""
    client = get_ws_client()
    return client is not None and client.state == ConnectionState.CONNECTED
