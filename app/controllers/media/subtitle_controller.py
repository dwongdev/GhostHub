"""Subtitle domain controller built on Specter."""

import os
import logging
import traceback

from flask import request, send_file
from urllib.parse import unquote

from specter import Controller
from app.services.media.category_query_service import (
    get_all_categories_with_details,
    get_category_by_id,
)
from app.services import subtitle_service
from app.utils.auth import admin_required, get_show_hidden_flag

logger = logging.getLogger(__name__)


class SubtitleController(Controller):
    """Controller for subtitle management and serving."""

    name = 'subtitle'
    url_prefix = '/api/subtitles'

    def build_routes(self, router):
        """Register HTTP endpoints for subtitle administration and streaming."""
        
        @router.route('/video', methods=['GET'])
        def get_video_subtitles():
            """Get available subtitles for a video file."""
            from flask import jsonify
            if not subtitle_service.is_subtitles_enabled():
                return jsonify([])
            
            video_url = request.args.get('video_url', '')
            if not video_url:
                return jsonify({'error': 'video_url parameter is required'}), 400
            
            try:
                if video_url.startswith('/media/'):
                    parts = video_url[7:].split('/', 1)
                    if len(parts) == 2:
                        category_id, filename = parts
                        filename = unquote(filename)
                        
                        from app.services.media.hidden_content_service import (
                            should_block_category_access,
                            should_block_file_access,
                        )

                        show_hidden = get_show_hidden_flag()
                        if should_block_category_access(category_id, show_hidden):
                            return jsonify([])

                        category = get_category_by_id(category_id)
                        if category and category.get('path'):
                            video_path = os.path.join(category['path'], filename)
                            video_path = os.path.realpath(video_path)

                            from app.services.storage import storage_io_service

                            if not storage_io_service.is_path_within(category['path'], video_path):
                                logger.warning(
                                    "Rejected subtitle lookup outside category root: %s",
                                    video_path,
                                )
                                return jsonify([])

                            if should_block_file_access(video_path, category_id, show_hidden):
                                return jsonify([])

                            if os.path.exists(video_path):
                                subtitles = subtitle_service.get_subtitles_for_video(video_path, category_id)
                                return jsonify(subtitles)
                            else:
                                logger.warning(f"Video file not found for subtitle lookup: {video_path}")
                                return jsonify([])
                        else:
                            logger.warning(f"Category not found for subtitle lookup: {category_id}")
                            return jsonify([])
                
                return jsonify([])
            except Exception as e:
                logger.error(f"Error getting subtitles for video: {e}")
                logger.debug(traceback.format_exc())
                return jsonify({'error': 'Failed to get subtitles'}), 500

        @router.route('/cache', methods=['GET'])
        def serve_cached_subtitle():
            """Serve a cached subtitle file (VTT format)."""
            if not subtitle_service.is_subtitles_enabled():
                return '', 404
            
            filename = request.args.get('file', '')
            from flask import jsonify
            if not filename:
                return jsonify({'error': 'file parameter is required'}), 400
            
            # Security: only allow .vtt files
            if not filename.endswith('.vtt'):
                return jsonify({'error': 'Invalid file type'}), 400
            
            try:
                file_path = subtitle_service.get_cached_subtitle_file(filename)
                if file_path and os.path.exists(file_path):
                    return send_file(
                        file_path,
                        mimetype='text/vtt',
                        as_attachment=False,
                        download_name=filename
                    )
                return '', 404
            except Exception as e:
                logger.error(f"Error serving cached subtitle: {e}")
                return '', 500

        @router.route('/external', methods=['GET'])
        def serve_external_subtitle():
            """Serve an external VTT subtitle file from the media directory."""
            if not subtitle_service.is_subtitles_enabled():
                return '', 404
            
            file_path = request.args.get('path', '')
            from flask import jsonify
            if not file_path:
                return jsonify({'error': 'path parameter is required'}), 400
            
            if not file_path.lower().endswith('.vtt'):
                return jsonify({'error': 'Invalid file type'}), 400
            
            try:
                # Security check
                file_path = os.path.realpath(file_path)
                categories = get_all_categories_with_details()
                is_valid_path = False
                matched_category_id = None

                for cat in categories:
                    cat_path = cat.get('path', '')
                    if cat_path and file_path.startswith(os.path.realpath(cat_path) + os.sep):
                        is_valid_path = True
                        matched_category_id = cat.get('id')
                        break

                if not is_valid_path:
                    logger.warning(f"Attempted to access subtitle outside media directories: {file_path}")
                    return jsonify({'error': 'Access denied'}), 403

                # Hidden content guard
                from app.services.media.hidden_content_service import (
                    should_block_category_access,
                    should_block_file_access,
                )
                show_hidden = get_show_hidden_flag()
                if matched_category_id and should_block_category_access(matched_category_id, show_hidden):
                    return '', 404
                if should_block_file_access(file_path, matched_category_id, show_hidden):
                    return '', 404

                if os.path.exists(file_path):
                    return send_file(
                        file_path,
                        mimetype='text/vtt',
                        as_attachment=False
                    )
                return '', 404
            except Exception as e:
                logger.error(f"Error serving external subtitle: {e}")
                return '', 500

        @router.route('/clear-cache', methods=['POST'])
        @admin_required
        def clear_subtitle_cache():
            """Clear the subtitle cache to force regeneration."""
            from flask import jsonify
            if not subtitle_service.is_subtitles_enabled():
                return jsonify({'message': 'Subtitles are disabled'}), 200
            
            try:
                cache_dir = subtitle_service.get_subtitle_cache_dir()
                if os.path.exists(cache_dir):
                    count = 0
                    for filename in os.listdir(cache_dir):
                        if filename.endswith('.vtt'):
                            try:
                                os.remove(os.path.join(cache_dir, filename))
                                count += 1
                            except OSError:
                                pass
                    logger.info(f"Cleared {count} cached subtitle files")
                    return jsonify({'message': f'Cleared {count} cached subtitle files', 'cleared': count})
                return jsonify({'message': 'Cache directory does not exist', 'cleared': 0})
            except Exception as e:
                logger.error(f"Error clearing subtitle cache: {e}")
                return jsonify({'error': 'Failed to clear cache'}), 500
