"""
Session runtime state store — Specter-owned replacement for current_app globals.

Replaces:
    - current_app.active_connections
    - current_app.sid_to_session
    - current_app.blocked_ips
    - current_app.ADMIN_SESSION_ID
    - current_app.admin_release_timers

All access is gevent-safe via the Store's built-in BoundedSemaphore.
"""

import json
import logging
import os
import time

import gevent

from specter import create_store

logger = logging.getLogger(__name__)
ADMIN_LOCK_FILENAME = 'admin_lock.json'
ADMIN_LOCK_IO_TIMEOUT_SECONDS = 2.0
KICK_IP_BLOCK_TTL_SECONDS = 600

session_store = create_store('session', {
    'active_connections': {},    # flask_session_id -> {sid, sids: set, ip, user_id, profile_id, profile_name}
    'sid_to_session': {},       # socket_sid -> flask_session_id
    'blocked_ips': {},          # ip -> expires_at timestamp for admin kick blocks
    'admin_session_id': None,   # current admin session cookie value
    'admin_lock_path': None,    # persisted admin lock file for cross-worker consistency
    'admin_release_timers': {}, # session_id -> {cancelled: bool, ...}
})


def _with_io_timeout(func, timeout_seconds=ADMIN_LOCK_IO_TIMEOUT_SECONDS):
    """Execute filesystem I/O through gevent's threadpool with a timeout."""
    if os.environ.get('GHOSTHUB_TESTING') == 'true':
        try:
            return func()
        except Exception:
            return None

    try:
        job = gevent.get_hub().threadpool.spawn(func)
        return job.get(timeout=timeout_seconds)
    except gevent.timeout.Timeout:
        return None
    except Exception:
        return None


def normalize_session_id(session_id):
    """Normalize quoted cookie values used by some clients/tests."""
    if not session_id or not isinstance(session_id, str):
        return session_id
    session_id = session_id.strip()
    if (
        len(session_id) >= 2 and
        session_id.startswith('"') and
        session_id.endswith('"')
    ):
        return session_id[1:-1]
    return session_id


def configure_admin_lock(instance_path):
    """Configure the persisted admin lock path for the current app instance."""
    lock_path = os.path.join(instance_path, ADMIN_LOCK_FILENAME) if instance_path else None

    def _merge(draft):
        if draft.get('admin_lock_path') != lock_path:
            draft['admin_lock_path'] = lock_path
            draft['admin_session_id'] = None

    session_store.update(_merge)


def _read_admin_lock_file(lock_path):
    if not lock_path or not os.path.exists(lock_path):
        return None

    with open(lock_path, 'r', encoding='utf-8') as lock_file:
        data = json.load(lock_file)
    return normalize_session_id(data.get('session_id'))


def get_admin_lock_path():
    """Return the configured admin lock path, if any."""
    return session_store.get('admin_lock_path')


def get_admin_session_id(refresh=False):
    """Return the active admin session ID from the store or persisted lock."""
    cached = normalize_session_id(session_store.get('admin_session_id'))
    if cached and not refresh:
        return cached

    lock_path = get_admin_lock_path()
    session_id = _with_io_timeout(lambda: _read_admin_lock_file(lock_path))
    session_id = normalize_session_id(session_id)

    if session_id != cached:
        session_store.set({'admin_session_id': session_id})

    return session_id


def set_admin_session_id(session_id):
    """Persist the active admin session ID to the store and lock file."""
    normalized_session_id = normalize_session_id(session_id)
    lock_path = get_admin_lock_path()

    session_store.set({'admin_session_id': normalized_session_id})

    if not lock_path:
        return

    if not normalized_session_id:
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception as exc:
            logger.warning("Failed to remove admin lock file: %s", exc)
        return

    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, 'w', encoding='utf-8') as lock_file:
            json.dump(
                {'session_id': normalized_session_id, 'updated_at': time.time()},
                lock_file,
            )
    except Exception as exc:
        logger.warning("Failed to write admin lock file: %s", exc)


def is_admin_session(session_id):
    """Return True when the provided session currently owns the admin lock."""
    normalized_session_id = normalize_session_id(session_id)
    admin_session_id = get_admin_session_id()
    return bool(
        normalized_session_id and
        admin_session_id and
        normalized_session_id == admin_session_id
    )


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def connect_client(
    flask_session_id,
    client_sid,
    client_ip,
    *,
    profile_id=None,
    profile_name=None,
):
    """Register a new socket connection for a browser session.

    Returns the updated session entry dict.
    """
    flask_session_id = normalize_session_id(flask_session_id)
    result = {}

    def _merge(draft):
        nonlocal result
        connections = draft.setdefault('active_connections', {})
        sid_map = draft.setdefault('sid_to_session', {})

        entry = connections.get(flask_session_id, {
            'sid': None,
            'sids': set(),
            'ip': client_ip,
            'user_id': profile_name or flask_session_id[:8],
            'profile_id': profile_id,
            'profile_name': profile_name,
        })
        entry['ip'] = client_ip
        entry['profile_id'] = profile_id
        entry['profile_name'] = profile_name
        entry['user_id'] = profile_name or flask_session_id[:8]
        if 'sids' not in entry or not isinstance(entry['sids'], set):
            entry['sids'] = set()
        entry['sids'].add(client_sid)
        entry['sid'] = client_sid

        connections[flask_session_id] = entry
        sid_map[client_sid] = flask_session_id
        result = dict(entry)

    session_store.update(_merge)
    return result


def disconnect_client(client_sid, flask_session_id=None):
    """Remove a socket SID from session tracking.

    Returns the flask_session_id that was cleaned up, or None.
    """
    flask_session_id = normalize_session_id(flask_session_id)
    cleaned_session_id = None

    def _merge(draft):
        nonlocal cleaned_session_id
        connections = draft.get('active_connections', {})
        sid_map = draft.get('sid_to_session', {})

        resolved_session = flask_session_id or sid_map.get(client_sid)

        if resolved_session and resolved_session in connections:
            entry = connections[resolved_session]
            sids = entry.get('sids')
            if isinstance(sids, set):
                sids.discard(client_sid)
                entry['sid'] = next(iter(sids), None)
                if len(sids) == 0:
                    del connections[resolved_session]
                    logger.info(
                        "Removed from active_connections: %s (last SID disconnected)",
                        resolved_session,
                    )
                else:
                    connections[resolved_session] = entry
                    logger.info(
                        "Updated active_connections for %s: SID count now %s",
                        resolved_session,
                        len(sids),
                    )
            else:
                del connections[resolved_session]
                logger.info(
                    "Removed from active_connections (no sids set): %s",
                    resolved_session,
                )
            cleaned_session_id = resolved_session
        elif resolved_session:
            logger.warning(
                "Flask session ID %s not found in active_connections during "
                "disconnect for client %s.",
                resolved_session,
                client_sid,
            )
        else:
            # Fallback: search by SID across all connections
            found_key = None
            for key, value in list(connections.items()):
                try:
                    if (
                        isinstance(value.get('sids'), set) and
                        client_sid in value['sids']
                    ) or value.get('sid') == client_sid:
                        found_key = key
                        break
                except Exception:
                    pass
            if found_key:
                del connections[found_key]
                logger.info(
                    "Removed from active_connections by SID lookup: %s (Client SID: %s)",
                    found_key,
                    client_sid,
                )
                cleaned_session_id = found_key

        # Clean up sid_to_session
        sid_map.pop(client_sid, None)

    session_store.update(_merge)
    return cleaned_session_id


def get_connection(flask_session_id):
    """Return the connection entry for a session, or None."""
    flask_session_id = normalize_session_id(flask_session_id)
    connections = session_store.get('active_connections') or {}
    return connections.get(flask_session_id)


def list_connections():
    """Return a copy of the full active_connections dict."""
    return dict(session_store.get('active_connections') or {})


def update_connection_profile(flask_session_id, profile_id=None, profile_name=None):
    """Update the active profile metadata for a connected session."""
    flask_session_id = normalize_session_id(flask_session_id)

    def _merge(draft):
        connections = draft.get('active_connections', {})
        entry = connections.get(flask_session_id)
        if entry is None:
            return

        entry['profile_id'] = profile_id
        entry['profile_name'] = profile_name
        entry['user_id'] = profile_name or flask_session_id[:8]
        connections[flask_session_id] = entry

    session_store.update(_merge)


def get_profile_owner_session(profile_id, exclude_session_id=None):
    """Return the active session currently using a profile, if any."""
    if not profile_id:
        return None

    exclude_session_id = normalize_session_id(exclude_session_id)
    connections = session_store.get('active_connections') or {}

    for flask_session_id, entry in connections.items():
        if exclude_session_id and flask_session_id == exclude_session_id:
            continue
        if entry.get('profile_id') == profile_id:
            return flask_session_id

    return None


def clear_connections_for_profile(profile_id):
    """Remove profile metadata from live sessions that reference a deleted profile."""
    if not profile_id:
        return 0

    cleared_count = 0

    def _merge(draft):
        nonlocal cleared_count
        connections = draft.get('active_connections', {})
        for flask_session_id, entry in connections.items():
            if entry.get('profile_id') != profile_id:
                continue
            entry['profile_id'] = None
            entry['profile_name'] = None
            entry['user_id'] = flask_session_id[:8]
            cleared_count += 1

    session_store.update(_merge)
    return cleared_count


def find_connection_by_user_id(user_id):
    """Find a connection entry by its 8-char user_id.

    Returns (flask_session_id, connection_info) or (None, None).
    """
    connections = session_store.get('active_connections') or {}
    for flask_session_id, conn_info in connections.items():
        if (
            conn_info.get('user_id') == user_id or
            conn_info.get('profile_name') == user_id or
            flask_session_id[:8] == user_id
        ):
            return flask_session_id, conn_info
    return None, None


def resolve_session_for_sid(client_sid):
    """Return the flask_session_id mapped to a socket SID, or None."""
    sid_map = session_store.get('sid_to_session') or {}
    return sid_map.get(client_sid)


def list_session_sids(flask_session_id):
    """Return all active socket SIDs currently associated with a session."""
    entry = get_connection(flask_session_id) or {}
    session_sids = entry.get('sids')

    if isinstance(session_sids, set):
        return sorted(session_sids)
    if isinstance(session_sids, (list, tuple)):
        return [sid for sid in session_sids if sid]

    primary_sid = entry.get('sid')
    return [primary_sid] if primary_sid else []


# ---------------------------------------------------------------------------
# IP blocking
# ---------------------------------------------------------------------------

def is_blocked(ip):
    """Return True if an IP is in the block list."""
    if not ip:
        return False

    now = time.time()
    blocked = False

    def _merge(draft):
        nonlocal blocked
        entries = _prune_expired_ip_blocks(draft, now=now)
        expires_at = entries.get(ip)
        blocked = expires_at is not None and expires_at > now

    session_store.update(_merge)
    return blocked


def _prune_expired_ip_blocks(draft, now=None):
    """Normalize and prune expired IP blocks in-place."""
    if now is None:
        now = time.time()

    blocked = draft.get('blocked_ips')
    if isinstance(blocked, set):
        blocked = {blocked_ip: now + KICK_IP_BLOCK_TTL_SECONDS for blocked_ip in blocked}
        draft['blocked_ips'] = blocked
    elif not isinstance(blocked, dict):
        blocked = {}
        draft['blocked_ips'] = blocked

    expired = [
        blocked_ip
        for blocked_ip, expires_at in blocked.items()
        if expires_at is None or expires_at <= now
    ]
    for blocked_ip in expired:
        blocked.pop(blocked_ip, None)

    return blocked


def block_ip(ip, duration_seconds=KICK_IP_BLOCK_TTL_SECONDS):
    """Add an IP to the block list. Returns the new block list size."""
    size = 0
    expires_at = time.time() + max(1, int(duration_seconds or KICK_IP_BLOCK_TTL_SECONDS))

    def _merge(draft):
        nonlocal size
        blocked = _prune_expired_ip_blocks(draft)
        blocked[ip] = expires_at
        size = len(blocked)

    session_store.update(_merge)
    logger.info(
        "IP %s added to blocklist until %s. Current blocklist size: %s",
        ip,
        int(expires_at),
        size,
    )
    return size


# ---------------------------------------------------------------------------
# Admin release timers
# ---------------------------------------------------------------------------

def cancel_admin_release_timer(session_id):
    """Cancel a pending admin release timer for a session.

    Returns True if a timer was found and cancelled.
    """
    cancelled = False

    def _merge(draft):
        nonlocal cancelled
        timers = draft.get('admin_release_timers', {})
        pending = timers.get(session_id)
        if pending:
            pending['cancelled'] = True
            del timers[session_id]
            cancelled = True

    session_store.update(_merge)
    if cancelled:
        logger.info(
            "Canceled pending admin release for session %s due to reconnect.",
            session_id,
        )
    return cancelled


def ensure_admin_release_timers():
    """Ensure the admin_release_timers key exists."""
    def _merge(draft):
        draft.setdefault('admin_release_timers', {})
    session_store.update(_merge)
