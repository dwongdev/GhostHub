"""
Tests for Subtitle Service
--------------------------
Tests for subtitle detection, extraction, and conversion.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open

class TestSubtitleServiceBasics:
    """Basic tests for SubtitleService."""

    def test_is_subtitles_enabled_config(self, app_context, mock_config):
        """Test is_subtitles_enabled respects config."""
        from app.services.media.subtitle_service import is_subtitles_enabled
        
        mock_config('ENABLE_SUBTITLES', True)
        assert is_subtitles_enabled() is True
        
        mock_config('ENABLE_SUBTITLES', False)
        assert is_subtitles_enabled() is False

    def test_get_subtitle_cache_dir(self, app_context):
        """Test cache directory creation."""
        from app.services.media.subtitle_service import get_subtitle_cache_dir
        
        with patch('os.makedirs') as mock_makedirs, \
             patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            cache_dir = get_subtitle_cache_dir()
            
            assert 'subtitle_cache' in cache_dir
            mock_makedirs.assert_called_once()

    def test_get_video_hash(self, app_context, tmp_path):
        """Test video hash generation."""
        from app.services.media.subtitle_service import get_video_hash
        
        video_file = tmp_path / 'test.mp4'
        video_file.write_text('fake content')
        
        hash1 = get_video_hash(str(video_file))
        hash2 = get_video_hash(str(video_file))
        
        assert hash1 == hash2
        assert len(hash1) == 16


class TestSubtitleConversion:
    """Tests for subtitle format conversion."""

    def test_convert_srt_to_vtt_success(self, app_context, tmp_path):
        """Test successful SRT to VTT conversion."""
        from app.services.media.subtitle_service import convert_srt_to_vtt
        
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Test subtitle line 1

2
00:00:05,500 --> 00:00:09,123
Test subtitle line 2
Multi-line text
"""
        srt_file = tmp_path / 'test.srt'
        srt_file.write_text(srt_content, encoding='utf-8')
        
        vtt_file = tmp_path / 'test.vtt'
        
        success = convert_srt_to_vtt(str(srt_file), str(vtt_file))
        
        assert success is True
        assert vtt_file.exists()
        
        content = vtt_file.read_text(encoding='utf-8')
        assert "WEBVTT" in content
        assert "00:00:01.000 --> 00:00:04.000" in content
        assert "Test subtitle line 1" in content

    def test_convert_srt_to_vtt_malformed(self, app_context, tmp_path):
        """Test conversion handles malformed SRT gracefully."""
        from app.services.media.subtitle_service import convert_srt_to_vtt
        
        srt_content = "Not a valid SRT file"
        srt_file = tmp_path / 'bad.srt'
        srt_file.write_text(srt_content, encoding='utf-8')
        
        vtt_file = tmp_path / 'bad.vtt'
        
        # Should return False but not crash
        success = convert_srt_to_vtt(str(srt_file), str(vtt_file))
        assert success is False


class TestExternalSubtitles:
    """Tests for finding external subtitles."""

    def test_find_external_subtitles_exact_match(self, app_context, tmp_path):
        """Test finding exact match external subtitles."""
        from app.services.media.subtitle_service import find_external_subtitles
        
        video_dir = tmp_path / 'movies'
        video_dir.mkdir()
        
        video = video_dir / 'movie.mp4'
        video.touch()
        
        srt = video_dir / 'movie.srt'
        srt.touch()
        
        subs = find_external_subtitles(str(video))
        
        assert len(subs) == 1
        assert subs[0]['filename'] == 'movie.srt'
        assert subs[0]['label'] == 'External'

    def test_find_external_subtitles_language_match(self, app_context, tmp_path):
        """Test finding language-tagged external subtitles."""
        from app.services.media.subtitle_service import find_external_subtitles
        
        video_dir = tmp_path / 'movies'
        video_dir.mkdir()
        
        video = video_dir / 'movie.mp4'
        video.touch()
        
        srt_en = video_dir / 'movie.en.srt'
        srt_en.touch()
        
        srt_es = video_dir / 'movie.spa.vtt'
        srt_es.touch()
        
        subs = find_external_subtitles(str(video))
        
        assert len(subs) == 2
        labels = [s['label'] for s in subs]
        assert 'English' in labels
        assert 'Spanish' in labels


class TestSubtitleExtraction:
    """Tests for ffmpeg extraction logic."""

    @patch('subprocess.run')
    def test_run_ffprobe_success(self, mock_run, app_context):
        """Test ffprobe parsing."""
        from app.services.media.subtitle_service import run_ffprobe
        
        mock_output = json.dumps({
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video"
                },
                {
                    "index": 1,
                    "codec_type": "subtitle",
                    "codec_name": "subrip",
                    "tags": {"language": "eng", "title": "English Subs"}
                }
            ]
        })
        
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        
        with patch('os.path.exists', return_value=True):
            tracks = run_ffprobe('/path/to/video.mp4')
            
            assert len(tracks) == 1
            assert tracks[0]['codec'] == 'subrip'
            assert 'English' in tracks[0]['label']

    @patch('app.services.subtitle_service.is_subtitles_enabled', return_value=True)
    @patch('app.services.subtitle_service.find_external_subtitles')
    @patch('app.services.subtitle_service.run_ffprobe')
    def test_get_subtitles_for_video(self, mock_ffprobe, mock_external, mock_enabled, app_context):
        """Test main entry point aggregates subtitles."""
        from app.services.media.subtitle_service import get_subtitles_for_video
        
        # Mock external subs
        mock_external.return_value = [{
            'path': '/path/movie.srt',
            'filename': 'movie.srt',
            'format': 'srt',
            'label': 'External',
            'type': 'external'
        }]
        
        # Mock embedded subs
        mock_ffprobe.return_value = [{
            'index': 2,
            'stream_index': 1,
            'codec': 'mov_text',
            'label': 'English',
            'type': 'embedded'
        }]
        
        with patch('os.path.exists', return_value=True), \
             patch('app.services.subtitle_service.convert_srt_to_vtt', return_value=True), \
             patch('app.services.subtitle_service.extract_subtitle_track', return_value=True):
            
            subs = get_subtitles_for_video('/path/movie.mp4')

            assert len(subs) == 2
            assert subs[0]['type'] == 'external_converted'
            assert subs[1]['type'] == 'embedded_image'
