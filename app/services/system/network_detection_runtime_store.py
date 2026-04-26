"""Specter-owned runtime store for network detection caches."""

from specter import create_store


network_detection_runtime_store = create_store('network_detection_runtime', {
    'interface_ips_cache': {
        'data': {},
        'timestamp': 0.0,
    },
    'tailscale_cache': {},
})
