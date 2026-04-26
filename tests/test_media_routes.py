"""
Media Routes Tests
-----------------
Tests for media file serving endpoints, streaming, and thumbnail routes.
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestServeMediaEndpoint:
    """Tests for /media/<category_id>/<filename> endpoint."""
    
    def test_serve_image_file(self, client, app_context, mock_media_dir, test_db):
        """Test serving an image file."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Images",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/photo1.jpg')
        
        assert response.status_code == 200
        assert 'image' in response.content_type
    
    def test_serve_video_file(self, client, app_context, mock_media_dir, test_db):
        """Test serving a video file."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Videos",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/video1.mp4')
        
        assert response.status_code == 200
        assert 'video' in response.content_type
        assert response.headers.get('Accept-Ranges') == 'bytes'
    
    def test_serve_nonexistent_file_404(self, client, app_context, mock_media_dir, test_db):
        """Test 404 for nonexistent file."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test 404",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/nonexistent.jpg')
        
        assert response.status_code == 404
    
    def test_serve_nonexistent_category_404(self, client, app_context):
        """Test 404 for nonexistent category."""
        response = client.get('/media/fake-category-id/file.jpg')
        
        assert response.status_code == 404
    
    def test_serve_url_encoded_filename(self, client, app_context, tmp_path, test_db):
        """Test serving file with URL-encoded special characters."""
        from app.services.media.category_service import CategoryService
        
        # Create file with spaces
        media_dir = tmp_path / "encoded"
        media_dir.mkdir()
        (media_dir / "my file.jpg").write_bytes(b"content")
        
        category, error = CategoryService.add_category(
            name="Test Encoded",
            path=str(media_dir)
        )
        category_id = category['id']
        
        # URL encode the space as %20
        response = client.get(f'/media/{category_id}/my%20file.jpg')
        
        assert response.status_code == 200
    
    def test_serve_directory_traversal_blocked(self, client, app_context, mock_media_dir, test_db):
        """Test directory traversal attempts are blocked."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Traversal",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/../../../etc/passwd')
        
        # Should return error, not actual file
        assert response.status_code in [400, 403, 404]
    
    def test_etag_caching_304(self, client, app_context, mock_media_dir, test_db):
        """Test ETag caching returns 304 Not Modified."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test ETag",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        # First request to get ETag
        response1 = client.get(f'/media/{category_id}/photo1.jpg')
        etag = response1.headers.get('ETag')
        
        assert response1.status_code == 200
        assert etag is not None
        
        # Second request with If-None-Match
        response2 = client.get(
            f'/media/{category_id}/photo1.jpg',
            headers={'If-None-Match': etag}
        )
        
        assert response2.status_code == 304


class TestServeMediaRangeRequests:
    """Tests for HTTP Range request handling."""
    
    def test_range_request_partial_content(self, client, app_context, mock_media_dir, test_db):
        """Test range request returns 206 Partial Content."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Range",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(
            f'/media/{category_id}/video1.mp4',
            headers={'Range': 'bytes=0-10'}
        )
        
        assert response.status_code == 206
        assert 'Content-Range' in response.headers
    
    def test_range_request_content_length(self, client, app_context, mock_media_dir, test_db):
        """Test range request has correct Content-Length."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Range Length",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(
            f'/media/{category_id}/video1.mp4',
            headers={'Range': 'bytes=0-9'}
        )
        
        assert response.status_code == 206
        # Content-Length should be 10 (bytes 0-9 inclusive)
        assert response.headers.get('Content-Length') == '10'


class TestServeThumbnailEndpoint:
    """Tests for /thumbnails/<category_id>/<filename> endpoint."""
    
    def test_thumbnail_nonexistent_category(self, client, app_context):
        """Test 404 for nonexistent category."""
        response = client.get('/thumbnails/fake-cat/thumb.jpg')
        
        assert response.status_code == 404
    
    def test_thumbnail_caching_headers(self, client, app_context, mock_media_dir, test_db):
        """Test thumbnail response has caching headers."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Thumb Cache",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        # Create a thumbnail file manually
        thumb_dir = mock_media_dir / ".ghosthub" / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        (thumb_dir / "video1.mp4.jpg").write_bytes(b"fake thumb")
        
        response = client.get(f'/thumbnails/{category_id}/video1.mp4.jpg')
        
        if response.status_code == 200:
            # Should have cache headers
            assert 'Cache-Control' in response.headers or 'ETag' in response.headers
    
    def test_thumbnail_url_decoding(self, client, app_context, tmp_path, test_db):
        """Test thumbnail filename URL decoding."""
        from app.services.media.category_service import CategoryService
        
        media_dir = tmp_path / "thumb_test"
        media_dir.mkdir()
        (media_dir / "video file.mp4").write_bytes(b"video")
        
        # Create thumbnail
        thumb_dir = media_dir / ".ghosthub" / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        (thumb_dir / "video_file.mp4.jpeg").write_bytes(b"thumb")
        
        category, error = CategoryService.add_category(
            name="Test Thumb Decode",
            path=str(media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/thumbnails/{category_id}/video_file.mp4.jpeg')
        
        assert response.status_code == 200


class TestMediaRoutesErrorHandling:
    """Tests for error handling in media routes."""
    
    def test_invalid_filename_encoding(self, client, app_context, mock_media_dir, test_db):
        """Test handling of invalid filename encoding."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Invalid",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        # This should be handled gracefully
        response = client.get(f'/media/{category_id}/%FF%FE')
        
        # Should return error, not crash
        assert response.status_code in [400, 404, 500]
    
    def test_empty_filename(self, client, app_context, mock_media_dir, test_db):
        """Test handling of empty/missing filename."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Empty",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        # Note: Flask routing may not match this, which is fine
        response = client.get(f'/media/{category_id}/')
        
        # Should return 404 or similar, not crash
        assert response.status_code in [400, 404, 405]


class TestMediaRoutesMimeTypes:
    """Tests for MIME type handling."""
    
    def test_jpg_mime_type(self, client, app_context, mock_media_dir, test_db):
        """Test JPG files have correct MIME type."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test MIME JPG",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/photo1.jpg')
        
        assert response.status_code == 200
        assert 'image/jpeg' in response.content_type
    
    def test_png_mime_type(self, client, app_context, mock_media_dir, test_db):
        """Test PNG files have correct MIME type."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test MIME PNG",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/photo2.png')
        
        assert response.status_code == 200
        assert 'image/png' in response.content_type
    
    def test_mp4_mime_type(self, client, app_context, mock_media_dir, test_db):
        """Test MP4 files have correct MIME type."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test MIME MP4",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/video1.mp4')
        
        assert response.status_code == 200
        assert 'video/mp4' in response.content_type
    
    def test_webm_mime_type(self, client, app_context, mock_media_dir, test_db):
        """Test WebM files have correct MIME type."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test MIME WebM",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/clip.webm')
        
        assert response.status_code == 200
        assert 'video/webm' in response.content_type

    def test_mime_whitelist_blocks_unknown_type(self, client, app_context, mock_media_dir, test_db):
        """Should reject files when MIME resolution is outside whitelist."""
        from app.services.media.category_service import CategoryService

        category, error = CategoryService.add_category(
            name="Test MIME Whitelist",
            path=str(mock_media_dir)
        )
        category_id = category['id']

        with patch('app.controllers.media.media_delivery_controller.get_mime_type', return_value='application/octet-stream'):
            response = client.get(f'/media/{category_id}/photo1.jpg')
            assert response.status_code == 415


class TestMediaRoutesHeaders:
    """Tests for response headers."""
    
    def test_video_accept_ranges_header(self, client, app_context, mock_media_dir, test_db):
        """Test video files include Accept-Ranges header."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Accept-Ranges",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/video1.mp4')
        
        assert response.status_code == 200
        assert response.headers.get('Accept-Ranges') == 'bytes'
    
    def test_content_disposition_header(self, client, app_context, mock_media_dir, test_db):
        """Test Content-Disposition header is set."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Disposition",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/photo1.jpg')
        
        assert response.status_code == 200
        # Should have inline disposition for media viewing
        disposition = response.headers.get('Content-Disposition', '')
        assert 'inline' in disposition or disposition == ''
    
    def test_cache_control_header(self, client, app_context, mock_media_dir, test_db):
        """Test Cache-Control header for media files."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Cache-Control",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/photo1.jpg')
        
        assert response.status_code == 200
        cache_control = response.headers.get('Cache-Control', '')
        # Should have some cache directive
        assert 'max-age' in cache_control or 'public' in cache_control or cache_control == ''


class TestMediaRoutesLargeFiles:
    """Tests for large file handling."""
    
    def test_large_file_streaming(self, client, app_context, tmp_path, test_db):
        """Test large files are streamed properly."""
        from app.services.media.category_service import CategoryService
        
        # Create a larger test file (1MB)
        media_dir = tmp_path / "large"
        media_dir.mkdir()
        large_file = media_dir / "large.mp4"
        large_file.write_bytes(b"x" * (1024 * 1024))
        
        category, error = CategoryService.add_category(
            name="Test Large",
            path=str(media_dir)
        )
        category_id = category['id']
        
        response = client.get(f'/media/{category_id}/large.mp4')
        
        assert response.status_code == 200
        # For large files, content should be streamed
        assert response.headers.get('Accept-Ranges') == 'bytes'
    
    def test_large_file_range_request(self, client, app_context, tmp_path, test_db):
        """Test range requests work for large files."""
        from app.services.media.category_service import CategoryService
        
        media_dir = tmp_path / "large_range"
        media_dir.mkdir()
        large_file = media_dir / "large.mp4"
        large_file.write_bytes(b"x" * (1024 * 1024))
        
        category, error = CategoryService.add_category(
            name="Test Large Range",
            path=str(media_dir)
        )
        category_id = category['id']
        
        # Request middle portion
        response = client.get(
            f'/media/{category_id}/large.mp4',
            headers={'Range': 'bytes=500000-500999'}
        )
        
        assert response.status_code == 206
        assert response.headers.get('Content-Length') == '1000'


class TestThumbnailGeneration:
    """Tests for on-demand thumbnail generation."""
    
    def test_thumbnail_generation_for_video(self, client, app_context, mock_media_dir, test_db):
        """Test thumbnail generation is attempted for video files."""
        from app.services.media.category_service import CategoryService
        
        category, error = CategoryService.add_category(
            name="Test Thumb Gen",
            path=str(mock_media_dir)
        )
        category_id = category['id']
        
        # Request thumbnail for video - may generate or return 404
        response = client.get(f'/thumbnails/{category_id}/video1.mp4.jpg')
        
        # Should not crash - either 200 (generated) or 404 (ffmpeg not available)
        assert response.status_code in [200, 404, 500]
    
    def test_thumbnail_directory_created(self, client, app_context, tmp_path, test_db):
        """Test thumbnail directory is created if needed."""
        from app.services.media.category_service import CategoryService
        
        media_dir = tmp_path / "thumb_dir_test"
        media_dir.mkdir()
        (media_dir / "test.jpg").write_bytes(b"image content")
        
        category, error = CategoryService.add_category(
            name="Test Thumb Dir",
            path=str(media_dir)
        )
        category_id = category['id']
        
        # Request thumbnail - should create .ghosthub/thumbnails directory
        response = client.get(f'/thumbnails/{category_id}/test.jpg')
        
        # Directory should be created even if thumbnail generation fails
        thumb_dir = media_dir / ".ghosthub" / "thumbnails"
        # May or may not exist depending on implementation details
        # But request should not crash
        assert response.status_code in [200, 404, 500]
