"""Tests for upload session runtime store access."""

from unittest.mock import patch

from gevent.lock import BoundedSemaphore

from app.services.storage.upload_session_runtime_service import UploadSessionRuntimeService
from specter import create_store


class TestUploadSessionRuntimeService:
    """Coverage for store-backed upload lock and active upload accessors."""

    def test_store_accessors_read_from_store_state(self):
        store = create_store('upload_sessions', {
            'active_uploads': {},
            'upload_lock': BoundedSemaphore(1),
        })
        service = UploadSessionRuntimeService()

        with patch(
            'app.services.storage.upload_session_runtime_service.registry.require',
            return_value=store,
        ):
            assert service.active_uploads is store.get('active_uploads')
            assert service.upload_lock is store.get('upload_lock')

    def test_upload_lock_accessor_self_heals_when_missing(self):
        store = create_store('upload_sessions', {
            'active_uploads': {},
        })
        service = UploadSessionRuntimeService()

        with patch(
            'app.services.storage.upload_session_runtime_service.registry.require',
            return_value=store,
        ):
            lock = service.upload_lock

        assert lock is store.get('upload_lock')
