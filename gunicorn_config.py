"""Default Gunicorn config for GhostHub production deployments."""

# CRITICAL: Patch gevent ssl in the master process BEFORE Gunicorn imports the worker class.
#
# Gunicorn resolves `worker_class` at config-parse time in the master, which imports
# geventwebsocket.gunicorn.workers -> geventwebsocket.handler -> ssl (C extension).
# If ssl is imported unpatched in the master, every forked worker inherits that
# unpatched C-level OpenSSL state. When the worker's init_process() then calls
# monkey.patch_all(), it tries to patch an already-initialized ssl object — on
# ARM/Raspberry Pi this is not fork-safe and causes an immediate SIGSEGV.
#
# We patch ONLY ssl here (not socket/os/time/thread).
# Patching socket would cause Gunicorn's master-process I/O to go through gevent,
# which creates a live gevent hub in the master.  When Gunicorn performs a graceful
# reload it forks new workers that inherit that hub; the workers' monkey.patch_all()
# then conflicts with the already-running hub and triggers another SIGSEGV on ARM.
# patch_ssl() registers ssl in sys.modules as the gevent-wrapped version so that
# when the worker's monkey.patch_all() runs, ssl is already "done" and skipped
# safely — without ever creating a hub in the master.
from gevent import monkey as _gevent_monkey
if not _gevent_monkey.is_module_patched('ssl'):
    _gevent_monkey.patch_ssl()

import gevent
import logging
import os
import sys
import warnings

# Suppress noisy gevent fork-cleanup assertion traces from subprocess children.
warnings.filterwarnings('ignore', message='.*after_fork_in_child.*')

_default_unraisablehook = sys.unraisablehook


def _ghosthub_unraisablehook(unraisable):
    """Ignore known gevent unraisable assertions emitted after fork."""
    obj = getattr(unraisable, 'object', None)
    exc_type = getattr(unraisable, 'exc_type', None)
    obj_repr = repr(obj)
    if (
        exc_type is AssertionError
        and "_ForkHooks.after_fork_in_child" in obj_repr
    ):
        return
    _default_unraisablehook(unraisable)


sys.unraisablehook = _ghosthub_unraisablehook

# Single worker is required for Socket.IO without Redis/sticky sessions.
workers = 1
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
worker_connections = 1000
timeout = 300
bind = "0.0.0.0:" + str(os.getenv("PORT", 5000))
accesslog = "-"
errorlog = "-"
loglevel = "info"
preload_app = False


def pre_fork(server, worker):
    os.environ['GHOSTHUB_WORKER_INITIALIZED'] = 'false'


def post_fork(server, worker):
    # Reinitialize gevent hub in each worker after fork so it starts with a
    # clean event loop regardless of any hub state inherited from the master.
    gevent.reinit()
    os.environ['GHOSTHUB_WORKER_INITIALIZED'] = 'true'


def worker_abort(worker):
    logging.error(
        "Worker %s ABORTED - check native code crashes (ffmpeg/Pillow)",
        worker.pid,
    )
