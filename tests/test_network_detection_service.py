"""
Tests for Network Detection Service
------------------------------------
Tests network interface detection, AP mode detection, and connection type classification.
"""
import pytest
import os
import subprocess
import socket
import psutil
from unittest.mock import patch, mock_open, MagicMock
from app.services.system.network_detection_service import (
    is_raspberry_pi,
    has_eth0_internet,
    wait_for_eth0,
    get_interface_ips,
    is_ap_mode_active,
    get_ap_subnet,
    ip_in_subnet,
    detect_interface_for_client,
    is_mobile_user_agent,
    is_tailscale_connection,
    get_client_connection_type,
    get_upload_settings,
    DEFAULT_AP_SUBNET,
    TAILSCALE_IP_RANGE,
)
from app.services.system.network_detection_runtime_store import network_detection_runtime_store
from app.config import Config


def clear_caches():
    network_detection_runtime_store.set({
        'interface_ips_cache': {
            'data': {},
            'timestamp': 0.0,
        },
        'tailscale_cache': {},
    })


class TestRaspberryPiDetection:
    """Tests for Raspberry Pi hardware detection."""

    def test_is_raspberry_pi_on_pi(self):
        """Should return True when /proc/cpuinfo contains Raspberry Pi."""
        cpuinfo_content = "Hardware\t: BCM2835\nRevision\t: a02082\nModel\t: Raspberry Pi 3 Model B Rev 1.2"
        with patch('builtins.open', mock_open(read_data=cpuinfo_content)):
            assert is_raspberry_pi() is True

    def test_is_raspberry_pi_with_bcm(self):
        """Should return True when /proc/cpuinfo contains BCM."""
        cpuinfo_content = "processor\t: 0\nmodel name\t: ARMv7 Processor rev 4 (v7l)\nBogoMIPS\t: 38.40\nFeatures\t: BCM2711"
        with patch('builtins.open', mock_open(read_data=cpuinfo_content)):
            assert is_raspberry_pi() is True

    def test_is_raspberry_pi_on_regular_pc(self):
        """Should return False on non-Pi hardware."""
        cpuinfo_content = "processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel Core i7"
        with patch('builtins.open', mock_open(read_data=cpuinfo_content)):
            assert is_raspberry_pi() is False

    def test_is_raspberry_pi_file_not_found(self):
        """Should return False when /proc/cpuinfo doesn't exist."""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            assert is_raspberry_pi() is False

    def test_is_raspberry_pi_permission_error(self):
        """Should return False when /proc/cpuinfo is not readable."""
        with patch('builtins.open', side_effect=PermissionError()):
            assert is_raspberry_pi() is False


class TestInterfaceIPDetection:
    """Tests for network interface IP address detection."""

    @patch('psutil.net_if_addrs')
    def test_get_interface_ips_eth0_and_wlan0(self, mock_net_if_addrs):
        """Should return IPs for eth0 and wlan0, exclude lo."""
        clear_caches()
        mock_net_if_addrs.return_value = {
            'eth0': [MagicMock(family=socket.AF_INET, address='192.168.1.100')],
            'wlan0': [MagicMock(family=socket.AF_INET, address='192.168.4.1')],
            'lo': [MagicMock(family=socket.AF_INET, address='127.0.0.1')]
        }

        result = get_interface_ips()

        assert result == {'eth0': '192.168.1.100', 'wlan0': '192.168.4.1'}
        assert 'lo' not in result

    @patch('psutil.net_if_addrs')
    def test_get_interface_ips_single_interface(self, mock_net_if_addrs):
        """Should handle single interface correctly."""
        clear_caches()
        mock_net_if_addrs.return_value = {
            'eth0': [MagicMock(family=socket.AF_INET, address='10.0.0.5')]
        }

        result = get_interface_ips()

        assert result == {'eth0': '10.0.0.5'}

    @patch('psutil.net_if_addrs')
    @patch('subprocess.run')
    @patch('os.path.exists', return_value=True)
    @patch('os.listdir', return_value=['eth0'])
    def test_get_interface_ips_fallback(self, mock_listdir, mock_exists, mock_run, mock_net_if_addrs):
        """Should fallback to subprocess if psutil fails."""
        clear_caches()
        mock_net_if_addrs.side_effect = Exception("psutil failed")
        mock_run.return_value = MagicMock(stdout="    inet 10.0.0.5/24 brd 10.0.0.255")

        result = get_interface_ips()

        assert result == {'eth0': '10.0.0.5'}

    @patch('psutil.net_if_addrs', return_value={})
    @patch('subprocess.run')
    @patch('os.path.exists', return_value=True)
    @patch('os.listdir', return_value=['eth0'])
    def test_get_interface_ips_no_inet_line(self, mock_listdir, mock_exists, mock_run, mock_net_if_addrs):
        """Should return empty dict when no inet line found in fallback."""
        clear_caches()
        mock_run.return_value = MagicMock(stdout="2: eth0: <NO-CARRIER,BROADCAST,MULTICAST,UP>")

        result = get_interface_ips()

        assert result == {}

    @patch('psutil.net_if_addrs', return_value={})
    @patch('os.path.exists', return_value=False)
    def test_get_interface_ips_no_sys_class_net(self, mock_exists, mock_net_if_addrs):
        """Should return empty dict when /sys/class/net doesn't exist in fallback."""
        clear_caches()
        result = get_interface_ips()
        assert result == {}

    @patch('psutil.net_if_addrs', return_value={})
    @patch('os.path.exists', return_value=True)
    @patch('os.listdir', return_value=['eth0'])
    @patch('subprocess.run', side_effect=subprocess.TimeoutExpired('ip', 5))
    def test_get_interface_ips_timeout(self, mock_run, mock_listdir, mock_exists, mock_net_if_addrs):
        """Should handle subprocess timeout gracefully in fallback."""
        clear_caches()
        result = get_interface_ips()
        assert result == {}

    @patch('psutil.net_if_addrs')
    def test_get_interface_ips_caching(self, mock_net_if_addrs):
        """Should cache results of get_interface_ips."""
        clear_caches()
        mock_net_if_addrs.return_value = {
            'eth0': [MagicMock(family=socket.AF_INET, address='192.168.1.100')]
        }

        # First call
        res1 = get_interface_ips()
        assert res1 == {'eth0': '192.168.1.100'}
        assert mock_net_if_addrs.call_count == 1

        # Second call within TTL
        res2 = get_interface_ips()
        assert res2 == {'eth0': '192.168.1.100'}
        assert mock_net_if_addrs.call_count == 1


class TestAPModeDetection:
    """Tests for WiFi Access Point mode detection."""

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('subprocess.run')
    def test_is_ap_mode_active_on_pi(self, mock_run, mock_is_pi):
        """Should return True when hostapd is active on Pi."""
        mock_run.return_value = MagicMock(stdout="active\n")
        assert is_ap_mode_active() is True

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('subprocess.run')
    def test_is_ap_mode_inactive_on_pi(self, mock_run, mock_is_pi):
        """Should return False when hostapd is inactive."""
        mock_run.return_value = MagicMock(stdout="inactive\n")
        assert is_ap_mode_active() is False

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=False)
    def test_is_ap_mode_not_on_pi(self, mock_is_pi):
        """Should return False when not on Raspberry Pi."""
        assert is_ap_mode_active() is False

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('subprocess.run', side_effect=Exception("Command not found"))
    def test_is_ap_mode_exception(self, mock_run, mock_is_pi):
        """Should return False when subprocess raises exception."""
        assert is_ap_mode_active() is False


class TestAPSubnetDetection:
    """Tests for AP subnet configuration detection."""

    @patch('os.path.exists', return_value=True)
    def test_get_ap_subnet_from_dnsmasq_config(self, mock_exists):
        """Should parse subnet from dnsmasq dhcp-range."""
        dnsmasq_content = "interface=wlan0\ndhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n"
        with patch('builtins.open', mock_open(read_data=dnsmasq_content)):
            result = get_ap_subnet()
            assert result == "192.168.4.0/24"

    @patch('os.path.exists', return_value=True)
    def test_get_ap_subnet_custom_range(self, mock_exists):
        """Should handle custom subnet ranges."""
        dnsmasq_content = "dhcp-range=10.0.0.50,10.0.0.150,255.255.255.0,12h\n"
        with patch('builtins.open', mock_open(read_data=dnsmasq_content)):
            result = get_ap_subnet()
            assert result == "10.0.0.0/24"

    @patch('os.path.exists', return_value=False)
    def test_get_ap_subnet_no_config_file(self, mock_exists):
        """Should return default subnet when config doesn't exist."""
        result = get_ap_subnet()
        assert result == DEFAULT_AP_SUBNET

    @patch('os.path.exists', return_value=True)
    def test_get_ap_subnet_no_dhcp_range(self, mock_exists):
        """Should return default when no dhcp-range found."""
        dnsmasq_content = "interface=wlan0\nlisten-address=192.168.4.1\n"
        with patch('builtins.open', mock_open(read_data=dnsmasq_content)):
            result = get_ap_subnet()
            assert result == DEFAULT_AP_SUBNET

    @patch('os.path.exists', return_value=True)
    def test_get_ap_subnet_read_error(self, mock_exists):
        """Should return default when file read fails."""
        with patch('builtins.open', side_effect=PermissionError()):
            result = get_ap_subnet()
            assert result == DEFAULT_AP_SUBNET


class TestSubnetChecking:
    """Tests for IP subnet membership checking."""

    def test_ip_in_subnet_valid_match(self):
        """Should return True for IP within subnet."""
        assert ip_in_subnet("192.168.4.10", "192.168.4.0/24") is True

    def test_ip_in_subnet_edge_case_first_ip(self):
        """Should include first usable IP in subnet."""
        assert ip_in_subnet("192.168.4.1", "192.168.4.0/24") is True

    def test_ip_in_subnet_edge_case_last_ip(self):
        """Should include last IP in subnet."""
        assert ip_in_subnet("192.168.4.254", "192.168.4.0/24") is True

    def test_ip_in_subnet_not_in_range(self):
        """Should return False for IP outside subnet."""
        assert ip_in_subnet("192.168.5.10", "192.168.4.0/24") is False

    def test_ip_in_subnet_different_network(self):
        """Should return False for completely different network."""
        assert ip_in_subnet("10.0.0.1", "192.168.4.0/24") is False

    def test_ip_in_subnet_invalid_ip(self):
        """Should return False for invalid IP."""
        assert ip_in_subnet("not.an.ip", "192.168.4.0/24") is False

    def test_ip_in_subnet_invalid_cidr(self):
        """Should return False for invalid CIDR."""
        assert ip_in_subnet("192.168.4.10", "invalid/cidr") is False


class TestClientInterfaceDetection:
    """Tests for detecting which interface a client is connected through."""

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_detect_interface_eth0(self, mock_get_ips):
        """Should detect client on eth0 network."""
        mock_get_ips.return_value = {'eth0': '192.168.1.100', 'wlan0': '192.168.4.1'}

        result = detect_interface_for_client('192.168.1.50')

        assert result == 'eth0'

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_detect_interface_wlan0(self, mock_get_ips):
        """Should detect client on wlan0 network."""
        mock_get_ips.return_value = {'eth0': '192.168.1.100', 'wlan0': '192.168.4.1'}

        result = detect_interface_for_client('192.168.4.15')

        assert result == 'wlan0'

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_detect_interface_unknown(self, mock_get_ips):
        """Should return None for unknown network."""
        mock_get_ips.return_value = {'eth0': '192.168.1.100'}

        result = detect_interface_for_client('10.0.0.50')

        assert result is None

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_detect_interface_no_interfaces(self, mock_get_ips):
        """Should return None when no interfaces found."""
        mock_get_ips.return_value = {}

        result = detect_interface_for_client('192.168.1.50')

        assert result is None


class TestMobileUserAgentDetection:
    """Tests for mobile device detection from user agent."""

    def test_is_mobile_android_phone(self):
        """Should detect Android mobile device."""
        ua = "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36"
        assert is_mobile_user_agent(ua) is True

    def test_is_mobile_iphone(self):
        """Should detect iPhone."""
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        assert is_mobile_user_agent(ua) is True

    def test_is_mobile_ipad(self):
        """Should detect iPad."""
        ua = "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X)"
        assert is_mobile_user_agent(ua) is True

    def test_is_mobile_windows_phone(self):
        """Should detect Windows Phone."""
        ua = "Mozilla/5.0 (Windows Phone 10.0; Android 6.0.1)"
        assert is_mobile_user_agent(ua) is True

    def test_is_mobile_desktop_chrome(self):
        """Should not detect desktop browser as mobile."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0"
        assert is_mobile_user_agent(ua) is False

    def test_is_mobile_desktop_firefox(self):
        """Should not detect desktop Firefox as mobile."""
        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
        assert is_mobile_user_agent(ua) is False

    def test_is_mobile_empty_user_agent(self):
        """Should return False for empty user agent."""
        assert is_mobile_user_agent("") is False

    def test_is_mobile_none_user_agent(self):
        """Should return False for None user agent."""
        assert is_mobile_user_agent(None) is False

    def test_is_mobile_case_insensitive(self):
        """Should detect mobile keywords case-insensitively."""
        ua = "MOBILE DEVICE TEST"
        assert is_mobile_user_agent(ua) is True


class TestTailscaleDetection:
    """Tests for Tailscale/Headscale connection detection."""

    def test_is_tailscale_cgnat_range_start(self):
        """Should detect IP at start of Tailscale CGNAT range (100.64.0.0/10)."""
        clear_caches()
        assert is_tailscale_connection('100.64.0.1') is True

    def test_is_tailscale_cgnat_range_mid(self):
        """Should detect IP in middle of Tailscale CGNAT range."""
        clear_caches()
        assert is_tailscale_connection('100.96.1.100') is True

    def test_is_tailscale_cgnat_range_end(self):
        """Should detect IP at end of Tailscale CGNAT range (100.127.255.255)."""
        clear_caches()
        assert is_tailscale_connection('100.127.255.255') is True

    def test_is_tailscale_outside_cgnat_range_below(self):
        """Should NOT detect IP below Tailscale CGNAT range (100.63.x.x)."""
        clear_caches()
        assert is_tailscale_connection('100.63.255.255') is False

    def test_is_tailscale_outside_cgnat_range_above(self):
        """Should NOT detect IP above Tailscale CGNAT range (100.128.x.x)."""
        clear_caches()
        assert is_tailscale_connection('100.128.0.1') is False

    def test_is_tailscale_regular_lan_ip(self):
        """Should NOT detect regular LAN IP as Tailscale."""
        clear_caches()
        assert is_tailscale_connection('192.168.1.100') is False

    def test_is_tailscale_localhost(self):
        """Should NOT detect localhost as Tailscale."""
        clear_caches()
        assert is_tailscale_connection('127.0.0.1') is False

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_is_tailscale_via_interface_name(self, mock_get_ips):
        """Should detect Tailscale via interface name (tailscale0)."""
        clear_caches()
        mock_get_ips.return_value = {'tailscale0': '100.64.0.5', 'eth0': '192.168.1.100'}

        assert is_tailscale_connection('100.64.0.10') is True

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_is_tailscale_via_headscale_interface(self, mock_get_ips):
        """Should detect Headscale via interface name (headscale0)."""
        clear_caches()
        mock_get_ips.return_value = {'headscale0': '100.65.0.1', 'eth0': '192.168.1.100'}

        assert is_tailscale_connection('100.65.0.50') is True

    @patch('app.services.system.network_detection_service.get_interface_ips')
    def test_is_tailscale_interface_different_subnet(self, mock_get_ips):
        """Should detect Tailscale interface even if client is in different /24."""
        clear_caches()
        mock_get_ips.return_value = {'tailscale0': '100.64.1.1'}

        # IP is in Tailscale CGNAT range, so should be detected
        assert is_tailscale_connection('100.64.2.100') is True

    def test_is_tailscale_invalid_ip(self):
        """Should handle invalid IP addresses gracefully."""
        # Should not raise exception, just return False
        clear_caches()
        assert is_tailscale_connection('not.an.ip') is False

    def test_is_tailscale_caching(self):
        """Should cache results of is_tailscale_connection."""
        clear_caches()
        with patch('app.services.system.network_detection_service.ip_in_subnet') as mock_subnet:
            mock_subnet.return_value = True

            # First call
            res1 = is_tailscale_connection('100.64.0.1')
            assert res1 is True
            assert mock_subnet.call_count == 1

            # Second call
            res2 = is_tailscale_connection('100.64.0.1')
            assert res2 is True
            assert mock_subnet.call_count == 1


class TestConnectionTypeDetection:
    """Tests for client connection type detection and upload settings."""

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value=None)
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=False)
    def test_get_client_connection_localhost(self, mock_ap, mock_detect, mock_is_pi):
        """Should detect localhost and use fast tier."""
        result = get_client_connection_type('127.0.0.1')

        assert result['interface'] == 'localhost'
        assert result['connection_type'] == 'local'
        assert result['tier'] == 'fast'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_FAST

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('app.services.system.network_detection_service.is_tailscale_connection', return_value=True)
    @patch('app.services.system.system_stats_service.get_hardware_tier', return_value='LITE')
    def test_get_client_connection_tailscale(self, mock_tier, mock_is_tailscale, mock_is_pi):
        """Should detect Tailscale and use Tailscale tier with small chunks."""
        result = get_client_connection_type('100.64.0.50')

        assert result['interface'] == 'tailscale'
        assert result['connection_type'] == 'tailscale'
        assert result['tier'] == 'tailscale'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_TAILSCALE
        # Should use moderate concurrency for Tailscale (based on base tier)
        assert result['max_concurrent_chunks'] == 2

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value='wlan0')
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=True)
    @patch('app.services.system.network_detection_service.get_ap_subnet', return_value='192.168.4.0/24')
    def test_get_client_connection_ap_mode_mobile(self, mock_subnet, mock_ap, mock_detect, mock_is_pi):
        """Should detect mobile on AP mode and use slow tier."""
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"

        result = get_client_connection_type('192.168.4.10', mobile_ua)

        assert result['connection_type'] == 'ap_mode'
        assert result['interface'] == 'wlan0'
        assert result['tier'] == 'slow'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_SLOW
        assert result['is_mobile'] is True

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value='wlan0')
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=True)
    @patch('app.services.system.network_detection_service.get_ap_subnet', return_value='192.168.4.0/24')
    def test_get_client_connection_ap_mode_desktop(self, mock_subnet, mock_ap, mock_detect, mock_is_pi):
        """Should detect desktop on AP mode and use medium tier."""
        desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"

        result = get_client_connection_type('192.168.4.10', desktop_ua)

        assert result['connection_type'] == 'ap_mode'
        assert result['tier'] == 'medium'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_MEDIUM

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value='eth0')
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=False)
    def test_get_client_connection_ethernet(self, mock_ap, mock_detect, mock_is_pi):
        """Should detect Ethernet connection and use fast tier."""
        result = get_client_connection_type('192.168.1.50')

        assert result['connection_type'] == 'ethernet'
        assert result['interface'] == 'eth0'
        assert result['tier'] == 'fast'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_FAST

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=True)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value='wlan1')
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=False)
    def test_get_client_connection_wifi_client(self, mock_ap, mock_detect, mock_is_pi):
        """Should detect WiFi client mode and use medium tier."""
        result = get_client_connection_type('192.168.1.50')

        assert result['connection_type'] == 'wifi_client'
        assert result['tier'] == 'medium'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_MEDIUM

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=False)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value=None)
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=False)
    def test_get_client_connection_unknown_mobile_fallback(self, mock_ap, mock_detect, mock_is_pi):
        """Should use mobile detection as fallback for unknown connections."""
        mobile_ua = "Mozilla/5.0 (Android; Mobile)"

        result = get_client_connection_type('10.0.0.50', mobile_ua)

        assert result['tier'] == 'slow'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_SLOW

    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=False)
    @patch('app.services.system.network_detection_service.detect_interface_for_client', return_value=None)
    @patch('app.services.system.network_detection_service.is_ap_mode_active', return_value=False)
    def test_get_client_connection_unknown_default(self, mock_ap, mock_detect, mock_is_pi):
        """Should use medium tier as default for unknown connections."""
        result = get_client_connection_type('10.0.0.50')

        assert result['tier'] == 'medium'
        assert result['chunk_size'] == Config.UPLOAD_CHUNK_SIZE_MEDIUM


class TestUploadSettings:
    """Tests for the upload settings entry point."""

    @patch('app.services.system.network_detection_service.get_client_connection_type')
    def test_get_upload_settings_returns_essential_fields(self, mock_get_conn):
        """Should return only essential upload configuration fields."""
        mock_get_conn.return_value = {
            'client_ip': '192.168.1.50',
            'interface': 'eth0',
            'connection_type': 'ethernet',
            'tier': 'fast',
            'chunk_size': 2097152,
            'max_concurrent_chunks': 4,
            'hardware_tier': 'STANDARD',
            'is_raspberry_pi': True,
            'is_mobile': False
        }

        result = get_upload_settings('192.168.1.50', 'Desktop User Agent')

        assert 'chunk_size' in result
        assert 'tier' in result
        assert 'connection_type' in result
        assert 'interface' in result
        assert 'max_concurrent_chunks' in result
        assert 'hardware_tier' in result
        assert result['chunk_size'] == 2097152
        assert result['tier'] == 'fast'
        assert result['max_concurrent_chunks'] == 4
        assert result['hardware_tier'] == 'STANDARD'

    @patch('app.services.system.network_detection_service.get_client_connection_type')
    def test_get_upload_settings_passes_user_agent(self, mock_get_conn):
        """Should pass user agent to connection detection."""
        mock_get_conn.return_value = {
            'chunk_size': 524288,
            'tier': 'slow',
            'connection_type': 'ap_mode',
            'interface': 'wlan0',
            'max_concurrent_chunks': 1,
            'hardware_tier': 'LITE'
        }

        user_agent = "Mozilla/5.0 (iPhone)"
        get_upload_settings('192.168.4.10', user_agent)

        mock_get_conn.assert_called_once_with('192.168.4.10', user_agent)


class TestEth0WaitFunction:
    """Tests for waiting for eth0 to be ready with internet connectivity."""

    @patch.dict(os.environ, {'GHOSTHUB_TESTING': 'false'}, clear=False)
    @patch('app.services.system.network_detection_service.has_eth0_internet', return_value=True)
    def test_wait_for_eth0_ready_immediately(self, mock_has_eth0):
        """Should return True immediately when eth0 is already ready."""
        result = wait_for_eth0(timeout=10)

        assert result is True
        mock_has_eth0.assert_called_once()

    @patch.dict(os.environ, {'GHOSTHUB_TESTING': 'false'}, clear=False)
    @patch('app.services.system.network_detection_service.gevent.sleep')
    @patch('app.services.system.network_detection_service.has_eth0_internet')
    def test_wait_for_eth0_ready_after_retries(self, mock_has_eth0, mock_sleep):
        """Should return True after a few retries when eth0 becomes ready."""
        # Simulate eth0 becoming ready after 3 attempts
        mock_has_eth0.side_effect = [False, False, True]

        result = wait_for_eth0(timeout=10)

        assert result is True
        assert mock_has_eth0.call_count == 3

    @patch.dict(os.environ, {'GHOSTHUB_TESTING': 'false'}, clear=False)
    @patch('time.time')
    @patch('app.services.system.network_detection_service.gevent.sleep')
    @patch('app.services.system.network_detection_service.has_eth0_internet', return_value=False)
    def test_wait_for_eth0_timeout(self, mock_has_eth0, mock_sleep, mock_time):
        """Should return False when timeout is reached."""
        # Simulate timeout by making time.time() increase
        # Provide plenty of values to avoid StopIteration
        mock_time.side_effect = [i for i in range(0, 200, 2)]

        result = wait_for_eth0(timeout=60)

        assert result is False

    @patch.dict(os.environ, {'GHOSTHUB_TESTING': 'false'}, clear=False)
    @patch('time.sleep')
    @patch('app.services.system.network_detection_service.has_eth0_internet')
    def test_wait_for_eth0_custom_timeout(self, mock_has_eth0, mock_sleep):
        """Should respect custom timeout parameter."""
        # eth0 never becomes ready, but should use provided timeout
        mock_has_eth0.return_value = False

        with patch('time.time', side_effect=[i for i in range(0, 200, 2)]), \
             patch('app.services.system.network_detection_service.gevent.sleep'):
            result = wait_for_eth0(timeout=30)

        assert result is False

    @patch.dict(os.environ, {'GHOSTHUB_TESTING': 'false'}, clear=False)
    @patch('app.services.system.network_detection_service.is_raspberry_pi', return_value=False)
    @patch('subprocess.run')
    def test_wait_for_eth0_non_pi_fallback(self, mock_run, mock_is_pi):
        """Should use general ping fallback on non-Pi systems."""
        # Non-Pi system should just check general connectivity
        mock_run.return_value = MagicMock(returncode=0)

        result = wait_for_eth0(timeout=10)

        assert result is True
        # Should call ping without eth0 binding
        mock_run.assert_called_with(['ping', '-c', '1', '-W', '2', '8.8.8.8'], capture_output=True, check=True)
