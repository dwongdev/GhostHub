"""
Tests for HdmiRuntimeService
Tests HDMI connection monitoring and cast-based kiosk power management.

Power management behavior:
- Kiosk starts when casting begins (not on HDMI connect)
- Kiosk stops after inactivity (idle duration + countdown)
- HDMI hotplug updates UI reactively but doesn't control kiosk
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess
import time


class TestHdmiRuntimeService:
    """Tests for HdmiRuntimeService class."""

    @pytest.fixture
    def hdmi_runtime_store(self):
        """Create a mock store for hdmi_runtime."""
        mock_store = MagicMock()
        mock_store.get.side_effect = lambda key: mock_store._state.get(key)
        mock_store.set.side_effect = lambda update: mock_store._state.update(update)
        mock_store.update.side_effect = lambda fn: fn(mock_store._state)
        mock_store._state = {
            'connected': False,
            'kiosk_running': False,
            'casting_active': False,
            'in_idle_mode': False,
            'in_shutdown_countdown': False,
            'shutdown_remaining': None,
            'pending_shutdown': False,
            'idle_greenlet': None,
            'countdown_greenlet': None
        }
        return mock_store

    @pytest.fixture
    def service(self, hdmi_runtime_store):
        """Create a fresh HdmiRuntimeService instance for testing."""
        from app.services.system.display.hdmi_runtime_service import HdmiRuntimeService
        from specter import registry
        
        service = HdmiRuntimeService()
        
        # Mock registry dependencies
        def mock_require(key):
            if key == 'hdmi_runtime':
                return hdmi_runtime_store
            if key == 'service_manager':
                return MagicMock(app=MagicMock())
            if key == 'tv_events':
                return MagicMock()
            raise KeyError(key)
            
        with patch('specter.registry.require', side_effect=mock_require):
            service.app = MagicMock()
            return service

    def test_initial_state(self, service, hdmi_runtime_store):
        """Test initial state of service via store."""
        from specter import registry
        with patch('specter.registry.require', return_value=hdmi_runtime_store):
            assert service.connected is False
            assert service.casting_active is False

    @patch('app.services.system.display.hdmi_runtime_service.check_hdmi_status')
    def test_check_status_connected(self, mock_check, service):
        """Test status check returns True when connected."""
        mock_check.return_value = True
        assert service.check_status() is True

    def test_handle_status_change_connected_emits_event(self, service, hdmi_runtime_store):
        """Test status change emits event but doesn't start kiosk."""
        from specter import registry
        tv_events = MagicMock()
        
        def mock_require(key):
            if key == 'hdmi_runtime': return hdmi_runtime_store
            if key == 'tv_events': return tv_events
            return MagicMock()

        with patch('specter.registry.require', side_effect=mock_require), \
             patch.object(service, '_start_kiosk') as mock_start:
            service._handle_status_change(True)
            # Kiosk should NOT be started on HDMI connect
            mock_start.assert_not_called()
            # tv_events should emit status
            tv_events.emit_hdmi_status.assert_called_once()

    def test_on_cast_start_starts_kiosk(self, service, hdmi_runtime_store):
        """Test that cast start triggers kiosk start."""
        from specter import registry
        
        def mock_require(key):
            if key == 'hdmi_runtime': return hdmi_runtime_store
            return MagicMock()

        with patch('specter.registry.require', side_effect=mock_require), \
             patch.object(service, 'check_status', return_value=True), \
             patch.object(service, '_start_kiosk', return_value=True) as mock_start:
             
            result = service.on_cast_start()
            
            assert result is True
            assert hdmi_runtime_store.get('casting_active') is True
            mock_start.assert_called_once()

    @patch('app.services.system.display.hdmi_runtime_service.start_idle_mode')
    def test_on_cast_stop_enters_idle_mode(self, mock_idle, service, hdmi_runtime_store):
        """Test that cast stop enters idle mode if HDMI connected."""
        from specter import registry
        hdmi_runtime_store.set({'casting_active': True, 'connected': True})
        
        def mock_require(key):
            if key == 'hdmi_runtime': return hdmi_runtime_store
            return MagicMock()

        with patch('specter.registry.require', side_effect=mock_require):
            service.on_cast_stop()
            
            assert hdmi_runtime_store.get('casting_active') is False
            mock_idle.assert_called_once()
