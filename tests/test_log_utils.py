"""
Tests for Log Utilities
Tests log obfuscation functionality.
"""
import pytest
import logging


class TestLogObfuscationFilter:
    """Tests for LogObfuscationFilter class."""
    
    @pytest.fixture
    def log_filter(self):
        """Create a log filter instance."""
        from app.utils.log_utils import LogObfuscationFilter
        return LogObfuscationFilter()
    
    def test_obfuscates_windows_path(self, log_filter):
        """Test obfuscation of Windows file paths."""
        text = "Loading file from C:\\Users\\admin\\Documents\\file.txt"
        result = log_filter._obfuscate_paths_and_filenames(text)
        
        assert 'C:\\Users' not in result
        assert '[PATH_REDACTED]' in result or '[FILENAME_REDACTED]' in result
    
    def test_obfuscates_unix_path(self, log_filter):
        """Test obfuscation of Unix file paths."""
        text = "Loading file from /home/user/documents/file.txt"
        result = log_filter._obfuscate_paths_and_filenames(text)
        
        assert '/home/user' not in result
    
    def test_obfuscates_url_paths(self, log_filter):
        """Test obfuscation of URL paths."""
        text = "Request to /api/media/category/file.mp4?quality=hd"
        result = log_filter._obfuscate_paths_and_filenames(text)
        
        assert '/api/media/category' not in result
    
    def test_obfuscates_filenames(self, log_filter):
        """Test obfuscation of standalone filenames."""
        text = "Processing document.pdf"
        result = log_filter._obfuscate_paths_and_filenames(text)
        
        assert 'document.pdf' not in result
    
    def test_filter_returns_true(self, log_filter):
        """Test that filter method returns True."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        result = log_filter.filter(record)
        
        assert result is True
    
    def test_filter_processes_log_record(self, log_filter):
        """Test that filter processes log record message."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Loading /home/user/file.txt',
            args=(),
            exc_info=None
        )
        
        log_filter.filter(record)
        
        assert '/home/user' not in record.msg
    
    def test_filter_processes_args(self, log_filter):
        """Test that filter processes log record args."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Loading %s',
            args=('/home/user/file.txt',),
            exc_info=None
        )
        
        log_filter.filter(record)
        
        assert '/home/user' not in str(record.args)
    
    def test_chat_message_redaction(self, log_filter):
        """Test that chat messages are redacted."""
        record = logging.LogRecord(
            name='app.controllers.streaming.chat_controller',
            level=logging.INFO,
            pathname='chat_controller.py',
            lineno=1,
            msg='Hello everyone!',
            args=(),
            exc_info=None
        )
        
        log_filter.filter(record)
        
        assert record.msg == '[CHAT_MESSAGE_REDACTED]'
    
    def test_non_string_not_processed(self, log_filter):
        """Test that non-string values are not processed."""
        result = log_filter._obfuscate_paths_and_filenames(12345)
        
        assert result == 12345
    
    def test_replacement_strings(self, log_filter):
        """Test replacement string values."""
        assert log_filter.path_replacement == "[PATH_REDACTED]"
        assert log_filter.filename_replacement == "[FILENAME_REDACTED]"
        assert log_filter.url_path_replacement == "[URL_REDACTED]"
        assert log_filter.chat_replacement == "[CHAT_MESSAGE_REDACTED]"
