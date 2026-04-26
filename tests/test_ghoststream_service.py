"""
Tests for GhostStream Service
------------------------------
Unit tests for GhostStream job tracking and state management.
Does NOT test actual GhostStream connectivity (integration tests only).
"""
import pytest
import threading
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def reset_ghoststream_runtime_state():
    """Reset shared GhostStream runtime state for test isolation."""
    from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

    ghoststream_runtime_store.set({
        'progress_callbacks': [],
        'status_callbacks': [],
        'last_error': None,
        'active_jobs': {},
        'job_servers': {},
        'server_callback_urls': {},
    })
    yield


class TestJobTracking:
    """Tests for job tracking and session management."""

    def test_track_job_adds_to_session(self, app_context):
        """Test that track_job adds job to session tracking."""
        from app.services.ghoststream import ghoststream_service

        session_id = 'test_session'
        job_id = 'job123'

        with patch.object(ghoststream_service, '_subscribe_job_ws'):
            ghoststream_service.track_job(session_id, job_id)

        jobs = ghoststream_service.get_session_jobs(session_id)
        assert job_id in jobs

    def test_untrack_job_removes_from_session(self, app_context):
        """Test that untrack_job removes job from session tracking."""
        from app.services.ghoststream import ghoststream_service

        session_id = 'test_session'
        job_id = 'job123'

        with patch.object(ghoststream_service, '_subscribe_job_ws'), \
             patch.object(ghoststream_service, '_unsubscribe_job_ws'):
            ghoststream_service.track_job(session_id, job_id)
            ghoststream_service.untrack_job(session_id, job_id)

        jobs = ghoststream_service.get_session_jobs(session_id)
        assert job_id not in jobs

    def test_get_session_jobs_returns_list(self, app_context):
        """Test that get_session_jobs returns a list."""
        from app.services.ghoststream import ghoststream_service

        session_id = 'test_session'

        jobs = ghoststream_service.get_session_jobs(session_id)
        assert isinstance(jobs, list)

    def test_get_session_jobs_empty_session(self, app_context):
        """Test that get_session_jobs returns empty list for unknown session."""
        from app.services.ghoststream import ghoststream_service

        jobs = ghoststream_service.get_session_jobs('nonexistent_session')
        assert jobs == []

    def test_cleanup_session_jobs(self, app_context):
        """Test that cleanup_session_jobs cancels all jobs for session."""
        from app.services.ghoststream import ghoststream_service

        session_id = 'test_session'
        job_ids = ['job1', 'job2', 'job3']

        with patch.object(ghoststream_service, '_subscribe_job_ws'), \
             patch.object(ghoststream_service, 'cancel_job') as mock_cancel:
            for job_id in job_ids:
                ghoststream_service.track_job(session_id, job_id)

            ghoststream_service.cleanup_session_jobs(session_id)

            assert mock_cancel.call_count == len(job_ids)

    def test_cleanup_session_jobs_handles_errors(self, app_context):
        """Test that cleanup_session_jobs handles cancellation errors gracefully."""
        from app.services.ghoststream import ghoststream_service

        session_id = 'test_session'
        job_id = 'job123'

        with patch.object(ghoststream_service, '_subscribe_job_ws'), \
             patch.object(ghoststream_service, 'cancel_job', side_effect=Exception("Cancel failed")):
            ghoststream_service.track_job(session_id, job_id)

            # Should not raise exception
            ghoststream_service.cleanup_session_jobs(session_id)


class TestErrorHandling:
    """Tests for error handling and logging."""

    def test_set_last_error(self, app_context):
        """Test that _set_last_error sets error message."""
        from app.services.ghoststream import ghoststream_service

        error_msg = "Test error message"
        ghoststream_service._set_last_error(error_msg)

        assert ghoststream_service._get_last_error() == error_msg

    def test_get_last_error(self, app_context):
        """Test that get_last_error returns last error."""
        from app.services.ghoststream import ghoststream_service

        error_msg = "Test error"
        ghoststream_service._set_last_error(error_msg)

        # If get_last_error exists
        if hasattr(ghoststream_service, 'get_last_error'):
            assert ghoststream_service.get_last_error() == error_msg


class TestCallbackManagement:
    """Tests for callback management (WebSocket integration)."""

    def test_progress_callbacks_list_exists(self, app_context):
        """Test that progress callbacks list is initialized."""
        from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

        callbacks = ghoststream_runtime_store.get('progress_callbacks')
        assert isinstance(callbacks, list)

    def test_status_callbacks_list_exists(self, app_context):
        """Test that status callbacks list is initialized."""
        from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

        callbacks = ghoststream_runtime_store.get('status_callbacks')
        assert isinstance(callbacks, list)


class TestServerCallbackUrls:
    """Tests for server callback URL management."""

    def test_set_server_callback_url(self, app_context):
        """Test callback URL lookup by explicit server name."""
        from app.services.ghoststream import ghoststream_service
        from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

        server_name = 'test_server'
        callback_url = 'http://192.168.1.100:5000'
        ghoststream_runtime_store.set({
            'server_callback_urls': {server_name: callback_url},
        })

        assert ghoststream_service.get_server_callback_url(server_name) == callback_url

    def test_get_server_callback_url(self, app_context):
        """Test callback URL lookup uses preferred server when no name passed."""
        from app.services.ghoststream import ghoststream_service
        from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

        server_name = 'test_server'
        callback_url = 'http://192.168.1.100:5000'
        ghoststream_runtime_store.set({
            'server_callback_urls': {server_name: callback_url},
        })

        fake_client = MagicMock()
        fake_client.preferred_server = server_name
        with patch.object(ghoststream_service, '_get_client', return_value=fake_client):
            assert ghoststream_service.get_server_callback_url() == callback_url


class TestThreadSafety:
    """Tests for thread safety of job tracking."""

    def test_concurrent_job_tracking(self, app_context):
        """Test that concurrent job tracking is thread-safe."""
        from app.services.ghoststream import ghoststream_service

        session_id = 'concurrent_session'
        num_threads = 10
        num_jobs_per_thread = 10

        def track_jobs(start_idx):
            with patch.object(ghoststream_service, '_subscribe_job_ws'):
                for i in range(num_jobs_per_thread):
                    job_id = f'job_{start_idx}_{i}'
                    ghoststream_service.track_job(session_id, job_id)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=track_jobs, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        jobs = ghoststream_service.get_session_jobs(session_id)
        # Should have all jobs tracked
        assert len(jobs) == num_threads * num_jobs_per_thread

    def test_concurrent_cleanup(self, app_context):
        """Test that concurrent cleanup operations are thread-safe."""
        from app.services.ghoststream import ghoststream_service

        num_sessions = 5

        def setup_and_cleanup(session_idx):
            session_id = f'session_{session_idx}'
            with patch.object(ghoststream_service, '_subscribe_job_ws'), \
                 patch.object(ghoststream_service, 'cancel_job'):
                for i in range(5):
                    ghoststream_service.track_job(session_id, f'job_{i}')
                ghoststream_service.cleanup_session_jobs(session_id)

        threads = []
        for i in range(num_sessions):
            t = threading.Thread(target=setup_and_cleanup, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All sessions should be cleaned up
        for i in range(num_sessions):
            session_id = f'session_{i}'
            assert len(ghoststream_service.get_session_jobs(session_id)) == 0


class TestInitialization:
    """Tests for service initialization."""

    def test_initial_state(self, app_context):
        """Test that service starts in correct initial state."""
        from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

        state = ghoststream_runtime_store.get()
        assert 'progress_callbacks' in state
        assert 'status_callbacks' in state
        assert 'active_jobs' in state
        assert 'discovery_lock' in state

    def test_jobs_lock_exists(self, app_context):
        """Test discovery lock exists for synchronized discovery transitions."""
        from app.services.ghoststream.ghoststream_runtime_store import ghoststream_runtime_store

        lock = ghoststream_runtime_store.get('discovery_lock')
        assert lock is not None
        assert hasattr(lock, 'acquire')
