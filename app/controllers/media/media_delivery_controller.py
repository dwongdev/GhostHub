"""Media delivery controller built on Specter."""

import logging
import os
import traceback
import gevent
from urllib.parse import unquote

from flask import Response, abort, request, send_file
from werkzeug import exceptions as werkzeug_exceptions

from app.services.core.runtime_config_service import (
    get_runtime_config_value,
    get_runtime_root_path,
    get_runtime_static_folder,
)
from app.services.media.category_query_service import get_category_by_id
from app.services.media import media_path_service
from app.services.streaming.streaming_service import SMALL_FILE_THRESHOLD, SPECIAL_MIME_TYPES, is_video_file, serve_large_file_non_blocking, serve_small_file, stream_video_file
from specter import Controller, registry
from app.utils.auth import get_show_hidden_flag
from app.utils.media_utils import (
    GHOSTHUB_DIR_NAME,
    PLACEHOLDER_THUMBNAIL,
    THUMBNAIL_DIR_NAME,
    get_mime_type,
)

logger = logging.getLogger(__name__)


class MediaDeliveryController(Controller):
    """Own direct media and thumbnail delivery endpoints."""

    name = 'media_delivery'

    def __init__(self):
        super().__init__()
        self._directory_cache = None
        self._directory_cache_size = None

    def build_routes(self, router):
        @router.route('/media/<category_id>/<path:filename>')
        def serve_media(category_id, filename):
            """Serve a media file with optimized streaming."""
            return self.serve_media(category_id, filename)

        @router.route('/thumbnails/<category_id>/<filename>')
        def serve_thumbnail(category_id, filename):
            """Serve a generated thumbnail with caching."""
            return self.serve_thumbnail(category_id, filename)

    def serve_media(self, category_id, filename):
        """Serve media file with optimized streaming based on file type and size."""
        decoded_filename = filename
        try:
            from app.services.media.hidden_content_service import (
                should_block_category_access,
                should_block_file_access,
            )

            show_hidden = get_show_hidden_flag()
            if should_block_category_access(category_id, show_hidden):
                logger.warning(
                    "Blocked media access to hidden category %s from %s",
                    category_id,
                    request.remote_addr,
                )
                return {'error': 'Media not found'}, 404

            try:
                decoded_filename = unquote(filename)
            except Exception as decode_error:
                logger.error("Error decoding filename '%s': %s", filename, decode_error)
                return {'error': 'Invalid filename encoding'}, 400

            filepath, error = media_path_service.get_media_filepath(category_id, decoded_filename)
            if error:
                if 'not found' in error:
                    status_code = 404
                elif 'not readable' in error or 'Access denied' in error:
                    status_code = 403
                elif 'Invalid filename' in error or 'not a file' in error:
                    status_code = 400
                else:
                    status_code = 500
                logger.warning(
                    "Failed to get media filepath for Cat=%s, File='%s': %s",
                    category_id,
                    decoded_filename,
                    error,
                )
                return {'error': error}, status_code

            if should_block_file_access(filepath, category_id, show_hidden):
                logger.warning(
                    "Blocked access to hidden file %s from %s",
                    filepath,
                    request.remote_addr,
                )
                return {'error': 'Media not found'}, 404

            file_stats = os.stat(filepath)
            file_size = file_stats.st_size
            file_mtime = file_stats.st_mtime
            etag = f'"{file_stats.st_ino}-{int(file_mtime)}-{file_size}"'

            client_etag = request.headers.get('If-None-Match')
            if client_etag and client_etag == etag:
                return '', 304

            is_vid = is_video_file(decoded_filename)
            if is_vid:
                _, ext = os.path.splitext(decoded_filename.lower())
                if ext in SPECIAL_MIME_TYPES:
                    mime_type = SPECIAL_MIME_TYPES[ext]
                    logger.info("Using special MIME type for %s: %s", ext, mime_type)
                else:
                    mime_type = get_mime_type(decoded_filename)

                if not self._is_allowed_media_mime(mime_type):
                    logger.warning(
                        "Blocked media with non-whitelisted MIME type: %s (%s)",
                        mime_type,
                        decoded_filename,
                    )
                    return {'error': 'Unsupported media type'}, 415

                logger.info("Using optimized HTTP Range streaming for video: %s", decoded_filename)
                return stream_video_file(filepath, mime_type, file_size, etag)

            mime_type = get_mime_type(decoded_filename)
            if not self._is_allowed_media_mime(mime_type):
                logger.warning(
                    "Blocked non-video media with non-whitelisted MIME type: %s (%s)",
                    mime_type,
                    decoded_filename,
                )
                return {'error': 'Unsupported media type'}, 415

            if file_size < SMALL_FILE_THRESHOLD:
                return serve_small_file(filepath, mime_type, etag, is_video=False)

            return serve_large_file_non_blocking(
                filepath,
                mime_type,
                file_size,
                etag,
                is_video=False,
                range_start=None,
                range_end=None,
            )
        except Exception as exc:
            logger.error(
                "Unexpected error serving media file Cat=%s, File='%s': %s",
                category_id,
                decoded_filename,
                exc,
            )
            logger.debug(traceback.format_exc())
            return {
                'error': 'An unexpected error occurred while serving the media file',
            }, 500

    def serve_thumbnail(self, category_id, filename):
        """Serve generated thumbnail with caching headers."""
        try:
            from app.services.media.hidden_content_service import (
                should_block_category_access,
                should_block_file_access,
            )
            from app.utils.media_utils import (
                get_thumbnail_filename,
                is_thumbnail_permanently_failed,
                should_retry_thumbnail,
            )

            show_hidden = get_show_hidden_flag()
            if should_block_category_access(category_id, show_hidden):
                logger.warning(
                    "Blocked thumbnail access to hidden category %s from %s",
                    category_id,
                    request.remote_addr,
                )
                abort(404, description="Thumbnail not found")

            category = get_category_by_id(category_id)
            if not category:
                logger.warning(
                    "Thumbnail request failed: Category ID %s not found.",
                    category_id,
                )
                abort(404, description="Category not found")

            category_path = category.get('path')
            if not category_path or not os.path.isdir(category_path):
                logger.error(
                    "Thumbnail request failed: Invalid path for category ID %s: %s",
                    category_id,
                    category_path,
                )
                abort(500, description="Category path configuration error")

            try:
                decoded_filename = unquote(filename)
            except Exception as exc:
                logger.error("Error decoding filename '%s': %s", filename, exc)
                abort(400, description="Invalid filename encoding")

            thumbnail_filename = get_thumbnail_filename(decoded_filename)
            media_file_path = os.path.join(category_path, decoded_filename)
            if os.path.exists(media_file_path) and should_block_file_access(
                media_file_path,
                category_id,
                show_hidden,
            ):
                logger.warning(
                    "Blocked thumbnail access to hidden file %s from %s",
                    media_file_path,
                    request.remote_addr,
                )
                abort(404, description="Thumbnail not found")

            ghosthub_dir = os.path.join(category_path, GHOSTHUB_DIR_NAME)
            thumbnail_dir = os.path.join(ghosthub_dir, THUMBNAIL_DIR_NAME)
            os.makedirs(thumbnail_dir, exist_ok=True)

            thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
            media_path = os.path.join(category_path, decoded_filename)

            try:
                stat = os.stat(thumbnail_path)
            except OSError:
                stat = None

            if stat and stat.st_size > 0:
                etag = f"{stat.st_ino}-{int(stat.st_mtime)}-{stat.st_size}"
                if request.if_none_match and etag in request.if_none_match:
                    return Response(status=304)

                response = send_file(
                    thumbnail_path,
                    mimetype='image/jpeg',
                    conditional=True,
                    etag=etag,
                    max_age=86400,
                    last_modified=stat.st_mtime,
                )
                response.cache_control.public = True
                response.add_etag()
                return response

            if not should_retry_thumbnail(thumbnail_path, media_path):
                return self._serve_placeholder_thumbnail()

            return self._generate_and_serve_thumbnail(
                category_id,
                category_path,
                decoded_filename,
                thumbnail_dir,
            )
        except werkzeug_exceptions.NotFound:
            raise
        except Exception as exc:
            logger.error(
                "Error serving thumbnail %s for category %s: %s",
                filename,
                category_id,
                exc,
            )
            logger.debug(traceback.format_exc())
            abort(500, description="Internal server error serving thumbnail")

    def _is_allowed_media_mime(self, mime_type):
        """Validate MIME type against configured media MIME whitelist."""
        if not mime_type:
            return False

        try:
            media_types = get_runtime_config_value('MEDIA_TYPES', {})
            allowed = set()
            for section in ('image', 'video'):
                section_cfg = media_types.get(section, {})
                allowed.update(section_cfg.get('mime_types', {}).values())
            allowed.update(SPECIAL_MIME_TYPES.values())
            return mime_type in allowed
        except Exception:
            return False

    def _queue_thumbnail_generation(self, category_path, category_id, filename):
        """Queue thumbnail generation through the Specter-owned library runtime."""
        runtime = registry.require('thumbnail_runtime')
        queued = runtime.queue_thumbnail(
            category_path,
            category_id,
            filename,
            force_refresh=False,
        )
        if queued:
            logger.debug("Queued thumbnail generation for %s", filename)
        else:
            logger.warning("Failed to queue thumbnail generation for %s", filename)
        return queued

    def _serve_placeholder_thumbnail(self):
        """Serve the GhostHub logo as a placeholder thumbnail."""
        placeholder_path = os.path.join(get_runtime_root_path(), '..', PLACEHOLDER_THUMBNAIL)
        placeholder_path = os.path.normpath(placeholder_path)

        if not os.path.exists(placeholder_path):
            placeholder_path = os.path.join(
                get_runtime_static_folder(),
                'icons',
                'Ghosthub192.png',
            )

        if os.path.exists(placeholder_path):
            response = send_file(
                placeholder_path,
                mimetype='image/png',
                max_age=604800,
            )
            response.headers['X-Thumbnail-Placeholder'] = '1'
            response.cache_control.public = True
            return response

        abort(404, description="Placeholder thumbnail not found")

    def _generate_and_serve_thumbnail(self, category_id, category_path, decoded_filename, thumbnail_dir):
        """Queue thumbnail generation and return a 404 until ready."""
        try:
            media_extensions = get_runtime_config_value('MEDIA_EXTENSIONS', [])
            file_ext = os.path.splitext(decoded_filename)[1].lower()

            media_path = None
            rel_path = None

            if file_ext in media_extensions:
                media_path = os.path.join(category_path, decoded_filename)
                if not (os.path.exists(media_path) and os.path.isfile(media_path)):
                    media_path = None
                else:
                    rel_path = decoded_filename

            if not media_path:
                media_path = self._find_matching_media(category_path, decoded_filename, media_extensions)
                if media_path:
                    rel_path = os.path.relpath(media_path, category_path).replace('\\', '/')

            if media_path and os.path.exists(media_path) and os.path.isfile(media_path):
                os.makedirs(thumbnail_dir, exist_ok=True)
                logger.info(
                    "Thumbnail generation requested for %s. Media: %s",
                    decoded_filename,
                    media_path,
                )

                queued = self._queue_thumbnail_generation(
                    category_path,
                    category_id,
                    rel_path or decoded_filename,
                )
                if queued:
                    logger.info("Thumbnail queued for background generation: %s", decoded_filename)
                else:
                    logger.warning("Failed to queue thumbnail generation: %s", decoded_filename)

                abort(404, description="Thumbnail generation in progress")

            logger.warning("Media file not found for thumbnail: %s", decoded_filename)
            abort(404, description="Thumbnail not found")
        except werkzeug_exceptions.NotFound:
            raise
        except Exception as exc:
            logger.error("Error queueing thumbnail generation: %s", exc)
            logger.debug(traceback.format_exc())
            abort(500, description="Error generating thumbnail")

    def _get_directory_cache_size(self):
        """Get tier-aware cache size for directory listings."""
        try:
            from app.services.system.system_stats_service import get_hardware_tier

            tier = get_hardware_tier()
            if tier == 'PRO':
                return 2000
            if tier == 'STANDARD':
                return 500
            return 100
        except Exception as exc:
            logger.warning("Error getting hardware tier for cache size: %s", exc)
            return 100

    def _get_cached_media_files(self, category_path, mtime, extensions_tuple):
        """Cached directory listing for media files."""
        current_size = self._get_directory_cache_size()
        if self._directory_cache is None or self._directory_cache_size != current_size:
            from functools import lru_cache as create_lru_cache

            self._directory_cache = create_lru_cache(maxsize=current_size)(
                self._get_media_files_impl,
            )
            self._directory_cache_size = current_size
            logger.info("Directory cache initialized with size %s", current_size)

        return self._directory_cache(category_path, mtime, extensions_tuple)

    @staticmethod
    def _get_media_files_impl(category_path, mtime, extensions_tuple):
        """Implementation of directory scanning separated for dynamic cache sizing."""
        media_files = []
        for root, _, files in os.walk(category_path):
            for filename in files:
                if os.path.splitext(filename)[1].lower() in extensions_tuple:
                    rel_path = os.path.relpath(os.path.join(root, filename), category_path)
                    media_files.append(rel_path)
                    if len(media_files) % 200 == 0:
                        gevent.sleep(0)
        return media_files

    def _find_matching_media(self, category_path, decoded_filename, media_extensions):
        """Find a matching media file with case-insensitive search."""
        try:
            try:
                dir_mtime = os.path.getmtime(category_path)
            except OSError:
                dir_mtime = 0

            extensions_tuple = tuple(sorted(media_extensions))
            media_files = self._get_cached_media_files(category_path, dir_mtime, extensions_tuple)

            for media_file in media_files:
                if media_file.lower() == decoded_filename.lower():
                    return os.path.join(category_path, media_file)

            try:
                from app.utils.media_utils import get_thumbnail_filename

                for media_file in media_files:
                    if get_thumbnail_filename(media_file).lower() == decoded_filename.lower():
                        return os.path.join(category_path, media_file)
            except Exception as exc:
                logger.warning("Error matching thumbnail filename to media file: %s", exc)

            file_base = os.path.splitext(decoded_filename)[0]
            for media_file in media_files:
                if os.path.splitext(media_file)[0].lower() == file_base.lower():
                    return os.path.join(category_path, media_file)

            if '_' in decoded_filename:
                file_basename = os.path.basename(decoded_filename)
                file_base_without_ext, _ = os.path.splitext(file_basename.lower())
                for media_file in media_files:
                    media_base, _ = os.path.splitext(os.path.basename(media_file).lower())
                    if media_base.startswith(file_base_without_ext) or file_base_without_ext.startswith(media_base):
                        return os.path.join(category_path, media_file)
        except Exception as exc:
            logger.warning("Error searching for media file: %s", exc)

        return None
