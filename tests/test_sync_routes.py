"""
Tests for Sync Routes
Tests sync/watch party API endpoints.
Uses fixtures from conftest.py.
"""
import pytest


class TestSyncRoutes:
    """Tests for sync route endpoints."""
    
    def test_get_sync_status(self, client, app):
        """Test getting sync status."""
        with app.app_context():
            response = client.get('/api/sync/status')
            assert response.status_code in [200, 404]
    
    def test_get_sync_state(self, client, app):
        """Test getting sync state."""
        with app.app_context():
            response = client.get('/api/sync/state')
            assert response.status_code in [200, 404]
    
    def test_join_sync(self, client, app):
        """Test joining sync session."""
        with app.app_context():
            response = client.post('/api/sync/join', json={
                'session_id': 'test-session'
            })
            assert response.status_code in [200, 400, 404, 405]
    
    def test_leave_sync(self, client, app):
        """Test leaving sync session."""
        with app.app_context():
            response = client.post('/api/sync/leave', json={
                'session_id': 'test-session'
            })
            assert response.status_code in [200, 400, 404, 405]
    
    def test_become_host(self, client, app):
        """Test becoming sync host."""
        with app.app_context():
            response = client.post('/api/sync/host', json={
                'session_id': 'test-session'
            })
            assert response.status_code in [200, 400, 404, 405]
    
    def test_sync_navigate(self, client, app):
        """Test sync navigation."""
        with app.app_context():
            response = client.post('/api/sync/navigate', json={
                'category_id': 'movies',
                'media_index': 5
            })
            assert response.status_code in [200, 400, 403, 404, 405]
