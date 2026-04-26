"""
Tests for Progress Service
--------------------------
Tests for playback progress management.
Focuses on video-specific progress tracking which is the current architecture.
"""
import pytest
import time
from unittest.mock import patch, MagicMock

PROFILE_ID = 'test-profile'


class TestDeleteProgress:
    """Tests for progress deletion."""
    
    def test_delete_all_progress(self, app_context, test_db, mock_config):
        """Test deleting all progress data."""
        mock_config('SAVE_VIDEO_PROGRESS', True)
        
        from app.services.media import video_progress_service as progress_service
        
        # Save video progress
        progress_service.save_video_progress('/media/video1.mp4', 'cat', 100.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress('/media/video2.mp4', 'cat', 200.0, profile_id=PROFILE_ID)

        result = progress_service.delete_all_video_progress(profile_id=PROFILE_ID)
        
        assert result['success'] is True
        
        # Verify deleted
        assert progress_service.get_video_progress('/media/video1.mp4', profile_id=PROFILE_ID) is None
        assert progress_service.get_video_progress('/media/video2.mp4', profile_id=PROFILE_ID) is None


class TestVideoProgressTracking:
    """Tests for per-video progress tracking."""

    def test_save_video_progress(self, app_context, test_db, mock_config):
        """Test saving video-specific progress."""
        mock_config('SAVE_VIDEO_PROGRESS', True)
        
        from app.services.media import video_progress_service as progress_service
        
        success, message = progress_service.save_video_progress(
            video_path='/media/movie.mp4',
            category_id='movies',
            video_timestamp=1500.0,
            video_duration=7200.0,
            thumbnail_url='/thumbnails/movie.jpg',
            profile_id=PROFILE_ID,
        )
        
        assert success is True
    
    def test_get_video_progress(self, app_context, test_db, mock_config):
        """Test retrieving video-specific progress."""
        mock_config('SAVE_VIDEO_PROGRESS', True)
        
        from app.services.media import video_progress_service as progress_service
        
        progress_service.save_video_progress(
            video_path='/media/test.mp4',
            category_id='test',
            video_timestamp=500.0,
            video_duration=2000.0,
            profile_id=PROFILE_ID,
        )

        progress = progress_service.get_video_progress('/media/test.mp4', profile_id=PROFILE_ID)
        
        assert progress is not None
        assert progress['video_timestamp'] == 500.0
        assert progress['video_duration'] == 2000.0
    
    def test_get_video_progress_nonexistent(self, app_context, test_db, mock_config):
        """Test get_video_progress returns None for non-existent video."""
        mock_config('SAVE_VIDEO_PROGRESS', True)
        
        from app.services.media import video_progress_service as progress_service
        
        progress = progress_service.get_video_progress('/nonexistent/video.mp4', profile_id=PROFILE_ID)
        
        assert progress is None

    def test_save_video_progress_rejects_deleted_profile(self, app_context, test_db, mock_config):
        """Progress writes should fail once the owning profile no longer exists."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        from app.services.core import profile_service
        from app.services.media import video_progress_service as progress_service

        created = profile_service.create_profile('Deleted Progress Owner')
        assert profile_service.delete_profile(created['id']) is True

        success, message = progress_service.save_video_progress(
            video_path='/media/deleted-owner.mp4',
            category_id='movies',
            video_timestamp=25.0,
            profile_id=created['id'],
        )

        assert success is False
        assert message == 'Active profile is invalid.'

    def test_save_video_progress_clears_completed_media(self, app_context, test_db, mock_config):
        """Explicit deletion should remove saved video progress."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        from app.services.media import video_progress_service as progress_service

        success, message = progress_service.save_video_progress(
            video_path='/media/completed.mp4',
            category_id='movies',
            video_timestamp=7190.0,
            video_duration=7200.0,
            profile_id=PROFILE_ID,
        )
        assert success is True

        # Explicitly delete progress to simulate completion
        progress_service.delete_video_progress('/media/completed.mp4', profile_id=PROFILE_ID)
        assert progress_service.get_video_progress('/media/completed.mp4', profile_id=PROFILE_ID) is None

    def test_get_video_progress_does_not_prune_near_end_entry(self, app_context, test_db, mock_config):
        """Near-end progress should still be readable until explicit completion."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        from app.services.media import video_progress_service as progress_service

        progress_service.save_video_progress(
            '/media/stale-finished.mp4',
            'movies',
            7195.0,
            7200.0,
            profile_id=PROFILE_ID,
        )

        progress = progress_service.get_video_progress('/media/stale-finished.mp4', profile_id=PROFILE_ID)
        assert progress is not None
        assert progress['video_timestamp'] == 7195.0
        assert progress_service.get_video_progress('/media/stale-finished.mp4', profile_id=PROFILE_ID) is not None
    
    def test_get_category_video_progress(self, app_context, test_db, mock_config):
        """Test getting all video progress for a category."""
        mock_config('SAVE_VIDEO_PROGRESS', True)
        
        from app.services.media import video_progress_service as progress_service
        
        # Save progress for multiple videos
        progress_service.save_video_progress('/media/v1.mp4', 'my-cat', 100.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress('/media/v2.mp4', 'my-cat', 200.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress('/media/v3.mp4', 'other-cat', 300.0, profile_id=PROFILE_ID)

        category_progress = progress_service.get_category_video_progress('my-cat', profile_id=PROFILE_ID)
        
        assert len(category_progress) == 2
        assert '/media/v1.mp4' in category_progress
        assert '/media/v2.mp4' in category_progress
        assert '/media/v3.mp4' not in category_progress
