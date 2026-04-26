"""
Streaming Service Tests
----------------------
Tests for HTTP Range request parsing, video streaming, and file caching.
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from flask import Response


class TestParseRangeHeader:
    """Tests for parse_range_header function."""
    
    def test_no_range_header(self, app_context):
        """Test when no range header is provided."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header(None, 1000)
        
        assert start == 0
        assert end == 999
        assert is_range is False
    
    def test_invalid_range_header_format(self, app_context):
        """Test invalid range header without bytes= prefix."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header("invalid-header", 1000)
        
        assert start == 0
        assert end == 999
        assert is_range is False
    
    def test_simple_range_request(self, app_context):
        """Test simple range: bytes=0-499."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header("bytes=0-499", 1000)
        
        assert start == 0
        assert end == 499
        assert is_range is True
    
    def test_range_from_offset(self, app_context):
        """Test range from offset: bytes=500-."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header("bytes=500-", 1000)
        
        assert start == 500
        assert end == 999
        assert is_range is True
    
    def test_suffix_range(self, app_context):
        """Test suffix range: bytes=-200 (last 200 bytes)."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header("bytes=-200", 1000)
        
        assert start == 800
        assert end == 999
        assert is_range is True
    
    def test_suffix_range_larger_than_file(self, app_context):
        """Test suffix range larger than file size."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header("bytes=-2000", 1000)
        
        assert start == 0
        assert end == 999
        assert is_range is True
    
    def test_invalid_range_start_beyond_file(self, app_context):
        """Test invalid range where start is beyond file size returns 'invalid' (416)."""
        from app.services.streaming.streaming_service import parse_range_header

        start, end, is_range = parse_range_header("bytes=2000-3000", 1000)

        assert is_range == 'invalid'

    def test_invalid_range_start_greater_than_end(self, app_context):
        """Test invalid range where start > end returns 'invalid' (416)."""
        from app.services.streaming.streaming_service import parse_range_header

        start, end, is_range = parse_range_header("bytes=500-100", 1000)

        assert is_range == 'invalid'
    
    def test_multi_range_uses_first(self, app_context):
        """Test that multi-range requests use only the first range."""
        from app.services.streaming.streaming_service import parse_range_header
        
        start, end, is_range = parse_range_header("bytes=0-100, 200-300", 1000)
        
        assert start == 0
        assert end == 100
        assert is_range is True
    
    def test_malformed_range_value(self, app_context):
        """Test malformed range value returns 'invalid' (416)."""
        from app.services.streaming.streaming_service import parse_range_header

        start, end, is_range = parse_range_header("bytes=abc-xyz", 1000)

        assert is_range == 'invalid'


class TestIsVideoFile:
    """Tests for is_video_file function."""
    
    def test_mp4_is_video(self, app_context):
        """Test .mp4 is recognized as video."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("movie.mp4") is True
    
    def test_mkv_is_video(self, app_context):
        """Test .mkv is recognized as video."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("movie.mkv") is True
    
    def test_webm_is_video(self, app_context):
        """Test .webm is recognized as video."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("clip.webm") is True
    
    def test_mov_is_video(self, app_context):
        """Test .mov is recognized as video."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("video.MOV") is True
    
    def test_jpg_is_not_video(self, app_context):
        """Test .jpg is not a video."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("photo.jpg") is False
    
    def test_png_is_not_video(self, app_context):
        """Test .png is not a video."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("image.png") is False
    
    def test_case_insensitive(self, app_context):
        """Test case insensitivity."""
        from app.services.streaming.streaming_service import is_video_file
        
        assert is_video_file("VIDEO.MP4") is True
        assert is_video_file("Movie.MKV") is True


class TestServeSmallFile:
    """Tests for serve_small_file function."""
    
    def test_serve_small_image(self, app_context, tmp_path):
        """Test serving a small image file."""
        from app.services.streaming.streaming_service import serve_small_file
        
        # Create a test file
        test_file = tmp_path / "test.jpg"
        test_content = b"fake image content"
        test_file.write_bytes(test_content)
        
        response = serve_small_file(
            str(test_file),
            "image/jpeg",
            '"123-456"',
            is_video=False
        )
        
        assert response.status_code == 200
        assert response.content_type == "image/jpeg"
        assert b"fake image content" in response.data
    
    def test_serve_small_video(self, app_context, tmp_path):
        """Test serving a small video file with video headers."""
        from app.services.streaming.streaming_service import serve_small_file
        
        test_file = tmp_path / "test.mp4"
        test_content = b"fake video content"
        test_file.write_bytes(test_content)
        
        response = serve_small_file(
            str(test_file),
            "video/mp4",
            '"123-456"',
            is_video=True
        )
        
        assert response.status_code == 200
        assert "video/mp4" in response.content_type
        assert response.headers.get('Accept-Ranges') == 'bytes'
    
    def test_serve_nonexistent_file(self, app_context, tmp_path):
        """Test serving a file that doesn't exist."""
        from app.services.streaming.streaming_service import serve_small_file
        
        response = serve_small_file(
            str(tmp_path / "nonexistent.jpg"),
            "image/jpeg",
            '"123-456"',
            is_video=False
        )
        
        # Should return error response
        assert response[1] == 500  # Status code
    
    def test_caching_headers(self, app_context, tmp_path):
        """Test that caching headers are set correctly."""
        from app.services.streaming.streaming_service import serve_small_file
        
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"content")
        
        response = serve_small_file(
            str(test_file),
            "image/jpeg",
            '"test-etag"',
            is_video=False
        )
        
        assert 'Cache-Control' in response.headers
        assert 'ETag' in response.headers


class TestStreamVideoFile:
    """Tests for stream_video_file function."""
    
    def test_full_video_request(self, app, tmp_path):
        """Test serving full video without range header."""
        from app.services.streaming.streaming_service import stream_video_file
        
        test_file = tmp_path / "video.mp4"
        test_content = b"x" * 10000
        test_file.write_bytes(test_content)
        
        with app.test_request_context():
            response = stream_video_file(
                str(test_file),
                "video/mp4",
                10000,
                '"etag-123"'
            )
            
            assert response.status_code == 200
            assert response.headers.get('Content-Length') == '10000'
            assert response.headers.get('Accept-Ranges') == 'bytes'
    
    def test_range_request_partial_content(self, app, tmp_path):
        """Test range request returns 206 Partial Content."""
        from app.services.streaming.streaming_service import stream_video_file
        
        test_file = tmp_path / "video.mp4"
        test_content = b"x" * 10000
        test_file.write_bytes(test_content)
        
        with app.test_request_context(headers={'Range': 'bytes=0-999'}):
            response = stream_video_file(
                str(test_file),
                "video/mp4",
                10000,
                '"etag-123"'
            )
            
            assert response.status_code == 206
            assert response.headers.get('Content-Length') == '1000'
            assert 'Content-Range' in response.headers
    
    def test_etag_not_modified(self, app, tmp_path):
        """Test If-None-Match returns 304 Not Modified."""
        from app.services.streaming.streaming_service import stream_video_file
        
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"content")
        
        with app.test_request_context(headers={'If-None-Match': '"etag-123"'}):
            response = stream_video_file(
                str(test_file),
                "video/mp4",
                7,
                '"etag-123"'
            )
            
            assert response[1] == 304  # Not Modified
    
    def test_content_range_header_format(self, app, tmp_path):
        """Test Content-Range header format for range requests."""
        from app.services.streaming.streaming_service import stream_video_file
        
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"x" * 1000)
        
        with app.test_request_context(headers={'Range': 'bytes=100-199'}):
            response = stream_video_file(
                str(test_file),
                "video/mp4",
                1000,
                None
            )
            
            assert response.headers.get('Content-Range') == 'bytes 100-199/1000'


class TestServeLargeFileNonBlocking:
    """Tests for serve_large_file_non_blocking function."""
    
    def test_serve_large_image(self, app, tmp_path):
        """Test serving large non-video file."""
        from app.services.streaming.streaming_service import serve_large_file_non_blocking

        test_file = tmp_path / "large.jpg"
        test_content = b"x" * 100000
        test_file.write_bytes(test_content)

        with app.test_request_context():
            response = serve_large_file_non_blocking(
                str(test_file),
                "image/jpeg",
                100000,
                '"etag"',
                is_video=False
            )

            assert response.status_code == 200
            assert 'X-Accel-Buffering' in response.headers
    
    def test_serve_large_video(self, app, tmp_path):
        """Test serving large video with preloading."""
        from app.services.streaming.streaming_service import serve_large_file_non_blocking

        test_file = tmp_path / "large.mp4"
        test_content = b"x" * 100000
        test_file.write_bytes(test_content)

        with app.test_request_context():
            response = serve_large_file_non_blocking(
                str(test_file),
                "video/mp4",
                100000,
                '"etag"',
                is_video=True
            )

            assert response.status_code == 200
            assert response.headers.get('Accept-Ranges') == 'bytes'
    
    def test_range_request_large_file(self, app, tmp_path):
        """Test range request for large file."""
        from app.services.streaming.streaming_service import serve_large_file_non_blocking

        test_file = tmp_path / "large.mp4"
        test_content = b"x" * 100000
        test_file.write_bytes(test_content)

        with app.test_request_context():
            response = serve_large_file_non_blocking(
                str(test_file),
                "video/mp4",
                100000,
                '"etag"',
                is_video=True,
                range_start=0,
                range_end=9999
            )

            assert response.status_code == 206
            assert 'Content-Range' in response.headers


class TestCommonResponseHeaders:
    """Tests for _set_common_response_headers function."""
    
    def test_video_headers(self, app_context, tmp_path):
        """Test that video files get appropriate headers."""
        from app.services.streaming.streaming_service import _set_common_response_headers
        
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"content")
        
        response = Response(b"test", mimetype="video/mp4")
        _set_common_response_headers(
            response,
            str(test_file),
            "video/mp4",
            1000,
            '"etag"',
            is_video=True
        )
        
        assert response.headers.get('Accept-Ranges') == 'bytes'
        assert 'X-Content-Type-Options' in response.headers
        assert response.headers.get('Access-Control-Allow-Origin') == '*'
    
    def test_non_video_headers(self, app_context, tmp_path):
        """Test that non-video files don't get video-specific headers."""
        from app.services.streaming.streaming_service import _set_common_response_headers
        
        test_file = tmp_path / "image.jpg"
        test_file.write_bytes(b"content")
        
        response = Response(b"test", mimetype="image/jpeg")
        _set_common_response_headers(
            response,
            str(test_file),
            "image/jpeg",
            1000,
            '"etag"',
            is_video=False
        )
        
        assert response.headers.get('Accept-Ranges') == 'none'
    
    def test_range_request_headers(self, app_context, tmp_path):
        """Test headers for range requests."""
        from app.services.streaming.streaming_service import _set_common_response_headers
        
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"content")
        
        response = Response(b"test", mimetype="video/mp4")
        _set_common_response_headers(
            response,
            str(test_file),
            "video/mp4",
            1000,
            '"etag"',
            is_video=True,
            is_range_request=True,
            range_start=0,
            range_end=499
        )
        
        assert response.status_code == 206
        assert response.headers.get('Content-Range') == 'bytes 0-499/1000'


class TestCacheIntegration:
    """Tests for cache utility integration."""
    
    def test_small_file_cache_hit(self, app_context, tmp_path):
        """Test that small files are cached and reused."""
        from app.services.streaming.streaming_service import serve_small_file
        from app.utils.cache_utils import get_from_small_cache
        
        test_file = tmp_path / "cached.jpg"
        test_file.write_bytes(b"cache test content")
        
        # First request should cache
        response1 = serve_small_file(
            str(test_file),
            "image/jpeg",
            '"cache-etag"',
            is_video=False
        )
        
        # Verify cached
        cache_result = get_from_small_cache(str(test_file))
        assert cache_result is not None
        
        # Second request should use cache
        response2 = serve_small_file(
            str(test_file),
            "image/jpeg",
            '"cache-etag"',
            is_video=False
        )
        
        assert response1.data == response2.data
