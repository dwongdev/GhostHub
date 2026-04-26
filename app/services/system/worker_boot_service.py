"""System-domain worker boot ownership."""

import logging

from specter import Service, registry

logger = logging.getLogger(__name__)


class SystemWorkerBootService(Service):
    """Own system-domain worker boot policy."""

    def __init__(self):
        super().__init__('system_worker_boot')
        self.priority = 200

    def initialize_runtime(self, app):
        """Initialize system runtimes that should start in worker processes."""
        result = {
            'hdmi_runtime_initialized': False,
            'rate_limiter_initialized': False,
            'tunnel_auto_start_attempted': False,
        }

        try:
            state = registry.require('hdmi_runtime_service').initialize_runtime()
            result['hdmi_runtime_initialized'] = bool(
                state.get('runtime_initialized', False),
            )
            logger.info("HDMI service initialized")
        except Exception as exc:
            logger.error("Failed to init HDMI service: %s", exc)

        try:
            import app.services.system.rate_limit_service as rate_limit_service

            rate_limit_service.init_rate_limiter(
                upload_per_client_mbps=app.config.get('UPLOAD_RATE_LIMIT_PER_CLIENT', 50.0),
                upload_global_mbps=app.config.get('UPLOAD_RATE_LIMIT_GLOBAL', 500.0),
                download_per_client_mbps=app.config.get('DOWNLOAD_RATE_LIMIT_PER_CLIENT', 50.0),
                download_global_mbps=app.config.get('DOWNLOAD_RATE_LIMIT_GLOBAL', 100.0),
            )
            result['rate_limiter_initialized'] = True
            logger.info("Rate limiter initialized")
        except Exception as exc:
            logger.error("Failed to init rate limiter: %s", exc)

        if not app.config.get('TUNNEL_AUTO_START'):
            return result

        provider = app.config.get('TUNNEL_PROVIDER', 'none')
        if provider == 'none':
            return result

        try:
            import app.services.system.tunnel.service as system_tunnel_service

            logger.info("Auto-starting tunnel: %s", provider)
            system_tunnel_service.start_tunnel(
                provider,
                local_port=app.config.get('PORT', 5000),
                pinggy_token=app.config.get('PINGGY_ACCESS_TOKEN'),
                wait_for_network=True,
            )
            result['tunnel_auto_start_attempted'] = True
        except Exception as exc:
            logger.error("Tunnel auto-start check failed: %s", exc)
            result['tunnel_auto_start_attempted'] = True

        return result


def initialize_system_worker_runtime(app):
    """Initialize system runtimes through the registered worker boot owner."""
    return registry.require('system_worker_boot').initialize_runtime(app)
