"""GhostStream ingress owned by a Specter controller."""

import logging
import os
import re
import socket

import requests as sync_requests
from flask import Response, request, send_file

from app.services.ghoststream import ghoststream_service, transcode_cache_service
from app.services.media.category_query_service import get_category_by_id
from specter import Controller, registry
from app.utils.auth import admin_required, get_request_session_id, is_current_admin_session_with_flag_sync

logger = logging.getLogger(__name__)


class GhostStreamController(Controller):
    """Own GhostStream HTTP ingress under Specter."""

    name = 'ghoststream'
    url_prefix = '/api/ghoststream'

    def build_routes(self, router):
        @router.route('/status', methods=['GET'])
        def get_status():
            return self.get_status()

        @router.route('/servers', methods=['GET'])
        def list_servers():
            return self.list_servers()

        @router.route('/servers/add', methods=['POST'])
        @admin_required
        def add_server():
            return self.add_server()

        @router.route('/servers/register', methods=['POST'])
        def register_server():
            return self.register_server()

        @router.route('/servers/unregister', methods=['POST'])
        def unregister_server():
            return self.unregister_server()

        @router.route('/servers/<server_name>', methods=['DELETE'])
        @admin_required
        def delete_server(server_name):
            return self.delete_server(server_name)

        @router.route('/servers/cleanup', methods=['POST'])
        @admin_required
        def cleanup_servers():
            return self.cleanup_servers()

        @router.route('/discovery/start', methods=['POST'])
        @admin_required
        def start_discovery():
            return self.start_discovery()

        @router.route('/discovery/stop', methods=['POST'])
        @admin_required
        def stop_discovery():
            return self.stop_discovery()

        @router.route('/capabilities', methods=['GET'])
        def get_capabilities():
            return self.get_capabilities()

        @router.route('/health', methods=['GET'])
        def health_check():
            return self.health_check()

        @router.route('/transcode', methods=['POST'])
        def start_transcode():
            return self.start_transcode()

        @router.route('/transcode/<job_id>/status', methods=['GET'])
        def get_job_status(job_id):
            return self.get_job_status(job_id)

        @router.route('/transcode/<job_id>/cancel', methods=['POST'])
        def cancel_job(job_id):
            return self.cancel_job(job_id)

        @router.route('/transcode/<job_id>/wait', methods=['GET'])
        def wait_for_job(job_id):
            return self.wait_for_job(job_id)

        @router.route('/debug', methods=['GET'])
        @admin_required
        def debug_info():
            return self.debug_info()

        @router.route('/stream/<job_id>/<path:filename>', methods=['GET', 'OPTIONS'])
        def proxy_hls_stream(job_id, filename):
            return self.proxy_hls_stream(job_id, filename)

        @router.route('/jobs/cancel-all', methods=['POST'])
        @admin_required
        def cancel_all_jobs():
            return self.cancel_all_jobs()

        @router.route('/cache/check', methods=['POST'])
        def check_cache():
            return self.check_cache()

        @router.route('/cache/serve/<category_id>/<path:filename>', methods=['GET'])
        def serve_cached_file(category_id, filename):
            return self.serve_cached_file(category_id, filename)

        @router.route('/cache/stats/<category_id>', methods=['GET'])
        def get_cache_stats(category_id):
            return self.get_cache_stats(category_id)

        @router.route('/cache/cleanup/<category_id>', methods=['POST'])
        @admin_required
        def cleanup_cache(category_id):
            return self.cleanup_cache(category_id)

        @router.route('/cache/batch', methods=['POST'])
        @admin_required
        def batch_transcode():
            return self.batch_transcode()

    def get_status(self):
        """Get GhostStream availability and server status."""
        try:
            return ghoststream_service.get_status_summary()
        except Exception as exc:
            logger.error("Error getting GhostStream status: %s", exc, exc_info=True)
            return {
                'available': False,
                'reason': f'GhostStream unavailable: {exc}',
                'servers': [],
                'discovery_started': False,
                'server_count': 0,
            }

    def list_servers(self):
        """Get the full list of GhostStream servers."""
        try:
            servers = ghoststream_service.get_servers()
            return {
                'servers': servers,
                'count': len(servers),
            }
        except Exception as exc:
            logger.error("Error listing GhostStream servers: %s", exc)
            return {'error': str(exc)}, 500

    def add_server(self):
        """Add a manual GhostStream server after verifying health."""
        data = request.get_json(silent=True) or {}
        address = data.get('address')

        if not address:
            return {'error': 'address is required'}, 400

        if ':' not in address:
            address = f'{address}:8765'

        try:
            import httpx

            host, port = address.split(':', 1)
            test_url = f'http://{host}:{port}/api/health'

            try:
                with httpx.Client(timeout=3.0) as client:
                    logger.info("[GhostStream] Testing connection to %s", test_url)
                    response = client.get(test_url)
                    logger.info("[GhostStream] Health check response: %s", response.status_code)
                    if response.status_code != 200:
                        return {
                            'error': (
                                f'Server responded with status {response.status_code}. '
                                'Is GhostStream running?'
                            ),
                        }, 400

                    health_data = response.json()
                    version = health_data.get('version', '')
                    hw_accels = health_data.get('hw_accels', [])
                    logger.info(
                        "[GhostStream] Server info: version=%s, hw_accels=%s",
                        version,
                        hw_accels,
                    )
            except httpx.ConnectError as exc:
                logger.error("[GhostStream] Connect error to %s: %s", address, exc)
                return {
                    'error': (
                        f'Cannot connect to {address}. Check the address and ensure '
                        'GhostStream is running.'
                    ),
                }, 400
            except httpx.TimeoutException:
                logger.error("[GhostStream] Timeout connecting to %s", address)
                return {'error': f'Connection to {address} timed out after 3s.'}, 400
            except Exception as exc:
                logger.error("[GhostStream] Connection failed to %s: %s", address, exc)
                return {'error': f'Connection failed: {exc}'}, 400

            success = ghoststream_service.add_manual_server(
                address,
                version=version,
                hw_accels=hw_accels,
            )
            if not success:
                return {'error': 'Failed to add server'}, 500

            return {
                'message': f'Server {address} added successfully',
                'servers': ghoststream_service.get_servers(),
            }
        except Exception as exc:
            logger.error("Error adding GhostStream server: %s", exc)
            return {'error': str(exc)}, 500

    def register_server(self):
        """Register a GhostStream server from GhostStream itself."""
        data = request.get_json(silent=True) or {}
        address = data.get('address')

        logger.info(
            "[GhostStream] Registration request received from %s: %s",
            request.remote_addr,
            data,
        )

        if not address:
            remote_ip = request.remote_addr
            port = data.get('port', 8765)
            address = f'{remote_ip}:{port}'
            logger.info("[GhostStream] No address provided, using remote IP: %s", address)

        if ':' not in address:
            address = f'{address}:8765'

        ghosthub_callback_url = f'http://{request.host}'
        logger.info("[GhostStream] GhostStream reached us via: %s", ghosthub_callback_url)

        try:
            success = ghoststream_service.add_manual_server(
                address,
                name=data.get('name'),
                version=data.get('version'),
                hw_accels=data.get('hw_accels'),
                ghosthub_callback_url=ghosthub_callback_url,
            )
            if not success:
                return {'error': 'Failed to register server', 'registered': False}, 500

            logger.info(
                "[GhostStream] Server registered successfully: %s (callback: %s)",
                address,
                ghosthub_callback_url,
            )
            return {
                'message': f'Server {address} registered successfully',
                'registered': True,
                'ghosthub_url': ghosthub_callback_url,
            }
        except Exception as exc:
            logger.error("Error registering GhostStream server: %s", exc)
            return {'error': str(exc), 'registered': False}, 500

    def unregister_server(self):
        """Unregister a GhostStream server (used for graceful exit)."""
        data = request.get_json(silent=True) or {}
        name = data.get('name')
        
        if not name:
            return {'error': 'name required', 'unregistered': False}, 400
            
        try:
            # We use name if provided, otherwise address
            success = ghoststream_service.remove_server(name)
            if not success:
                # Try fallback address check if name didn't work (e.g. name was truncated or changed)
                address = data.get('address')
                if address:
                    success = ghoststream_service.remove_server(f"ghoststream_{address.replace('.', '_').split(':')[0]}")
            
            logger.info("[GhostStream] Server unregistration results for %s: %s", name, success)
            return {'unregistered': success}, 200
        except Exception as exc:
            logger.error("Error unregistering GhostStream server: %s", exc)
            return {'error': str(exc), 'unregistered': False}, 500

    def delete_server(self, server_name):
        """Remove a GhostStream server."""
        try:
            success = ghoststream_service.remove_server(server_name)
            if not success:
                return {'error': 'Server not found'}, 404

            return {
                'message': f'Server {server_name} removed',
                'servers': ghoststream_service.get_servers(),
            }
        except Exception as exc:
            logger.error("Error removing GhostStream server %s: %s", server_name, exc)
            return {'error': str(exc)}, 500

    def cleanup_servers(self):
        """Remove unreachable GhostStream servers."""
        try:
            removed = ghoststream_service.cleanup_unreachable_servers()
            return {
                'message': f'Removed {removed} unreachable server(s)',
                'removed_count': removed,
                'servers': ghoststream_service.get_servers(),
            }
        except Exception as exc:
            logger.error("Error cleaning up GhostStream servers: %s", exc)
            return {'error': str(exc)}, 500

    def start_discovery(self):
        """Start mDNS discovery for GhostStream servers."""
        try:
            success = registry.require('ghoststream_runtime').start_discovery()
            if success:
                return {'message': 'Discovery started'}
            return {'error': 'Failed to start discovery'}, 500
        except Exception as exc:
            logger.error("Error starting GhostStream discovery: %s", exc)
            return {'error': str(exc)}, 500

    def stop_discovery(self):
        """Stop GhostStream discovery."""
        try:
            registry.require('ghoststream_runtime').stop_discovery()
            return {'message': 'Discovery stopped'}
        except Exception as exc:
            logger.error("Error stopping GhostStream discovery: %s", exc)
            return {'error': str(exc)}, 500

    def get_capabilities(self):
        """Get capabilities for the preferred or requested GhostStream server."""
        server_name = request.args.get('server')

        try:
            capabilities = ghoststream_service.get_capabilities(server_name)
            if capabilities:
                return capabilities
            return {'error': 'No server available or failed to get capabilities'}, 404
        except Exception as exc:
            logger.error("Error getting GhostStream capabilities: %s", exc)
            return {'error': str(exc)}, 500

    def health_check(self):
        """Check health of the preferred or requested GhostStream server."""
        server_name = request.args.get('server')

        try:
            return {
                'healthy': ghoststream_service.health_check(server_name),
                'server': server_name or 'preferred',
            }
        except Exception as exc:
            logger.error("Error checking GhostStream health: %s", exc)
            return {'error': str(exc)}, 500

    def start_transcode(self):
        """Start a GhostStream transcoding job."""
        data = request.get_json(silent=True) or {}
        source = data.get('source')
        category_id = data.get('category_id')
        filename = data.get('filename')
        ghosthub_base = None

        if source and not is_current_admin_session_with_flag_sync():
            return {'error': 'Only administrators may transcode arbitrary source URLs'}, 403

        if not source:
            if not category_id or not filename:
                return {'error': 'category_id and filename required'}, 400

            ghosthub_base = self._resolve_ghosthub_base_url(data)
            if not ghosthub_base:
                return {'error': 'Could not determine a safe GhostHub source URL'}, 500
            source = ghoststream_service.build_source_url(category_id, filename, ghosthub_base)
            logger.info("[GhostStream] Built source URL: %s", source)

        try:
            session_id = get_request_session_id()
            subtitles = []
            if category_id and filename:
                ghosthub_base = ghosthub_base or self._resolve_ghosthub_base_url(data)
                subtitles = self._build_subtitle_payloads(category_id, filename, ghosthub_base)

            job = ghoststream_service.transcode(
                source=source,
                mode=data.get('mode', 'stream'),
                format=data.get('format', 'hls'),
                video_codec=data.get('video_codec', 'h264'),
                audio_codec=data.get('audio_codec', 'aac'),
                resolution=data.get('resolution', 'original'),
                bitrate=data.get('bitrate', 'auto'),
                hw_accel=data.get('hw_accel', 'auto'),
                start_time=float(data.get('start_time', 0)),
                abr=data.get('abr', False),
                session_id=session_id,
                subtitles=subtitles or None,
            )

            if not job:
                return {'error': 'Failed to start transcode - no server available'}, 503

            if job.get('error'):
                return job, 503

            if job.get('status') == 'error':
                return {
                    'error': job.get('error_message', 'Transcoding failed'),
                    'job_id': job.get('job_id'),
                }, 500

            logger.info(
                "[GhostStream] Returning to frontend: job_id=%s, stream_url=%s, status=%s",
                job.get('job_id'),
                job.get('stream_url'),
                job.get('status'),
            )
            return job
        except Exception as exc:
            logger.error("Error starting GhostStream transcode: %s", exc)
            return {'error': str(exc)}, 500

    def get_job_status(self, job_id):
        """Get the status of a GhostStream job."""
        try:
            job = ghoststream_service.get_job_status(job_id)
            if job:
                return job
            return {'error': 'Job not found'}, 404
        except Exception as exc:
            logger.error("Error getting GhostStream job status %s: %s", job_id, exc)
            return {'error': str(exc)}, 500

    def cancel_job(self, job_id):
        """Cancel a GhostStream job."""
        try:
            success = ghoststream_service.cancel_job(job_id)
            if success:
                return {'message': 'Job cancelled', 'job_id': job_id}
            return {'error': 'Failed to cancel job'}, 500
        except Exception as exc:
            logger.error("Error cancelling GhostStream job %s: %s", job_id, exc)
            return {'error': str(exc)}, 500

    def wait_for_job(self, job_id):
        """Wait for a GhostStream job to reach a terminal streaming state."""
        timeout = request.args.get('timeout', 60, type=float)

        try:
            job = ghoststream_service.wait_for_ready(job_id, timeout=timeout)
            if job:
                return job
            return {'error': 'Timeout or job failed'}, 408
        except Exception as exc:
            logger.error("Error waiting for GhostStream job %s: %s", job_id, exc)
            return {'error': str(exc)}, 500

    def debug_info(self):
        """Return GhostStream connectivity debug information."""
        local_ip = 'unknown'
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(('8.8.8.8', 80))
            local_ip = probe.getsockname()[0]
            probe.close()
        except Exception as exc:
            local_ip = f'error: {exc}'

        servers = ghoststream_service.get_servers()
        server_health = []
        for server in servers:
            server_health.append({
                **server,
                'health_check': 'ok' if ghoststream_service.health_check(server.get('name')) else 'failed',
            })

        return {
            'ghosthub_ip': local_ip,
            'ghosthub_host': request.host,
            'discovery_started': ghoststream_service.is_discovery_started(),
            'available': ghoststream_service.is_available(),
            'server_count': len(servers),
            'servers': server_health,
            'preferred_server': ghoststream_service.get_preferred_server(),
            'tips': [
                'Ensure GhostStream is running on another device',
                'Both devices must be on the same network',
                f'GhostStream should register at: http://{local_ip}:5000/api/ghoststream/servers/register',
                'Or manually add server in GhostHub settings',
            ],
        }

    def proxy_hls_stream(self, job_id, filename):
        """Proxy HLS assets from GhostStream to avoid browser CORS issues."""
        if request.method == 'OPTIONS':
            return Response('', status=204, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Range',
                'Access-Control-Max-Age': '86400',
            })

        upstream_url = ghoststream_service.get_stream_proxy_target(job_id, filename)
        if not upstream_url:
            return {'error': 'No GhostStream server available'}, 503

        try:
            request_headers = ghoststream_service.get_job_auth_headers(job_id)
            response = sync_requests.get(
                upstream_url,
                timeout=120.0,
                allow_redirects=False,
                headers=request_headers,
            )

            if response.status_code == 307:
                redirect_url = response.headers.get('location', '')
                if redirect_url:
                    match = re.search(r'/stream/([^/]+)/(.+)$', redirect_url)
                    if match:
                        proxy_redirect = f"/api/ghoststream/stream/{match.group(1)}/{match.group(2)}"
                        logger.info(
                            "[GhostStream Proxy] Stream restarted, redirecting to %s",
                            proxy_redirect,
                        )
                        return Response('', status=307, headers={
                            'Location': proxy_redirect,
                            'Access-Control-Allow-Origin': '*',
                        })
                return Response(response.content, status=307, headers={
                    'Location': redirect_url,
                    'Access-Control-Allow-Origin': '*',
                })

            if response.status_code != 200:
                return Response(response.content, status=response.status_code)

            if filename.endswith('.m3u8'):
                content_type = 'application/vnd.apple.mpegurl'
            elif filename.endswith('.ts'):
                content_type = 'video/mp2t'
            elif filename.endswith('.mp4'):
                content_type = 'video/mp4'
            else:
                content_type = 'application/octet-stream'

            return Response(
                response.content,
                status=200,
                content_type=content_type,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'no-cache',
                },
            )
        except Exception as exc:
            logger.error("[GhostStream Proxy] Error: %s", exc)
            return {'error': str(exc)}, 500

    def cancel_all_jobs(self):
        """Cancel all active GhostStream jobs."""
        try:
            cancelled = ghoststream_service.cancel_all_jobs()
            return {'cancelled': cancelled, 'success': True}
        except Exception as exc:
            logger.error("Error cancelling all GhostStream jobs: %s", exc)
            return {'error': str(exc), 'cancelled': 0}, 500

    def check_cache(self):
        """Check if a transcoded cache entry already exists."""
        data = request.get_json(silent=True) or {}
        category_id = data.get('category_id')
        filename = data.get('filename')
        resolution = data.get('resolution', 'original')
        video_codec = data.get('video_codec', 'h264')
        audio_codec = data.get('audio_codec', 'aac')

        if not category_id or not filename:
            return {'error': 'category_id and filename required'}, 400

        try:
            category_path = self._get_category_path(category_id)
            if not category_path:
                return {'cached': False, 'error': 'Category not found'}

            cached_path = transcode_cache_service.get_cached_file(
                category_path,
                filename,
                resolution,
                video_codec,
                audio_codec,
            )
            if not cached_path:
                return {'cached': False}

            return {
                'cached': True,
                'path': cached_path,
                'url': f"/api/ghoststream/cache/serve/{category_id}/{os.path.basename(cached_path)}",
            }
        except Exception as exc:
            logger.error("Error checking GhostStream cache: %s", exc)
            return {'cached': False, 'error': str(exc)}

    def serve_cached_file(self, category_id, filename):
        """Serve a cached transcoded file."""
        try:
            category_path = self._get_category_path(category_id)
            if not category_path:
                return {'error': 'Category not found'}, 404

            cache_dir = transcode_cache_service.get_cache_path(category_path).resolve()
            file_path = (cache_dir / filename).resolve()
            if cache_dir not in file_path.parents:
                logger.warning(
                    "Blocked GhostStream cache traversal attempt: %s",
                    filename,
                )
                return {'error': 'Cached file not found'}, 404

            if not file_path.exists():
                return {'error': 'Cached file not found'}, 404

            return send_file(file_path, mimetype='video/mp4', as_attachment=False)
        except Exception as exc:
            logger.error("Error serving cached GhostStream file: %s", exc)
            return {'error': str(exc)}, 500

    def get_cache_stats(self, category_id):
        """Get cache statistics for a category."""
        try:
            category_path = self._get_category_path(category_id)
            if not category_path:
                return {'error': 'Category not found'}, 404

            return transcode_cache_service.get_cache_stats(category_path)
        except Exception as exc:
            logger.error("Error getting GhostStream cache stats: %s", exc)
            return {'error': str(exc)}, 500

    def cleanup_cache(self, category_id):
        """Clean up GhostStream cache for a category."""
        data = request.get_json(silent=True) or {}
        max_age_days = data.get('max_age_days', 30)
        max_size_gb = data.get('max_size_gb', 50)

        try:
            category_path = self._get_category_path(category_id)
            if not category_path:
                return {'error': 'Category not found'}, 404

            age_removed = transcode_cache_service.cleanup_old_cache(category_path, max_age_days)
            size_removed = transcode_cache_service.cleanup_cache_by_size(category_path, max_size_gb)
            return {
                'removed_by_age': age_removed,
                'removed_by_size': size_removed,
                'total_removed': age_removed + size_removed,
            }
        except Exception as exc:
            logger.error("Error cleaning GhostStream cache: %s", exc)
            return {'error': str(exc)}, 500

    def batch_transcode(self):
        """Start GhostStream batch transcoding to cache for a category."""
        data = request.get_json(silent=True) or {}
        category_id = data.get('category_id')
        files = data.get('files')
        resolution = data.get('resolution', 'original')
        video_codec = data.get('video_codec', 'h264')
        audio_codec = data.get('audio_codec', 'aac')

        if not category_id:
            return {'error': 'category_id required'}, 400

        try:
            category_path = self._get_category_path(category_id)
            if not category_path:
                return {'error': 'Category not found'}, 404

            if not files:
                return {
                    'error': 'files list required; enumerate directory contents client-side before calling batch transcode',
                }, 400

            ghosthub_base_url = data.get('ghosthub_base_url') or self._build_request_base_url()
            logger.info("[GhostStream] Batch transcode using base URL: %s", ghosthub_base_url)

            return transcode_cache_service.batch_transcode_to_cache(
                category_path,
                files,
                resolution,
                video_codec,
                audio_codec,
                category_id=category_id,
                ghosthub_base_url=ghosthub_base_url,
            )
        except Exception as exc:
            logger.error("Error starting GhostStream batch transcode: %s", exc)
            return {'error': str(exc)}, 500

    def _get_category_path(self, category_id):
        """Resolve the category path for a category id."""
        category = get_category_by_id(category_id)
        return category.get('path') if category else None

    def _build_subtitle_payloads(self, category_id, filename, ghosthub_base):
        """Build GhostStream subtitle payloads for a media item."""
        from app.services.media import subtitle_service

        subtitles = []
        if not subtitle_service.is_subtitles_enabled():
            return subtitles

        category = get_category_by_id(category_id)
        if not category:
            return subtitles

        video_path = os.path.join(category['path'], filename)
        if not os.path.exists(video_path):
            return subtitles

        available_subs = subtitle_service.get_subtitles_for_video(video_path, category_id)
        for subtitle in available_subs:
            if subtitle.get('url') and subtitle.get('supported', True):
                subtitles.append({
                    'url': f"{ghosthub_base}{subtitle['url']}",
                    'label': subtitle.get('label', 'Unknown'),
                    'language': subtitle.get('language', 'und'),
                    'default': subtitle.get('default', False),
                })

        if subtitles:
            logger.info("[GhostStream] Found %s subtitles for %s", len(subtitles), filename)
        return subtitles

    def _resolve_ghosthub_base_url(self, data):
        """Resolve a GhostHub base URL that GhostStream can reach."""
        ghosthub_base = ghoststream_service.get_server_callback_url()
        if ghosthub_base:
            logger.info("[GhostStream] Using stored callback URL: %s", ghosthub_base)
            return ghosthub_base

        preferred_server = ghoststream_service.get_preferred_server()
        if preferred_server:
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                probe.connect((preferred_server['host'], preferred_server['port']))
                local_ip = probe.getsockname()[0]
                probe.close()
                if local_ip and not local_ip.startswith('127.'):
                    port = request.host.split(':')[1] if ':' in request.host else '5000'
                    ghosthub_base = f'http://{local_ip}:{port}'
                    logger.info("[GhostStream] Found reachable IP for GhostStream: %s", ghosthub_base)
                    return ghosthub_base
            except Exception as exc:
                logger.warning("[GhostStream] Could not find reachable IP: %s", exc)

        provided_base = data.get('ghosthub_base_url')
        if provided_base:
            logger.info("[GhostStream] Using frontend-provided URL: %s", provided_base)
            ghosthub_base = provided_base

        needs_detection = (
            not ghosthub_base or
            'ghosthub.local' in ghosthub_base or
            'ghosthub.mesh.local' in ghosthub_base or
            'localhost' in ghosthub_base or
            '127.0.0.1' in ghosthub_base
        )
        if not needs_detection:
            return ghosthub_base

        request_host = request.host.split(':')[0]
        port = request.host.split(':')[1] if ':' in request.host else '5000'
        logger.info("[GhostStream] Request host: %s:%s", request_host, port)

        if request_host not in ('ghosthub.local', 'ghosthub.mesh.local', 'localhost', '127.0.0.1'):
            detected_base = f'http://{request_host}:{port}'
            logger.info("[GhostStream] Using request host IP: %s", detected_base)
            return detected_base

        detected_ip = self._detect_local_ip()
        if detected_ip:
            detected_base = f'http://{detected_ip}:{port}'
            logger.info("[GhostStream] Using detected IP: %s", detected_base)
            return detected_base

        fallback = f'http://192.168.4.1:{port}'
        logger.warning("[GhostStream] Using default AP IP: %s", fallback)
        return fallback

    def _build_request_base_url(self):
        """Build a reasonable GhostHub base URL from the current request."""
        request_host = request.host.split(':')[0]
        port = request.host.split(':')[1] if ':' in request.host else '5000'

        if request_host in ('localhost', '127.0.0.1', 'ghosthub.local', 'ghosthub.mesh.local'):
            request_host = self._detect_local_ip() or '192.168.4.1'

        return f'http://{request_host}:{port}'

    @staticmethod
    def _detect_local_ip():
        """Detect a LAN-reachable local IP address for GhostHub."""
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            probe.connect(('<broadcast>', 0))
            detected_ip = probe.getsockname()[0]
            probe.close()
            if detected_ip and not detected_ip.startswith('127.'):
                logger.info("[GhostStream] Broadcast detection found: %s", detected_ip)
                return detected_ip
        except Exception:
            pass

        try:
            hostname = socket.gethostname()
            for ip_info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                detected_ip = ip_info[4][0]
                if not detected_ip.startswith('127.'):
                    logger.info("[GhostStream] Hostname lookup found: %s", detected_ip)
                    return detected_ip
        except Exception:
            pass

        for test_ip in ('192.168.4.1', '192.168.137.1', '10.42.0.1'):
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                probe.settimeout(0.1)
                probe.bind((test_ip, 0))
                probe.close()
                logger.info("[GhostStream] AP mode IP found: %s", test_ip)
                return test_ip
            except Exception:
                continue

        return None
