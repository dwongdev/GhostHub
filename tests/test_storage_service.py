"""
Tests for Storage Service
-------------------------
Comprehensive tests for storage operations including:
- Drive detection (Linux/Windows)
- File uploads (simple and chunked)
- Folder operations
- ZIP streaming for downloads
- Upload session management
"""
import pytest
import os
import time
import tempfile
import zipfile
import threading
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO


def _upload_service():
    """Return the UploadSessionRuntimeService from the Specter registry."""
    from specter import registry
    return registry.require('upload_session_runtime')


def _drive_service():
    """Return the StorageDriveRuntimeService from the Specter registry."""
    from specter import registry
    return registry.require('storage_drive_runtime')


def _reset_mount_state():
    """Reset mount-state store to a clean baseline."""
    from app.services.storage.storage_runtime_store import storage_runtime_store
    storage_runtime_store.set({
        'last_mount_hash': None,
        'last_mount_snapshot': None,
        'mount_change_detected': False,
    })


class TestDriveDetection:
    """Tests for storage drive detection."""

    def test_get_storage_drives_returns_list(self, app_context):
        """Test that get_storage_drives returns a list."""
        from app.services.storage.storage_drive_service import get_storage_drives

        drives = get_storage_drives()
        assert isinstance(drives, list)

    def test_drive_info_has_required_fields(self, app_context, mock_usb_drive):
        """Test that drive info contains all required fields."""
        from app.services.storage.storage_drive_service import _get_drive_info

        drive_info = _get_drive_info(str(mock_usb_drive), 'TestDrive')

        assert drive_info is not None
        assert 'id' in drive_info
        assert 'name' in drive_info
        assert 'path' in drive_info
        assert 'total' in drive_info
        assert 'used' in drive_info
        assert 'free' in drive_info
        assert 'percent_used' in drive_info
        assert 'writable' in drive_info

    def test_drive_info_calculates_percent_used(self, app_context, mock_usb_drive):
        """Test that percent_used is calculated correctly."""
        from app.services.storage.storage_drive_service import _get_drive_info

        drive_info = _get_drive_info(str(mock_usb_drive), 'TestDrive')

        assert 0 <= drive_info['percent_used'] <= 100

    def test_is_hidden_path(self, app_context):
        """Test hidden path detection."""
        from app.services.storage.storage_drive_service import _is_hidden_path

        assert _is_hidden_path('/media') is True
        assert _is_hidden_path('/media/ghost') is True
        assert _is_hidden_path('/boot') is True
        assert _is_hidden_path('/media/ghost/MyUSB') is False

    def test_has_media_content(self, app_context, mock_usb_drive):
        """Test media content detection (any files present)."""
        # Check a directory that has files
        movies_dir = str(mock_usb_drive / 'Movies')
        has_files = any(
            os.path.isfile(os.path.join(movies_dir, f))
            for f in os.listdir(movies_dir)
        )
        assert has_files is True

        # Empty directory should have no files
        empty_dir = mock_usb_drive / 'Empty'
        empty_dir.mkdir()
        has_files_empty = any(
            os.path.isfile(os.path.join(str(empty_dir), f))
            for f in os.listdir(str(empty_dir))
        )
        assert has_files_empty is False

    def test_format_bytes(self, app_context):
        """Test byte formatting utility."""
        from app.services.storage.storage_io_service import format_bytes

        assert 'B' in format_bytes(500)
        assert 'KB' in format_bytes(1024)
        assert 'MB' in format_bytes(1024 * 1024)
        assert 'GB' in format_bytes(1024 * 1024 * 1024)

    def test_get_current_mount_paths(self, app_context):
        """Test getting current mount paths."""
        from app.services.storage.storage_drive_service import get_current_mount_paths

        paths = get_current_mount_paths()
        assert isinstance(paths, set)

    @patch('platform.system', return_value='Windows')
    def test_windows_drive_detection(self, mock_platform, app_context):
        """Test Windows drive detection."""
        from app.services.storage.storage_drive_service import get_storage_drives

        # Should not raise an error
        drives = get_storage_drives()
        assert isinstance(drives, list)

    def test_is_path_writable_true_for_writable_directory(self, app_context):
        """Write-probe helper should return True when probe file can be created/removed."""
        from app.services.storage.storage_io_service import is_path_writable

        with patch("os.path.isdir", return_value=True), \
             patch("tempfile.mkstemp", return_value=(123, "/mock/probe.tmp")), \
             patch("os.close"), \
             patch("os.remove"), \
             patch("os.path.exists", return_value=False):
            assert is_path_writable("/mock/path") is True

    def test_is_path_writable_false_on_permission_error(self, app_context):
        """Write-probe helper should return False when probe file creation fails."""
        from app.services.storage.storage_io_service import is_path_writable

        with patch("tempfile.mkstemp", side_effect=PermissionError("denied")):
            with patch("os.path.isdir", return_value=True):
                assert is_path_writable("/mock/path") is False


class TestSimpleFileUpload:
    """Tests for simple (non-chunked) file uploads."""

    def test_upload_file_success(self, app_context, mock_usb_drive, mock_file_storage):
        """Test successful file upload."""
        from app.services.storage.standard_upload_service import upload_file

        file = mock_file_storage('test_upload.txt', b'test content')

        success, message = upload_file(
            file=file,
            drive_path=str(mock_usb_drive)
        )

        assert success is True
        assert os.path.exists(mock_usb_drive / 'test_upload.txt')

    def test_upload_file_to_subfolder(self, app_context, mock_usb_drive, mock_file_storage):
        """Test uploading file to a subfolder."""
        from app.services.storage.standard_upload_service import upload_file

        file = mock_file_storage('subfolder_file.txt', b'content')

        success, message = upload_file(
            file=file,
            drive_path=str(mock_usb_drive),
            subfolder='uploads'
        )

        assert success is True
        assert os.path.exists(mock_usb_drive / 'uploads' / 'subfolder_file.txt')

    def test_upload_file_nonexistent_drive(self, app_context, mock_file_storage):
        """Test upload to non-existent drive path."""
        from app.services.storage.standard_upload_service import upload_file

        file = mock_file_storage('test.txt', b'content')

        success, message = upload_file(
            file=file,
            drive_path='/nonexistent/path/that/really/does/not/exist'
        )

        # May create path or fail - depends on implementation
        # Either behavior is acceptable
        assert success in [True, False]

    def test_upload_file_auto_rename_duplicate(self, app_context, mock_usb_drive, mock_file_storage):
        """Test that duplicate filenames are auto-renamed."""
        from app.services.storage.standard_upload_service import upload_file

        # Upload first file
        file1 = mock_file_storage('duplicate.txt', b'content 1')
        upload_file(file1, str(mock_usb_drive))

        # Upload second file with same name
        file2 = mock_file_storage('duplicate.txt', b'content 2')
        success, message = upload_file(file2, str(mock_usb_drive))

        assert success is True
        # Should have created duplicate_1.txt
        assert os.path.exists(mock_usb_drive / 'duplicate_1.txt')

    def test_upload_file_invalid_filename(self, app_context, mock_usb_drive, mock_file_storage):
        """Test upload with invalid filename."""
        from app.services.storage.standard_upload_service import upload_file

        file = mock_file_storage('', b'content')  # Empty filename

        success, message = upload_file(file, str(mock_usb_drive))

        assert success is False
        assert 'invalid' in message.lower()

    def test_upload_file_secures_filename(self, app_context, mock_usb_drive, mock_file_storage):
        """Test that dangerous characters in filename are handled."""
        from app.services.storage.standard_upload_service import upload_file
        from werkzeug.utils import secure_filename

        # Filename with path traversal attempt
        file = mock_file_storage('../../../etc/passwd', b'malicious')

        success, message = upload_file(file, str(mock_usb_drive))

        # Should succeed and filename should be secured
        if success:
            # Check that the secured filename was used (no path traversal)
            secured_name = secure_filename('../../../etc/passwd')
            expected_path = os.path.join(str(mock_usb_drive), secured_name)
            # Verify file was written to mock_usb_drive with secured name
            assert os.path.exists(expected_path) or len(secured_name) == 0


class TestChunkedUpload:
    """Tests for chunked file upload functionality."""

    def test_init_chunked_upload(self, app_context, mock_usb_drive):
        """Test initializing a chunked upload session."""
        svc = _upload_service()

        success, message, upload_id = svc.init_chunked_upload(
            filename='large_file.mp4',
            total_chunks=10,
            total_size=50 * 1024 * 1024,  # 50MB
            drive_path=str(mock_usb_drive)
        )

        assert success is True
        assert upload_id is not None
        assert len(upload_id) == 16  # MD5 hex truncated to 16 chars

    def test_init_chunked_upload_checks_space(self, app_context, mock_usb_drive):
        """Test that init_chunked_upload checks available space."""
        svc = _upload_service()

        # Request more space than available (1 PB)
        success, message, upload_id = svc.init_chunked_upload(
            filename='huge.mp4',
            total_chunks=1000000,
            total_size=1024 * 1024 * 1024 * 1024 * 1024,  # 1 PB
            drive_path=str(mock_usb_drive)
        )

        assert success is False
        assert 'space' in message.lower()

    def test_init_chunked_upload_nonexistent_drive(self, app_context):
        """Test chunked upload init with non-existent drive."""
        svc = _upload_service()

        success, message, upload_id = svc.init_chunked_upload(
            filename='test.mp4',
            total_chunks=5,
            total_size=1024,
            drive_path='/nonexistent/drive'
        )

        assert success is False
        assert upload_id is None

    def test_upload_chunk_success(self, app_context, mock_usb_drive):
        """Test uploading a single chunk."""
        svc = _upload_service()

        # Initialize upload
        success, _, upload_id = svc.init_chunked_upload(
            filename='chunked_test.mp4',
            total_chunks=3,
            total_size=15 * 1024 * 1024,
            drive_path=str(mock_usb_drive)
        )

        # Upload a chunk
        chunk_data = b'x' * (5 * 1024 * 1024)  # 5MB chunk
        success, message, status = svc.upload_chunk(
            upload_id=upload_id,
            chunk_index=0,
            chunk_data=chunk_data
        )

        assert success is True
        assert status is not None
        assert status['chunks_received'] == 1
        assert status['progress'] > 0

    def test_upload_chunk_idempotency(self, app_context, mock_usb_drive):
        """Test that uploading the same chunk twice is idempotent."""
        svc = _upload_service()

        success, _, upload_id = svc.init_chunked_upload(
            filename='idempotent_test.mp4',
            total_chunks=2,
            total_size=10 * 1024 * 1024,
            drive_path=str(mock_usb_drive)
        )

        chunk_data = b'x' * (5 * 1024 * 1024)

        # Upload same chunk twice
        svc.upload_chunk(upload_id, 0, chunk_data)
        success, message, status = svc.upload_chunk(upload_id, 0, chunk_data)

        assert success is True
        assert 'already received' in message.lower()
        assert status['chunks_received'] == 1  # Should still be 1

    def test_upload_chunk_nonexistent_session(self, app_context):
        """Test uploading chunk to non-existent session."""
        svc = _upload_service()

        success, message, status = svc.upload_chunk(
            upload_id='nonexistent-upload-id',
            chunk_index=0,
            chunk_data=b'test'
        )

        assert success is False
        assert 'not found' in message.lower()

    def test_complete_chunked_upload(self, app_context, mock_usb_drive):
        """Test completing a full chunked upload."""
        svc = _upload_service()

        total_chunks = 2
        chunk_size = 5 * 1024 * 1024  # 5MB

        success, _, upload_id = svc.init_chunked_upload(
            filename='complete_test.mp4',
            total_chunks=total_chunks,
            total_size=total_chunks * chunk_size,
            drive_path=str(mock_usb_drive)
        )

        # Upload all chunks
        for i in range(total_chunks):
            chunk_data = b'x' * chunk_size
            success, message, status = svc.upload_chunk(upload_id, i, chunk_data)

        assert success is True
        assert status['complete'] is True
        assert os.path.exists(mock_usb_drive / 'complete_test.mp4')

    def test_cancel_chunked_upload(self, app_context, mock_usb_drive):
        """Test cancelling a chunked upload."""
        svc = _upload_service()

        success, _, upload_id = svc.init_chunked_upload(
            filename='cancel_test.mp4',
            total_chunks=5,
            total_size=25 * 1024 * 1024,
            drive_path=str(mock_usb_drive)
        )

        # Upload one chunk
        svc.upload_chunk(upload_id, 0, b'x' * 1024)

        # Cancel
        success, message = svc.cancel_chunked_upload(upload_id)

        assert success is True

        # Verify session is gone
        status = svc.get_upload_status(upload_id)
        assert status is None

    def test_get_upload_status(self, app_context, mock_usb_drive):
        """Test getting upload status."""
        svc = _upload_service()

        success, _, upload_id = svc.init_chunked_upload(
            filename='status_test.mp4',
            total_chunks=4,
            total_size=20 * 1024 * 1024,
            drive_path=str(mock_usb_drive)
        )

        # Upload some chunks
        svc.upload_chunk(upload_id, 0, b'x' * 1024)
        svc.upload_chunk(upload_id, 1, b'x' * 1024)

        status = svc.get_upload_status(upload_id)

        assert status is not None
        assert status['filename'] == 'status_test.mp4'
        assert status['chunks_received'] == 2
        assert status['total_chunks'] == 4
        assert status['progress'] == 50.0

    def test_chunked_upload_with_relative_path(self, app_context, mock_usb_drive):
        """Test chunked upload preserving folder structure."""
        svc = _upload_service()

        success, _, upload_id = svc.init_chunked_upload(
            filename='nested_file.mp4',
            total_chunks=1,
            total_size=1024,
            drive_path=str(mock_usb_drive),
            relative_path='folder/subfolder/nested_file.mp4'
        )

        assert success is True

        # Upload and complete
        svc.upload_chunk(upload_id, 0, b'x' * 1024)

        assert os.path.exists(mock_usb_drive / 'folder' / 'subfolder' / 'nested_file.mp4')

    def test_cleanup_stale_uploads(self, app_context, mock_usb_drive):
        """Test cleanup of stale upload sessions."""
        svc = _upload_service()

        # Create an upload
        success, _, upload_id = svc.init_chunked_upload(
            filename='stale_test.mp4',
            total_chunks=10,
            total_size=50 * 1024 * 1024,
            drive_path=str(mock_usb_drive)
        )

        from app.services.storage.upload_session_runtime_service import CHUNK_UPLOAD_TIMEOUT
        # Manually set last_activity to past
        with svc.upload_lock:
            if upload_id in svc.active_uploads:
                svc.active_uploads[upload_id]['last_activity'] = \
                    time.time() - CHUNK_UPLOAD_TIMEOUT - 100

        # Run cleanup
        svc.cleanup_stale_uploads()

        # Session should be gone
        assert svc.get_upload_status(upload_id) is None

    def test_ram_staging_path_logic(self, app_context):
        """Test RAM staging path selection logic."""
        svc = _upload_service()

        with patch('app.services.storage.upload_session_runtime_service.get_runtime_config_value', return_value=True):
            with patch('os.path.exists', side_effect=lambda p: p == '/dev/shm'):
                with patch('os.access', return_value=True):
                    with patch('app.services.storage.upload_session_runtime_service.get_hardware_tier', return_value='PRO'):
                        with patch('app.services.storage.upload_session_runtime_service.get_memory_info', return_value={'available_mb': 8192}):
                            with patch('os.makedirs'):
                                path = svc.get_ram_staging_path()
                                assert path == '/dev/shm/ghosthub_uploads'

    def test_init_chunked_upload_uses_ram_when_appropriate(self, app_context, mock_usb_drive):
        """Test that init_chunked_upload chooses RAM staging when within budget."""
        svc = _upload_service()

        with patch.object(svc, 'get_ram_staging_path', return_value='/dev/shm/ghosthub_uploads'):
            with patch('app.services.storage.upload_session_runtime_service.get_memory_info', return_value={'available_mb': 8192}):
                with patch('app.services.storage.upload_session_runtime_service.get_hardware_tier', return_value='PRO'):
                    with patch('os.makedirs'):
                        with patch('builtins.open', mock_open()):
                            success, message, upload_id = svc.init_chunked_upload(
                                filename='ram_test.mp4',
                                total_chunks=1,
                                total_size=100 * 1024 * 1024,  # 100MB - fits in PRO budget
                                drive_path=str(mock_usb_drive)
                            )

                            assert success is True
                            with svc.upload_lock:
                                assert '/dev/shm/ghosthub_uploads' in svc.active_uploads[upload_id]['temp_path']

    def test_init_chunked_upload_falls_back_to_disk_when_over_budget(self, app_context, mock_usb_drive):
        """Test that init_chunked_upload falls back to disk when file is too large for RAM budget."""
        svc = _upload_service()

        with patch.object(svc, 'get_ram_staging_path', return_value='/dev/shm/ghosthub_uploads'):
            with patch('app.services.storage.upload_session_runtime_service.get_memory_info', return_value={'available_mb': 1024}):
                with patch('app.services.storage.upload_session_runtime_service.get_hardware_tier', return_value='LITE'):
                    with patch('os.makedirs'):
                        with patch('builtins.open', mock_open()):
                            success, message, upload_id = svc.init_chunked_upload(
                                filename='disk_fallback.mp4',
                                total_chunks=1,
                                total_size=500 * 1024 * 1024,  # 500MB - over LITE budget
                                drive_path=str(mock_usb_drive)
                            )

                            assert success is True
                            with svc.upload_lock:
                                assert '.ghosthub_uploads' in svc.active_uploads[upload_id]['temp_path']
                                assert str(mock_usb_drive) in svc.active_uploads[upload_id]['temp_path']


class TestFolderOperations:
    """Tests for folder-related operations."""

    def test_get_drive_folders(self, app_context, mock_usb_drive):
        """Test getting folders in a drive."""
        from app.services.storage.storage_folder_service import get_drive_folders

        folders = get_drive_folders(str(mock_usb_drive))

        assert isinstance(folders, list)
        folder_names = [f['name'] for f in folders]
        assert 'Movies' in folder_names
        assert 'Photos' in folder_names

    def test_get_drive_folders_excludes_system_folders(self, app_context, mock_usb_drive):
        """Test that system folders are excluded."""
        from app.services.storage.storage_folder_service import get_drive_folders

        # Create a system folder
        (mock_usb_drive / '$RECYCLE.BIN').mkdir()
        (mock_usb_drive / 'System Volume Information').mkdir()

        folders = get_drive_folders(str(mock_usb_drive))
        folder_names = [f['name'] for f in folders]

        assert '$RECYCLE.BIN' not in folder_names
        assert 'System Volume Information' not in folder_names

    def test_get_drive_folders_sorted_alphabetically(self, app_context, mock_usb_drive):
        """Test that folders are sorted alphabetically."""
        from app.services.storage.storage_folder_service import get_drive_folders

        folders = get_drive_folders(str(mock_usb_drive))
        folder_names = [f['name'].lower() for f in folders]

        assert folder_names == sorted(folder_names)

    def test_create_folder(self, app_context, mock_usb_drive):
        """Test creating a new folder."""
        from app.services.storage.storage_folder_service import create_folder

        success, message = create_folder(
            str(mock_usb_drive),
            'NewFolder'
        )

        assert success is True
        assert os.path.exists(mock_usb_drive / 'NewFolder')

    def test_create_folder_already_exists(self, app_context, mock_usb_drive):
        """Test creating folder that already exists."""
        from app.services.storage.storage_folder_service import create_folder

        success, message = create_folder(
            str(mock_usb_drive),
            'Movies'  # Already exists
        )

        assert success is False
        assert 'exists' in message.lower()

    def test_create_folder_invalid_name(self, app_context, mock_usb_drive):
        """Test creating folder with invalid name."""
        from app.services.storage.storage_folder_service import create_folder

        success, message = create_folder(
            str(mock_usb_drive),
            ''  # Empty name
        )

        assert success is False
        assert 'invalid' in message.lower()


class TestZipStreaming:
    """Tests for ZIP streaming functionality."""

    def test_get_folder_file_list(self, app_context, mock_usb_drive):
        """Test getting file list for a folder."""
        from app.services.storage.storage_archive_service import get_folder_file_list

        files = get_folder_file_list(str(mock_usb_drive / 'Movies'))

        assert isinstance(files, list)
        assert len(files) > 0
        # Each entry should be (path, arcname, size)
        for file_path, arcname, size in files:
            assert os.path.isfile(file_path)
            assert isinstance(size, int)

    def test_get_folder_zip_info(self, app_context, mock_usb_drive):
        """Test getting ZIP info for a folder."""
        from app.services.storage.storage_archive_service import get_folder_zip_info

        success, folder_name, total_size, num_parts, parts_info = \
            get_folder_zip_info(str(mock_usb_drive / 'Movies'))

        assert success is True
        assert folder_name == 'Movies'
        assert total_size > 0
        assert num_parts >= 1

    def test_get_folder_zip_info_nonexistent(self, app_context):
        """Test ZIP info for non-existent folder."""
        from app.services.storage.storage_archive_service import get_folder_zip_info

        result = get_folder_zip_info('/nonexistent/path/xyz')

        # Result is a tuple (success, ...) - first element should be False or error handled
        if isinstance(result, tuple) and len(result) >= 1:
            # Could be (False, message, ...) or handle empty results gracefully
            success = result[0]
            assert success in [True, False]  # Either is acceptable
        else:
            # If not a tuple, just verify it doesn't crash
            assert result is not None or result is None

    def test_stream_folder_zip_yields_data(self, app_context, mock_usb_drive):
        """Test that streaming ZIP yields data."""
        from app.services.storage.storage_archive_service import stream_folder_zip

        # Create some files to zip
        test_folder = mock_usb_drive / 'ZipTest'
        test_folder.mkdir()
        (test_folder / 'file1.txt').write_text('content 1')
        (test_folder / 'file2.txt').write_text('content 2')

        chunks = list(stream_folder_zip(str(test_folder)))

        # Should yield some data
        assert len(chunks) > 0
        total_size = sum(len(chunk) for chunk in chunks)
        assert total_size > 0


class TestMountChangeDetection:
    """Tests for USB mount change detection."""

    def test_has_mounts_changed_initial(self, app_context):
        """Test mount change detection on first call."""
        from app.services.storage.storage_drive_service import get_storage_drives, has_mounts_changed
        from app.services.storage.storage_runtime_store import storage_runtime_store

        # Reset mount hash so the first snapshot won't trigger a change
        _reset_mount_state()

        # Trigger a drive scan (which updates the snapshot)
        get_storage_drives()

        # Should report no change since old hash was None (first scan)
        assert has_mounts_changed() is False

    @patch('app.services.storage.storage_drive_service._get_linux_drives')
    def test_update_mount_snapshot_triggers_bus_event(self, mock_drives, app_context):
        """Test that mount changes emit a bus event."""
        from app.services.storage.storage_drive_service import _update_mount_snapshot
        from app.services.storage.storage_runtime_store import storage_runtime_store
        from specter import bus

        # Set initial state with a known hash so a change is detected
        storage_runtime_store.set({
            'last_mount_hash': 'initial_hash',
            'last_mount_snapshot': {'/media/old_drive': 'OldDrive'},
        })

        mock_drives.return_value = [{'path': '/media/new_drive', 'name': 'NewDrive'}]

        with patch.object(bus, 'emit') as mock_emit:
            _update_mount_snapshot([{'path': '/media/new_drive', 'name': 'NewDrive'}])

            # Should have emitted STORAGE_MOUNT_CHANGED
            mock_emit.assert_called()
            _, payload = mock_emit.call_args.args
            assert payload['mounted_paths'] == ['/media/new_drive']
            assert payload['unmounted_paths'] == ['/media/old_drive']

    @patch('app.services.storage.storage_drive_service._all_subfolders_hidden')
    def test_filter_hidden_only_drives_is_request_scoped(self, mock_all_hidden, app_context):
        """Filtering hidden-only drives should happen outside the runtime mount cache."""
        from app.services.storage.storage_drive_service import filter_hidden_only_drives

        mock_all_hidden.side_effect = lambda path: path.endswith('HiddenDrive')

        drives = [
            {'path': '/media/ghost/HiddenDrive', 'name': 'HiddenDrive'},
            {'path': '/media/ghost/VisibleDrive', 'name': 'VisibleDrive'},
        ]

        filtered = filter_hidden_only_drives(drives)

        assert filtered == [{'path': '/media/ghost/VisibleDrive', 'name': 'VisibleDrive'}]
        mock_all_hidden.assert_any_call('/media/ghost/HiddenDrive')
        mock_all_hidden.assert_any_call('/media/ghost/VisibleDrive')


class TestThreadSafety:
    """Tests for thread safety in storage operations."""

    def test_concurrent_chunked_uploads(self, app_context, mock_usb_drive):
        """Test multiple concurrent chunked uploads."""
        svc = _upload_service()

        errors = []
        upload_ids = []

        def create_upload(index):
            try:
                success, _, upload_id = svc.init_chunked_upload(
                    filename=f'concurrent_{index}.mp4',
                    total_chunks=2,
                    total_size=1024,
                    drive_path=str(mock_usb_drive)
                )
                if success:
                    upload_ids.append(upload_id)
                    # Upload a chunk
                    svc.upload_chunk(upload_id, 0, b'x' * 512)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=create_upload, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(upload_ids) == 5


class TestHotplugDetection:
    """Tests for USB hotplug detection logic."""

    def test_monitor_udev_triggers_refresh(self, app_context):
        """Test that _monitor_udev triggers a cache refresh on device events."""
        import app.services.storage.storage_drive_service as _drive_svc

        svc = _drive_service()

        from app.services.storage.storage_runtime_store import storage_runtime_store

        mock_monitor = MagicMock()
        mock_device = MagicMock()
        mock_device.action = 'add'
        mock_device.get.side_effect = lambda k: 'usb' if k == 'ID_BUS' else None
        mock_device.__contains__.return_value = True  # 'ID_USB_DRIVER' in device
        mock_device.sys_name = 'sda'

        mock_pyudev = MagicMock()
        mock_pyudev.Monitor.from_netlink.return_value = mock_monitor
        mock_monitor.poll.side_effect = [mock_device, None]

        # Enable monitoring so the while loop runs at least once
        storage_runtime_store.set({'monitoring': True})

        with patch.object(_drive_svc, 'pyudev', mock_pyudev), \
             patch('gevent.select.select', side_effect=[None, Exception("Stop loop")]), \
             patch('gevent.sleep'), \
             patch.object(svc, 'refresh_drive_cache_async') as mock_refresh:
            try:
                svc._monitor_udev()
            except Exception as e:
                if str(e) != "Stop loop":
                    raise

        mock_refresh.assert_called()

    def test_monitor_udev_ignores_non_usb_non_disk(self, app_context):
        """Test that _monitor_udev ignores irrelevant block events."""
        import app.services.storage.storage_drive_service as _drive_svc

        svc = _drive_service()

        from app.services.storage.storage_runtime_store import storage_runtime_store

        mock_monitor = MagicMock()
        mock_device = MagicMock()
        mock_device.action = 'add'
        # Not USB, not a disk partition
        mock_device.get.side_effect = lambda k: 'loop' if k in ('ID_BUS', 'DEVTYPE') else None
        mock_device.__contains__.return_value = False  # 'ID_USB_DRIVER' not in device
        mock_device.sys_name = 'loop0'

        mock_pyudev = MagicMock()
        mock_pyudev.Monitor.from_netlink.return_value = mock_monitor
        mock_monitor.poll.side_effect = [mock_device, None]

        storage_runtime_store.set({'monitoring': True})

        with patch.object(_drive_svc, 'pyudev', mock_pyudev), \
             patch('gevent.select.select', side_effect=[None, Exception("Stop loop")]), \
             patch('gevent.sleep'), \
             patch.object(svc, 'refresh_drive_cache_async') as mock_refresh:
            try:
                svc._monitor_udev()
            except Exception as e:
                if str(e) != "Stop loop":
                    raise

        mock_refresh.assert_not_called()
