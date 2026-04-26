"""Specter service for Flask request/response lifecycle hooks."""

from collections import OrderedDict
import gzip
import logging
import os
import uuid

from flask import abort, request, session
from gevent.lock import BoundedSemaphore

from specter import Service, registry
from app.services.core.session_store import is_blocked

logger = logging.getLogger(__name__)


COMPRESSIBLE_MIME_TYPES = {
    'application/javascript',
    'application/json',
    'application/manifest+json',
    'application/xml',
    'image/svg+xml',
    'text/css',
    'text/html',
    'text/javascript',
    'text/plain',
    'text/xml',
}

_gzip_cache = OrderedDict()
_gzip_cache_lock = BoundedSemaphore(1)


class AppRequestLifecycleService(Service):
    """Own Flask middleware registration for request/response handling."""

    def __init__(self):
        super().__init__('app_request_lifecycle', {
            'hooks_registered': False,
        })

    def on_start(self):
        """Register Flask lifecycle hooks on the current app."""
        app = registry.require('service_manager').app
        self._register_request_hooks(app)
        self.set_state({
            'hooks_registered': True,
        })

    @staticmethod
    def _register_request_hooks(app):
        """Attach the request/response middleware owned by this service."""

        @app.before_request
        def make_session_permanent():
            """Keep Flask session lifetime aligned with the custom cookie."""
            session.permanent = True

        @app.before_request
        def block_kicked_ips():
            """Block clients that were explicitly kicked from the session."""
            if is_blocked(request.remote_addr):
                logger.warning(
                    "Blocked IP %s attempted to access %s",
                    request.remote_addr,
                    request.path,
                )
                abort(403, "Your IP address has been temporarily blocked from this session.")

        @app.after_request
        def ensure_session_cookie(response):
            """Attach the custom session cookie to successful responses."""
            if 'session_id' in request.cookies or response.status_code >= 400:
                return response

            session_id = session.get('server_session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['server_session_id'] = session_id

            max_age = app.config.get('SESSION_EXPIRY', 604800)
            secure_setting = app.config.get('SESSION_COOKIE_SECURE_MODE', 'auto')
            if isinstance(secure_setting, str):
                secure_setting = secure_setting.strip().lower()
            else:
                secure_setting = 'true' if bool(secure_setting) else 'false'

            secure = request.is_secure if secure_setting == 'auto' else secure_setting == 'true'

            logger.info("Setting new session_id cookie via global after_request: %s", session_id)
            response.set_cookie(
                'session_id',
                session_id,
                max_age=max_age,
                httponly=False,
                samesite='Lax',
                secure=secure,
            )
            return response

        @app.after_request
        def optimize_response(response):
            """Apply shared caching and security headers."""
            if request.path.startswith('/static/'):
                response.headers['Cache-Control'] = 'public, max-age=86400'

            if request.path.startswith('/media/'):
                response.headers['Content-Encoding'] = 'identity'

            if request.path.startswith('/api/'):
                vary = response.headers.get('Vary', '')
                if vary:
                    if 'X-Show-Hidden' not in vary:
                        response.headers['Vary'] = f"{vary}, X-Show-Hidden"
                else:
                    response.headers['Vary'] = 'X-Show-Hidden'

            response.headers.setdefault('X-Frame-Options', 'DENY')
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
            response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
            response.headers.setdefault(
                'Content-Security-Policy',
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "worker-src 'self' blob:; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "media-src 'self' blob:; "
                "connect-src 'self' ws: wss:; "
                "font-src 'self' data:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "object-src 'none'",
            )
            return AppRequestLifecycleService._compress_response_if_supported(app, response)

    @staticmethod
    def _append_vary_header(response, value):
        """Append a value to the Vary header without duplicating entries."""
        current = [
            part.strip()
            for part in response.headers.get('Vary', '').split(',')
            if part.strip()
        ]
        if value not in current:
            current.append(value)
            response.headers['Vary'] = ', '.join(current)

    @staticmethod
    def _client_accepts_gzip():
        """Return True when the client allows gzip content encoding."""
        return request.accept_encodings['gzip'] > 0

    @staticmethod
    def _is_download_response(response):
        """Return True when the response represents a file download/attachment."""
        content_disposition = response.headers.get('Content-Disposition', '')
        return 'attachment' in content_disposition.lower()

    @staticmethod
    def _is_compressible_response(app, response):
        """Return True when the current response should be gzip-compressed."""
        if not app.config.get('ENABLE_GZIP_COMPRESSION', True):
            return False

        if request.method == 'HEAD':
            return False

        if request.path.startswith('/media/') or request.path.startswith('/socket.io'):
            return False

        if response.status_code < 200 or response.status_code in (204, 206, 304):
            return False

        if 'Content-Range' in response.headers:
            return False

        if AppRequestLifecycleService._is_download_response(response):
            return False

        # Non-static streamed/direct-passthrough responses should keep their original delivery mode.
        if (
            not request.path.startswith('/static/')
            and (response.is_streamed or response.direct_passthrough)
        ):
            return False

        if not AppRequestLifecycleService._client_accepts_gzip():
            return False

        content_encoding = response.headers.get('Content-Encoding', '').strip().lower()
        if content_encoding and content_encoding != 'identity':
            return False

        mimetype = (response.mimetype or '').lower()
        if not (mimetype.startswith('text/') or mimetype in COMPRESSIBLE_MIME_TYPES):
            return False

        return True

    @staticmethod
    def _compress_response_if_supported(app, response):
        """Gzip eligible text responses for clients that advertise support."""
        AppRequestLifecycleService._append_vary_header(response, 'Accept-Encoding')
        if not AppRequestLifecycleService._is_compressible_response(app, response):
            return response

        min_size = max(0, int(app.config.get('GZIP_MIN_SIZE', 1024)))
        compression_level = min(9, max(1, int(app.config.get('GZIP_COMPRESSION_LEVEL', 5))))
        cache_key = AppRequestLifecycleService._build_static_cache_key(app, response, compression_level)

        response.direct_passthrough = False
        payload = response.get_data()
        if len(payload) < min_size:
            return response

        compressed = AppRequestLifecycleService._get_cached_gzip_payload(app, cache_key)
        if compressed is None:
            compressed = gzip.compress(payload, compresslevel=compression_level)
            if len(compressed) >= len(payload):
                return response
            AppRequestLifecycleService._store_cached_gzip_payload(app, cache_key, compressed)

        if len(compressed) >= len(payload):
            return response

        response.set_data(compressed)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = str(len(compressed))
        response.headers.pop('ETag', None)
        return response

    @staticmethod
    def _build_static_cache_key(app, response, compression_level):
        """Build a stable cache key for static-file gzip responses."""
        if not app.config.get('ENABLE_GZIP_CACHE', True):
            return None

        if not request.path.startswith('/static/'):
            return None

        static_root = os.path.abspath(app.static_folder or '')
        rel_path = request.path[len('/static/'):].lstrip('/')
        candidate = os.path.abspath(os.path.join(static_root, rel_path))
        if not static_root or (
            candidate != static_root and not candidate.startswith(f'{static_root}{os.sep}')
        ):
            return None

        try:
            stat_info = os.stat(candidate)
        except OSError:
            return None

        return (
            candidate,
            stat_info.st_mtime_ns,
            stat_info.st_size,
            response.mimetype,
            compression_level,
        )

    @staticmethod
    def _get_cached_gzip_payload(app, cache_key):
        """Fetch a compressed static payload from the LRU cache."""
        if cache_key is None:
            return None

        with _gzip_cache_lock:
            payload = _gzip_cache.pop(cache_key, None)
            if payload is None:
                return None
            _gzip_cache[cache_key] = payload
            return payload

    @staticmethod
    def _store_cached_gzip_payload(app, cache_key, compressed):
        """Store a compressed static payload in the bounded LRU cache."""
        if cache_key is None:
            return

        max_entries = max(1, int(app.config.get('GZIP_CACHE_MAX_ENTRIES', 64)))
        with _gzip_cache_lock:
            _gzip_cache[cache_key] = compressed
            while len(_gzip_cache) > max_entries:
                _gzip_cache.popitem(last=False)
