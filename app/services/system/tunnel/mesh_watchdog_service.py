"""Mesh watchdog and recovery ownership."""

import logging
import time

import gevent

from app.services.system.headscale.connectivity_service import (
    is_hs_running,
    verify_tailscale_connectivity,
)
from app.services.system.tunnel.state_service import (
    get_active_tunnel_info,
    tunnel_runtime_access,
    update_tunnel_runtime,
)
from specter import Service, registry

logger = logging.getLogger(__name__)


class MeshWatchdogService(Service):
    """Own mesh watchdog and recovery lifecycle under Specter."""

    def __init__(self):
        super().__init__('mesh_watchdog', {
            'watchdog_running': False,
            'recovery_in_progress': False,
        })
        self._watchdog_greenlet = None

    def attempt_recovery(self, reason: str):
        """Attempt to recover mesh connectivity with cooldown to avoid thrashing."""
        now = time.time()
        should_start = False

        def _mark_recovery(draft):
            nonlocal should_start
            if draft.get('mesh_recovery_in_progress', False):
                return
            last_attempt = draft.get('last_mesh_recovery_attempt', 0.0)
            cooldown = draft.get('mesh_recovery_cooldown_seconds', 60)
            if now - last_attempt < cooldown:
                return
            draft['last_mesh_recovery_attempt'] = now
            draft['mesh_recovery_in_progress'] = True
            should_start = True

        update_tunnel_runtime(_mark_recovery)
        if not should_start:
            return False

        self.set_state({'recovery_in_progress': True})
        self.spawn(self._recover_mesh, reason, label='mesh-recovery')
        return True

    def start_watchdog(self):
        """Start a background watchdog to keep mesh connectivity stable."""
        started = False

        def _mark_watchdog_started(draft):
            nonlocal started
            if draft.get('mesh_watchdog_running', False):
                return
            draft['mesh_watchdog_running'] = True
            started = True

        update_tunnel_runtime(_mark_watchdog_started)
        if not started:
            return False

        self.set_state({'watchdog_running': True})
        self._watchdog_greenlet = self.spawn(self._watchdog_loop, label='mesh-watchdog')
        return True

    def stop_watchdog(self):
        """Stop the mesh watchdog loop."""
        update_tunnel_runtime(
            lambda draft: draft.update({
                'mesh_watchdog_running': False,
            }),
        )
        self.set_state({'watchdog_running': False})
        if self._watchdog_greenlet is not None:
            self.cancel_greenlet(self._watchdog_greenlet)
            self._watchdog_greenlet = None
        return True

    def on_stop(self):
        """Tear down any running watchdog on service shutdown."""
        self.stop_watchdog()

    def _recover_mesh(self, reason):
        try:
            logger.warning("Mesh recovery triggered: %s", reason)
            success, message = registry.require('headscale_runtime').start_runtime()
            if success:
                logger.info("Mesh recovery succeeded")
            else:
                logger.warning("Mesh recovery failed: %s", message)
        except Exception as err:
            logger.error("Mesh recovery exception: %s", err)
        finally:
            update_tunnel_runtime(
                lambda draft: draft.__setitem__('mesh_recovery_in_progress', False),
            )
            self.set_state({'recovery_in_progress': False})

    def _watchdog_loop(self):
        logger.info("Mesh watchdog started")
        while tunnel_runtime_access(lambda state: state.get('mesh_watchdog_running', False)):
            try:
                if get_active_tunnel_info().get("provider") != "mesh":
                    gevent.sleep(5)
                    continue

                if not is_hs_running():
                    self.attempt_recovery("Watchdog detected Headscale is not running")
                    gevent.sleep(10)
                    continue

                if verify_tailscale_connectivity():
                    update_tunnel_runtime(
                        lambda draft: draft.__setitem__('mesh_connectivity_failures', 0),
                    )
                else:
                    failures = update_tunnel_runtime(
                        lambda draft: draft.__setitem__(
                            'mesh_connectivity_failures',
                            draft.get('mesh_connectivity_failures', 0) + 1,
                        ),
                    ).get('mesh_connectivity_failures', 0)
                    if failures >= 3:
                        self.attempt_recovery(
                            f"Watchdog connectivity failures: {failures}",
                        )
                gevent.sleep(20)
            except Exception as err:
                logger.warning("Mesh watchdog loop error: %s", err)
                gevent.sleep(10)
        logger.info("Mesh watchdog stopped")


def attempt_mesh_recovery(reason: str):
    """Attempt mesh recovery through the registered Specter owner."""
    return registry.require('mesh_watchdog').attempt_recovery(reason)


def start_mesh_watchdog():
    """Start the mesh watchdog through the registered Specter owner."""
    return registry.require('mesh_watchdog').start_watchdog()


def stop_mesh_watchdog():
    """Stop the mesh watchdog through the registered Specter owner."""
    return registry.require('mesh_watchdog').stop_watchdog()
