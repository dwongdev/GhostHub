"""
Tests for Subtitle Routes
--------------------------
Tests subtitle management and serving endpoints.
"""
import pytest
import os
from unittest.mock import patch, mock_open, MagicMock


class TestGetVideoSubtitles:
    """Tests for GET /api/subtitles/video endpoint."""

    def test_get_subtitles_disabled(self, client, app_context, mock_config):
        """Should return empty array when subtitles disabled."""
        mock_config('ENABLE_SUBTITLES', False)

        response = client.get('/api/subtitles/video?video_url=/media/movies/test.mp4')

        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_get_subtitles_missing_video_url(self, client, app_context, mock_config):
        """Should return error when video_url missing."""
        mock_config('ENABLE_SUBTITLES', True)

        response = client.get('/api/subtitles/video')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_get_subtitles_success(self, client, app_context, mock_config, tmp_path):
        """Should return subtitles for existing video."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.get_category_by_id',
                   return_value={'id': 'movies', 'path': str(tmp_path / 'movies')}):
            with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
                with patch('os.path.exists', return_value=True):
                    mock_subtitle_service.is_subtitles_enabled.return_value = True
                    mock_subtitle_service.get_subtitles_for_video.return_value = [
                        {'label': 'English', 'src': '/api/subtitles/cache?file=test_en.vtt'},
                        {'label': 'Spanish', 'src': '/api/subtitles/cache?file=test_es.vtt'}
                    ]

                    response = client.get('/api/subtitles/video?video_url=/media/movies/test.mp4')

                    assert response.status_code == 200
                    data = response.get_json()
                    assert len(data) == 2
                    assert data[0]['label'] == 'English'

    def test_get_subtitles_video_not_found(self, client, app_context, mock_config, tmp_path):
        """Should return empty array when video not found."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.get_category_by_id',
                   return_value={'id': 'movies', 'path': str(tmp_path / 'movies')}):
            with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
                with patch('os.path.exists', return_value=False):
                    mock_subtitle_service.is_subtitles_enabled.return_value = True

                    response = client.get('/api/subtitles/video?video_url=/media/movies/notfound.mp4')

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data == []

    def test_get_subtitles_category_not_found(self, client, app_context, mock_config):
        """Should return empty array when category not found."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.get_category_by_id', return_value=None):
            with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
                mock_subtitle_service.is_subtitles_enabled.return_value = True

                response = client.get('/api/subtitles/video?video_url=/media/invalid/test.mp4')

                assert response.status_code == 200
                data = response.get_json()
                assert data == []

    def test_get_subtitles_url_decoding(self, client, app_context, mock_config, tmp_path):
        """Should decode URL-encoded filenames."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.get_category_by_id',
                   return_value={'id': 'movies', 'path': str(tmp_path / 'movies')}):
            with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
                with patch('os.path.exists', return_value=True):
                    mock_subtitle_service.is_subtitles_enabled.return_value = True
                    mock_subtitle_service.get_subtitles_for_video.return_value = []

                    response = client.get('/api/subtitles/video?video_url=/media/movies/test%20movie.mp4')

                    assert response.status_code == 200
                    # Should have decoded "test%20movie.mp4" to "test movie.mp4"
                    mock_subtitle_service.get_subtitles_for_video.assert_called_once()

    def test_get_subtitles_error_handling(self, client, app_context, mock_config):
        """Should return 500 on service error."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.get_category_by_id',
                   side_effect=Exception('Database error')):
            with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
                mock_subtitle_service.is_subtitles_enabled.return_value = True

                response = client.get('/api/subtitles/video?video_url=/media/movies/test.mp4')

                assert response.status_code == 500


class TestServeCachedSubtitle:
    """Tests for GET /api/subtitles/cache endpoint."""

    def test_serve_cached_disabled(self, client, app_context, mock_config):
        """Should return 404 when subtitles disabled."""
        mock_config('ENABLE_SUBTITLES', False)

        response = client.get('/api/subtitles/cache?file=test.vtt')

        assert response.status_code == 404

    def test_serve_cached_missing_file_param(self, client, app_context, mock_config):
        """Should return error when file param missing."""
        mock_config('ENABLE_SUBTITLES', True)

        response = client.get('/api/subtitles/cache')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_serve_cached_invalid_extension(self, client, app_context, mock_config):
        """Should reject non-VTT files."""
        mock_config('ENABLE_SUBTITLES', True)

        response = client.get('/api/subtitles/cache?file=test.txt')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid file type' in data['error']

    def test_serve_cached_success(self, client, app_context, mock_config, tmp_path):
        """Should serve cached subtitle file."""
        mock_config('ENABLE_SUBTITLES', True)

        # Create a test VTT file
        vtt_file = tmp_path / 'test.vtt'
        vtt_file.write_text('WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest subtitle')

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
            mock_subtitle_service.get_cached_subtitle_file.return_value = str(vtt_file)

            response = client.get('/api/subtitles/cache?file=test.vtt')

            assert response.status_code == 200
            # Check content type
            assert response.content_type == 'text/vtt; charset=utf-8'

    def test_serve_cached_file_not_found(self, client, app_context, mock_config):
        """Should return 404 when cached file not found."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
            mock_subtitle_service.get_cached_subtitle_file.return_value = '/nonexistent/test.vtt'

            with patch('os.path.exists', return_value=False):
                response = client.get('/api/subtitles/cache?file=test.vtt')

                assert response.status_code == 404

    def test_serve_cached_error_handling(self, client, app_context, mock_config):
        """Should return 500 on service error."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
            mock_subtitle_service.get_cached_subtitle_file.side_effect = Exception('IO error')

            response = client.get('/api/subtitles/cache?file=test.vtt')

            assert response.status_code == 500


class TestServeExternalSubtitle:
    """Tests for GET /api/subtitles/external endpoint."""

    def test_serve_external_disabled(self, client, app_context, mock_config):
        """Should return 404 when subtitles disabled."""
        mock_config('ENABLE_SUBTITLES', False)

        response = client.get('/api/subtitles/external?path=/path/to/test.vtt')

        assert response.status_code == 404

    def test_serve_external_missing_path(self, client, app_context, mock_config):
        """Should return error when path param missing."""
        mock_config('ENABLE_SUBTITLES', True)

        response = client.get('/api/subtitles/external')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_serve_external_invalid_extension(self, client, app_context, mock_config):
        """Should reject non-VTT files."""
        mock_config('ENABLE_SUBTITLES', True)

        response = client.get('/api/subtitles/external?path=/path/to/test.txt')

        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid file type' in data['error']

    def test_serve_external_security_check(self, client, app_context, mock_config, tmp_path):
        """Should reject files outside media directories."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service, \
             patch('app.controllers.media.subtitle_controller.get_all_categories_with_details',
                   return_value=[{'path': str(tmp_path / 'movies')}]):
            mock_subtitle_service.is_subtitles_enabled.return_value = True

            # Try to access file outside allowed directories
            response = client.get('/api/subtitles/external?path=/etc/passwd.vtt')

            assert response.status_code == 403
            data = response.get_json()
            assert 'Access denied' in data['error']

    def test_serve_external_success(self, client, app_context, mock_config, tmp_path):
        """Should serve external subtitle file from valid directory."""
        mock_config('ENABLE_SUBTITLES', True)

        # Create media directory and subtitle file
        movies_dir = tmp_path / 'movies'
        movies_dir.mkdir()
        vtt_file = movies_dir / 'test.vtt'
        vtt_file.write_text('WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest subtitle')

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service, \
             patch('app.controllers.media.subtitle_controller.get_all_categories_with_details',
                   return_value=[{'path': str(movies_dir)}]):
            mock_subtitle_service.is_subtitles_enabled.return_value = True

            response = client.get(f'/api/subtitles/external?path={str(vtt_file)}')

            assert response.status_code == 200
            assert response.content_type == 'text/vtt; charset=utf-8'

    def test_serve_external_file_not_found(self, client, app_context, mock_config, tmp_path):
        """Should return 404 when file doesn't exist."""
        mock_config('ENABLE_SUBTITLES', True)

        movies_dir = tmp_path / 'movies'
        movies_dir.mkdir()

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service, \
             patch('app.controllers.media.subtitle_controller.get_all_categories_with_details',
                   return_value=[{'path': str(movies_dir)}]):
            mock_subtitle_service.is_subtitles_enabled.return_value = True

            response = client.get(f'/api/subtitles/external?path={str(movies_dir / "notfound.vtt")}')

            assert response.status_code == 404


class TestClearSubtitleCache:
    """Tests for POST /api/subtitles/clear-cache endpoint."""

    def test_clear_cache_disabled(self, admin_client, app_context, mock_config):
        """Should indicate subtitles disabled."""
        mock_config('ENABLE_SUBTITLES', False)

        response = admin_client.post('/api/subtitles/clear-cache')

        assert response.status_code == 200
        data = response.get_json()
        assert 'Subtitles are disabled' in data['message']

    def test_clear_cache_requires_admin(self, client, app_context, mock_config):
        """Should require admin privileges."""
        mock_config('ENABLE_SUBTITLES', True)

        response = client.post('/api/subtitles/clear-cache')
        assert response.status_code == 403

    def test_clear_cache_success(self, admin_client, app_context, mock_config, tmp_path):
        """Should clear cached subtitle files."""
        mock_config('ENABLE_SUBTITLES', True)

        # Create cache directory with VTT files
        cache_dir = tmp_path / 'subtitle_cache'
        cache_dir.mkdir()
        (cache_dir / 'test1.vtt').write_text('WEBVTT')
        (cache_dir / 'test2.vtt').write_text('WEBVTT')
        (cache_dir / 'other.txt').write_text('not a subtitle')

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
            mock_subtitle_service.get_subtitle_cache_dir.return_value = str(cache_dir)

            response = admin_client.post('/api/subtitles/clear-cache')

            assert response.status_code == 200
            data = response.get_json()
            assert 'cleared' in data
            assert data['cleared'] == 2  # Should clear 2 VTT files

            # VTT files should be removed
            assert not (cache_dir / 'test1.vtt').exists()
            assert not (cache_dir / 'test2.vtt').exists()
            # Other files should remain
            assert (cache_dir / 'other.txt').exists()

    def test_clear_cache_no_directory(self, admin_client, app_context, mock_config):
        """Should handle non-existent cache directory."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
            mock_subtitle_service.get_subtitle_cache_dir.return_value = '/nonexistent/cache'

            response = admin_client.post('/api/subtitles/clear-cache')

            assert response.status_code == 200
            data = response.get_json()
            assert data['cleared'] == 0
            assert 'does not exist' in data['message']

    def test_clear_cache_error_handling(self, admin_client, app_context, mock_config):
        """Should return 500 on error."""
        mock_config('ENABLE_SUBTITLES', True)

        with patch('app.controllers.media.subtitle_controller.subtitle_service') as mock_subtitle_service:
            mock_subtitle_service.get_subtitle_cache_dir.side_effect = Exception('IO error')

            response = admin_client.post('/api/subtitles/clear-cache')

            assert response.status_code == 500
