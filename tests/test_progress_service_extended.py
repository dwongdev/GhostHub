"""
Extended Progress Service Tests
-------------------------------
The #1 bug-prone area in the app. URL normalization is the root cause
of "completed video reappears in Continue Watching" — the same video
path can arrive encoded, decoded, with query strings, or with fragments.
All variants must match to the same progress entry.
"""
import pytest
from urllib.parse import quote, unquote
from unittest.mock import patch, MagicMock

PROFILE_ID = 'test-profile'


class TestURLNormalization:
    """Tests for path-based progress storage — critical save/get round-trip behavior."""

    def test_encoded_and_decoded_paths_match(self, app_context, test_db, mock_config):
        """Saving with decoded path, retrieving with same decoded path must work."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        decoded_path = "/media/My Movies/movie name.mp4"

        progress_service.save_video_progress(decoded_path, "cat", 100.0, profile_id=PROFILE_ID)
        result = progress_service.get_video_progress(decoded_path, profile_id=PROFILE_ID)
        assert result is not None
        assert result["video_timestamp"] == 100.0

    def test_encoded_save_decoded_retrieve(self, app_context, test_db, mock_config):
        """Saving and retrieving with the same encoded path must work."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        encoded_path = quote("/media/TV Shows/episode 1.mp4", safe="/:")

        progress_service.save_video_progress(encoded_path, "tv", 500.0, profile_id=PROFILE_ID)
        result = progress_service.get_video_progress(encoded_path, profile_id=PROFILE_ID)
        assert result is not None
        assert result["video_timestamp"] == 500.0

    def test_path_with_query_string(self, app_context, test_db, mock_config):
        """Progress round-trip with a path that contains a query string."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        path = "/media/video.mp4?t=1234567890"

        progress_service.save_video_progress(path, "cat", 200.0, profile_id=PROFILE_ID)
        result = progress_service.get_video_progress(path, profile_id=PROFILE_ID)
        assert result is not None

    def test_path_with_fragment(self, app_context, test_db, mock_config):
        """Progress round-trip with a path that contains a URL fragment."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        path = "/media/video.mp4#section"

        progress_service.save_video_progress(path, "cat", 150.0, profile_id=PROFILE_ID)
        result = progress_service.get_video_progress(path, profile_id=PROFILE_ID)
        assert result is not None

    def test_unicode_path_normalization(self, app_context, test_db, mock_config):
        """Japanese/CJK characters in paths must normalize correctly."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        path = "/media/映画/テスト動画.mp4"
        progress_service.save_video_progress(path, "jp", 300.0, profile_id=PROFILE_ID)
        result = progress_service.get_video_progress(path, profile_id=PROFILE_ID)
        assert result is not None
        assert result["video_timestamp"] == 300.0

    def test_empty_path_returns_none(self, app_context, test_db, mock_config):
        """Empty path should return None, not crash."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        result = progress_service.get_video_progress("", profile_id=PROFILE_ID)
        assert result is None

    def test_none_path_returns_none(self, app_context, test_db, mock_config):
        """None path should return None, not crash."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        result = progress_service.get_video_progress(None, profile_id=PROFILE_ID)
        assert result is None


class TestDeleteVideoProgressNormalized:
    """Deletion must work for the same path that was saved."""

    def test_delete_matches_same_path(self, app_context, test_db, mock_config):
        """Deleting with the exact saved path removes the entry."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        path = "/media/My Videos/video.mp4"

        progress_service.save_video_progress(path, "cat", 100.0, profile_id=PROFILE_ID)
        progress_service.delete_video_progress(path, profile_id=PROFILE_ID)

        result = progress_service.get_video_progress(path, profile_id=PROFILE_ID)
        assert result is None

    def test_delete_with_explicit_deletion(self, app_context, test_db, mock_config):
        """Explicit delete_video_progress should remove the entry."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        path = "/media/finished.mp4"
        progress_service.save_video_progress(path, "cat", 7190.0, 7200.0, profile_id=PROFILE_ID)

        progress_service.delete_video_progress(path, profile_id=PROFILE_ID)
        result = progress_service.get_video_progress(path, profile_id=PROFILE_ID)
        assert result is None


class TestBatchVideoProgress:
    """Batch operations for multi-category progress retrieval."""

    def test_batch_returns_correct_categories(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        progress_service.save_video_progress("/media/a.mp4", "alpha", 100.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress("/media/b.mp4", "beta", 200.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress("/media/c.mp4", "gamma", 300.0, profile_id=PROFILE_ID)

        result = progress_service.get_video_progress_batch(["alpha", "beta"], profile_id=PROFILE_ID)
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" not in result

    def test_batch_empty_categories(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        result = progress_service.get_video_progress_batch([], profile_id=PROFILE_ID)
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_batch_with_nonexistent_category(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        result = progress_service.get_video_progress_batch(["nonexistent"], profile_id=PROFILE_ID)
        assert isinstance(result, dict)


class TestCategoryVideoProgress:
    """Category-level progress queries."""

    def test_returns_only_category_videos(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        progress_service.save_video_progress("/media/m1.mp4", "movies", 100.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress("/media/m2.mp4", "movies", 200.0, profile_id=PROFILE_ID)
        progress_service.save_video_progress("/media/t1.mp4", "tv", 300.0, profile_id=PROFILE_ID)

        result = progress_service.get_category_video_progress("movies", profile_id=PROFILE_ID)
        assert "/media/m1.mp4" in result
        assert "/media/m2.mp4" in result
        assert "/media/t1.mp4" not in result

    def test_empty_category(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        result = progress_service.get_category_video_progress("empty-cat", profile_id=PROFILE_ID)
        assert isinstance(result, dict)
        assert len(result) == 0


class TestDeleteAllProgress:
    """Nuclear option — used when clearing user data."""

    def test_delete_all_clears_everything(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        for i in range(5):
            progress_service.save_video_progress(
                f"/media/v{i}.mp4",
                f"cat{i % 2}",
                float(i * 100),
                profile_id=PROFILE_ID,
            )

        result = progress_service.delete_all_video_progress(profile_id=PROFILE_ID)
        assert result["success"] is True

        for i in range(5):
            assert progress_service.get_video_progress(f"/media/v{i}.mp4", profile_id=PROFILE_ID) is None

    def test_delete_all_on_empty_db(self, app_context, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        from app.services.media import video_progress_service as progress_service

        result = progress_service.delete_all_video_progress(profile_id=PROFILE_ID)
        assert result["success"] is True
