"""Regression checks for app startup cleanup behavior."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch


def test_on_start_schedules_cleanup_after_boot():
    """Startup service should queue cleanup instead of running it inline during boot."""
    from app.services.core.app_startup_service import AppStartupService

    service = AppStartupService()

    with patch('app.services.core.app_startup_service.registry.require') as mock_require, patch.object(
        service,
        '_configure_admin_lock',
        return_value=True,
    ), patch.object(
        service,
        '_sync_wifi_config',
        return_value=True,
    ), patch.object(
        service,
        'spawn_later',
    ) as mock_spawn_later:
        app = SimpleNamespace(app_context=nullcontext)
        mock_require.return_value = SimpleNamespace(app=app)

        service.start()

    assert service.state['startup_cleanup_completed'] is False
    mock_spawn_later.assert_called_once()
    delay, callback, callback_app = mock_spawn_later.call_args[0]
    assert delay == 1
    assert callback == service._run_startup_cleanup_task
    assert callback_app is app


def test_startup_cleanup_scans_mounts_without_registry_runtime():
    """Startup cleanup should not depend on storage runtime registry boot order."""
    from app.services.core.app_startup_service import AppStartupService

    with patch(
        'app.services.storage.storage_drive_service.get_current_mount_paths_fresh',
        return_value={'/media/usb1'},
    ) as mock_mounts, patch(
        'app.services.media.media_index_service.cleanup_media_index_for_unmounted_paths',
    ) as mock_cleanup_paths, patch(
        'app.services.media.media_index_service.cleanup_media_index_by_category_path_check',
        return_value=0,
    ), patch(
        'app.services.media.category_query_service.get_all_categories_with_details',
        return_value=[{'id': 7}],
    ), patch(
        'app.services.media.media_index_service.cleanup_orphaned_media_index',
    ) as mock_cleanup_orphans:
        result = AppStartupService._run_startup_cleanup()

    assert result is True
    mock_mounts.assert_called_once_with()
    mock_cleanup_paths.assert_called_once_with({'/media/usb1'})
    mock_cleanup_orphans.assert_called_once_with([7])
