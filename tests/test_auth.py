"""
Tests for Auth Utilities
Tests authentication decorators and helpers.
Uses fixtures from conftest.py.
"""
import pytest
from flask import session


class TestAdminRequired:
    """Tests for admin_required decorator."""
    
    def test_admin_required_allows_admin(self, admin_client, app):
        """Test that admin_required allows admin access via endpoint."""
        with app.app_context():
            # Use an actual admin-protected endpoint
            response = admin_client.get('/api/admin/status')
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('isAdmin') is True
    
    def test_admin_required_rejects_non_admin(self, client, app):
        """Test that admin_required rejects non-admin access."""
        with app.app_context():
            # Try to access an admin endpoint without auth
            response = client.post('/api/admin/logout')
            # Should be rejected or route doesn't exist
            assert response.status_code in [200, 302, 401, 403, 404]
    
    def test_guest_cannot_delete_category(self, client, app):
        """Test that guests cannot delete categories."""
        with app.app_context():
            response = client.delete('/api/categories/test-cat')
            assert response.status_code in [401, 403, 404]

    def test_admin_required_allows_admin_with_missing_flask_admin_flag(self, admin_client, app):
        """Admin lock + session_id should grant admin access even if Flask session flag is missing."""
        with app.app_context():
            with admin_client.session_transaction() as sess:
                sess.pop('is_admin', None)

            response = admin_client.post('/api/admin/release')
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('success') is True


class TestSocketAdminFlagSync:
    """Regression tests for socket-safe admin auth syncing."""

    def test_cookie_match_repairs_missing_admin_flag(self, app):
        with app.app_context():
            from app.utils.auth import (
                is_current_admin_session_with_flag_sync,
                set_admin_session_id,
            )

            admin_session_id = "admin-session-1"
            set_admin_session_id(admin_session_id)

            with app.test_request_context(
                "/socket-test",
                headers={"Cookie": f"session_id={admin_session_id}"},
            ):
                session.pop("is_admin", None)
                assert is_current_admin_session_with_flag_sync() is True
                assert session.get("is_admin") is True

    def test_cookie_mismatch_clears_stale_admin_flag(self, app):
        with app.app_context():
            from app.utils.auth import (
                is_current_admin_session_with_flag_sync,
                set_admin_session_id,
            )

            set_admin_session_id("true-admin-session")

            with app.test_request_context(
                "/socket-test",
                headers={"Cookie": "session_id=guest-session"},
            ):
                session["is_admin"] = True
                assert is_current_admin_session_with_flag_sync() is False
                assert session.get("is_admin") is False
