"""
System Stats Service
--------------------
Collects hardware metrics for Raspberry Pi monitoring.
Provides CPU, RAM, temperature, disk usage, and network stats.
"""
import os
import logging
import platform
import subprocess
import time
import psutil
from datetime import datetime, timezone

from app.services.system.platform_service import is_raspberry_pi
from app.services.system.system_stats_runtime_store import system_stats_runtime_store

logger = logging.getLogger(__name__)


def _system_stats_runtime_access(reader):
    """Read system-stats runtime state atomically."""
    return system_stats_runtime_store.access(reader)


def _update_system_stats_runtime(mutator):
    """Mutate system-stats runtime state atomically."""
    return system_stats_runtime_store.update(mutator)

def get_cpu_usage():
    """Get current CPU usage percentage (smoothed with EMA)."""
    current_time = time.time()
    cpu_state = _system_stats_runtime_access(lambda state: {
        'last_cpu_times': state.get('last_cpu_times'),
        'last_cpu_percent': state.get('last_cpu_percent', 0.0),
        'last_poll_time': state.get('last_poll_time', 0.0),
    })

    # Throttling: Return cached value if called too frequently (within 500ms)
    # to avoid the monitoring itself spiking the CPU
    if current_time - cpu_state['last_poll_time'] < 0.5:
        return cpu_state['last_cpu_percent']

    # Smoothing factor (Exponential Moving Average)
    # 0.5 means 50% last value + 50% new value
    # Lower = smoother/slower, Higher = more erratic/responsive
    ALPHA = 0.5

    usage_raw = None

    try:
        # Method 1: psutil
        usage_raw = psutil.cpu_percent(interval=None)
        if cpu_state['last_cpu_times'] is None and usage_raw == 0:
            # First call to psutil(None) always returns 0
            _update_system_stats_runtime(
                lambda state: state.update({'last_cpu_times': True})
            )
            return cpu_state['last_cpu_percent']
        cpu_state['last_cpu_times'] = True
    except Exception as e:
        logger.debug(f"psutil failed: {e}")

    # Method 2: /proc/stat fallback
    if usage_raw is None or usage_raw < 0:
        try:
            if os.path.exists('/proc/stat'):
                with open('/proc/stat', 'r') as f:
                    cpu_line = f.readline().split()
                
                fields = [int(x) for x in cpu_line[1:]]
                total = sum(fields)
                idle = fields[3] + (fields[4] if len(fields) > 4 else 0) 
                active = total - idle
                
                if isinstance(cpu_state['last_cpu_times'], tuple):
                    prev_total, prev_active = cpu_state['last_cpu_times']
                    diff_total = total - prev_total
                    diff_active = active - prev_active
                    
                    if diff_total > 0:
                        usage_raw = (diff_active / diff_total) * 100
                
                cpu_state['last_cpu_times'] = (total, active)
        except Exception as e:
            logger.debug(f"Error calculating CPU delta fallback: {e}")

    # Apply Smoothing (EMA)
    if usage_raw is not None:
        usage_raw = max(0.0, min(100.0, usage_raw))
        
        # If this is our first real reading, set it directly
        if cpu_state['last_cpu_percent'] == 0 and usage_raw > 0:
            cpu_state['last_cpu_percent'] = round(usage_raw, 1)
        else:
            # Formula: (1 - alpha) * last + alpha * current
            smoothed = ((1 - ALPHA) * cpu_state['last_cpu_percent']) + (ALPHA * usage_raw)
            cpu_state['last_cpu_percent'] = round(smoothed, 1)

        cpu_state['last_poll_time'] = current_time

    _update_system_stats_runtime(
        lambda state: state.update({
            'last_cpu_times': cpu_state['last_cpu_times'],
            'last_cpu_percent': cpu_state['last_cpu_percent'],
            'last_poll_time': cpu_state['last_poll_time'],
        })
    )
    return cpu_state['last_cpu_percent']


def get_cpu_count():
    """Get number of CPU cores."""
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def get_cpu_frequency():
    """Get current CPU frequency in MHz."""
    try:
        # Raspberry Pi specific
        if os.path.exists('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'):
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq', 'r') as f:
                freq_khz = int(f.read().strip())
                return round(freq_khz / 1000)  # Convert to MHz
    except Exception as e:
        logger.debug(f"Error getting CPU frequency: {e}")
    
    return None


def get_memory_info():
    """Get memory usage information."""
    try:
        if os.path.exists('/proc/meminfo'):
            meminfo = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]  # Get just the number
                        meminfo[key] = int(value)  # Values are in KB
            
            total = meminfo.get('MemTotal', 0)
            available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
            buffers = meminfo.get('Buffers', 0)
            cached = meminfo.get('Cached', 0)
            
            # Calculate used memory (excluding buffers/cache)
            used = total - available
            
            return {
                'total_mb': round(total / 1024),
                'used_mb': round(used / 1024),
                'available_mb': round(available / 1024),
                'buffers_mb': round(buffers / 1024),
                'cached_mb': round(cached / 1024),
                'percent': round((used / total) * 100, 1) if total > 0 else 0
            }
    except Exception as e:
        logger.debug(f"Error getting memory info: {e}")
    
    return None


def get_cpu_temperature():
    """Get CPU temperature in Celsius."""
    temp_paths = [
        '/sys/class/thermal/thermal_zone0/temp',  # Raspberry Pi
        '/sys/class/hwmon/hwmon0/temp1_input',    # Some Linux systems
    ]
    
    for path in temp_paths:
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    temp = int(f.read().strip())
                    # Temperature is in millidegrees Celsius
                    return round(temp / 1000, 1)
        except Exception as e:
            logger.debug(f"Error reading temperature from {path}: {e}")
    
    # Try vcgencmd for Raspberry Pi
    try:
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Output is like "temp=42.8'C"
            temp_str = result.stdout.strip()
            temp = float(temp_str.replace("temp=", "").replace("'C", ""))
            return round(temp, 1)
    except Exception as e:
        logger.debug(f"Error getting temperature from vcgencmd: {e}")
    
    return None


def get_gpu_memory():
    """Get GPU memory allocation (Raspberry Pi specific)."""
    try:
        result = subprocess.run(
            ['vcgencmd', 'get_mem', 'gpu'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Output is like "gpu=128M"
            mem_str = result.stdout.strip()
            mem = int(mem_str.replace("gpu=", "").replace("M", ""))
            return mem
    except Exception as e:
        logger.debug(f"Error getting GPU memory: {e}")
    
    return None


def get_disk_usage():
    """Get disk usage for main storage and mounted USB drives."""
    disks = []
    
    try:
        # Get main filesystem
        if os.path.exists('/'):
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            
            disks.append({
                'mount': '/',
                'device': 'root',
                'total_gb': round(total / (1024**3), 1),
                'used_gb': round(used / (1024**3), 1),
                'free_gb': round(free / (1024**3), 1),
                'percent': round((used / total) * 100, 1) if total > 0 else 0
            })
        
        # Check for USB drives on common mount points
        usb_mount_points = []
        for base_path in ['/media', '/mnt']:
            if os.path.exists(base_path):
                try:
                    for entry in os.scandir(base_path):
                        if entry.is_dir():
                            # Check subdirectories (e.g., /media/ghost/USBDRIVE)
                            try:
                                for sub in os.scandir(entry.path):
                                    if sub.is_dir():
                                        usb_mount_points.append(sub.path)
                            except PermissionError:
                                usb_mount_points.append(entry.path)
                except PermissionError:
                    pass
        
        for mount in usb_mount_points:
            try:
                stat = os.statvfs(mount)
                total = stat.f_blocks * stat.f_frsize
                if total > 0:  # Only include if it's a real filesystem
                    free = stat.f_bavail * stat.f_frsize
                    used = total - free
                    
                    disks.append({
                        'mount': mount,
                        'device': os.path.basename(mount),
                        'total_gb': round(total / (1024**3), 1),
                        'used_gb': round(used / (1024**3), 1),
                        'free_gb': round(free / (1024**3), 1),
                        'percent': round((used / total) * 100, 1)
                    })
            except Exception as e:
                logger.debug(f"Error getting disk usage for {mount}: {e}")
        
    except Exception as e:
        logger.debug(f"Error getting disk usage: {e}")
    
    return disks


def get_network_info():
    """Get network interface information using psutil (no subprocess per interface)."""
    interfaces = []

    try:
        # psutil provides both addresses and I/O stats in a single call each — no subprocess
        net_addrs = psutil.net_if_addrs()
        net_io = psutil.net_io_counters(pernic=True)

        import socket as _socket
        for iface, addrs in net_addrs.items():
            if iface == 'lo':
                continue  # Skip loopback

            ip = None
            for addr in addrs:
                if addr.family == _socket.AF_INET:
                    ip = addr.address
                    break

            io = net_io.get(iface)
            rx_bytes = io.bytes_recv if io else 0
            tx_bytes = io.bytes_sent if io else 0

            interfaces.append({
                'name': iface,
                'ip': ip,
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'rx_mb': round(rx_bytes / (1024 ** 2), 1),
                'tx_mb': round(tx_bytes / (1024 ** 2), 1),
            })
    except Exception as e:
        logger.debug(f"Error getting network info: {e}")

    return interfaces


def get_uptime():
    """Get system uptime."""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
    except Exception as e:
        logger.debug(f"Error getting uptime: {e}")
    
    return None


def get_load_average():
    """Get system load averages (1, 5, 15 min)."""
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
            return {
                '1min': float(parts[0]),
                '5min': float(parts[1]),
                '15min': float(parts[2])
            }
    except Exception as e:
        logger.debug(f"Error getting load average: {e}")
    
    return None


def get_pi_model():
    """Get Raspberry Pi model information."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return f.read().strip().replace('\x00', '')
    except OSError:
        pass
    
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Model'):
                    return line.split(':')[1].strip()
    except OSError:
        pass
    
    return None


def get_throttle_status():
    """Get throttling status (Raspberry Pi specific)."""
    try:
        result = subprocess.run(
            ['vcgencmd', 'get_throttled'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Output is like "throttled=0x0"
            hex_val = result.stdout.strip().split('=')[1]
            throttle_int = int(hex_val, 16)
            
            # Decode throttle flags
            return {
                'raw': hex_val,
                'under_voltage_now': bool(throttle_int & 0x1),
                'arm_freq_capped_now': bool(throttle_int & 0x2),
                'throttled_now': bool(throttle_int & 0x4),
                'soft_temp_limit_now': bool(throttle_int & 0x8),
                'under_voltage_occurred': bool(throttle_int & 0x10000),
                'arm_freq_capped_occurred': bool(throttle_int & 0x20000),
                'throttled_occurred': bool(throttle_int & 0x40000),
                'soft_temp_limit_occurred': bool(throttle_int & 0x80000)
            }
    except Exception as e:
        logger.debug(f"Error getting throttle status: {e}")
    
    return None


def get_hardware_tier():
    """
    Categorize hardware based on total RAM.
    Returns: 'LITE' (2GB-class), 'STANDARD' (4GB-class), 'PRO' (8GB-class)
    """
    mem = get_memory_info()
    if not mem:
        return 'LITE'
    
    total_mb = mem.get('total_mb', 0)
    
    # Use conservative thresholds to avoid misclassifying 4GB boards with
    # larger GPU splits / container overhead as LITE.
    if total_mb >= 6400:  # 8GB-class devices commonly report ~6.8-7.6GB usable
        return 'PRO'
    elif total_mb >= 2600:  # 4GB-class devices can report ~2.8-3.8GB usable
        return 'STANDARD'
    else:
        return 'LITE'


def get_all_stats():
    """Get all system statistics."""
    is_pi = is_raspberry_pi()
    
    stats = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'is_raspberry_pi': is_pi,
        'platform': platform.system(),
        'hostname': platform.node(),
        'cpu': {
            'usage_percent': get_cpu_usage(),
            'cores': get_cpu_count(),
            'frequency_mhz': get_cpu_frequency(),
            'temperature_c': get_cpu_temperature()
        },
        'memory': get_memory_info(),
        'disks': get_disk_usage(),
        'network': get_network_info(),
        'uptime': get_uptime(),
        'load_average': get_load_average()
    }
    
    # Add Pi-specific info
    if is_pi:
        stats['pi_model'] = get_pi_model()
        stats['gpu_memory_mb'] = get_gpu_memory()
        stats['throttle'] = get_throttle_status()
    
    return stats
