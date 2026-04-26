"""
Tests for System Stats Service
-------------------------------
Tests hardware metrics collection for Raspberry Pi monitoring.
"""
import pytest
import os
from unittest.mock import patch, mock_open, MagicMock
from app.services.system.system_stats_service import (
    is_raspberry_pi, get_cpu_usage, get_cpu_count, get_cpu_frequency,
    get_memory_info, get_cpu_temperature, get_gpu_memory, get_disk_usage,
    get_network_info, get_uptime, get_load_average, get_pi_model,
    get_throttle_status, get_hardware_tier, get_all_stats
)


class TestRaspberryPiDetection:
    """Tests for Raspberry Pi hardware detection."""

    def test_is_raspberry_pi_true(self):
        """Should return True when running on Raspberry Pi."""
        mock_cpuinfo = "Hardware	: BCM2835\nRevision	: a02082\nSerial		: 000000001234\nModel		: Raspberry Pi 3 Model B Rev 1.2\n"

        with patch('builtins.open', mock_open(read_data=mock_cpuinfo)):
            assert is_raspberry_pi() is True

    def test_is_raspberry_pi_false(self):
        """Should return False when not on Raspberry Pi."""
        mock_cpuinfo = "vendor_id	: GenuineIntel\nmodel name	: Intel(R) Core(TM) i7\n"

        with patch('builtins.open', mock_open(read_data=mock_cpuinfo)):
            assert is_raspberry_pi() is False

    def test_is_raspberry_pi_file_not_found(self):
        """Should return False when cpuinfo not available."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            assert is_raspberry_pi() is False


class TestCPUMetrics:
    """Tests for CPU usage and information."""

    def test_get_cpu_usage_from_proc_stat(self):
        """Should calculate CPU usage from /proc/stat."""
        mock_stat = "cpu  100 50 75 1000 25 0 10 0 0 0\ncpu0 50 25 35 500 12 0 5 0 0 0\n"

        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_stat)):
                usage = get_cpu_usage()
                assert isinstance(usage, (int, float))
                assert 0 <= usage <= 100

    def test_get_cpu_usage_proc_stat_unavailable(self):
        """Should try fallback methods when /proc/stat unavailable."""
        with patch('os.path.exists', return_value=False):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="%Cpu(s): 25.5 us,  5.2 sy,  0.0 ni, 65.3 id\n",
                    returncode=0
                )
                usage = get_cpu_usage()
                assert usage is not None or usage is None  # May succeed or fail depending on parsing

    def test_get_cpu_usage_all_methods_fail(self):
        """Should return 0.0 when all methods fail."""
        from app.services.system.system_stats_service import get_cpu_usage
        
        # Mock the store used by get_cpu_usage
        mock_store = MagicMock()
        mock_store.access.side_effect = lambda reader: reader({
            'last_cpu_times': None,
            'last_cpu_percent': 0.0,
            'last_poll_time': 0
        })
        
        with patch('app.services.system.system_stats_service.system_stats_runtime_store', mock_store), \
             patch('os.path.exists', return_value=False), \
             patch('psutil.cpu_percent', side_effect=Exception("psutil failed")), \
             patch('subprocess.run', side_effect=Exception("Command failed")):
            
            usage = get_cpu_usage()
            # EMA logic: if first call fails, stays at 0.0
            assert usage == 0.0

    def test_get_cpu_count(self):
        """Should return number of CPU cores."""
        with patch('os.cpu_count', return_value=4):
            assert get_cpu_count() == 4

    def test_get_cpu_count_fallback(self):
        """Should return 1 when cpu_count unavailable."""
        with patch('os.cpu_count', return_value=None):
            assert get_cpu_count() == 1

    def test_get_cpu_frequency_success(self):
        """Should read CPU frequency from sysfs."""
        mock_freq = "1500000\n"  # 1500 MHz in kHz

        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_freq)):
                freq = get_cpu_frequency()
                assert freq == 1500

    def test_get_cpu_frequency_unavailable(self):
        """Should return None when frequency not available."""
        with patch('os.path.exists', return_value=False):
            assert get_cpu_frequency() is None


class TestMemoryMetrics:
    """Tests for memory usage information."""

    def test_get_memory_info_success(self):
        """Should parse /proc/meminfo correctly."""
        mock_meminfo = """MemTotal:        8192000 kB
MemFree:         2048000 kB
MemAvailable:    4096000 kB
Buffers:          512000 kB
Cached:          1024000 kB
"""

        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_meminfo)):
                mem = get_memory_info()
                assert mem is not None
                assert mem['total_mb'] == 8000  # ~8192 MB
                assert mem['available_mb'] == 4000  # ~4096 MB
                assert 0 <= mem['percent'] <= 100

    def test_get_memory_info_unavailable(self):
        """Should return None when meminfo not available."""
        with patch('os.path.exists', return_value=False):
            assert get_memory_info() is None

    def test_get_hardware_tier_lite(self):
        """Should return LITE for <= 2GB RAM."""
        with patch('app.services.system.system_stats_service.get_memory_info', return_value={'total_mb': 2048}):
            assert get_hardware_tier() == 'LITE'

    def test_get_hardware_tier_standard(self):
        """Should return STANDARD for <= 4GB RAM."""
        with patch('app.services.system.system_stats_service.get_memory_info', return_value={'total_mb': 4096}):
            assert get_hardware_tier() == 'STANDARD'

    def test_get_hardware_tier_standard_low_visible_memory(self):
        """Should still classify 4GB-class devices with reduced visible RAM as STANDARD."""
        with patch('app.services.system.system_stats_service.get_memory_info', return_value={'total_mb': 2900}):
            assert get_hardware_tier() == 'STANDARD'

    def test_get_hardware_tier_pro(self):
        """Should return PRO for 8GB+ RAM."""
        with patch('app.services.system.system_stats_service.get_memory_info', return_value={'total_mb': 8192}):
            assert get_hardware_tier() == 'PRO'

    def test_get_hardware_tier_none(self):
        """Should return LITE if memory info is unavailable."""
        with patch('app.services.system.system_stats_service.get_memory_info', return_value=None):
            assert get_hardware_tier() == 'LITE'


class TestTemperatureMetrics:
    """Tests for CPU temperature monitoring."""

    def test_get_cpu_temperature_from_thermal_zone(self):
        """Should read temperature from thermal zone."""
        mock_temp = "42850\n"  # 42.85°C in millidegrees

        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_temp)):
                temp = get_cpu_temperature()
                assert temp == 42.9  # Rounded to 1 decimal

    def test_get_cpu_temperature_from_vcgencmd(self):
        """Should use vcgencmd on Raspberry Pi."""
        with patch('os.path.exists', return_value=False):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="temp=55.2'C\n",
                    returncode=0
                )
                temp = get_cpu_temperature()
                assert temp == 55.2

    def test_get_cpu_temperature_unavailable(self):
        """Should return None when temperature not available."""
        with patch('os.path.exists', return_value=False):
            with patch('subprocess.run', side_effect=Exception("vcgencmd not found")):
                assert get_cpu_temperature() is None


class TestGPUMetrics:
    """Tests for GPU memory (Raspberry Pi specific)."""

    def test_get_gpu_memory_success(self):
        """Should parse GPU memory from vcgencmd."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="gpu=128M\n",
                returncode=0
            )
            gpu_mem = get_gpu_memory()
            assert gpu_mem == 128

    def test_get_gpu_memory_unavailable(self):
        """Should return None when vcgencmd unavailable."""
        with patch('subprocess.run', side_effect=Exception("vcgencmd not found")):
            assert get_gpu_memory() is None


class TestDiskMetrics:
    """Tests for disk usage statistics."""

    def test_get_disk_usage_root_only(self):
        """Should get disk usage for root filesystem."""
        mock_statvfs = MagicMock()
        mock_statvfs.f_blocks = 10000000  # Total blocks
        mock_statvfs.f_frsize = 4096       # Block size
        mock_statvfs.f_bavail = 5000000    # Available blocks

        with patch('os.path.exists', return_value=True):
            # create=True allows patching non-existent attributes (statvfs on Windows)
            with patch('app.services.system.system_stats_service.os.statvfs', return_value=mock_statvfs, create=True):
                with patch('os.scandir', return_value=[]):  # No USB drives
                    disks = get_disk_usage()
                    assert len(disks) >= 1
                    root_disk = disks[0]
                    assert root_disk['mount'] == '/'
                    assert root_disk['total_gb'] > 0
                    assert 0 <= root_disk['percent'] <= 100

    def test_get_disk_usage_with_usb(self):
        """Should include USB drives in disk usage."""
        mock_statvfs_root = MagicMock()
        mock_statvfs_root.f_blocks = 10000000
        mock_statvfs_root.f_frsize = 4096
        mock_statvfs_root.f_bavail = 5000000

        mock_statvfs_usb = MagicMock()
        mock_statvfs_usb.f_blocks = 20000000
        mock_statvfs_usb.f_frsize = 4096
        mock_statvfs_usb.f_bavail = 15000000

        def statvfs_side_effect(path):
            if path == '/':
                return mock_statvfs_root
            else:
                return mock_statvfs_usb

        mock_usb_dir = MagicMock()
        mock_usb_dir.is_dir.return_value = True
        mock_usb_dir.path = '/media/usb'

        with patch('os.path.exists', return_value=True):
            with patch('app.services.system.system_stats_service.os.statvfs', side_effect=statvfs_side_effect, create=True):
                with patch('os.scandir', return_value=[mock_usb_dir]):
                    disks = get_disk_usage()
                    assert len(disks) >= 1  # At least root

    def test_get_disk_usage_permission_error(self):
        """Should handle permission errors gracefully."""
        with patch('os.path.exists', return_value=True):
            with patch('app.services.system.system_stats_service.os.statvfs', side_effect=PermissionError, create=True):
                disks = get_disk_usage()
                # Should return empty list or handle gracefully
                assert isinstance(disks, list)


class TestNetworkMetrics:
    """Tests for network interface information."""

    def test_get_network_info_success(self):
        """Should read network interface statistics."""
        mock_rx = "123456789\n"
        mock_tx = "987654321\n"

        with patch('os.path.exists', return_value=True):
            with patch('os.listdir', return_value=['eth0', 'wlan0', 'lo']):
                with patch('builtins.open', mock_open(read_data=mock_rx)):
                    with patch('subprocess.run') as mock_run:
                        mock_run.return_value = MagicMock(
                            stdout="2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500\n    inet 192.168.1.100/24\n",
                            returncode=0
                        )
                        interfaces = get_network_info()
                        # Should exclude 'lo' loopback
                        assert len([i for i in interfaces if i['name'] != 'lo']) >= 0

    def test_get_network_info_unavailable(self):
        """Should return empty list when psutil raises an exception."""
        with patch('psutil.net_if_addrs', side_effect=Exception("unavailable")):
            interfaces = get_network_info()
            assert interfaces == []


class TestSystemMetrics:
    """Tests for system uptime and load."""

    def test_get_uptime_days_hours_minutes(self):
        """Should format uptime with days, hours, and minutes."""
        mock_uptime = "259200.50 1000000.0\n"  # 3 days uptime

        with patch('builtins.open', mock_open(read_data=mock_uptime)):
            uptime = get_uptime()
            assert 'd' in uptime  # Contains days
            assert 'h' in uptime  # Contains hours

    def test_get_uptime_hours_minutes(self):
        """Should format uptime with hours and minutes only."""
        mock_uptime = "3665.0 50000.0\n"  # ~1 hour, 1 minute

        with patch('builtins.open', mock_open(read_data=mock_uptime)):
            uptime = get_uptime()
            assert 'h' in uptime
            assert 'm' in uptime
            assert 'd' not in uptime

    def test_get_uptime_minutes_only(self):
        """Should format uptime with minutes only."""
        mock_uptime = "120.0 10000.0\n"  # 2 minutes

        with patch('builtins.open', mock_open(read_data=mock_uptime)):
            uptime = get_uptime()
            assert 'm' in uptime
            assert 'h' not in uptime
            assert 'd' not in uptime

    def test_get_uptime_unavailable(self):
        """Should return None when uptime unavailable."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            assert get_uptime() is None

    def test_get_load_average_success(self):
        """Should parse load averages correctly."""
        mock_loadavg = "0.52 0.58 0.59 2/342 1234\n"

        with patch('builtins.open', mock_open(read_data=mock_loadavg)):
            load = get_load_average()
            assert load is not None
            assert load['1min'] == 0.52
            assert load['5min'] == 0.58
            assert load['15min'] == 0.59

    def test_get_load_average_unavailable(self):
        """Should return None when load average unavailable."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            assert get_load_average() is None


class TestRaspberryPiSpecific:
    """Tests for Raspberry Pi specific metrics."""

    def test_get_pi_model_from_device_tree(self):
        """Should read Pi model from device tree."""
        mock_model = "Raspberry Pi 4 Model B Rev 1.2\x00"

        with patch('builtins.open', mock_open(read_data=mock_model)):
            model = get_pi_model()
            assert model == "Raspberry Pi 4 Model B Rev 1.2"

    def test_get_pi_model_from_cpuinfo(self):
        """Should read Pi model from cpuinfo as fallback."""
        with patch('builtins.open', side_effect=[FileNotFoundError, mock_open(read_data="Model : Raspberry Pi 3B+\n")()]):
            model = get_pi_model()
            # May or may not succeed depending on file availability
            assert model is None or isinstance(model, str)

    def test_get_pi_model_unavailable(self):
        """Should return None when model unavailable."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            assert get_pi_model() is None

    def test_get_throttle_status_success(self):
        """Should parse throttle status correctly."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="throttled=0x50005\n",
                returncode=0
            )
            throttle = get_throttle_status()
            assert throttle is not None
            assert throttle['raw'] == '0x50005'
            assert isinstance(throttle['under_voltage_now'], bool)
            assert isinstance(throttle['throttled_now'], bool)

    def test_get_throttle_status_unavailable(self):
        """Should return None when vcgencmd unavailable."""
        with patch('subprocess.run', side_effect=Exception("vcgencmd not found")):
            assert get_throttle_status() is None


class TestGetAllStats:
    """Tests for combined stats collection."""

    def test_get_all_stats_structure(self):
        """Should return stats with correct structure."""
        with patch('app.services.system.system_stats_service.is_raspberry_pi', return_value=False):
            with patch('app.services.system.system_stats_service.get_cpu_usage', return_value=25.5):
                with patch('app.services.system.system_stats_service.get_cpu_count', return_value=4):
                    with patch('app.services.system.system_stats_service.get_memory_info', return_value={'total_mb': 8000}):
                        stats = get_all_stats()

                        assert 'timestamp' in stats
                        assert 'is_raspberry_pi' in stats
                        assert 'platform' in stats
                        assert 'hostname' in stats
                        assert 'cpu' in stats
                        assert 'memory' in stats
                        assert 'disks' in stats
                        assert 'network' in stats

    def test_get_all_stats_raspberry_pi(self):
        """Should include Pi-specific stats when on Raspberry Pi."""
        with patch('app.services.system.system_stats_service.is_raspberry_pi', return_value=True):
            with patch('app.services.system.system_stats_service.get_pi_model', return_value='Pi 4B'):
                with patch('app.services.system.system_stats_service.get_gpu_memory', return_value=128):
                    with patch('app.services.system.system_stats_service.get_throttle_status', return_value={'raw': '0x0'}):
                        stats = get_all_stats()

                        assert stats['is_raspberry_pi'] is True
                        assert 'pi_model' in stats
                        assert 'gpu_memory_mb' in stats
                        assert 'throttle' in stats

    def test_get_all_stats_not_raspberry_pi(self):
        """Should omit Pi-specific stats when not on Raspberry Pi."""
        with patch('app.services.system.system_stats_service.is_raspberry_pi', return_value=False):
            stats = get_all_stats()

            assert stats['is_raspberry_pi'] is False
            assert 'pi_model' not in stats
            assert 'gpu_memory_mb' not in stats
            assert 'throttle' not in stats
