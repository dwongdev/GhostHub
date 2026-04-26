"""Tests for the Specter-owned library runtime service."""

from unittest.mock import patch

from app.services.media.library_runtime_service import LibraryRuntimeService


class TestLibraryRuntimeService:
    """Tests for library runtime orchestration hooks."""

    def test_initialize_runtime_starts_scan_once(self):
        """Runtime initialization should delegate to indexing + thumbnail runtimes."""
        from unittest.mock import MagicMock
        service = LibraryRuntimeService()
        thumbnail_runtime = MagicMock()
        indexing_runtime = MagicMock()

        def require_side_effect(key):
            if key == 'thumbnail_runtime':
                return thumbnail_runtime
            if key == 'indexing_runtime':
                return indexing_runtime
            raise KeyError(key)

        with (
            patch(
                'app.services.media.library_runtime_service.registry.require',
                side_effect=require_side_effect,
            ),
            patch.object(
                thumbnail_runtime,
                'ensure_workers',
                return_value=None,
                create=True,
            ) as mock_workers,
            patch.object(
                indexing_runtime,
                'initialize_runtime',
                return_value={
                    'runtime_initialized': True,
                    'periodic_scan_enabled': True,
                    'scan_interval_seconds': 300,
                },
                create=True,
            ) as mock_initialize,
        ):
            state = service.initialize_runtime(
                initial_delay_seconds=12,
                scan_interval_seconds=300,
            )

        mock_workers.assert_called_once_with()
        mock_initialize.assert_called_once_with(
            initial_delay_seconds=12,
            scan_interval_seconds=300,
        )
        assert state['runtime_initialized'] is True
        assert state['periodic_scan_enabled'] is True
        assert state['scan_interval_seconds'] == 300

    def test_quiesce_for_reindex_combines_legacy_workers(self):
        """Reindex quiesce should aggregate dedicated runtimes."""
        from unittest.mock import MagicMock
        service = LibraryRuntimeService()
        thumbnail_runtime = MagicMock()
        indexing_runtime = MagicMock()

        def require_side_effect(key):
            if key == 'thumbnail_runtime':
                return thumbnail_runtime
            if key == 'indexing_runtime':
                return indexing_runtime
            raise KeyError(key)

        with (
            patch(
                'app.services.media.library_runtime_service.registry.require',
                side_effect=require_side_effect,
            ),
            patch.object(
                thumbnail_runtime,
                'quiesce_thumbnail_runtime',
                return_value={'drained_tasks': 4, 'idle': True},
                create=True,
            ) as mock_thumb,
            patch.object(
                indexing_runtime,
                'quiesce_indexing',
                return_value={'stopped': True, 'drained_tasks': 2},
                create=True,
            ) as mock_indexer,
        ):
            result = service.quiesce_for_reindex(timeout_seconds=5, clear_queue=True)

        mock_thumb.assert_called_once_with(timeout_seconds=5, clear_queue=True)
        mock_indexer.assert_called_once_with(timeout_seconds=5, clear_queue=True)
        assert result == {
            'thumbnail': {'drained_tasks': 4, 'idle': True},
            'indexer': {'stopped': True, 'drained_tasks': 2},
        }
