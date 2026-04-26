"""Tests for the USB sentinel factory reset service."""

import os
import tempfile
from unittest.mock import MagicMock, patch, call

from app.services.system.factory_reset_service import (
    FactoryResetService,
    SENTINEL_FILENAME,
)


class TestFactoryResetService:
    """Unit tests for FactoryResetService."""

    def test_ignores_mounts_without_sentinel(self, tmp_path):
        """Drives without .ghosthub_reset are ignored."""
        service = FactoryResetService()
        mount_dir = str(tmp_path / "usb_drive")
        os.makedirs(mount_dir)

        with patch.object(service, '_perform_reset') as mock_reset:
            service._handle_mount_changed({
                'mounted_paths': [mount_dir],
                'unmounted_paths': [],
            })
            mock_reset.assert_not_called()

    def test_detects_sentinel_and_triggers_reset(self, tmp_path):
        """A drive with .ghosthub_reset triggers the reset flow."""
        service = FactoryResetService()
        mount_dir = str(tmp_path / "usb_drive")
        os.makedirs(mount_dir)
        sentinel = os.path.join(mount_dir, SENTINEL_FILENAME)
        open(sentinel, 'w').close()

        with patch.object(service, '_perform_reset') as mock_reset:
            service._handle_mount_changed({
                'mounted_paths': [mount_dir],
                'unmounted_paths': [],
            })
            mock_reset.assert_called_once_with(sentinel)

    def test_only_first_sentinel_triggers_reset(self, tmp_path):
        """If multiple drives have sentinels, only the first one triggers."""
        service = FactoryResetService()
        dirs = []
        for name in ("drive_a", "drive_b"):
            d = str(tmp_path / name)
            os.makedirs(d)
            open(os.path.join(d, SENTINEL_FILENAME), 'w').close()
            dirs.append(d)

        with patch.object(service, '_perform_reset') as mock_reset:
            service._handle_mount_changed({
                'mounted_paths': dirs,
                'unmounted_paths': [],
            })
            mock_reset.assert_called_once()

    def test_ignores_unmounted_paths(self, tmp_path):
        """Unmounted paths are not checked for sentinels."""
        service = FactoryResetService()
        mount_dir = str(tmp_path / "usb_drive")
        os.makedirs(mount_dir)
        open(os.path.join(mount_dir, SENTINEL_FILENAME), 'w').close()

        with patch.object(service, '_perform_reset') as mock_reset:
            service._handle_mount_changed({
                'mounted_paths': [],
                'unmounted_paths': [mount_dir],
            })
            mock_reset.assert_not_called()

    def test_ignores_empty_payload(self):
        """Empty or missing mounted_paths does not crash."""
        service = FactoryResetService()
        with patch.object(service, '_perform_reset') as mock_reset:
            service._handle_mount_changed({})
            mock_reset.assert_not_called()
            service._handle_mount_changed({'mounted_paths': None})
            mock_reset.assert_not_called()

    def test_reset_passwords_updates_runtime_and_persists(self):
        """_reset_passwords sets runtime values and saves config."""
        mock_config_data = {
            'python_config': {
                'SESSION_PASSWORD': 'secret',
                'ADMIN_PASSWORD': 'hunter2',
            }
        }

        with (
            patch(
                'app.services.core.runtime_config_service.set_runtime_config_value'
            ) as mock_set_runtime,
            patch(
                'app.services.core.config_service.load_config',
                return_value=(mock_config_data, None),
            ),
            patch(
                'app.services.core.config_service.save_config',
                return_value=(True, 'ok'),
            ) as mock_save,
        ):
            FactoryResetService._reset_passwords()

            mock_set_runtime.assert_any_call('SESSION_PASSWORD', '')
            mock_set_runtime.assert_any_call('ADMIN_PASSWORD', 'admin')
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved['python_config']['SESSION_PASSWORD'] == ''
            assert saved['python_config']['ADMIN_PASSWORD'] == 'admin'

    def test_clear_admin_lock(self):
        """_clear_admin_lock calls set_admin_session_id(None)."""
        with patch(
            'app.services.core.session_store.set_admin_session_id'
        ) as mock_clear:
            FactoryResetService._clear_admin_lock()
            mock_clear.assert_called_once_with(None)

    def test_notify_clients_emits_socket_event(self):
        """_notify_clients emits FACTORY_RESET via socket transport."""
        mock_transport = MagicMock()

        with patch(
            'app.services.system.factory_reset_service.registry.resolve',
            return_value=mock_transport,
        ):
            FactoryResetService._notify_clients()
            mock_transport.emit.assert_called_once()
            event_name = mock_transport.emit.call_args[0][0]
            assert event_name == 'factory_reset'

    def test_notify_clients_handles_missing_transport(self):
        """_notify_clients does not crash when socket transport is unavailable."""
        with patch(
            'app.services.system.factory_reset_service.registry.resolve',
            return_value=None,
        ):
            FactoryResetService._notify_clients()

    def test_remove_sentinel_deletes_file(self, tmp_path):
        """_remove_sentinel deletes the sentinel file."""
        sentinel = str(tmp_path / SENTINEL_FILENAME)
        open(sentinel, 'w').close()
        assert os.path.exists(sentinel)

        FactoryResetService._remove_sentinel(sentinel)
        assert not os.path.exists(sentinel)

    def test_remove_sentinel_handles_read_only(self, tmp_path):
        """_remove_sentinel logs warning but does not crash on read-only drives."""
        with patch('os.remove', side_effect=OSError("Read-only filesystem")):
            FactoryResetService._remove_sentinel('/fake/path/.ghosthub_reset')

    def test_perform_reset_full_flow(self, tmp_path):
        """_perform_reset calls all steps in order."""
        sentinel = str(tmp_path / SENTINEL_FILENAME)
        open(sentinel, 'w').close()

        service = FactoryResetService()
        with (
            patch.object(service, '_reset_passwords') as m_pw,
            patch.object(service, '_clear_admin_lock') as m_lock,
            patch.object(service, '_notify_clients') as m_notify,
            patch.object(service, '_remove_sentinel') as m_remove,
        ):
            service._perform_reset(sentinel)
            m_pw.assert_called_once()
            m_lock.assert_called_once()
            m_notify.assert_called_once()
            m_remove.assert_called_once_with(sentinel)
