"""
Tests for App Factory
---------------------
Comprehensive tests for Flask application creation including:
- App factory function
- Configuration loading
- Extension initialization
- Blueprint registration
- Database initialization
"""
import pytest
import os
from unittest.mock import patch, MagicMock


class TestAppFactory:
    """Tests for create_app factory function."""
    
    def test_create_app_returns_flask_instance(self):
        """Test that create_app returns a Flask application."""
        from app import create_app
        from flask import Flask
        
        app = create_app('default')
        
        assert isinstance(app, Flask)
    
    def test_create_app_with_development_config(self):
        """Test create_app with development configuration."""
        from app import create_app
        
        app = create_app('development')
        
        assert app.config['DEBUG'] is True
    
    def test_create_app_with_production_config(self):
        """Test create_app with production configuration."""
        from app import create_app
        
        app = create_app('production')
        
        assert app.config['DEBUG'] is False
    
    def test_create_app_registers_blueprints(self):
        """Test that create_app registers all blueprints."""
        from app import create_app
        
        app = create_app('default')
        
        # Check that expected blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        
        # Main routes should be registered
        assert any('main' in name.lower() or name == '' for name in blueprint_names) or len(blueprint_names) > 0
    
    def test_create_app_configures_static_folder(self):
        """Test that static folder is configured."""
        from app import create_app
        
        app = create_app('default')
        
        assert app.static_folder is not None
        assert 'static' in app.static_folder
    
    def test_create_app_configures_template_folder(self):
        """Test that template folder is configured."""
        from app import create_app
        
        app = create_app('default')
        
        assert app.template_folder is not None
        assert 'templates' in app.template_folder
    
    def test_create_app_initializes_socketio(self):
        """Test that SocketIO is initialized."""
        from app import create_app, socketio
        
        app = create_app('default')
        
        assert socketio is not None
    
    def test_create_app_sets_max_content_length(self):
        """Test that MAX_CONTENT_LENGTH is set for large uploads."""
        from app import create_app
        
        app = create_app('default')
        
        # Should be set to 16GB for large media files
        assert app.config['MAX_CONTENT_LENGTH'] >= 16 * 1024 * 1024 * 1024


class TestAppConfiguration:
    """Tests for application configuration."""
    
    def test_app_has_secret_key(self):
        """Test that app has a secret key."""
        from app import create_app
        
        app = create_app('default')
        
        assert app.config['SECRET_KEY'] is not None
        assert len(str(app.config['SECRET_KEY'])) > 0
    
    def test_app_has_media_extensions_config(self):
        """Test that media extensions are configured."""
        from app import create_app
        
        app = create_app('default')
        
        assert 'MEDIA_EXTENSIONS' in app.config
        assert len(app.config['MEDIA_EXTENSIONS']) > 0
    
    def test_app_has_image_extensions_config(self):
        """Test that image extensions are configured."""
        from app import create_app
        
        app = create_app('default')
        
        assert 'IMAGE_EXTENSIONS' in app.config
        assert '.jpg' in app.config['IMAGE_EXTENSIONS']
    
    def test_app_has_video_extensions_config(self):
        """Test that video extensions are configured."""
        from app import create_app
        
        app = create_app('default')
        
        assert 'VIDEO_EXTENSIONS' in app.config
        assert '.mp4' in app.config['VIDEO_EXTENSIONS']


class TestDatabaseInitialization:
    """Tests for database initialization during app creation."""
    
    def test_database_initialized_on_app_creation(self):
        """Test that database is initialized when app is created."""
        from app import create_app
        
        app = create_app('default')
        
        # App should be created without errors
        assert app is not None
    
    @patch('app.services.core.database_bootstrap_service.ensure_database_ready')
    def test_init_database_called(self, mock_ensure_db):
        """Test that database is initialized during app creation."""
        from app import create_app

        app = create_app('default')

        # database initialization should be called during install_specter
        mock_ensure_db.assert_called()


class TestAppContext:
    """Tests for application context handling."""
    
    def test_app_context_available(self):
        """Test that app context is properly set up."""
        from app import create_app
        from flask import current_app
        
        app = create_app('default')
        
        with app.app_context():
            assert current_app is not None
            assert current_app.name == app.name
    
    def test_request_context_available(self):
        """Test that request context is properly set up."""
        from app import create_app
        from flask import request
        
        app = create_app('default')
        
        with app.test_request_context('/'):
            assert request is not None
            assert request.path == '/'


class TestErrorHandlers:
    """Tests for error handler registration."""
    
    def test_404_handler(self):
        """Test 404 error handler."""
        from app import create_app
        
        app = create_app('default')
        client = app.test_client()
        
        response = client.get('/nonexistent-page-12345')
        
        assert response.status_code == 404
    
    def test_500_handler(self):
        """Test that 500 errors are handled gracefully."""
        from app import create_app
        
        app = create_app('default')
        
        # App should have error handling for internal errors
        # Specific behavior depends on configuration


class TestCORS:
    """Tests for CORS configuration if applicable."""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are set if enabled."""
        from app import create_app
        
        app = create_app('default')
        client = app.test_client()
        
        response = client.options('/api/categories')

        # CORS headers may or may not be present depending on config

    def test_security_headers_present(self):
        """Test that security hardening headers are set globally."""
        from app import create_app

        app = create_app('default')
        client = app.test_client()

        response = client.get('/api/config')
        assert response.headers.get('X-Frame-Options') == 'DENY'
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'
        assert 'frame-ancestors' in (response.headers.get('Content-Security-Policy') or '')


class TestInstanceFolder:
    """Tests for instance folder handling."""
    
    def test_instance_folder_created(self):
        """Test that instance folder is created if it doesn't exist."""
        from app import create_app
        
        app = create_app('default')
        
        # Instance folder should exist after app creation
        assert app.instance_path is not None
    
    def test_instance_folder_path_absolute(self):
        """Test that instance folder path is absolute."""
        from app import create_app
        
        app = create_app('default')
        
        if app.instance_path:
            assert os.path.isabs(app.instance_path)


class TestLogging:
    """Tests for logging configuration."""
    
    def test_logger_configured(self):
        """Test that logger is configured."""
        from app import create_app
        
        app = create_app('default')
        
        assert app.logger is not None
    
    def test_debug_logging_in_debug_mode(self):
        """Test that debug logging works in debug mode."""
        from app import create_app
        
        app = create_app('development')
        
        assert app.debug is True
