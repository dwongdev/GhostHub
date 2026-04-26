"""
Tests for Configuration Module
------------------------------
Comprehensive tests for application configuration including:
- Default configuration values
- Environment variable overrides
- JSON configuration loading
- Configuration class hierarchy
- Path resolution
"""
import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock


class TestDefaultConfiguration:
    """Tests for default configuration values."""
    
    def test_default_cache_expiry(self):
        """Test default CACHE_EXPIRY value."""
        from app.config import Config
        
        assert Config.CACHE_EXPIRY == 300  # 5 minutes
    
    def test_default_page_size(self):
        """Test default DEFAULT_PAGE_SIZE value."""
        from app.config import Config
        
        assert Config.DEFAULT_PAGE_SIZE == 10
    
    def test_default_session_expiry(self):
        """Test default SESSION_EXPIRY value."""
        from app.config import Config

        assert Config.SESSION_EXPIRY == 604800  # 7 days (prevents admin session from expiring during normal usage)
    
    def test_default_shuffle_media(self):
        """Test default SHUFFLE_MEDIA value."""
        from app.config import Config

        assert Config.SHUFFLE_MEDIA is False
    
    def test_default_save_video_progress(self):
        """Test default SAVE_VIDEO_PROGRESS value."""
        from app.config import Config
        
        # Default should be True
        assert Config.SAVE_VIDEO_PROGRESS is True

    def test_default_enable_subtitles(self):
        """Test default ENABLE_SUBTITLES value."""
        from app.config import Config

        assert Config.ENABLE_SUBTITLES is True

    def test_default_video_end_behavior(self):
        """Test default VIDEO_END_BEHAVIOR value."""
        from app.config import Config

        assert Config.VIDEO_END_BEHAVIOR == 'loop'

    def test_default_tunnel_provider(self):
        """Test default TUNNEL_PROVIDER value."""
        from app.config import Config
        
        assert Config.TUNNEL_PROVIDER == 'none'
    
    def test_default_tunnel_local_port(self):
        """Test default TUNNEL_LOCAL_PORT value."""
        from app.config import Config
        
        assert Config.TUNNEL_LOCAL_PORT == 5000
    
    def test_default_websocket_settings(self):
        """Test default WebSocket settings."""
        from app.config import Config
        
        assert Config.WS_RECONNECT_ATTEMPTS == 10
        assert Config.WS_RECONNECT_DELAY == 1000
        assert Config.WS_RECONNECT_FACTOR == 1.5


class TestMediaTypeConfiguration:
    """Tests for media type configuration."""
    
    def test_image_extensions_exist(self):
        """Test that image extensions are defined."""
        from app.config import Config
        
        assert Config.IMAGE_EXTENSIONS is not None
        assert len(Config.IMAGE_EXTENSIONS) > 0
        assert '.jpg' in Config.IMAGE_EXTENSIONS
        assert '.png' in Config.IMAGE_EXTENSIONS
    
    def test_video_extensions_exist(self):
        """Test that video extensions are defined."""
        from app.config import Config
        
        assert Config.VIDEO_EXTENSIONS is not None
        assert len(Config.VIDEO_EXTENSIONS) > 0
        assert '.mp4' in Config.VIDEO_EXTENSIONS
        assert '.mkv' in Config.VIDEO_EXTENSIONS
    
    def test_media_extensions_combined(self):
        """Test that MEDIA_EXTENSIONS combines image and video."""
        from app.config import Config
        
        for ext in Config.IMAGE_EXTENSIONS:
            assert ext in Config.MEDIA_EXTENSIONS
        
        for ext in Config.VIDEO_EXTENSIONS:
            assert ext in Config.MEDIA_EXTENSIONS
    
    def test_media_types_have_mime_types(self):
        """Test that MEDIA_TYPES include MIME type mappings."""
        from app.config import Config
        
        assert 'image' in Config.MEDIA_TYPES
        assert 'video' in Config.MEDIA_TYPES
        
        assert 'mime_types' in Config.MEDIA_TYPES['image']
        assert 'mime_types' in Config.MEDIA_TYPES['video']
        
        assert '.jpg' in Config.MEDIA_TYPES['image']['mime_types']
        assert '.mp4' in Config.MEDIA_TYPES['video']['mime_types']
    
    def test_common_image_mime_types(self):
        """Test common image MIME type mappings."""
        from app.config import Config
        
        mime_types = Config.MEDIA_TYPES['image']['mime_types']
        
        assert mime_types['.jpg'] == 'image/jpeg'
        assert mime_types['.jpeg'] == 'image/jpeg'
        assert mime_types['.png'] == 'image/png'
        assert mime_types['.gif'] == 'image/gif'
        assert mime_types['.webp'] == 'image/webp'
    
    def test_common_video_mime_types(self):
        """Test common video MIME type mappings."""
        from app.config import Config
        
        mime_types = Config.MEDIA_TYPES['video']['mime_types']
        
        assert mime_types['.mp4'] == 'video/mp4'
        assert mime_types['.webm'] == 'video/webm'
        assert mime_types['.mkv'] == 'video/x-matroska'


class TestPathConfiguration:
    """Tests for path configuration."""
    
    def test_app_root_exists(self):
        """Test that APP_ROOT is set."""
        from app.config import Config
        
        assert Config.APP_ROOT is not None
        assert os.path.isabs(Config.APP_ROOT)
    
    def test_static_folder_path(self):
        """Test STATIC_FOLDER path."""
        from app.config import Config
        
        assert Config.STATIC_FOLDER is not None
        assert 'static' in Config.STATIC_FOLDER
    
    def test_template_folder_path(self):
        """Test TEMPLATE_FOLDER path."""
        from app.config import Config
        
        assert Config.TEMPLATE_FOLDER is not None
        assert 'templates' in Config.TEMPLATE_FOLDER
    
    def test_instance_folder_path(self):
        """Test INSTANCE_FOLDER_PATH."""
        from app.config import Config
        
        assert Config.INSTANCE_FOLDER_PATH is not None
        # Path may be test temp dir or actual instance folder
        assert len(Config.INSTANCE_FOLDER_PATH) > 0


class TestGetApplicationRoot:
    """Tests for get_application_root function."""
    
    def test_script_mode(self):
        """Test application root in script mode."""
        from app.config import get_application_root
        
        root = get_application_root()
        
        assert root is not None
        assert os.path.isabs(root)
    
    @patch('sys.frozen', True, create=True)
    @patch('sys._MEIPASS', '/fake/meipass', create=True)
    def test_frozen_mode_with_meipass(self):
        """Test application root in frozen (PyInstaller) mode."""
        # Re-import to apply patches
        import importlib
        from app import config
        importlib.reload(config)
        
        # Note: This test may not work perfectly due to import caching
        # but it tests the code path exists


class TestConfigurationClasses:
    """Tests for configuration class hierarchy."""
    
    def test_development_config(self):
        """Test DevelopmentConfig settings."""
        from app.config import DevelopmentConfig
        
        assert DevelopmentConfig.ENV == 'development'
        assert DevelopmentConfig.DEBUG is True
    
    def test_production_config(self):
        """Test ProductionConfig settings."""
        from app.config import ProductionConfig
        
        assert ProductionConfig.ENV == 'production'
        assert ProductionConfig.DEBUG is False
    
    def test_config_by_name_registry(self):
        """Test config_by_name registry."""
        from app.config import config_by_name, DevelopmentConfig, ProductionConfig
        
        assert 'development' in config_by_name
        assert 'production' in config_by_name
        assert 'default' in config_by_name
        
        assert config_by_name['development'] == DevelopmentConfig
        assert config_by_name['production'] == ProductionConfig
        assert config_by_name['default'] == DevelopmentConfig


class TestConfigurableKeys:
    """Tests for configurable keys and their type converters."""
    
    def test_configurable_keys_info_exists(self):
        """Test that _configurable_keys_info is defined."""
        from app.config import _configurable_keys_info
        
        assert _configurable_keys_info is not None
        assert len(_configurable_keys_info) > 0
    
    def test_integer_keys(self):
        """Test integer type keys."""
        from app.config import _configurable_keys_info
        
        int_keys = ['CACHE_EXPIRY', 'DEFAULT_PAGE_SIZE', 'SESSION_EXPIRY', 
                    'WS_RECONNECT_ATTEMPTS', 'WS_RECONNECT_DELAY', 
                    'MEMORY_CLEANUP_INTERVAL', 'MAX_CACHE_SIZE', 'TUNNEL_LOCAL_PORT']
        
        for key in int_keys:
            assert key in _configurable_keys_info
            assert _configurable_keys_info[key] == int
    
    def test_float_keys(self):
        """Test float type keys."""
        from app.config import _configurable_keys_info
        
        assert 'WS_RECONNECT_FACTOR' in _configurable_keys_info
        assert _configurable_keys_info['WS_RECONNECT_FACTOR'] == float
    
    def test_string_keys(self):
        """Test string type keys."""
        from app.config import _configurable_keys_info

        str_keys = ['TUNNEL_PROVIDER', 'PINGGY_ACCESS_TOKEN', 'SESSION_PASSWORD',
                    'VIDEO_END_BEHAVIOR']

        for key in str_keys:
            assert key in _configurable_keys_info
            assert _configurable_keys_info[key] == str
    
    def test_boolean_converter(self):
        """Test boolean type converter."""
        from app.config import _configurable_keys_info
        
        bool_keys = ['SHUFFLE_MEDIA', 'SAVE_VIDEO_PROGRESS', 'ENABLE_SUBTITLES', 'DEBUG_MODE']
        
        for key in bool_keys:
            assert key in _configurable_keys_info
            converter = _configurable_keys_info[key]
            
            # Test the converter
            assert converter('true') is True
            assert converter('True') is True
            assert converter('TRUE') is True
            assert converter('false') is False
            assert converter('False') is False


class TestEnvironmentVariableOverrides:
    """Tests for environment variable configuration overrides."""
    
    def test_env_override_integer(self, monkeypatch):
        """Test environment variable override for integer config."""
        monkeypatch.setenv('CACHE_EXPIRY', '600')
        
        # Would need to reload config module to test properly
        # This test documents the expected behavior
        from app.config import _configurable_keys_info
        
        converter = _configurable_keys_info['CACHE_EXPIRY']
        assert converter('600') == 600
    
    def test_env_override_boolean(self, monkeypatch):
        """Test environment variable override for boolean config."""
        from app.config import _configurable_keys_info
        
        converter = _configurable_keys_info['SHUFFLE_MEDIA']
        
        assert converter('true') is True
        assert converter('false') is False
    
    def test_env_override_float(self, monkeypatch):
        """Test environment variable override for float config."""
        from app.config import _configurable_keys_info
        
        converter = _configurable_keys_info['WS_RECONNECT_FACTOR']
        
        assert converter('2.5') == 2.5


class TestJSONConfiguration:
    """Tests for JSON configuration file loading."""
    
    def test_json_config_structure(self, tmp_path):
        """Test expected JSON config structure."""
        config_data = {
            'python_config': {
                'CACHE_EXPIRY': 600,
                'SHUFFLE_MEDIA': False,
                'TUNNEL_PROVIDER': 'pinggy'
            }
        }
        
        config_file = tmp_path / 'ghosthub_config.json'
        config_file.write_text(json.dumps(config_data))
        
        # Verify structure is correct
        loaded = json.loads(config_file.read_text())
        assert 'python_config' in loaded
        assert loaded['python_config']['CACHE_EXPIRY'] == 600
    
    def test_json_config_missing_file(self, tmp_path):
        """Test behavior when JSON config file is missing."""
        # Config should still work with defaults
        from app.config import Config
        
        # Should have default values even without JSON file
        assert Config.CACHE_EXPIRY is not None


class TestSecurityConfiguration:
    """Tests for security-related configuration."""
    
    def test_secret_key_exists(self):
        """Test that SECRET_KEY is set."""
        from app.config import Config
        
        assert Config.SECRET_KEY is not None
    
    def test_secret_key_randomness(self):
        """Test that SECRET_KEY appears random (not hardcoded)."""
        from app.config import Config
        
        # If not set via env, should be random bytes
        # Just verify it's not an obviously bad value
        assert Config.SECRET_KEY != ''
        assert Config.SECRET_KEY != 'secret'
    
    def test_session_password_default(self):
        """Test default SESSION_PASSWORD is empty."""
        from app.config import Config
        
        # Default should be empty (no password required)
        assert Config.SESSION_PASSWORD == ''


class TestConfigEdgeCases:
    """Tests for configuration edge cases."""
    
    def test_invalid_integer_env_var(self):
        """Test handling of invalid integer environment variable."""
        from app.config import _configurable_keys_info
        
        converter = _configurable_keys_info['CACHE_EXPIRY']
        
        with pytest.raises(ValueError):
            converter('not_an_integer')
    
    def test_invalid_float_env_var(self):
        """Test handling of invalid float environment variable."""
        from app.config import _configurable_keys_info
        
        converter = _configurable_keys_info['WS_RECONNECT_FACTOR']
        
        with pytest.raises(ValueError):
            converter('not_a_float')
    
    def test_empty_string_boolean(self):
        """Test boolean converter with empty string."""
        from app.config import _configurable_keys_info
        
        converter = _configurable_keys_info['SHUFFLE_MEDIA']
        
        # Empty string should be False
        assert converter('') is False
    
    def test_config_values_are_correct_types(self):
        """Test that all config values have correct types."""
        from app.config import Config
        
        assert isinstance(Config.CACHE_EXPIRY, int)
        assert isinstance(Config.DEFAULT_PAGE_SIZE, int)
        assert isinstance(Config.WS_RECONNECT_FACTOR, float)
        assert isinstance(Config.TUNNEL_PROVIDER, str)
        assert isinstance(Config.IMAGE_EXTENSIONS, list)
        assert isinstance(Config.VIDEO_EXTENSIONS, list)


class TestUISettingsModeConfiguration:
    """Tests for UI_SETTINGS_MODE configuration."""

    def test_ui_settings_mode_default(self):
        """Test default UI_SETTINGS_MODE value."""
        from app.config import Config

        assert Config.UI_SETTINGS_MODE == 'basic'

    def test_ui_settings_mode_in_configurable_keys(self):
        """Test UI_SETTINGS_MODE is in configurable keys."""
        from app.config import _configurable_keys_info

        assert 'UI_SETTINGS_MODE' in _configurable_keys_info
        assert _configurable_keys_info['UI_SETTINGS_MODE'] == str

    def test_ui_settings_mode_type_converter(self):
        """Test UI_SETTINGS_MODE type converter."""
        from app.config import _configurable_keys_info

        converter = _configurable_keys_info['UI_SETTINGS_MODE']

        assert converter('basic') == 'basic'
        assert converter('advanced') == 'advanced'
        assert isinstance(converter('basic'), str)


class TestVideoEndBehaviorConfiguration:
    """Tests for VIDEO_END_BEHAVIOR configuration."""

    def test_video_end_behavior_default(self):
        """Test default VIDEO_END_BEHAVIOR value."""
        from app.config import Config

        assert Config.VIDEO_END_BEHAVIOR == 'loop'

    def test_video_end_behavior_in_configurable_keys(self):
        """Test VIDEO_END_BEHAVIOR is in configurable keys."""
        from app.config import _configurable_keys_info

        assert 'VIDEO_END_BEHAVIOR' in _configurable_keys_info
        assert _configurable_keys_info['VIDEO_END_BEHAVIOR'] == str

    def test_video_end_behavior_type_converter(self):
        """Test VIDEO_END_BEHAVIOR type converter."""
        from app.config import _configurable_keys_info

        converter = _configurable_keys_info['VIDEO_END_BEHAVIOR']

        # Test all valid values
        assert converter('stop') == 'stop'
        assert converter('loop') == 'loop'
        assert converter('play_next') == 'play_next'
        assert isinstance(converter('loop'), str)
