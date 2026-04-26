"""
Tests for System Utilities
Tests system-level operations.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import socket


class TestSystemUtils:
    """Tests for system_utils module."""
    
    def test_get_local_ip_success(self):
        """Test successful local IP detection."""
        from app.utils.system_utils import get_local_ip
        
        with patch('socket.socket') as mock_socket_class:
            mock_socket = Mock()
            mock_socket.getsockname.return_value = ('192.168.1.100', 0)
            mock_socket_class.return_value = mock_socket
            
            result = get_local_ip()
            
            assert result == '192.168.1.100'
            mock_socket.connect.assert_called_with(('8.8.8.8', 80))
            mock_socket.close.assert_called_once()
    
    def test_get_local_ip_fallback_to_hostname(self):
        """Test fallback to hostname method."""
        from app.utils.system_utils import get_local_ip
        
        with patch('socket.socket') as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect.side_effect = Exception("Connection failed")
            mock_socket_class.return_value = mock_socket
            
            with patch('socket.gethostname', return_value='myhost'):
                with patch('socket.gethostbyname', return_value='192.168.1.50'):
                    result = get_local_ip()
                    
                    assert result == '192.168.1.50'
    
    def test_get_local_ip_fallback_to_localhost(self):
        """Test fallback to localhost when all methods fail."""
        from app.utils.system_utils import get_local_ip
        
        with patch('socket.socket') as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect.side_effect = Exception("Connection failed")
            mock_socket_class.return_value = mock_socket
            
            with patch('socket.gethostname', side_effect=Exception("Hostname failed")):
                result = get_local_ip()
                
                assert result == '127.0.0.1'
    
    def test_get_local_ip_hostname_method_error(self):
        """Test handling of hostname method errors."""
        from app.utils.system_utils import get_local_ip
        
        with patch('socket.socket') as mock_socket_class:
            mock_socket = Mock()
            mock_socket.connect.side_effect = Exception("Connection failed")
            mock_socket_class.return_value = mock_socket
            
            with patch('socket.gethostname', return_value='myhost'):
                with patch('socket.gethostbyname', side_effect=Exception("DNS failed")):
                    result = get_local_ip()
                    
                    assert result == '127.0.0.1'
