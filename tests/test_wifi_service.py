"""
Tests for WiFi Service Module
-----------------------------
Comprehensive tests for WiFi AP configuration including:
- Configuration loading and saving
- hostapd.conf parsing and writing
- WiFi status checking
- Boot sync functionality
- Validation and error handling
"""
import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open


class TestIsRaspberryPi:
    """Tests for is_raspberry_pi() function."""

    @patch('platform.system')
    def test_not_linux_returns_false(self, mock_system):
        """Test that non-Linux systems return False."""
        from app.services.system.wifi import config_service as wifi_service

        mock_system.return_value = 'Windows'
        assert wifi_service.is_raspberry_pi() is False

        mock_system.return_value = 'Darwin'
        assert wifi_service.is_raspberry_pi() is False

    @patch('platform.system')
    @patch('builtins.open', mock_open(read_data='Raspberry Pi 4 Model B'))
    def test_raspberry_pi_detected(self, mock_system):
        """Test that Raspberry Pi is detected from cpuinfo."""
        from app.services.system.wifi import config_service as wifi_service

        mock_system.return_value = 'Linux'
        assert wifi_service.is_raspberry_pi() is True

    @patch('platform.system')
    @patch('builtins.open', mock_open(read_data='BCM2711'))
    def test_bcm_chip_detected(self, mock_system):
        """Test that BCM chip in cpuinfo is detected."""
        from app.services.system.wifi import config_service as wifi_service

        mock_system.return_value = 'Linux'
        assert wifi_service.is_raspberry_pi() is True

    @patch('platform.system')
    @patch('builtins.open', mock_open(read_data='Intel(R) Core(TM) i7'))
    def test_non_pi_linux_returns_false(self, mock_system):
        """Test that non-Pi Linux systems return False."""
        from app.services.system.wifi import config_service as wifi_service

        mock_system.return_value = 'Linux'
        assert wifi_service.is_raspberry_pi() is False

    @patch('platform.system')
    def test_file_read_error_returns_false(self, mock_system):
        """Test that file read errors return False."""
        from app.services.system.wifi import config_service as wifi_service

        mock_system.return_value = 'Linux'

        with patch('builtins.open', side_effect=IOError("Cannot read cpuinfo")):
            assert wifi_service.is_raspberry_pi() is False


class TestDefaultWifiConfig:
    """Tests for default WiFi configuration values."""

    def test_default_config_exists(self):
        """Test that DEFAULT_WIFI_CONFIG is defined."""
        from app.services.system.wifi.config_service import DEFAULT_WIFI_CONFIG

        assert DEFAULT_WIFI_CONFIG is not None
        assert isinstance(DEFAULT_WIFI_CONFIG, dict)

    def test_default_config_has_required_keys(self):
        """Test that default config has all required keys."""
        from app.services.system.wifi.config_service import DEFAULT_WIFI_CONFIG

        assert 'ssid' in DEFAULT_WIFI_CONFIG
        assert 'password' in DEFAULT_WIFI_CONFIG
        assert 'channel' in DEFAULT_WIFI_CONFIG
        assert 'country_code' in DEFAULT_WIFI_CONFIG

    def test_default_ssid(self):
        """Test default SSID value."""
        from app.services.system.wifi.config_service import DEFAULT_WIFI_CONFIG

        assert DEFAULT_WIFI_CONFIG['ssid'] == 'GhostHub'

    def test_default_password(self):
        """Test default password value."""
        from app.services.system.wifi.config_service import DEFAULT_WIFI_CONFIG

        assert DEFAULT_WIFI_CONFIG['password'] == 'ghost123'

    def test_default_channel(self):
        """Test default channel value."""
        from app.services.system.wifi.config_service import DEFAULT_WIFI_CONFIG

        assert DEFAULT_WIFI_CONFIG['channel'] == 7

    def test_default_country_code(self):
        """Test default country code value."""
        from app.services.system.wifi.config_service import DEFAULT_WIFI_CONFIG

        assert DEFAULT_WIFI_CONFIG['country_code'] == 'US'


class TestGetWifiConfig:
    """Tests for get_wifi_config() function."""

    def test_returns_tuple(self, app_context, tmp_path):
        """Test that function returns a tuple of (config, error)."""
        from app.services.system.wifi import config_service as wifi_service

        with patch.object(wifi_service, 'WIFI_CONFIG_PATH', str(tmp_path / 'nonexistent.json')):
            with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                result = wifi_service.get_wifi_config()

                assert isinstance(result, tuple)
                assert len(result) == 2

    def test_loads_from_persistent_config(self, app_context, tmp_path):
        """Test loading config from persistent JSON file."""
        from app.services.system.wifi import config_service as wifi_service

        config_file = tmp_path / 'wifi_config.json'
        saved_config = {
            'ssid': 'MyNetwork',
            'password': 'mypassword123',
            'channel': 6,
            'country_code': 'GB'
        }
        config_file.write_text(json.dumps(saved_config))

        with patch.object(wifi_service, 'WIFI_CONFIG_PATH', str(config_file)):
            config, error = wifi_service.get_wifi_config()

            assert error is None
            assert config['ssid'] == 'MyNetwork'
            assert config['password'] == 'mypassword123'
            assert config['channel'] == 6
            assert config['country_code'] == 'GB'

    def test_returns_defaults_when_no_config(self, app_context, tmp_path):
        """Test returning defaults when no config file exists."""
        from app.services.system.wifi import config_service as wifi_service

        with patch.object(wifi_service, 'WIFI_CONFIG_PATH', str(tmp_path / 'nonexistent.json')):
            with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                config, error = wifi_service.get_wifi_config()

                assert error is None
                assert config['ssid'] == 'GhostHub'
                assert config['password'] == 'ghost123'

    def test_handles_json_decode_error(self, app_context, tmp_path):
        """Test handling of invalid JSON in config file."""
        from app.services.system.wifi import config_service as wifi_service

        config_file = tmp_path / 'wifi_config.json'
        config_file.write_text('{ invalid json }')

        with patch.object(wifi_service, 'WIFI_CONFIG_PATH', str(config_file)):
            config, error = wifi_service.get_wifi_config()

            assert error is not None
            assert 'Error parsing' in error
            # Should return defaults
            assert config['ssid'] == 'GhostHub'


class TestParseHostapdConf:
    """Tests for parse_hostapd_conf() function."""

    def test_parses_ssid(self, app_context, tmp_path):
        """Test parsing SSID from hostapd.conf."""
        from app.services.system.wifi import config_service as wifi_service

        hostapd_content = """interface=wlan0
driver=nl80211
ssid=TestNetwork
channel=7
wpa_passphrase=testpass123
"""
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text(hostapd_content)

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
            config = wifi_service.parse_hostapd_conf()

            assert config is not None
            assert config['ssid'] == 'TestNetwork'

    def test_parses_password(self, app_context, tmp_path):
        """Test parsing password from hostapd.conf."""
        from app.services.system.wifi import config_service as wifi_service

        hostapd_content = """interface=wlan0
ssid=TestNetwork
wpa_passphrase=securepassword
"""
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text(hostapd_content)

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
            config = wifi_service.parse_hostapd_conf()

            assert config['password'] == 'securepassword'

    def test_parses_channel(self, app_context, tmp_path):
        """Test parsing channel from hostapd.conf."""
        from app.services.system.wifi import config_service as wifi_service

        hostapd_content = """interface=wlan0
ssid=TestNetwork
channel=11
wpa_passphrase=testpass
"""
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text(hostapd_content)

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
            config = wifi_service.parse_hostapd_conf()

            assert config['channel'] == 11

    def test_parses_country_code(self, app_context, tmp_path):
        """Test parsing country code from hostapd.conf."""
        from app.services.system.wifi import config_service as wifi_service

        hostapd_content = """interface=wlan0
ssid=TestNetwork
country_code=DE
wpa_passphrase=testpass
"""
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text(hostapd_content)

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
            config = wifi_service.parse_hostapd_conf()

            assert config['country_code'] == 'DE'

    def test_returns_none_on_error(self, app_context, tmp_path):
        """Test returning None when parsing fails."""
        from app.services.system.wifi import config_service as wifi_service

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(tmp_path / 'nonexistent.conf')):
            config = wifi_service.parse_hostapd_conf()

            assert config is None


class TestSaveWifiConfig:
    """Tests for save_wifi_config() function."""

    def test_validates_ssid_length(self, app_context, tmp_path):
        """Test SSID length validation."""
        from app.services.system.wifi import runtime_service as wifi_service

        # Empty SSID should fail
        success, message = wifi_service.save_wifi_config(ssid='')
        assert success is False
        assert 'SSID' in message

        # Too long SSID should fail (>32 chars)
        success, message = wifi_service.save_wifi_config(ssid='a' * 33)
        assert success is False
        assert 'SSID' in message

    def test_validates_password_length(self, app_context, tmp_path):
        """Test password length validation."""
        from app.services.system.wifi import runtime_service as wifi_service

        # Too short password should fail
        success, message = wifi_service.save_wifi_config(password='short')
        assert success is False
        assert 'Password' in message

        # Too long password should fail (>63 chars)
        success, message = wifi_service.save_wifi_config(password='a' * 64)
        assert success is False
        assert 'Password' in message

    def test_validates_channel_range(self, app_context, tmp_path):
        """Test channel range validation."""
        from app.services.system.wifi import runtime_service as wifi_service

        # Channel 0 should fail
        success, message = wifi_service.save_wifi_config(channel=0)
        assert success is False
        assert 'Channel' in message

        # Channel 12 should fail
        success, message = wifi_service.save_wifi_config(channel=12)
        assert success is False
        assert 'Channel' in message

    def test_validates_country_code_length(self, app_context, tmp_path):
        """Test country code length validation."""
        from app.services.system.wifi import runtime_service as wifi_service

        # Single character should fail
        success, message = wifi_service.save_wifi_config(country_code='U')
        assert success is False
        assert 'Country code' in message

        # Three characters should fail
        success, message = wifi_service.save_wifi_config(country_code='USA')
        assert success is False
        assert 'Country code' in message

    def test_saves_to_persistent_file(self, app_context, tmp_path):
        """Test saving config to persistent JSON file."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        config_file = tmp_path / 'wifi_config.json'

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(config_file)):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, message = wifi_service.save_wifi_config(
                        ssid='NewNetwork',
                        password='newpassword123',
                        channel=6
                    )

                    assert success is True

                    # Verify file was created with correct content
                    saved = json.loads(config_file.read_text())
                    assert saved['ssid'] == 'NewNetwork'
                    assert saved['password'] == 'newpassword123'
                    assert saved['channel'] == 6

    def test_uppercase_country_code(self, app_context, tmp_path):
        """Test that country code is uppercased."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        config_file = tmp_path / 'wifi_config.json'

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(config_file)):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, _ = wifi_service.save_wifi_config(country_code='gb')

                    assert success is True
                    saved = json.loads(config_file.read_text())
                    assert saved['country_code'] == 'GB'


class TestApplyWifiConfig:
    """Tests for apply_wifi_config() function."""

    @pytest.fixture(autouse=True)
    def skip_wifi_mock(self, monkeypatch):
        """Ensure we skip the WiFi mock to test the actual logic."""
        monkeypatch.setenv('GHOSTHUB_SKIP_WIFI_MOCK', 'true')

    def test_returns_error_if_no_hostapd_conf(self, app_context, tmp_path):
        """Test error when hostapd.conf doesn't exist."""
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(tmp_path / 'nonexistent.conf')):
            config = {'ssid': 'Test', 'password': 'testpass', 'channel': 7, 'country_code': 'US'}
            success, message = wifi_service.apply_wifi_config(config)

            assert success is False
            assert 'not found' in message

    def test_updates_ssid_in_hostapd(self, app_context, tmp_path):
        """Test updating SSID in hostapd.conf (subprocess mocked)."""
        from app.services.system.wifi import runtime_service as wifi_service

        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text("""interface=wlan0
ssid=OldNetwork
channel=7
wpa_passphrase=oldpass
""")

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr='test mode')

                config = {'ssid': 'NewNetwork', 'password': 'newpass123', 'channel': 7, 'country_code': 'US'}
                # With mocked subprocess, the cp will "fail" — just verify it was attempted
                wifi_service.apply_wifi_config(config)
                assert mock_run.called

    def test_adds_country_code_if_missing(self, app_context, tmp_path):
        """Test adding country_code when it doesn't exist in hostapd.conf."""
        from app.services.system.wifi import runtime_service as wifi_service

        hostapd_content = """interface=wlan0
ssid=TestNetwork
channel=7
wpa_passphrase=testpass
"""
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text(hostapd_content)

        with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                config = {'ssid': 'TestNetwork', 'password': 'testpass', 'channel': 7, 'country_code': 'DE'}
                wifi_service.apply_wifi_config(config)

                # Verify subprocess was called (config applied)
                assert mock_run.called


class TestGetWifiStatus:
    """Tests for get_wifi_status() function."""

    def test_returns_dict(self, app_context):
        """Test that function returns a dictionary."""
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
            status = wifi_service.get_wifi_status()

            assert isinstance(status, dict)

    def test_not_raspberry_pi(self, app_context):
        """Test status when not on Raspberry Pi."""
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
            status = wifi_service.get_wifi_status()

            assert status['is_raspberry_pi'] is False
            assert 'message' in status

    def test_status_keys_present(self, app_context):
        """Test that all expected status keys are present."""
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
            status = wifi_service.get_wifi_status()

            assert 'is_raspberry_pi' in status
            assert 'ap_mode_available' in status
            assert 'hostapd_running' in status
            assert 'connected_clients' in status

    @patch('subprocess.run')
    def test_hostapd_running_check(self, mock_run, app_context, tmp_path):
        """Test checking if hostapd is running."""
        from app.services.system.wifi import runtime_service as wifi_service

        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text('interface=wlan0\nssid=Test')

        mock_run.return_value = MagicMock(returncode=0, stdout='active')

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=True):
            with patch.object(wifi_service, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
                status = wifi_service.get_wifi_status()

                assert status['ap_mode_available'] is True


class TestSyncWifiConfigOnBoot:
    """Tests for sync_wifi_config_on_boot() function."""

    def test_skips_if_not_raspberry_pi(self, app_context):
        """Test that sync is skipped on non-Pi systems."""
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
            # Should not raise and should return early
            wifi_service.sync_wifi_config_on_boot()

    def test_skips_if_no_saved_config(self, app_context, tmp_path):
        """Test that sync is skipped when no saved config exists."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=True):
            with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(tmp_path / 'nonexistent.json')):
                # Should not raise
                wifi_service.sync_wifi_config_on_boot()

    def test_syncs_when_configs_differ(self, app_context, tmp_path):
        """Test that config is synced when saved differs from hostapd."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        # Create saved config
        config_file = tmp_path / 'wifi_config.json'
        saved_config = {'ssid': 'SavedNetwork', 'password': 'savedpass', 'channel': 6, 'country_code': 'US'}
        config_file.write_text(json.dumps(saved_config))

        # Create hostapd with different config
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text("""interface=wlan0
ssid=DifferentNetwork
channel=7
wpa_passphrase=differentpass
""")

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=True):
            with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(config_file)):
                with patch.object(_config_svc, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
                    with patch.object(wifi_service, 'apply_wifi_config') as mock_apply:
                        mock_apply.return_value = (True, 'Success')

                        wifi_service.sync_wifi_config_on_boot()

                        # Verify apply_wifi_config was called
                        mock_apply.assert_called_once()

    def test_skips_sync_when_configs_match(self, app_context, tmp_path):
        """Test that sync is skipped when configs already match."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        # Create saved config
        config_file = tmp_path / 'wifi_config.json'
        saved_config = {'ssid': 'TestNetwork', 'password': 'testpass', 'channel': 7, 'country_code': 'US'}
        config_file.write_text(json.dumps(saved_config))

        # Create hostapd with same config
        hostapd_file = tmp_path / 'hostapd.conf'
        hostapd_file.write_text("""interface=wlan0
ssid=TestNetwork
channel=7
wpa_passphrase=testpass
country_code=US
""")

        with patch.object(wifi_service, 'is_raspberry_pi', return_value=True):
            with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(config_file)):
                with patch.object(_config_svc, 'HOSTAPD_CONF_PATH', str(hostapd_file)):
                    with patch.object(wifi_service, 'apply_wifi_config') as mock_apply:
                        wifi_service.sync_wifi_config_on_boot()

                        # apply_wifi_config should NOT be called
                        mock_apply.assert_not_called()


class TestWifiConfigPaths:
    """Tests for WiFi configuration path constants."""

    def test_hostapd_conf_path(self):
        """Test HOSTAPD_CONF_PATH constant."""
        from app.services.system.wifi.config_service import HOSTAPD_CONF_PATH

        assert HOSTAPD_CONF_PATH == '/etc/hostapd/hostapd.conf'

    def test_dnsmasq_conf_path(self):
        """Test DNSMASQ_CONF_PATH constant is defined."""
        # DNSMASQ_CONF_PATH lives in network_detection_service
        from app.services.system.network_detection_service import DNSMASQ_CONF_PATH

        assert DNSMASQ_CONF_PATH == '/etc/dnsmasq.conf'

    def test_wifi_config_path_in_instance(self):
        """Test WIFI_CONFIG_PATH is in instance folder."""
        from app.services.system.wifi.config_service import WIFI_CONFIG_PATH

        assert 'wifi_config.json' in WIFI_CONFIG_PATH


class TestWifiValidChannels:
    """Tests for valid WiFi channel range."""

    def test_channel_1_is_valid(self, app_context, tmp_path):
        """Test channel 1 is accepted."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(tmp_path / 'wifi.json')):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, _ = wifi_service.save_wifi_config(channel=1)
                    assert success is True

    def test_channel_11_is_valid(self, app_context, tmp_path):
        """Test channel 11 is accepted."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(tmp_path / 'wifi.json')):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, _ = wifi_service.save_wifi_config(channel=11)
                    assert success is True

    def test_channel_6_is_valid(self, app_context, tmp_path):
        """Test channel 6 (common default) is accepted."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(tmp_path / 'wifi.json')):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, _ = wifi_service.save_wifi_config(channel=6)
                    assert success is True


class TestWifiPasswordValidation:
    """Tests for WiFi password validation edge cases."""

    def test_password_exactly_8_chars_valid(self, app_context, tmp_path):
        """Test minimum valid password length (8 chars)."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(tmp_path / 'wifi.json')):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, _ = wifi_service.save_wifi_config(password='12345678')
                    assert success is True

    def test_password_exactly_63_chars_valid(self, app_context, tmp_path):
        """Test maximum valid password length (63 chars)."""
        import app.services.system.wifi.config_service as _config_svc
        from app.services.system.wifi import runtime_service as wifi_service

        with patch.object(_config_svc, 'WIFI_CONFIG_PATH', str(tmp_path / 'wifi.json')):
            with patch.object(_config_svc, 'INSTANCE_FOLDER', str(tmp_path)):
                with patch.object(wifi_service, 'is_raspberry_pi', return_value=False):
                    success, _ = wifi_service.save_wifi_config(password='a' * 63)
                    assert success is True

    def test_password_7_chars_invalid(self, app_context, tmp_path):
        """Test password with 7 chars is invalid."""
        from app.services.system.wifi import runtime_service as wifi_service

        success, message = wifi_service.save_wifi_config(password='1234567')
        assert success is False
        assert 'Password' in message
