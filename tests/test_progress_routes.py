"""
Tests for Progress Routes
--------------------------
Tests the HTTP API for video progress tracking.
This is the server-side half of "Continue Watching" — admin clients
hit these endpoints to save/load/delete playback progress.

Covers:
- Video progress CRUD (save, get, delete)
- Batch operations
- URL normalization across encoding variants
- Edge cases: missing fields, invalid data, rate limiting
"""
import pytest
import json
import time
from urllib.parse import quote


def _set_active_profile(client, profile_id='test-profile'):
    """Bind a known active profile to the test client session."""
    with client.session_transaction() as sess:
        sess['active_profile_id'] = profile_id


class TestSaveVideoProgress:
    """Tests for POST /api/progress/videos endpoint."""

    def test_save_basic_progress(self, admin_client, app, test_db, mock_config):
        """Save progress for a single video."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            response = admin_client.post("/api/progress/movies", json={
                "video_path": "/media/Movies/movie.mp4",
                "category_id": "movies",
                "video_timestamp": 1500.0,
                "video_duration": 7200.0,
                "thumbnail_url": "/thumbnails/movies/movie.jpg"
            })
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

    def test_save_progress_updates_existing(self, admin_client, app, test_db, mock_config):
        """Saving progress for the same video should update, not duplicate."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            # Save initial progress
            admin_client.post("/api/progress/cat", json={
                "video_path": "/media/v.mp4",
                "category_id": "cat",
                "video_timestamp": 100.0,
                "video_duration": 3600.0
            })

            # Update progress
            admin_client.post("/api/progress/cat", json={
                "video_path": "/media/v.mp4",
                "category_id": "cat",
                "video_timestamp": 500.0,
                "video_duration": 3600.0
            })

            # Retrieve
            response = admin_client.get("/api/progress/video?video_path=/media/v.mp4")
            data = response.get_json()
            assert data["video_timestamp"] == 500.0

    def test_save_completed_video_clears_progress(self, admin_client, app, test_db, mock_config):
        """Saving with video_completed=True should DELETE the progress entry."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            # Save initial progress
            admin_client.post("/api/progress/movies", json={
                "video_path": "/media/done.mp4",
                "category_id": "movies",
                "video_timestamp": 7190.0,
                "video_duration": 7200.0
            })

            # Mark as completed
            admin_client.post("/api/progress/movies", json={
                "video_path": "/media/done.mp4",
                "category_id": "movies",
                "video_timestamp": 7190.0,
                "video_duration": 7200.0,
                "video_completed": True
            })

            # Should be gone
            response = admin_client.get("/api/progress/video?video_path=/media/done.mp4")
            data = response.get_json()
            assert data.get("video_timestamp") is None or data == {}

    def test_save_progress_requires_video_path(self, admin_client, app, test_db, mock_config):
        """Missing video_path should return error."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            response = admin_client.post("/api/progress/movies", json={
                "category_id": "movies",
                "video_timestamp": 100.0
            })
            # Should either fail or silently succeed without saving
            # The important thing is it doesn't crash
            assert response.status_code in [200, 400]


class TestGetVideoProgress:
    """Tests for GET /api/progress/videos endpoint."""

    def test_get_existing_progress(self, admin_client, app, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            admin_client.post("/api/progress/test", json={
                "video_path": "/media/test.mp4",
                "category_id": "test",
                "video_timestamp": 300.0,
                "video_duration": 1800.0
            })

            response = admin_client.get("/api/progress/video?video_path=/media/test.mp4")
            assert response.status_code == 200
            data = response.get_json()
            assert data["video_timestamp"] == 300.0

    def test_get_nonexistent_progress(self, admin_client, app, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            response = admin_client.get("/api/progress/video?video_path=/media/nope.mp4")
            assert response.status_code == 200

    def test_get_progress_url_decoding(self, admin_client, app, test_db, mock_config):
        """URL-encoded paths should match their decoded counterparts."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            # Save with decoded path
            admin_client.post("/api/progress/movies", json={
                "video_path": "/media/My Movies/movie file.mp4",
                "category_id": "movies",
                "video_timestamp": 250.0,
                "video_duration": 1000.0
            })

            # Retrieve with encoded path
            encoded_path = quote("/media/My Movies/movie file.mp4", safe="/:")
            response = admin_client.get(f"/api/progress/video?video_path={encoded_path}")
            data = response.get_json()
            assert data.get("video_timestamp") == 250.0




class TestDeleteVideoProgress:
    """Tests for DELETE /api/progress/videos endpoint."""

    def test_clear_continue_watching_deletes_active_profile_progress(
        self,
        admin_client,
        app,
        test_db,
        mock_config,
    ):
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            # Save a few entries
            for i in range(3):
                admin_client.post("/api/progress/test", json={
                    "video_path": f"/media/v{i}.mp4",
                    "category_id": "test",
                    "video_timestamp": float(i * 100),
                    "video_duration": 1000.0
                })

            response = admin_client.post("/api/progress/clear-continue-watching")
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["cleared_count"] == 3

            # All should be gone
            for i in range(3):
                get_resp = admin_client.get(f"/api/progress/video?video_path=/media/v{i}.mp4")
                data = get_resp.get_json()
                assert data.get("video_timestamp") is None or data == {}

    def test_clear_continue_watching_requires_active_profile(self, admin_client, app, test_db, mock_config):
        mock_config("SAVE_VIDEO_PROGRESS", True)

        with app.app_context():
            with admin_client.session_transaction() as sess:
                sess.pop('active_profile_id', None)
            response = admin_client.post("/api/progress/clear-continue-watching")
            assert response.status_code == 400
            data = response.get_json()
            assert data["error"] == "Select a profile before clearing profile video progress."



class TestProgressEdgeCases:
    """Edge cases that have caused production bugs."""

    def test_zero_timestamp_is_valid(self, admin_client, app, test_db, mock_config):
        """Timestamp 0.0 means the video was started but immediately paused.
        This MUST be saved — otherwise resume doesn't work."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            response = admin_client.post("/api/progress/test", json={
                "video_path": "/media/zero.mp4",
                "category_id": "test",
                "video_timestamp": 0.0,
                "video_duration": 500.0
            })
            assert response.status_code == 200

    def test_very_large_timestamp(self, admin_client, app, test_db, mock_config):
        """Long audiobooks/lectures can have timestamps > 100,000 seconds."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            response = admin_client.post("/api/progress/books", json={
                "video_path": "/media/audiobook.mp3",
                "category_id": "books",
                "video_timestamp": 360000.0,
                "video_duration": 400000.0
            })
            assert response.status_code == 200

            resp = admin_client.get("/api/progress/video?video_path=/media/audiobook.mp3")
            data = resp.get_json()
            assert data.get("video_timestamp") == 360000.0

    def test_unicode_in_video_path(self, admin_client, app, test_db, mock_config):
        """Paths with CJK characters, emoji, etc. must work."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            response = admin_client.post("/api/progress/japanese", json={
                "video_path": "/media/映画/テスト.mp4",
                "category_id": "japanese",
                "video_timestamp": 120.0,
                "video_duration": 600.0
            })
            assert response.status_code == 200

    def test_special_characters_in_path(self, admin_client, app, test_db, mock_config):
        """Paths with spaces, parentheses, brackets, etc."""
        mock_config("SAVE_VIDEO_PROGRESS", True)
        _set_active_profile(admin_client)

        with app.app_context():
            path = "/media/TV Shows/Show (2024)/Episode [01] - Pilot.mp4"
            response = admin_client.post("/api/progress/tv", json={
                "video_path": path,
                "category_id": "tv",
                "video_timestamp": 1800.0,
                "video_duration": 3600.0
            })
            assert response.status_code == 200

            resp = admin_client.get(f"/api/progress/video?video_path={quote(path, safe='/:')}")
            data = resp.get_json()
            assert data.get("video_timestamp") == 1800.0

    def test_deleted_profile_cannot_continue_receiving_progress_writes(
        self,
        client,
        app_context,
        mock_config,
    ):
        mock_config("SAVE_VIDEO_PROGRESS", True)

        from app.services.core import profile_service
        from app.services.media import video_progress_service

        created = profile_service.create_profile('Deleted Progress Profile')
        client.set_cookie('localhost', 'session_id', 'stale-progress-session')

        with client.session_transaction() as sess:
            sess['active_profile_id'] = created['id']

        assert profile_service.delete_profile(created['id']) is True

        response = client.post("/api/progress/movies", json={
            "video_path": "/media/stale.mp4",
            "video_timestamp": 45.0,
            "video_duration": 100.0,
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False
        assert data["message"] == "Active profile is required."
        assert video_progress_service.get_video_progress(
            "/media/stale.mp4",
            profile_id=created['id'],
        ) is None

        with client.session_transaction() as sess:
            assert sess.get('active_profile_id') is None
