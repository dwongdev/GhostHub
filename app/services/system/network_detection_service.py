# app/services/network_detection_service.py
"""
Network Detection Service
-------------------------
Detects network interface type and connection quality for clients.
Used to optimize upload chunk sizes based on connection type (AP mode, Ethernet, etc).
Optimized for 2GB RAM Raspberry Pi.
"""
import os
import re
import logging
import ipaddress
import subprocess
import requests
import socket
import psutil
import time
import gevent
from typing import Dict, Optional

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.system.platform_service import is_raspberry_pi
from app.services.system.network_detection_runtime_store import (
    network_detection_runtime_store,
)

logger = logging.getLogger(__name__)

# Default AP mode subnet (from dnsmasq/hostapd typical config)
DEFAULT_AP_SUBNET = "192.168.4.0/24"

# dnsmasq config path for parsing AP range
DNSMASQ_CONF_PATH = "/etc/dnsmasq.conf"

# Tailscale CGNAT IP range (RFC 6598)
TAILSCALE_IP_RANGE = "100.64.0.0/10"  # 100.64.0.0 - 100.127.255.255

INTERFACE_CACHE_TTL = 60.0  # 1 minute

TAILSCALE_CACHE_TTL = 300.0  # 5 minutes


def _network_detection_runtime_access(reader):
    """Read network-detection runtime state atomically."""
    return network_detection_runtime_store.access(reader)


def _update_network_detection_runtime(mutator):
    """Mutate network-detection runtime state atomically."""
    return network_detection_runtime_store.update(mutator)


def has_eth0_internet() -> bool:
    """
    Check if eth0 has actual internet connectivity.
    Binds ping to eth0 interface to ensure we're testing the right path.
    """
    if not is_raspberry_pi():
        # Fallback for non-Pi development: just check general connectivity if eth0 doesn't exist
        try:
            subprocess.run(['ping', '-c', '1', '-W', '2', '8.8.8.8'], capture_output=True, check=True)
            return True
        except Exception:
            return False

    try:
        # Check if eth0 is up first
        result = subprocess.run(['ip', 'addr', 'show', 'eth0'], capture_output=True, text=True)
        if 'state UP' not in result.stdout:
            return False

        # Ping 8.8.8.8 bound to eth0
        result = subprocess.run(
            ['ping', '-I', 'eth0', '-c', '1', '-W', '2', '8.8.8.8'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Error checking eth0 internet: {e}")
        return False


def wait_for_eth0(timeout: int = 60) -> bool:
    """
    Wait for eth0 to be up with internet connectivity.
    Used during tunnel auto-start on boot to ensure we get the correct IP (10.0.0.X instead of 192.168.1.X).

    Args:
        timeout: Maximum seconds to wait (default 60)

    Returns:
        True if eth0 is ready with internet, False if timeout reached
    """
    import time
    if os.environ.get('GHOSTHUB_TESTING') == 'true':
        return False

    logger.info(f"Waiting for eth0 to be ready (timeout: {timeout}s)...")
    start_time = time.time()
    attempt = 0

    while time.time() - start_time < timeout:
        attempt += 1

        if has_eth0_internet():
            elapsed = time.time() - start_time
            logger.info(f"eth0 is ready with internet connectivity (took {elapsed:.1f}s)")
            return True

        # Log progress every 10 seconds
        if attempt % 5 == 0:  # Every 10 seconds (5 attempts * 2s sleep)
            elapsed = time.time() - start_time
            logger.info(f"Still waiting for eth0... ({elapsed:.0f}s elapsed)")

        gevent.sleep(2)  # Check every 2 seconds

    logger.warning(f"Timeout waiting for eth0 after {timeout}s")
    return False


def get_public_ip() -> Optional[str]:
    """
    Determine the public IP address of the Pi.
    Required for Wireguard client endpoint configuration.
    """
    urls = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://v4.ident.me'
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                # Basic IP validation
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    return ip
        except Exception as e:
            logger.debug(f"Failed to fetch public IP from {url}: {e}")
            continue
            
    return None


def get_interface_ips() -> Dict[str, str]:
    """
    Get IP addresses for each network interface.
    Optimized with psutil and caching to avoid subprocess overhead.

    Returns:
        Dict mapping interface name to IP address, e.g. {'eth0': '192.168.1.100', 'wlan0': '192.168.4.1'}
    """
    now = time.time()
    cached_interfaces = _network_detection_runtime_access(
        lambda state: {
            'data': dict(state.get('interface_ips_cache', {}).get('data', {})),
            'timestamp': state.get('interface_ips_cache', {}).get('timestamp', 0.0),
        }
    )
    if now - cached_interfaces['timestamp'] < INTERFACE_CACHE_TTL:
        return cached_interfaces['data']

    interfaces = {}

    # Primary method: psutil (much faster, no fork+exec)
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            if iface == 'lo':
                continue
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces[iface] = addr.address
                    break
    except Exception as e:
        logger.debug(f"psutil.net_if_addrs failed, falling back to subprocess: {e}")

    # Fallback: existing subprocess method (only if psutil failed or returned nothing)
    if not interfaces:
        try:
            net_path = '/sys/class/net'
            if os.path.exists(net_path):
                for iface in os.listdir(net_path):
                    if iface == 'lo':
                        continue
                    try:
                        result = subprocess.run(
                            ['ip', '-4', 'addr', 'show', iface],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        for line in result.stdout.split('\n'):
                            if 'inet ' in line:
                                ip = line.strip().split()[1].split('/')[0]
                                interfaces[iface] = ip
                                break
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Subprocess fallback for interface IPs failed: {e}")

    # Update cache
    _update_network_detection_runtime(
        lambda state: state.update({
            'interface_ips_cache': {
                'data': dict(interfaces),
                'timestamp': now,
            }
        })
    )
    return interfaces


def is_ap_mode_active() -> bool:
    """Check if hostapd (WiFi AP mode) is running."""
    if not is_raspberry_pi():
        return False

    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'hostapd'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() == 'active'
    except Exception as e:
        logger.debug(f"Error checking hostapd status: {e}")
        return False


def get_ap_subnet() -> str:
    """
    Get the AP mode subnet range from dnsmasq config.
    Falls back to default 192.168.4.0/24 if not found.

    Returns:
        CIDR notation subnet string
    """
    try:
        if os.path.exists(DNSMASQ_CONF_PATH):
            with open(DNSMASQ_CONF_PATH, 'r') as f:
                content = f.read()

            # Look for dhcp-range line: dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
            match = re.search(r'dhcp-range=(\d+\.\d+\.\d+)\.\d+,', content)
            if match:
                network_prefix = match.group(1)
                return f"{network_prefix}.0/24"
    except Exception as e:
        logger.debug(f"Error parsing dnsmasq config: {e}")

    return DEFAULT_AP_SUBNET


def ip_in_subnet(ip: str, cidr: str) -> bool:
    """Check if an IP address is within a subnet."""
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False


def detect_interface_for_client(client_ip: str) -> Optional[str]:
    """
    Determine which interface a client is connected through.

    Args:
        client_ip: The client's IP address

    Returns:
        Interface name (e.g., 'eth0', 'wlan0') or None if unknown
    """
    interfaces = get_interface_ips()

    for iface_name, iface_ip in interfaces.items():
        try:
            # Get the subnet for this interface
            # Assume /24 for simplicity (covers most home networks)
            network = ipaddress.ip_network(f"{iface_ip}/24", strict=False)
            if ipaddress.ip_address(client_ip) in network:
                return iface_name
        except ValueError:
            continue

    return None


def is_tailscale_connection(client_ip: str) -> bool:
    """
    Detect if a client is connected via Tailscale/Headscale.
    Optimized with caching to handle frequent range requests.

    Tailscale uses the 100.64.0.0/10 CGNAT IP range (RFC 6598).
    This range is 100.64.0.0 - 100.127.255.255.

    Args:
        client_ip: The client's IP address

    Returns:
        True if client is connected via Tailscale/Headscale
    """
    now = time.time()
    cached_entry = _network_detection_runtime_access(
        lambda state: state.get('tailscale_cache', {}).get(client_ip)
    )
    if cached_entry is not None:
        cached_val, timestamp = cached_entry
        if now - timestamp < TAILSCALE_CACHE_TTL:
            return cached_val

    result = False
    try:
        # Check if IP is in Tailscale CGNAT range
        if ip_in_subnet(client_ip, TAILSCALE_IP_RANGE):
            logger.debug(f"Client {client_ip} detected as Tailscale (CGNAT range)")
            result = True
        else:
            # Also check if any interface has "tailscale" or "headscale" in name
            interfaces = get_interface_ips()
            for iface_name, iface_ip in interfaces.items():
                if 'tailscale' in iface_name.lower() or 'headscale' in iface_name.lower():
                    # Check if client is in same /24 as Tailscale interface
                    try:
                        network = ipaddress.ip_network(f"{iface_ip}/24", strict=False)
                        if ipaddress.ip_address(client_ip) in network:
                            logger.debug(f"Client {client_ip} detected as Tailscale (interface {iface_name})")
                            result = True
                            break
                    except ValueError:
                        continue

    except Exception as e:
        logger.debug(f"Error detecting Tailscale connection: {e}")
        result = False

    # Prune cache if it gets too large (>1000 IPs)
    def mutate(state):
        tailscale_cache = dict(state.get('tailscale_cache', {}))
        if len(tailscale_cache) > 1000:
            tailscale_cache.clear()
        tailscale_cache[client_ip] = (result, now)
        state['tailscale_cache'] = tailscale_cache

    _update_network_detection_runtime(mutate)
    return result


def is_mobile_user_agent(user_agent: str) -> bool:
    """Check if user agent indicates a mobile device."""
    if not user_agent:
        return False

    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    ua_lower = user_agent.lower()
    return any(keyword in ua_lower for keyword in mobile_keywords)


def get_client_connection_type(client_ip: str, user_agent: str = None) -> Dict:
    """
    Analyze client connection and return optimal upload settings.
    Hardware-aware: considers Pi RAM tier for concurrency and chunk size limits.

    Args:
        client_ip: The client's IP address
        user_agent: Optional user agent string for mobile detection

    Returns:
        Dict with connection info and recommended chunk size
    """
    from app.services.system.system_stats_service import get_hardware_tier
    
    tier = get_hardware_tier()
    
    result = {
        'client_ip': client_ip,
        'interface': 'unknown',
        'connection_type': 'unknown',
        'tier': 'medium',  # Default to medium
        'chunk_size': get_runtime_config_value('UPLOAD_CHUNK_SIZE_MEDIUM'),
        'max_concurrent_chunks': 2, # Default for LITE/2GB
        'is_raspberry_pi': is_raspberry_pi(),
        'is_mobile': False,
        'hardware_tier': tier
    }

    # Set concurrency based on hardware
    if tier == 'PRO':
        result['max_concurrent_chunks'] = 6
    elif tier == 'STANDARD':
        result['max_concurrent_chunks'] = 4
    else:
        result['max_concurrent_chunks'] = 2

    # Check for localhost/loopback
    if client_ip in ('127.0.0.1', '::1', 'localhost'):
        result['interface'] = 'localhost'
        result['connection_type'] = 'local'
        result['tier'] = 'fast'
        result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_FAST')
        # Local uploads can handle more concurrency if hardware permits
        if tier == 'PRO': result['max_concurrent_chunks'] = 8
        return result

    # Check for Tailscale/Headscale connection (high latency, needs small chunks)
    if is_tailscale_connection(client_ip):
        result['interface'] = 'tailscale'
        result['connection_type'] = 'tailscale'
        result['tier'] = 'tailscale'
        result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_TAILSCALE')
        # Tailscale adds latency, so use moderate concurrency
        if tier == 'PRO':
            result['max_concurrent_chunks'] = 4
        elif tier == 'STANDARD':
            result['max_concurrent_chunks'] = 3
        else:
            result['max_concurrent_chunks'] = 2
        logger.info(f"Tailscale client detected: {client_ip}, chunk_size={result['chunk_size']}")
        return result

    # Detect mobile
    if user_agent:
        result['is_mobile'] = is_mobile_user_agent(user_agent)

    # Determine which interface the client is on
    detected_interface = detect_interface_for_client(client_ip)
    if detected_interface:
        result['interface'] = detected_interface

    # Check if client is on AP mode subnet
    ap_active = is_ap_mode_active()
    ap_subnet = get_ap_subnet()

    if ap_active and ip_in_subnet(client_ip, ap_subnet):
        # Client is connected via WiFi AP
        result['connection_type'] = 'ap_mode'
        result['interface'] = 'wlan0'

        if result['is_mobile']:
            # Mobile on AP = slowest tier
            result['tier'] = 'slow'
            result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_SLOW')
            result['max_concurrent_chunks'] = 1
        else:
            # Desktop on AP = medium tier
            result['tier'] = 'medium'
            result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_MEDIUM')
            # concurrency already set by hardware tier

    elif detected_interface == 'eth0':
        # Client is on Ethernet network - boost concurrency (Ethernet can handle it)
        result['connection_type'] = 'ethernet'
        result['tier'] = 'fast'
        result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_FAST')
        # Ethernet gets +2 concurrent chunks (small RAM cost: 8MB for 4MB chunks)
        if tier == 'PRO':
            result['max_concurrent_chunks'] = 8
        elif tier == 'STANDARD':
            result['max_concurrent_chunks'] = 6
        else:
            result['max_concurrent_chunks'] = 4  # Base tier: 2→4 for Ethernet

    elif detected_interface and detected_interface.startswith('wlan'):
        # WiFi but not AP mode (Pi is WiFi client)
        result['connection_type'] = 'wifi_client'
        result['tier'] = 'medium'
        result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_MEDIUM')

    else:
        # Unknown - use mobile detection as fallback
        if result['is_mobile']:
            result['tier'] = 'slow'
            result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_SLOW')
            result['max_concurrent_chunks'] = 1
        else:
            result['tier'] = 'medium'
            result['chunk_size'] = get_runtime_config_value('UPLOAD_CHUNK_SIZE_MEDIUM')

    logger.debug(
        f"Client {client_ip}: interface={result['interface']}, "
        f"type={result['connection_type']}, tier={result['tier']}, "
        f"hw_tier={result['hardware_tier']}, chunk_size={result['chunk_size']}, "
        f"concurrency={result['max_concurrent_chunks']}"
    )

    return result


def get_upload_settings(client_ip: str, user_agent: str = None) -> Dict:
    """
    Get optimal upload settings for a client.
    This is the main entry point for the negotiate endpoint.

    Args:
        client_ip: The client's IP address
        user_agent: Optional user agent string

    Returns:
        Dict with chunk_size, tier, connection_type, interface, max_concurrent_chunks
    """
    connection = get_client_connection_type(client_ip, user_agent)

    return {
        'chunk_size': connection['chunk_size'],
        'tier': connection['tier'],
        'connection_type': connection['connection_type'],
        'interface': connection['interface'],
        'max_concurrent_chunks': connection['max_concurrent_chunks'],
        'hardware_tier': connection['hardware_tier']
    }
