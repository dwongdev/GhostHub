"""
Tests for Main Routes
Tests main page and template rendering.
Uses fixtures from conftest.py.
"""
import gzip

import pytest


class TestMainRoutes:
    """Tests for main route endpoints."""
    
    def test_index_page(self, client, app):
        """Test main index page renders."""
        with app.app_context():
            response = client.get('/')
            assert response.status_code == 200
            assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
    
    def test_index_returns_html(self, client, app):
        """Test index returns HTML content type."""
        with app.app_context():
            response = client.get('/')
            assert 'text/html' in response.content_type
    
    #def test_tv_display_page(self, client, app):
    #    """Test TV display page renders."""
    #    with app.app_context():
    #        response = client.get('/tv')
    #        assert response.status_code in [200, 302, 404]
    
    def test_static_files_accessible(self, client, app):
        """Test that static files are accessible."""
        with app.app_context():
            response = client.get('/static/manifest.json')
            assert response.status_code == 200

    def test_static_js_is_gzipped_when_requested(self, client, app):
        """Test that static JavaScript is gzip-compressed for capable clients."""
        with app.app_context():
            response = client.get(
                '/static/js/main.js',
                headers={'Accept-Encoding': 'gzip'},
            )
            assert response.status_code == 200
            assert response.headers.get('Content-Encoding') == 'gzip'
            assert 'Accept-Encoding' in (response.headers.get('Vary') or '')
            assert gzip.decompress(response.data).startswith(b'/**')
    
    def test_favicon(self, client, app):
        """Test favicon is accessible."""
        with app.app_context():
            response = client.get('/static/icons/Ghosthub.ico')
            assert response.status_code == 200
    
    def test_404_handler(self, client, app):
        """Test 404 error handling."""
        with app.app_context():
            response = client.get('/nonexistent-page-12345')
            assert response.status_code == 404
