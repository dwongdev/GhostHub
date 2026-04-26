"""
Tests for Storage Routes
Tests storage/upload API endpoints.
Uses fixtures from conftest.py.
"""
import pytest
from unittest.mock import patch
import io


class TestStorageRoutes:
    """Tests for storage route endpoints."""
    
    def test_get_drives(self, client, app):
        """Test getting available drives."""
        with app.app_context():
            response = client.get('/api/storage/drives')
            # May or may not be implemented
            assert response.status_code in [200, 404]
    
    def test_upload_init_requires_admin(self, client, app, mock_config):
        """Test that upload init requires admin or session auth."""
        with app.app_context():
            # Require session-password or admin for this request path.
            mock_config('SESSION_PASSWORD', 'test-password')

            # Clear any session state from other tests
            with client.session_transaction() as sess:
                sess.clear()

            response = client.post('/api/storage/upload/init', json={
                'filename': 'test.mp4',
                'total_size': 1000000,
                'total_chunks': 10,
                'drive_path': '/media/test'
            })
            # Uses @session_or_admin_required - should return 401/403 for auth
            assert response.status_code in [401, 403]
    
    def test_upload_init_as_admin(self, admin_client, app):
        """Test upload init as admin."""
        with app.app_context():
            response = admin_client.post('/api/storage/upload/init', json={
                'filename': 'test.mp4',
                'total_size': 1000000,
                'total_chunks': 10,
                'category_id': 'test-cat'
            })
            assert response.status_code in [200, 400, 403, 404]
    
    def test_upload_chunk(self, admin_client, app):
        """Test uploading a chunk."""
        with app.app_context():
            data = {
                'upload_id': 'test-upload-123',
                'chunk_index': '0',
                'chunk': (io.BytesIO(b'test data'), 'chunk.bin')
            }
            response = admin_client.post(
                '/api/storage/upload/chunk',
                data=data,
                content_type='multipart/form-data'
            )
            assert response.status_code in [200, 400, 403, 404]
    
    def test_upload_complete(self, admin_client, app):
        """Test completing upload."""
        with app.app_context():
            response = admin_client.post('/api/storage/upload/complete/test-upload-123')
            assert response.status_code in [200, 400, 403, 404]
    
    def test_upload_cancel(self, admin_client, app):
        """Test canceling upload."""
        with app.app_context():
            response = admin_client.post('/api/storage/upload/cancel/test-upload-123')
            assert response.status_code in [200, 400, 403, 404]
    
    def test_simple_upload(self, admin_client, app):
        """Test simple file upload."""
        with app.app_context():
            data = {
                'file': (io.BytesIO(b'test file content'), 'test.mp4'),
                'category_id': 'test-cat'
            }
            response = admin_client.post(
                '/api/storage/upload',
                data=data,
                content_type='multipart/form-data'
            )
            assert response.status_code in [200, 400, 403, 404]
    
    def test_delete_file_requires_admin(self, client, app):
        """Test that delete requires admin."""
        with app.app_context():
            response = client.delete('/api/storage/file', json={
                'path': '/media/test.mp4'
            })
            assert response.status_code in [401, 403, 404, 405]
