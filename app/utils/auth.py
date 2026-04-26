"""
Authentication Utilities
------------------------
Shared authentication decorators and helpers for route protection.
"""

import logging
import time
from functools import wraps
from flask import jsonify, request, session

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.core import session_store

logger = logging.getLogger(__name__)


def get_admin_session_id() -> str:
    """Get the active admin session ID from shared storage."""
    return session_store.get_admin_session_id()


def set_admin_session_id(session_id: str) -> None:
    """Persist the admin session ID to shared storage."""
    session_store.set_admin_session_id(session_id)


def get_request_session_id() -> str:
    """Return the normalized request cookie session ID."""
    return session_store.normalize_session_id(request.cookies.get("session_id"))


def _cookie_matches_admin_session() -> bool:
    """Return True when the request cookie owns the admin lock."""
    return session_store.is_admin_session(get_request_session_id())


def is_current_admin_session() -> bool:
    """
    Return True when the current request holds the global admin lock.

    This uses the shared admin lock + session_id cookie as the source of truth
    so admin auth remains stable across reconnects and session-cookie resets.
    """
    return is_current_admin_session_with_flag_sync()


def is_current_admin_session_with_flag_sync() -> bool:
    """
    Strict admin check for request/socket contexts that rely on session flag.

    Enforces AND-logic:
      1) session['is_admin'] is True
      2) session_id cookie matches the global admin lock

    Also self-heals stale session flags:
      - If cookie/admin-lock match but flag is False, set it True.
      - If flag is True but cookie/admin-lock mismatch, clear it.
    """
    cookie_matches_admin = _cookie_matches_admin_session()
    has_admin_flag = bool(session.get("is_admin", False))

    if cookie_matches_admin and not has_admin_flag:
        session["is_admin"] = True
        session.modified = True
        has_admin_flag = True
    elif has_admin_flag and not cookie_matches_admin:
        session["is_admin"] = False
        session.modified = True
        has_admin_flag = False

    return bool(cookie_matches_admin and has_admin_flag)


def admin_required(f):
    """
    Decorator that requires admin privileges for the route.

    Checks both session admin flag and session_id cookie against
    the global ADMIN_SESSION_ID to ensure the user is the current admin.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_current_admin_session_with_flag_sync():
            logger.warning(
                f"Unauthorized admin API access attempt by session: "
                f"{get_request_session_id()}, IP: {request.remote_addr} "
                f"for path {request.path}"
            )
            return jsonify({"error": "Administrator privileges required."}), 403
        return f(*args, **kwargs)

    return decorated_function


def session_or_admin_required(f):
    """
    Decorator that allows access if the user is an admin OR if they have
    a validated session password.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Check if user is admin
        is_admin = is_current_admin_session_with_flag_sync()

        if is_admin:
            if not session.get("is_admin", False):
                session["is_admin"] = True
            return f(*args, **kwargs)

        # 2. Check if session password is required and validated
        session_password = get_runtime_config_value("SESSION_PASSWORD", "")
        if not session_password:
            # If no password set, we still restrict to admin for "admin" actions
            # unless specifically allowed. But for uploads, if no password,
            # we allow it as requested.
            return f(*args, **kwargs)

        if session.get("session_password_validated", False):
            return f(*args, **kwargs)

        logger.warning(
            f"Unauthorized access attempt (session/admin required) by session: "
            f"{get_request_session_id()}, IP: {request.remote_addr} "
            f"for path {request.path}"
        )
        return jsonify(
            {"error": "Session password or administrator privileges required."}
        ), 401

    return decorated_function


def get_show_hidden_flag():
    """
    Get show_hidden flag from Flask session with automatic expiration.
    Also checks X-Show-Hidden header and query param as fallback.

    Returns True if:
    1. User is admin AND Flask session has show_hidden=True (not expired), OR
    2. User is admin AND X-Show-Hidden header is 'true', OR
    3. User is admin AND show_hidden query param is 'true'

    Returns:
        bool: True if admin AND show_hidden is active, False otherwise
    """
    # Only allow show_hidden for authenticated admins
    if not is_current_admin_session_with_flag_sync():
        return False

    # Check Flask session first (with expiry)
    show_hidden = session.get("show_hidden", False)
    if show_hidden:
        timestamp = session.get("show_hidden_timestamp", 0)
        duration = session.get("show_hidden_duration", 3600)

        if time.time() - timestamp > duration:
            # Expired - clear session
            session.pop("show_hidden", None)
            session.pop("show_hidden_timestamp", None)
            session.pop("show_hidden_duration", None)
            session.modified = True
        else:
            return True

    # Fallback: Check for X-Show-Hidden header (case-insensitive) OR query param
    if request.headers.get("X-Show-Hidden", "").lower() == "true":
        return True
    if request.args.get("show_hidden", "").lower() == "true":
        return True
    return False
