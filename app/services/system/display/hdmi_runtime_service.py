"""
Specter runtime owner for HDMI and kiosk lifecycle.
-----------
Monitors HDMI connection status using udev and manages the Kiosk service.
Ensures resources are saved by stopping the Kiosk when HDMI is disconnected.

Cast-based power management:
- Kiosk starts when casting begins (saves RAM when idle)
- Kiosk stops after inactivity (120s idle + 120s countdown)
- HDMI hotplug events still handled for reactive UI
"""
import logging
import time

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.system.display.hdmi_detection_service import (
    check_hdmi_status,
    force_hdmi_reinit as run_hdmi_reinit,
)
from app.services.system.display.hdmi_runtime_store import hdmi_runtime_store as _hdmi_runtime_store
from app.services.system.display.hotplug_service import (
    start_hotplug_monitor,
    stop_hotplug_monitor,
    supports_hotplug_monitoring,
)
from app.services.system.display.kiosk_timer_service import (
    cancel_kiosk_timers,
    start_idle_mode,
)
from app.services.system.display.kiosk_process_service import (
    check_kiosk_status,
    restart_kiosk as restart_kiosk_process,
    start_kiosk as start_kiosk_process,
    stop_kiosk as stop_kiosk_process,
)
from specter import Service, registry

logger = logging.getLogger(__name__)


class HdmiRuntimeService(Service):
    """Coordinates HDMI hotplug detection and TV kiosk lifecycle."""

    def __init__(self):
        super().__init__('hdmi_runtime_service', {
            'runtime_initialized': False,
        })
        self.app = None

    def on_start(self):
        """Bind the Flask app without starting worker-owned runtime work."""
        self.app = registry.require('service_manager').app

    def initialize_runtime(self):
        """Initialize worker-owned HDMI runtime once."""
        if self.state.get('runtime_initialized'):
            return self.get_state()

        self.app = registry.require('service_manager').app

        # Check initial HDMI status (but don't auto-start kiosk - wait for cast)
        initial_connected = self.check_status()
        initial_kiosk_running = self._check_kiosk_status()

        logger.info(
            "HDMI status at runtime init: %s",
            'connected' if initial_connected else 'disconnected',
        )
        logger.info(
            "Kiosk status at runtime init: %s",
            'running' if initial_kiosk_running else 'stopped',
        )

        store = registry.require('hdmi_runtime')
        store.set({
            'runtime_initialized': True,
            'connected': initial_connected,
            'kiosk_running': initial_kiosk_running,
        })

        if start_hotplug_monitor(self, self.check_status, self._handle_status_change):
            logger.info("HDMI monitoring greenlet started")
        elif not supports_hotplug_monitoring():
            logger.error("CRITICAL: pyudev not installed - HDMI hotplug detection disabled")

        self.set_state({'runtime_initialized': True})
        return self.get_state()

    def on_stop(self):
        """Tear down worker-owned HDMI runtime work."""
        stop_hotplug_monitor()
        cancel_kiosk_timers()
        registry.require('hdmi_runtime').set({
            'runtime_initialized': False,
            'monitoring_active': False,
        })
        self.set_state({'runtime_initialized': False})

    @property
    def connected(self):
        return registry.require('hdmi_runtime').get('connected')

    @property
    def casting_active(self):
        return registry.require('hdmi_runtime').get('casting_active')

    def check_status(self):
        """Check actual HDMI status from the detection owner."""
        return check_hdmi_status()

    def force_hdmi_reinit(self):
        """Force HDMI re-initialization to fix 'NOT SUPPORT!' errors after hotplug."""
        return run_hdmi_reinit()

    def wake_tv_via_cec(self):
        """Send CEC wake command to TV."""
        from app.services.system.display.hdmi_detection_service import wake_tv_via_cec

        return wake_tv_via_cec(get_runtime_config_value('ENABLE_CEC_WAKE'))

    def _handle_status_change(self, is_connected):
        """Handle HDMI hotplug: update socket for reactive UI."""
        status_str = "connected" if is_connected else "disconnected"
        logger.info(f"HDMI is now {status_str}")
        store = registry.require('hdmi_runtime')
        is_kiosk_running = store.get('kiosk_running')

        if is_connected and is_kiosk_running:
            logger.info("HDMI hotplug with kiosk running - forcing re-initialization")
            self.force_hdmi_reinit()
            restart_kiosk_process()
        elif is_connected:
            logger.info("HDMI connected, kiosk not running - console display active")

        should_stop = False
        casting_active = store.get('casting_active')
        if not is_connected and casting_active:
            logger.info("HDMI disconnected during cast - stopping kiosk")
            store.set({'casting_active': False})
            should_stop = True

        if should_stop:
            cancel_kiosk_timers()
            self._stop_kiosk()

        if self.app:
            with self.app.app_context():
                registry.require('tv_events').emit_hdmi_status({
                    'connected': is_connected,
                    'kiosk_running': store.get('kiosk_running')
                })

                logger.info(f"[HDMI] Emitted status: connected={is_connected}, kiosk_running={store.get('kiosk_running')}")

    def _check_kiosk_status(self):
        """Check if kiosk service is active."""
        return check_kiosk_status()

    def _start_kiosk(self):
        """Start the ghosthub-kiosk service."""
        store = registry.require('hdmi_runtime')
        kiosk_running = start_kiosk_process(cec_enabled=get_runtime_config_value('ENABLE_CEC_WAKE'))
        store.set({'kiosk_running': kiosk_running})
        return kiosk_running

    def _stop_kiosk(self):
        """Stop the kiosk service."""
        store = registry.require('hdmi_runtime')
        stopped = stop_kiosk_process()
        store.set({'kiosk_running': check_kiosk_status()})
        return stopped

    def on_cast_start(self):
        """Called when casting starts - start kiosk if HDMI connected."""
        logger.info("Cast started - starting kiosk")

        store = registry.require('hdmi_runtime')
        store.set({'casting_active': True})

        cancel_kiosk_timers()

        current_status = self.check_status()
        store.set({'connected': current_status})

        if not current_status:
            logger.warning("HDMI not detected but starting kiosk anyway")

        success = self._start_kiosk()

        if self.app:
            with self.app.app_context():
                registry.require('tv_events').emit_kiosk_status({
                    'running': store.get('kiosk_running'),
                    'casting': True,
                    'hdmi_connected': current_status,
                    'idle_mode': False,
                    'shutdown_in': None
                })

        return success

    def on_cast_stop(self):
        """Called when casting stops - enter idle mode then start shutdown countdown."""
        logger.info("Cast stopped - checking state")

        should_idle = False
        should_stop = False
        store = registry.require('hdmi_runtime')

        casting_active = store.get('casting_active')
        connected = store.get('connected')
        
        if casting_active:
            store.set({'casting_active': False})
            if connected:
                should_idle = True
            else:
                logger.info("HDMI disconnected, stopping cast without idle mode")
                should_stop = True
        else:
            logger.info("Cast already stopped or handled")

        cancel_kiosk_timers()

        if should_stop:
            self._stop_kiosk()
        elif should_idle:
            start_idle_mode(self.app, owner=self, stop_kiosk=self._stop_kiosk)

        return True

    def get_status(self):
        """Get current HDMI and kiosk status."""
        current_status = self.check_status()
        kiosk_running = self._check_kiosk_status()
        store = registry.require('hdmi_runtime')
        
        def update_and_read(state):
            state['connected'] = current_status
            state['kiosk_running'] = kiosk_running
            return state
            
        state = store.update(update_and_read)

        shutdown_remaining = None
        if state.get('shutdown_start_time') and state.get('shutdown_duration'):
            elapsed = time.time() - state['shutdown_start_time']
            shutdown_remaining = max(0, int(state['shutdown_duration'] - elapsed))

        return {
            'hdmi_connected': state['connected'],
            'kiosk_running': state['kiosk_running'],
            'casting_active': state['casting_active'],
            'in_idle_mode': state['in_idle_mode'],
            'in_shutdown_countdown': state['in_shutdown_countdown'],
            'shutdown_remaining': shutdown_remaining,
            'pending_shutdown': state['in_idle_mode'] or state['in_shutdown_countdown']
        }
