"""Tests for media storage mount-change handling."""

from unittest.mock import MagicMock, patch


class TestMediaStorageEventHandlerService:
    """Regression tests for drive mount/unmount cleanup notifications."""

    def test_unmount_only_uses_light_refresh_after_cleanup(self):
        """Unmount cleanup should notify clients without forcing a reindex path."""
        from app.services.media.storage_event_handler_service import (
            MediaStorageEventHandlerService,
        )

        library_events = MagicMock()
        storage_events = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'storage_events':
                return storage_events
            raise KeyError(key)

        service = MediaStorageEventHandlerService()

        with (
            patch(
                'app.services.media.storage_event_handler_service.category_cache_service.invalidate_cache',
            ),
            patch(
                'app.services.media.storage_event_handler_service.get_all_categories_with_details',
                return_value=[],
            ),
            patch(
                'app.services.media.storage_event_handler_service.media_index_service.cleanup_orphaned_media_index',
            ),
            patch(
                'app.services.media.storage_event_handler_service.media_index_service.delete_media_index_by_path_prefix',
                return_value=4,
            ) as delete_by_prefix_mock,
            patch(
                'app.services.media.storage_event_handler_service.category_persistence_service.delete_categories_by_path_prefix',
                return_value=1,
            ) as delete_categories_mock,
            patch(
                'app.services.media.storage_event_handler_service.media_index_service.cleanup_media_index_by_category_path_check',
                return_value=2,
            ),
            patch(
                'app.services.media.storage_event_handler_service.media_index_service.get_all_category_ids_from_media_index',
                return_value=[],
            ),
            patch(
                'app.services.media.storage_event_handler_service.registry.require',
                side_effect=mock_require,
            ),
        ):
            service._handle_mount_changed({
                'mounted_paths': [],
                'unmounted_paths': ['/media/ghost/USB_A'],
            })

        delete_by_prefix_mock.assert_called_once_with('/media/ghost/USB_A')
        delete_categories_mock.assert_called_once_with('/media/ghost/USB_A')
        storage_events.emit_usb_mounts_changed.assert_called_once()
        usb_payload = storage_events.emit_usb_mounts_changed.call_args.args[0]
        assert usb_payload['mounted_paths'] == []
        assert usb_payload['unmounted_paths'] == ['/media/ghost/USB_A']
        assert usb_payload['force_refresh'] is False

        library_events.emit_category_updated.assert_not_called()

    def test_mount_only_uses_force_refresh(self):
        """Mount additions should force-refresh so newly available media is indexed."""
        from app.services.media.storage_event_handler_service import (
            MediaStorageEventHandlerService,
        )

        library_events = MagicMock()
        storage_events = MagicMock()

        def mock_require(key):
            if key == 'library_events':
                return library_events
            if key == 'storage_events':
                return storage_events
            raise KeyError(key)

        service = MediaStorageEventHandlerService()

        with (
            patch(
                'app.services.media.storage_event_handler_service.category_cache_service.invalidate_cache',
            ),
            patch(
                'app.services.media.storage_event_handler_service.get_all_categories_with_details',
                return_value=[],
            ),
            patch(
                'app.services.media.storage_event_handler_service.media_index_service.cleanup_orphaned_media_index',
            ),
            patch(
                'app.services.media.storage_event_handler_service.registry.require',
                side_effect=mock_require,
            ),
        ):
            service._handle_mount_changed({
                'mounted_paths': ['/media/ghost/USB_B'],
                'unmounted_paths': [],
            })

        storage_events.emit_usb_mounts_changed.assert_called_once()
        usb_payload = storage_events.emit_usb_mounts_changed.call_args.args[0]
        assert usb_payload['mounted_paths'] == ['/media/ghost/USB_B']
        assert usb_payload['unmounted_paths'] == []
        assert usb_payload['force_refresh'] is True
        library_events.emit_category_updated.assert_not_called()
