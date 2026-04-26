"""HDMI hotplug monitoring ownership."""

import logging
import time

import gevent

from specter import registry

logger = logging.getLogger(__name__)

try:
    import pyudev
except ImportError:
    logger.warning("pyudev not installed. HDMI monitoring will not work (OK if on Windows).")
    pyudev = None

POLL_INTERVAL = 5


def supports_hotplug_monitoring():
    """Return True when pyudev-backed HDMI monitoring is available."""
    return pyudev is not None


def start_hotplug_monitor(owner, check_status, handle_status_change):
    """Start the HDMI hotplug monitor once under a Specter owner."""
    store = registry.require('hdmi_runtime')
    if store.get('monitoring_active') or pyudev is None:
        return False

    store.set({'monitoring_active': True})
    owner.spawn(
        _monitor_udev,
        check_status,
        handle_status_change,
        label='hdmi-hotplug-monitor',
    )
    return True


def stop_hotplug_monitor():
    """Stop the HDMI hotplug monitor."""
    store = registry.resolve('hdmi_runtime')
    if store:
        store.set({'monitoring_active': False})


def _monitor_udev(check_status, handle_status_change):
    """Monitor udev events for HDMI hotplug with polling fallback."""
    store = registry.require('hdmi_runtime')
    try:
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='drm')
        monitor.start()

        last_check = time.time()

        while store.get('monitoring_active'):
            device = monitor.poll(timeout=POLL_INTERVAL)

            if device and 'HDMI' in device.sys_name:
                logger.info("HDMI event: %s on %s", device.action, device.sys_name)
                gevent.sleep(1)

                new_status = check_status()
                if _update_connected_status(new_status):
                    handle_status_change(new_status)

            current_time = time.time()
            if current_time - last_check >= POLL_INTERVAL:
                new_status = check_status()
                if _update_connected_status(new_status):
                    logger.info("HDMI status changed via polling: %s", new_status)
                    handle_status_change(new_status)
                last_check = current_time

    except Exception as err:
        logger.error("HDMI Monitor Error: %s", err)
        store.set({'monitoring_active': False})


def _update_connected_status(new_status):
    """Update the store and report whether the HDMI status changed."""
    store = registry.require('hdmi_runtime')
    status_changed = False

    def _update(state):
        nonlocal status_changed
        if state['connected'] != new_status:
            state['connected'] = new_status
            status_changed = True
        return state

    store.update(_update)
    return status_changed
