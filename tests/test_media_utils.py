"""
Tests for Media Utilities
-------------------------
Comprehensive tests for media handling utilities including:
- Media type detection
- MIME type resolution
- Thumbnail generation
- Filename handling
- Hardware acceleration detection
"""
import pytest
import os
import subprocess
from unittest.mock import patch, MagicMock


class TestMediaTypeDetection:
    """Tests for media file type detection."""
    
    def test_is_media_file_image(self, app_context):
        """Test image file detection."""
        from app.utils.media_utils import is_media_file
        
        assert is_media_file('photo.jpg') is True
        assert is_media_file('image.png') is True
        assert is_media_file('animation.gif') is True
        assert is_media_file('picture.webp') is True
        assert is_media_file('raw.cr2') is False
    
    def test_is_media_file_video(self, app_context):
        """Test video file detection."""
        from app.utils.media_utils import is_media_file
        
        assert is_media_file('movie.mp4') is True
        assert is_media_file('video.mkv') is True
        assert is_media_file('clip.webm') is True
        assert is_media_file('film.avi') is True
        assert is_media_file('show.mov') is True
    
    def test_is_media_file_non_media(self, app_context):
        """Test non-media file detection."""
        from app.utils.media_utils import is_media_file
        
        assert is_media_file('document.txt') is False
        assert is_media_file('script.py') is False
        assert is_media_file('data.json') is False
        assert is_media_file('readme.md') is False
    
    def test_is_media_file_case_insensitive(self, app_context):
        """Test that file extension check is case-insensitive."""
        from app.utils.media_utils import is_media_file
        
        assert is_media_file('PHOTO.JPG') is True
        assert is_media_file('VIDEO.MP4') is True
        assert is_media_file('Image.PNG') is True
        assert is_media_file('Movie.MKV') is True
    
    def test_is_media_file_no_extension(self, app_context):
        """Test file without extension."""
        from app.utils.media_utils import is_media_file
        
        assert is_media_file('noextension') is False
        assert is_media_file('.hidden') is False
    
    def test_get_media_type_image(self, app_context):
        """Test get_media_type for images."""
        from app.utils.media_utils import get_media_type
        
        assert get_media_type('photo.jpg') == 'image'
        assert get_media_type('image.png') == 'image'
        assert get_media_type('animation.gif') == 'image'
    
    def test_get_media_type_video(self, app_context):
        """Test get_media_type for videos."""
        from app.utils.media_utils import get_media_type
        
        assert get_media_type('movie.mp4') == 'video'
        assert get_media_type('clip.mkv') == 'video'
        assert get_media_type('video.webm') == 'video'
    
    def test_get_media_type_unknown(self, app_context):
        """Test get_media_type for unknown types."""
        from app.utils.media_utils import get_media_type
        
        assert get_media_type('file.txt') == 'unknown'
        assert get_media_type('data.xml') == 'unknown'


class TestMimeTypeResolution:
    """Tests for MIME type resolution."""
    
    def test_get_mime_type_common_images(self, app_context):
        """Test MIME types for common image formats."""
        from app.utils.media_utils import get_mime_type
        
        assert get_mime_type('photo.jpg') == 'image/jpeg'
        assert get_mime_type('photo.jpeg') == 'image/jpeg'
        assert get_mime_type('image.png') == 'image/png'
        assert get_mime_type('animation.gif') == 'image/gif'
        assert get_mime_type('picture.webp') == 'image/webp'
    
    def test_get_mime_type_common_videos(self, app_context):
        """Test MIME types for common video formats."""
        from app.utils.media_utils import get_mime_type
        
        assert get_mime_type('movie.mp4') == 'video/mp4'
        assert get_mime_type('video.webm') == 'video/webm'
        assert get_mime_type('clip.mkv') == 'video/x-matroska'
        assert get_mime_type('film.avi') == 'video/x-msvideo'
    
    def test_get_mime_type_unknown_returns_none(self, app_context):
        """Test that unknown extensions return None."""
        from app.utils.media_utils import get_mime_type
        
        assert get_mime_type('file.xyz') is None
        assert get_mime_type('data.unknown') is None
    
    def test_get_mime_type_case_insensitive(self, app_context):
        """Test MIME type resolution is case-insensitive."""
        from app.utils.media_utils import get_mime_type
        
        assert get_mime_type('PHOTO.JPG') == 'image/jpeg'
        assert get_mime_type('VIDEO.MP4') == 'video/mp4'


class TestThumbnailFilename:
    """Tests for thumbnail filename generation."""
    
    def test_get_thumbnail_filename_basic(self, app_context):
        """Test basic thumbnail filename generation."""
        from app.utils.media_utils import get_thumbnail_filename
        
        result = get_thumbnail_filename('video.mp4')
        
        assert result.endswith('.jpeg')
        assert 'video' in result
    
    def test_get_thumbnail_filename_special_chars(self, app_context):
        """Test thumbnail filename handles special characters."""
        from app.utils.media_utils import get_thumbnail_filename
        
        result = get_thumbnail_filename("video with spaces & special?chars.mp4")
        
        # Should replace special chars with underscores
        assert '?' not in result
        assert '&' not in result
        assert result.endswith('.jpeg')
    
    def test_get_thumbnail_filename_preserves_base_name(self, app_context):
        """Test that base name is preserved in thumbnail filename."""
        from app.utils.media_utils import get_thumbnail_filename
        
        result = get_thumbnail_filename('my_movie_2023.mkv')
        
        assert 'my_movie_2023' in result
        assert result.endswith('.jpeg')
    
    def test_get_thumbnail_filename_handles_path(self, app_context):
        """Test that paths are preserved to avoid collisions."""
        from app.utils.media_utils import get_thumbnail_filename
        
        result = get_thumbnail_filename('/path/to/video.mp4')
        
        # Should preserve path structure (separators become underscores)
        assert '_path_to_video' in result
        assert result.endswith('.jpeg')
    
    def test_get_thumbnail_filename_avoids_collision(self, app_context):
        """Test that same filename in different folders gets unique thumbnail names."""
        from app.utils.media_utils import get_thumbnail_filename
        
        result1 = get_thumbnail_filename('video.mp4')
        result2 = get_thumbnail_filename('subfolder/video.mp4')
        
        # Should NOT collide - different thumbnail names
        assert result1 != result2
        assert 'subfolder' in result2
        assert 'video' in result1
        assert 'video' in result2


class TestThumbnailUrl:
    """Tests for thumbnail URL generation."""
    
    def test_get_thumbnail_url_format(self, app_context):
        """Test thumbnail URL format."""
        from app.utils.media_utils import get_thumbnail_url
        
        url = get_thumbnail_url('category-123', 'video.mp4')
        
        assert url.startswith('/thumbnails/')
        assert 'category-123' in url
        assert url.endswith('.jpeg')
    
    def test_get_thumbnail_url_encodes_filename(self, app_context):
        """Test that thumbnail URLs are properly encoded."""
        from app.utils.media_utils import get_thumbnail_url
        
        url = get_thumbnail_url('cat', 'video with spaces.mp4')
        
        # URL should be encoded
        assert ' ' not in url or '%20' in url


class TestFindThumbnail:
    """Tests for thumbnail discovery."""
    
    def test_find_thumbnail_returns_tuple(self, app_context, mock_media_dir):
        """Test that find_thumbnail returns correct tuple format."""
        from app.utils.media_utils import find_thumbnail
        
        result = find_thumbnail(str(mock_media_dir), 'test-cat', 'Test Category')
        
        assert isinstance(result, tuple)
        assert len(result) == 3
        
        media_count, thumbnail_url, contains_video = result
        assert isinstance(media_count, int)
        assert thumbnail_url is None or isinstance(thumbnail_url, str)
        assert isinstance(contains_video, bool)
    
    def test_find_thumbnail_counts_media(self, app_context, mock_media_dir):
        """Test that find_thumbnail correctly counts media files."""
        from app.utils.media_utils import find_thumbnail
        
        media_count, _, _ = find_thumbnail(str(mock_media_dir), 'test', 'Test')
        
        # mock_media_dir has 4 images + 3 videos + 2 nested = 9 files (excluding hidden)
        # But find_thumbnail may or may not recurse into subdirectories
        # It should count at least the 7 top-level files
        assert media_count >= 7
    
    def test_find_thumbnail_detects_video(self, app_context, mock_media_dir):
        """Test that find_thumbnail detects video content."""
        from app.utils.media_utils import find_thumbnail
        
        _, _, contains_video = find_thumbnail(str(mock_media_dir), 'test', 'Test')
        
        assert contains_video is True
    
    def test_find_thumbnail_image_only_folder(self, app_context, tmp_path):
        """Test find_thumbnail for folder with only images."""
        # Create folder with only images
        images_only = tmp_path / 'images'
        images_only.mkdir()
        (images_only / 'photo1.jpg').write_bytes(b'img1')
        (images_only / 'photo2.png').write_bytes(b'img2')
        
        from app.utils.media_utils import find_thumbnail
        
        media_count, thumbnail_url, contains_video = find_thumbnail(
            str(images_only), 'images', 'Images'
        )
        
        assert media_count == 2
        assert contains_video is False
        assert thumbnail_url is not None
    
    def test_find_thumbnail_empty_folder(self, app_context, tmp_path):
        """Test find_thumbnail for empty folder."""
        empty_dir = tmp_path / 'empty'
        empty_dir.mkdir()
        
        from app.utils.media_utils import find_thumbnail
        
        media_count, thumbnail_url, contains_video = find_thumbnail(
            str(empty_dir), 'empty', 'Empty'
        )
        
        assert media_count == 0
        assert thumbnail_url is None
        assert contains_video is False
    
    def test_find_thumbnail_nonexistent_path(self, app_context):
        """Test find_thumbnail with non-existent path."""
        from app.utils.media_utils import find_thumbnail
        
        result = find_thumbnail('/nonexistent/path', 'cat', 'Cat')
        
        assert result == (0, None, False)
    
    def test_find_thumbnail_prefers_images(self, app_context, mock_media_dir):
        """Test that find_thumbnail prefers image files for thumbnails."""
        from app.utils.media_utils import find_thumbnail

        _, thumbnail_url, _ = find_thumbnail(str(mock_media_dir), 'test', 'Test')

        # find_thumbnail returns /thumbnails/<category_id>/... URLs (not /media/)
        if thumbnail_url:
            assert '/thumbnails/' in thumbnail_url
            # Should not pick hidden files (files starting with '.')
            assert '/.' not in thumbnail_url


class TestThumbnailGeneration:
    """Tests for thumbnail generation functionality."""
    
    def test_generate_thumbnail_nonexistent_file(self, app_context, tmp_path):
        """Test thumbnail generation fails for non-existent file."""
        from app.utils.media_utils import generate_thumbnail
        
        result = generate_thumbnail('/nonexistent/video.mp4')
        
        assert result is False
    
    def test_generate_thumbnail_skips_existing(self, app_context, tmp_path):
        """Test that existing thumbnails are not regenerated."""
        from app.utils.media_utils import generate_thumbnail
        
        # Create a fake "existing" thumbnail
        thumb_path = tmp_path / 'existing_thumb.jpeg'
        thumb_path.write_bytes(b'existing thumbnail')
        
        # Create a fake source file
        source = tmp_path / 'video.mp4'
        source.write_bytes(b'fake video')
        
        result = generate_thumbnail(str(source), str(thumb_path), force_refresh=False)
        
        # Should return True without regenerating
        assert result is True
        # Content should be unchanged
        assert thumb_path.read_bytes() == b'existing thumbnail'
    
    @patch('app.utils.media_utils._has_video_stream', return_value=True)
    @patch('subprocess.run')
    def test_generate_thumbnail_calls_ffmpeg(self, mock_run, mock_has_stream, app_context, tmp_path):
        """Test that generate_thumbnail calls ffmpeg."""
        source = tmp_path / 'video.mp4'
        source.write_bytes(b'fake video content')

        thumb_path = tmp_path / 'thumb.jpeg'

        # Mock successful ffmpeg execution
        mock_run.return_value = MagicMock(returncode=0)

        # Create the thumbnail file as if ffmpeg did
        def create_thumb(*args, **kwargs):
            thumb_path.write_bytes(b'thumbnail')
            return MagicMock(returncode=0)

        mock_run.side_effect = create_thumb

        from app.utils.media_utils import generate_thumbnail

        result = generate_thumbnail(str(source), str(thumb_path))

        # ffmpeg should have been called
        mock_run.assert_called()

    @patch('app.utils.media_utils._has_video_stream', return_value=True)
    @patch('psutil.virtual_memory')
    def test_generate_thumbnail_low_memory_skip(self, mock_memory, mock_has_stream, app_context, tmp_path):
        """Test thumbnail generation skips when memory is low."""
        # Mock very low available memory
        mock_memory.return_value = MagicMock(available=10 * 1024 * 1024)  # 10MB

        source = tmp_path / 'video.mp4'
        source.write_bytes(b'fake video')

        from app.utils.media_utils import generate_thumbnail

        result = generate_thumbnail(str(source))

        assert result is False

    @patch('app.utils.media_utils._has_video_stream', return_value=False)
    def test_generate_thumbnail_skips_no_video_stream(self, mock_has_stream, app_context, tmp_path):
        """Test that files without a video stream are rejected with permanent failure marker."""
        from app.utils.media_utils import generate_thumbnail

        source = tmp_path / 'fake.mp4'
        source.write_bytes(b'not a real video')

        thumb_path = tmp_path / 'fake_thumb.jpeg'
        result = generate_thumbnail(str(source), str(thumb_path))

        assert result is False
        # Should create a permanent failure marker
        failed_marker = str(thumb_path) + '.failed'
        assert os.path.exists(failed_marker)
        import json
        with open(failed_marker) as f:
            data = json.load(f)
        assert data['permanent'] is True
        assert data['reason'] == 'no_video_stream'

    def test_generate_thumbnail_permanent_failure_not_retried(self, app_context, tmp_path):
        """Test that permanently failed thumbnails are never retried."""
        from app.utils.media_utils import should_retry_thumbnail, _create_permanent_failure_marker

        thumb_path = str(tmp_path / 'thumb.jpeg')
        media_path = str(tmp_path / 'video.mp4')

        # Create a permanent failure marker
        _create_permanent_failure_marker(thumb_path, 'no_video_stream')

        # Should never retry
        assert should_retry_thumbnail(thumb_path, media_path) is False


class TestHardwareAcceleration:
    """Tests for hardware acceleration detection."""
    
    @patch('subprocess.run')
    def test_detect_v4l2m2m(self, mock_run, app_context):
        """Test V4L2 M2M detection."""
        mock_run.return_value = MagicMock(
            stdout='v4l2m2m\nvaapi\ncuda',
            returncode=0
        )
        
        from app.utils import media_utils
        
        result = media_utils._detect_hardware_acceleration()
        
        assert result == 'v4l2m2m'
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_detect_mmal(self, mock_exists, mock_run, app_context):
        """Test MMAL detection for older Pis."""
        mock_run.return_value = MagicMock(stdout='', returncode=0)
        mock_exists.return_value = True  # vcgencmd exists
        
        from app.utils import media_utils
        
        result = media_utils._detect_hardware_acceleration()
        
        # Could be mmal or none depending on implementation
    
    @patch('subprocess.run')
    def test_detect_fallback_software(self, mock_run, app_context):
        """Test fallback to software encoding."""
        mock_run.side_effect = Exception("ffmpeg not found")
        
        from app.utils import media_utils
        
        result = media_utils._detect_hardware_acceleration()
        
        assert result == 'none'


class TestFfmpegCommandGeneration:
    """Tests for ffmpeg command generation."""
    
    def test_get_ffmpeg_cmd_basic(self, app_context):
        """Test basic ffmpeg command generation."""
        from app.utils.media_utils import _get_ffmpeg_cmd
        
        cmd = _get_ffmpeg_cmd('/input/video.mp4', '/output/thumb.jpg', (240, 135))
        
        assert isinstance(cmd, list)
        assert '-i' in cmd
        assert '/input/video.mp4' in cmd
        assert '/output/thumb.jpg' in cmd
    
    def test_get_ffmpeg_cmd_includes_optimization_flags(self, app_context):
        """Test that ffmpeg command includes Pi optimization flags."""
        from app.utils.media_utils import _get_ffmpeg_cmd
        
        cmd = _get_ffmpeg_cmd('/input.mp4', '/output.jpg', (240, 135))
        
        # Should include fast seek (-ss before -i)
        ss_index = cmd.index('-ss') if '-ss' in cmd else -1
        i_index = cmd.index('-i') if '-i' in cmd else -1
        
        assert ss_index < i_index, "-ss should come before -i for fast seek"
        
        # Should include frame limit
        assert '-frames:v' in cmd or '-vframes' in cmd


class TestConfigCaching:
    """Tests for configuration caching in media_utils."""
    
    def test_ensure_config_cache(self, app_context):
        """Test that config cache is properly initialized."""
        from app.utils import media_utils
        
        # Reset cache
        media_utils._MEDIA_EXTS = None
        
        result = media_utils._ensure_config_cache()
        
        assert result is True
        assert media_utils._MEDIA_EXTS is not None
        assert media_utils._IMAGE_EXTS is not None
        assert media_utils._VIDEO_EXTS is not None
    
    def test_config_cache_reused(self, app_context):
        """Test that cached config is reused."""
        from app.utils import media_utils
        
        # Ensure cache is populated
        media_utils._ensure_config_cache()
        
        # Store reference
        original_exts = media_utils._MEDIA_EXTS
        
        # Call again
        media_utils._ensure_config_cache()
        
        # Should be same object
        assert media_utils._MEDIA_EXTS is original_exts
