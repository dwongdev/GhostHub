"""
Tests for StorageManagementController drive-label update flows.
"""

from unittest.mock import MagicMock, patch


class TestDriveLabelUpdates:
    """Regression coverage for drive-label cache invalidation and broadcasts."""

    def test_rename_drive_label_refreshes_cache_and_broadcasts(self, app):
        """Successful drive-label updates should refresh caches and notify clients."""
        from app.controllers.storage.storage_management_controller import (
            StorageManagementController,
        )

        controller = StorageManagementController()
        library_events = MagicMock()

        with app.test_request_context(
            '/api/storage/drive-label',
            method='PUT',
            json={'device_key': 'usb-1', 'label': 'Living Room'},
        ):
            with patch(
                'app.services.storage.drive_label_service.set_drive_label',
                return_value=True,
            ) as set_drive_label, patch(
                'app.services.storage.storage_drive_service.get_storage_drives_fresh',
            ) as get_storage_drives_fresh, patch(
                'app.services.media.category_cache_service.invalidate_cache',
            ) as invalidate_cache, patch(
                'specter.registry.require',
                return_value=library_events,
            ) as require:
                response = controller.rename_drive_label()

        assert response == {'success': True, 'label': 'Living Room'}
        set_drive_label.assert_called_once_with('usb-1', 'Living Room')
        get_storage_drives_fresh.assert_called_once_with()
        invalidate_cache.assert_called_once_with()
        require.assert_called_once_with('library_events')

        payload = library_events.emit_category_updated.call_args.args[0]
        assert payload['reason'] == 'drive_label_updated'
        assert payload['device_key'] == 'usb-1'
        assert payload['force_refresh'] is True
        assert 'timestamp' in payload

    def test_delete_drive_label_refreshes_cache_and_broadcasts(self, app):
        """Deleting a drive label should invalidate cache state and notify clients."""
        from app.controllers.storage.storage_management_controller import (
            StorageManagementController,
        )

        controller = StorageManagementController()
        library_events = MagicMock()

        with app.test_request_context(
            '/api/storage/drive-label',
            method='DELETE',
            json={'device_key': 'usb-1'},
        ):
            with patch(
                'app.services.storage.drive_label_service.delete_drive_label',
                return_value=True,
            ) as delete_drive_label, patch(
                'app.services.storage.storage_drive_service.get_storage_drives_fresh',
            ) as get_storage_drives_fresh, patch(
                'app.services.media.category_cache_service.invalidate_cache',
            ) as invalidate_cache, patch(
                'specter.registry.require',
                return_value=library_events,
            ) as require:
                response = controller.delete_drive_label()

        assert response == {'success': True}
        delete_drive_label.assert_called_once_with('usb-1')
        get_storage_drives_fresh.assert_called_once_with()
        invalidate_cache.assert_called_once_with()
        require.assert_called_once_with('library_events')

        payload = library_events.emit_category_updated.call_args.args[0]
        assert payload['reason'] == 'drive_label_deleted'
        assert payload['device_key'] == 'usb-1'
        assert payload['force_refresh'] is True
        assert 'timestamp' in payload


class TestDriveVisibilityFiltering:
    """Regression coverage for request-time drive visibility filtering."""

    def test_admin_keeps_hidden_only_drives_visible(self, app):
        """Admin requests should not drop drives whose folders are all hidden."""
        from app.controllers.storage.storage_management_controller import (
            StorageManagementController,
        )

        controller = StorageManagementController()
        drives = [{
            'id': 'usb-hidden',
            'name': 'HiddenDrive',
            'path': '/media/ghost/HiddenDrive',
            'total': 1024,
            'used': 128,
            'free': 896,
            'percent_used': 12.5,
            'writable': True,
        }]

        with app.test_request_context('/api/storage/drives', method='GET'):
            with patch(
                'app.services.storage.storage_drive_service.get_storage_drives',
            return_value=drives,
            ), patch(
                'app.services.storage.storage_drive_service.filter_hidden_only_drives',
            ) as filter_hidden_only_drives, patch(
                'app.services.storage.drive_label_service.get_all_drive_labels',
                return_value={},
            ), patch(
                'app.services.storage.storage_io_service.format_bytes',
                side_effect=lambda value: f'{value} B',
            ), patch(
                'app.controllers.storage.storage_management_controller.get_show_hidden_flag',
                return_value=False,
            ), patch(
                'app.controllers.storage.storage_management_controller.is_current_admin_session',
                return_value=True,
            ), patch.object(
                controller,
                'spawn',
            ):
                response = controller.list_storage_drives()

        assert response['drives'][0]['path'] == '/media/ghost/HiddenDrive'
        filter_hidden_only_drives.assert_not_called()

    def test_non_admin_filters_hidden_only_drives(self, app):
        """Non-admin requests should still hide drives with no visible folders."""
        from app.controllers.storage.storage_management_controller import (
            StorageManagementController,
        )

        controller = StorageManagementController()
        drives = [{
            'id': 'usb-hidden',
            'name': 'HiddenDrive',
            'path': '/media/ghost/HiddenDrive',
            'total': 1024,
            'used': 128,
            'free': 896,
            'percent_used': 12.5,
            'writable': True,
        }]

        with app.test_request_context('/api/storage/drives', method='GET'):
            with patch(
                'app.services.storage.storage_drive_service.get_storage_drives',
                return_value=drives,
            ), patch(
                'app.services.storage.storage_drive_service.filter_hidden_only_drives',
                return_value=[],
            ) as filter_hidden_only_drives, patch(
                'app.services.storage.drive_label_service.get_all_drive_labels',
                return_value={},
            ), patch(
                'app.services.storage.storage_io_service.format_bytes',
                side_effect=lambda value: f'{value} B',
            ), patch(
                'app.controllers.storage.storage_management_controller.get_show_hidden_flag',
                return_value=False,
            ), patch(
                'app.controllers.storage.storage_management_controller.is_current_admin_session',
                return_value=False,
            ), patch.object(
                controller,
                'spawn',
            ):
                response = controller.list_storage_drives()

        assert response == {'drives': []}
        filter_hidden_only_drives.assert_called_once_with(drives)
