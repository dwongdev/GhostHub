"""Tests for the dedicated Specter thumbnail runtime service."""

import logging
import time
from app.services.media.thumbnail_runtime_service import ThumbnailRuntimeService


class TestThumbnailRuntimeService:
    """Tests for thumbnail runtime queue ownership."""

    def test_queue_thumbnail_accepts_relative_path_string(self):
        """Single-file queue API should accept a plain relative path."""
        from unittest.mock import MagicMock, patch
        
        # Mock dependencies
        library_events = MagicMock()
        service_manager = MagicMock()
        
        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', return_value='clip.mp4.jpg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=True),
            patch('os.path.exists', return_value=False),
        ):
            service = ThumbnailRuntimeService()
            queued = service.queue_thumbnail(
                '/media/Movies',
                'movies',
                'clip.mp4',
                force_refresh=False,
                check_exists=False,
            )

            assert queued is True
            assert service._thumbnail_queue.qsize() == 1
            task = service._thumbnail_queue.get_nowait()
            assert task['category_id'] == 'movies'
            assert task['file_meta']['path'] == 'clip.mp4'

    def test_prioritize_media_slice_promotes_requested_items_and_boost_is_temporary(self):
        """Requested thumbnail slices should be promoted first with a short-lived category boost."""
        from unittest.mock import MagicMock, patch

        library_events = MagicMock()
        service_manager = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.services.media.category_query_service.get_category_by_id', return_value={'path': '/media/Movies'}),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', side_effect=lambda rel: f'{rel}.jpg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=True),
            patch('os.path.exists', return_value=False),
        ):
            service = ThumbnailRuntimeService()

            assert service.queue_thumbnail(
                '/media/Movies',
                'movies',
                'later.mp4',
                check_exists=False,
            ) is True

            result = service.prioritize_media_slice(
                [{'categoryId': 'movies', 'name': 'visible.mp4', 'path': 'visible.mp4'}],
                boost_seconds=30,
            )

            assert result == {'queued': 1, 'promoted': 0, 'reordered': 0, 'skipped': 0}
            assert [task['file_meta']['path'] for task in service._thumbnail_priority_queue] == ['visible.mp4']

            assert service.queue_thumbnail(
                '/media/Movies',
                'movies',
                'adjacent.mp4',
                check_exists=False,
            ) is True
            assert [task['file_meta']['path'] for task in service._thumbnail_priority_queue] == [
                'visible.mp4',
                'adjacent.mp4',
            ]

            with patch(
                'app.services.media.thumbnail_runtime_service.time.time',
                return_value=time.time() + 31,
            ):
                assert service.queue_thumbnail(
                    '/media/Movies',
                    'movies',
                    'after-expiry.mp4',
                    check_exists=False,
                ) is True

            assert service._thumbnail_queue.qsize() == 2

    def test_prioritize_media_slice_promotes_existing_regular_task_without_duplication(self):
        """Promoting an already-queued task should move it forward, not add a duplicate."""
        from unittest.mock import MagicMock, patch

        library_events = MagicMock()
        service_manager = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.services.media.category_query_service.get_category_by_id', return_value={'path': '/media/Movies'}),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', side_effect=lambda rel: f'{rel}.jpg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=True),
            patch('os.path.exists', return_value=False),
        ):
            service = ThumbnailRuntimeService()

            assert service.queue_thumbnail('/media/Movies', 'movies', 'first.mp4', check_exists=False) is True
            assert service.queue_thumbnail('/media/Movies', 'movies', 'second.mp4', check_exists=False) is True

            result = service.prioritize_media_slice([
                {'categoryId': 'movies', 'name': 'second.mp4', 'path': 'second.mp4'}
            ])

            assert result == {'queued': 0, 'promoted': 1, 'reordered': 0, 'skipped': 0}
            assert [task['file_meta']['path'] for task in service._thumbnail_priority_queue] == ['second.mp4']
            assert [task['file_meta']['path'] for task in list(service._thumbnail_queue.queue)] == ['first.mp4']
            assert len(service._queued_thumbnail_task_keys) == 2

    def test_prioritize_media_slice_reorders_existing_priority_task_without_duplication(self):
        """Repeated prioritization of the same visible item should only reorder it in place."""
        from unittest.mock import MagicMock, patch

        library_events = MagicMock()
        service_manager = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.services.media.category_query_service.get_category_by_id', return_value={'path': '/media/Movies'}),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', side_effect=lambda rel: f'{rel}.jpg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=True),
            patch('os.path.exists', return_value=False),
        ):
            service = ThumbnailRuntimeService()

            first = {'categoryId': 'movies', 'name': 'visible.mp4', 'path': 'visible.mp4'}
            second = {'categoryId': 'movies', 'name': 'other.mp4', 'path': 'other.mp4'}

            assert service.prioritize_media_slice([first, second]) == {
                'queued': 2, 'promoted': 0, 'reordered': 0, 'skipped': 0
            }
            assert [task['file_meta']['path'] for task in service._thumbnail_priority_queue] == [
                'visible.mp4',
                'other.mp4',
            ]

            result = service.prioritize_media_slice([second])

            assert result == {'queued': 0, 'promoted': 0, 'reordered': 1, 'skipped': 0}
            assert [task['file_meta']['path'] for task in service._thumbnail_priority_queue] == [
                'other.mp4',
                'visible.mp4',
            ]
            assert len(service._queued_thumbnail_task_keys) == 2

    def test_prioritize_media_slice_skips_media_with_existing_thumbnail_on_disk(self):
        """Visible items with an existing thumbnail file should not be requeued."""
        from unittest.mock import MagicMock, patch

        library_events = MagicMock()
        service_manager = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.services.media.category_query_service.get_category_by_id', return_value={'path': '/media/Movies'}),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', side_effect=lambda rel: f'{rel}.jpg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=True),
            patch('os.path.exists', return_value=True),
        ):
            service = ThumbnailRuntimeService()

            result = service.prioritize_media_slice([
                {'categoryId': 'movies', 'name': 'already-thumbed.mp4', 'thumbnailUrl': '/thumbnails/movies/already-thumbed.mp4.jpg'}
            ])

            assert result == {'queued': 0, 'promoted': 0, 'reordered': 0, 'skipped': 0}
            assert list(service._thumbnail_priority_queue) == []
            assert service._thumbnail_queue.qsize() == 0
            assert len(service._queued_thumbnail_task_keys) == 0

    def test_queue_thumbnail_force_refresh_skips_up_to_date_existing_thumbnail(self):
        """Force refresh should not requeue a thumbnail file that is already current."""
        from unittest.mock import MagicMock, patch

        library_events = MagicMock()
        service_manager = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', return_value='clip.jpeg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=True),
            patch('os.path.exists', return_value=True),
            patch('os.path.getmtime', side_effect=[100.0, 120.0]),
        ):
            service = ThumbnailRuntimeService()

            queued = service.queue_thumbnail(
                '/media/Movies',
                'movies',
                {'name': 'clip.mp4', 'mtime': 100.0},
                force_refresh=True,
                check_exists=True,
            )

            assert queued is False
            assert service._thumbnail_queue.qsize() == 0

    def test_queue_thumbnail_force_refresh_respects_failure_marker(self):
        """Force refresh should still skip files that are in thumbnail retry cooldown."""
        from unittest.mock import MagicMock, patch

        library_events = MagicMock()
        service_manager = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'service_manager':
                return service_manager
            raise KeyError(key)

        with (
            patch('app.services.media.thumbnail_runtime_service.registry.require', side_effect=mock_require),
            patch('app.services.media.thumbnail_runtime_service.get_max_concurrent_tasks', return_value=2),
            patch('app.services.media.thumbnail_runtime_service.get_max_queue_size', return_value=500),
            patch('app.utils.media_utils.get_media_type', return_value='video'),
            patch('app.utils.media_utils.get_thumbnail_filename', return_value='clip.jpeg'),
            patch('app.utils.media_utils.should_retry_thumbnail', return_value=False),
            patch('os.path.exists', return_value=False),
        ):
            service = ThumbnailRuntimeService()

            queued = service.queue_thumbnail(
                '/media/Movies',
                'movies',
                {'name': 'clip.mp4', 'mtime': 100.0},
                force_refresh=True,
                check_exists=True,
            )

            assert queued is False
            assert service._thumbnail_queue.qsize() == 0


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    def test_init_default_window_size(self):
        """Test default window size."""
        from app.services.media.thumbnail_runtime_service import PerformanceMonitor
        monitor = PerformanceMonitor()
        assert monitor.window_size == 10
        assert monitor.tasks_processed == 0

    def test_record_task(self):
        """Test recording task duration."""
        from app.services.media.thumbnail_runtime_service import PerformanceMonitor
        monitor = PerformanceMonitor()
        monitor.record_task(1.5)
        assert monitor.tasks_processed == 1
        assert len(monitor.task_times) == 1

    def test_get_tasks_per_minute(self):
        """Test tasks per minute calculation."""
        from app.services.media.thumbnail_runtime_service import PerformanceMonitor
        monitor = PerformanceMonitor()
        monitor.record_task(1.0)
        monitor.record_task(1.0)
        tpm = monitor.get_tasks_per_minute()
        assert tpm > 0
