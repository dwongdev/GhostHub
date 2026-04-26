"""
Tests for Streaming Controllers (Chat and Sync)
Replaces legacy socket handler tests following the Specter migration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestChatController:
    """Tests for ChatController socket events."""

    @pytest.fixture
    def controller(self):
        from app.controllers.streaming.chat_controller import ChatController
        return ChatController()

    def test_build_events_registers_handlers(self, controller):
        """Test that ChatController registers expected socket events."""
        mock_handler = MagicMock()
        from app.constants import SOCKET_EVENTS as SE
        
        controller.build_events(mock_handler)
        
        # Verify specific events are registered
        mock_handler.on.assert_any_call(SE['JOIN_CHAT'], controller.handle_join_chat)
        mock_handler.on.assert_any_call(SE['CHAT_MESSAGE'], controller.handle_chat_message)
        mock_handler.on.assert_any_call(SE['COMMAND'], controller.handle_command)

    def test_handle_chat_message_logic(self, controller):
        """Test basic chat message handling logic."""
        from specter import registry
        mock_events = MagicMock()
        
        def mock_require(key):
            if key == 'chat_events': return mock_events
            return MagicMock()

        from app import create_app
        app = create_app('default')
        
        with patch('specter.registry.require', side_effect=mock_require), \
             app.test_request_context('/chat', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            
            # Manually set sid since test_request_context doesn't do it like SocketIO
            from flask import request
            request.sid = 'test_sid'
            
            with patch('app.controllers.streaming.chat_controller.get_request_session_id', return_value='test_session_id'):
                controller.handle_chat_message({'message': 'Hello World'})
                
                # Should emit message to room
                mock_events.emit_message.assert_called_once()
                args, _ = mock_events.emit_message.call_args
                assert args[0]['message'] == 'Hello World'
                assert args[0]['user_id'] == 'test_ses' # First 8 chars


class TestSyncController:
    """Tests for SyncController socket events."""

    @pytest.fixture
    def controller(self):
        from app.controllers.streaming.sync_controller import SyncController
        controller = SyncController()
        controller.store = MagicMock()
        return controller

    def test_build_events_registers_handlers(self, controller):
        """Test that SyncController registers expected socket events."""
        mock_handler = MagicMock()
        from app.constants import SOCKET_EVENTS as SE
        
        controller.build_events(mock_handler)
        
        mock_handler.on.assert_any_call(SE['JOIN_SYNC'], controller.handle_join_sync)
        mock_handler.on.assert_any_call(SE['PLAYBACK_SYNC'], controller.handle_playback_sync)
        mock_handler.on.assert_any_call(SE['UPDATE_MY_STATE'], controller.handle_socket_state_update)

    def test_handle_join_sync_requires_active(self, controller):
        """Test that JOIN_SYNC fails if sync is not enabled."""
        from specter import registry
        mock_events = MagicMock()
        
        def mock_require(key):
            if key == 'sync_events': return mock_events
            return MagicMock()

        controller.store.get.return_value = {'enabled': False}
        
        from app import create_app
        app = create_app('default')

        with patch('specter.registry.require', side_effect=mock_require), \
             app.test_request_context('/sync'):
            
            from flask import request
            request.sid = 'test_sid'
            
            result = controller.handle_join_sync()
            assert result['status'] == 'error'
            mock_events.emit_sync_error.assert_called_once()
