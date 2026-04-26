"""Kiosk idle/countdown timer ownership."""

import logging
import time

import gevent

from specter import registry

logger = logging.getLogger(__name__)

KIOSK_IDLE_TIMEOUT = 120
KIOSK_SHUTDOWN_COUNTDOWN = 120


def cancel_kiosk_timers():
    """Cancel all idle/countdown timers and clear timer state."""
    logger.debug("Cancelling all kiosk timers")
    store = registry.require('hdmi_runtime')

    greenlets_to_kill = []

    def _collect_and_clear(state):
        if state['idle_greenlet']:
            greenlets_to_kill.append(state['idle_greenlet'])
        if state['countdown_greenlet']:
            greenlets_to_kill.append(state['countdown_greenlet'])

        state['idle_greenlet'] = None
        state['countdown_greenlet'] = None
        state['shutdown_start_time'] = None
        state['shutdown_duration'] = None
        state['in_idle_mode'] = False
        state['in_shutdown_countdown'] = False
        return state

    store.update(_collect_and_clear)

    for greenlet in greenlets_to_kill:
        try:
            greenlet.kill()
            logger.info("Killed timer greenlet: %s", greenlet)
        except Exception as err:
            logger.warning("Error killing greenlet: %s", err)


def start_idle_mode(app, *, owner, stop_kiosk):
    """Enter idle mode and schedule the shutdown countdown."""
    store = registry.require('hdmi_runtime')
    store.set({
        'in_idle_mode': True,
        'in_shutdown_countdown': False,
    })
    logger.info("Entering idle mode, shutdown countdown starts in %ss", KIOSK_IDLE_TIMEOUT)
    _emit_kiosk_status(app, {
        'running': True,
        'casting': False,
        'idle_mode': True,
        'idle_timeout': KIOSK_IDLE_TIMEOUT,
        'shutdown_in': None,
    })

    def _idle_timeout_callback():
        gevent.sleep(KIOSK_IDLE_TIMEOUT)
        if store.get('casting_active'):
            logger.info("Casting resumed during idle, aborting shutdown")
            return

        logger.info("Idle timeout expired, starting shutdown countdown")
        start_shutdown_countdown(app, owner=owner, stop_kiosk=stop_kiosk)

    greenlet = owner.spawn(_idle_timeout_callback, label='kiosk-idle-timeout')
    store.set({'idle_greenlet': greenlet})


def start_shutdown_countdown(app, *, owner, stop_kiosk):
    """Run the kiosk shutdown countdown after idle mode expires."""
    store = registry.require('hdmi_runtime')
    if store.get('casting_active'):
        logger.info("Casting resumed, aborting shutdown countdown")
        return

    if store.get('countdown_greenlet'):
        logger.info("Shutdown countdown already running")
        return

    store.set({
        'in_idle_mode': False,
        'in_shutdown_countdown': True,
        'shutdown_start_time': time.time(),
        'shutdown_duration': KIOSK_SHUTDOWN_COUNTDOWN,
    })

    logger.info("Starting %ss shutdown countdown", KIOSK_SHUTDOWN_COUNTDOWN)

    def _countdown_loop():
        remaining = KIOSK_SHUTDOWN_COUNTDOWN
        while remaining > 0:
            if store.get('casting_active'):
                logger.info("Casting resumed during countdown, aborting shutdown")
                return

            _emit_kiosk_status(app, {
                'running': True,
                'casting': False,
                'idle_mode': False,
                'shutdown_in': remaining,
            })
            gevent.sleep(1)
            remaining -= 1

        if store.get('casting_active'):
            logger.info("Casting resumed during countdown, aborting shutdown")
            return

        store.set({
            'in_shutdown_countdown': False,
            'shutdown_start_time': None,
            'shutdown_duration': None,
            'countdown_greenlet': None,
        })

        logger.info("Shutdown countdown complete - stopping kiosk")
        stop_kiosk()
        _emit_kiosk_status(app, {
            'running': False,
            'casting': False,
            'reason': 'inactivity_timeout',
            'shutdown_in': 0,
        })

    greenlet = owner.spawn(_countdown_loop, label='kiosk-shutdown-countdown')
    store.set({'countdown_greenlet': greenlet})


def _emit_kiosk_status(app, payload):
    """Emit kiosk status updates when the Flask app context is available."""
    if not app:
        return
    with app.app_context():
        registry.require('tv_events').emit_kiosk_status(payload)
