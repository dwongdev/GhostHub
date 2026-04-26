#!/usr/bin/env python3
"""
GhostHub System Monitor Dashboard
---------------------------------
Real-time monitoring of CPU, RAM, temperature, disk I/O, and network throughput
specifically designed for Raspberry Pi 4 running GhostHub.

Logs data to CSV for post-test analysis and optionally displays live dashboard.
"""

import os
import sys
import time
import json
import argparse
import threading
import signal
from datetime import datetime
from pathlib import Path

# Optional: Check for psutil availability
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("WARNING: psutil not installed. Install with: pip install psutil")


class SystemMonitor:
    """Real-time system metrics collector for Raspberry Pi."""
    
    def __init__(self, output_dir: str = None, interval: float = 1.0):
        self.interval = interval
        self.running = False
        self.data_points = []
        self.start_time = None
        
        # Output directory for logs
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).parent / "results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Network baseline for delta calculation
        self.last_net_io = None
        self.last_disk_io = None
        self.last_sample_time = None
        
        # Pi-specific paths
        self.temp_path = "/sys/class/thermal/thermal_zone0/temp"
        self.is_pi = os.path.exists(self.temp_path)
        
    def get_cpu_temp(self) -> float:
        """Get CPU temperature (Raspberry Pi specific)."""
        try:
            if self.is_pi:
                with open(self.temp_path, 'r') as f:
                    temp_milli = int(f.read().strip())
                    return temp_milli / 1000.0
            elif HAS_PSUTIL:
                # Try psutil for other platforms
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current:
                                return entry.current
            return 0.0
        except Exception:
            return 0.0
    
    def get_cpu_freq(self) -> dict:
        """Get CPU frequency info."""
        try:
            if HAS_PSUTIL:
                freq = psutil.cpu_freq()
                if freq:
                    return {
                        'current': freq.current,
                        'min': freq.min,
                        'max': freq.max
                    }
        except Exception:
            pass
        return {'current': 0, 'min': 0, 'max': 0}
    
    def get_network_throughput(self) -> dict:
        """Calculate network throughput since last sample."""
        if not HAS_PSUTIL:
            return {'rx_bytes_sec': 0, 'tx_bytes_sec': 0, 'rx_total': 0, 'tx_total': 0}
        
        try:
            current = psutil.net_io_counters()
            current_time = time.time()
            
            result = {
                'rx_total': current.bytes_recv,
                'tx_total': current.bytes_sent,
                'rx_bytes_sec': 0,
                'tx_bytes_sec': 0
            }
            
            if self.last_net_io and self.last_sample_time:
                elapsed = current_time - self.last_sample_time
                if elapsed > 0:
                    result['rx_bytes_sec'] = (current.bytes_recv - self.last_net_io.bytes_recv) / elapsed
                    result['tx_bytes_sec'] = (current.bytes_sent - self.last_net_io.bytes_sent) / elapsed
            
            self.last_net_io = current
            return result
        except Exception:
            return {'rx_bytes_sec': 0, 'tx_bytes_sec': 0, 'rx_total': 0, 'tx_total': 0}
    
    def get_disk_io(self) -> dict:
        """Calculate disk I/O throughput since last sample."""
        if not HAS_PSUTIL:
            return {'read_bytes_sec': 0, 'write_bytes_sec': 0}
        
        try:
            current = psutil.disk_io_counters()
            current_time = time.time()
            
            result = {
                'read_bytes_sec': 0,
                'write_bytes_sec': 0,
                'read_total': current.read_bytes,
                'write_total': current.write_bytes
            }
            
            if self.last_disk_io and self.last_sample_time:
                elapsed = current_time - self.last_sample_time
                if elapsed > 0:
                    result['read_bytes_sec'] = (current.read_bytes - self.last_disk_io.read_bytes) / elapsed
                    result['write_bytes_sec'] = (current.write_bytes - self.last_disk_io.write_bytes) / elapsed
            
            self.last_disk_io = current
            return result
        except Exception:
            return {'read_bytes_sec': 0, 'write_bytes_sec': 0}
    
    def get_memory_info(self) -> dict:
        """Get detailed memory information."""
        if not HAS_PSUTIL:
            return {'total': 0, 'available': 0, 'used': 0, 'percent': 0, 'swap_percent': 0}
        
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                'total': mem.total,
                'available': mem.available,
                'used': mem.used,
                'percent': mem.percent,
                'swap_used': swap.used,
                'swap_percent': swap.percent
            }
        except Exception:
            return {'total': 0, 'available': 0, 'used': 0, 'percent': 0, 'swap_percent': 0}
    
    def get_load_average(self) -> tuple:
        """Get system load average (1, 5, 15 minutes)."""
        try:
            return os.getloadavg()
        except (OSError, AttributeError):
            # Windows doesn't have getloadavg
            if HAS_PSUTIL:
                return (psutil.cpu_percent() / 100, 0, 0)
            return (0, 0, 0)
    
    def get_ghosthub_processes(self) -> dict:
        """Get info about GhostHub-related processes."""
        if not HAS_PSUTIL:
            return {'count': 0, 'total_cpu': 0, 'total_mem': 0}
        
        try:
            result = {'count': 0, 'total_cpu': 0, 'total_mem': 0, 'processes': []}
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'ghosthub' in cmdline.lower() or 'gunicorn' in cmdline.lower() or 'flask' in cmdline.lower():
                        result['count'] += 1
                        result['total_cpu'] += proc.info['cpu_percent'] or 0
                        result['total_mem'] += proc.info['memory_percent'] or 0
                        result['processes'].append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cpu': proc.info['cpu_percent'],
                            'mem': proc.info['memory_percent']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return result
        except Exception:
            return {'count': 0, 'total_cpu': 0, 'total_mem': 0}
    
    def collect_sample(self) -> dict:
        """Collect a single sample of all metrics."""
        current_time = time.time()
        
        sample = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': current_time - self.start_time if self.start_time else 0,
            'cpu_percent': psutil.cpu_percent(interval=None) if HAS_PSUTIL else 0,
            'cpu_percent_per_core': psutil.cpu_percent(interval=None, percpu=True) if HAS_PSUTIL else [],
            'cpu_temp': self.get_cpu_temp(),
            'cpu_freq': self.get_cpu_freq(),
            'memory': self.get_memory_info(),
            'load_average': self.get_load_average(),
            'network': self.get_network_throughput(),
            'disk_io': self.get_disk_io(),
            'ghosthub_procs': self.get_ghosthub_processes()
        }
        
        self.last_sample_time = current_time
        return sample
    
    def format_bytes(self, bytes_val: float) -> str:
        """Format bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(bytes_val) < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}TB"
    
    def print_dashboard(self, sample: dict, clear: bool = True):
        """Print a live dashboard to the console."""
        if clear:
            # Clear screen (works on both Windows and Unix)
            os.system('cls' if os.name == 'nt' else 'clear')
        
        mem = sample['memory']
        net = sample['network']
        disk = sample['disk_io']
        load = sample['load_average']
        freq = sample['cpu_freq']
        gh = sample['ghosthub_procs']
        
        # Throttling indicator (Pi throttles at 80°C)
        temp = sample['cpu_temp']
        temp_status = "🔥 THROTTLING" if temp >= 80 else "⚠️  HIGH" if temp >= 70 else "✓ OK"
        
        print("=" * 70)
        print("  GhostHub System Monitor - Raspberry Pi 4 Stress Test Dashboard")
        print("=" * 70)
        print(f"  Time: {sample['timestamp']}  |  Elapsed: {sample['elapsed_seconds']:.1f}s")
        print("-" * 70)
        
        # CPU Section
        print("\n  📊 CPU")
        print(f"     Usage: {sample['cpu_percent']:5.1f}%  |  Temp: {temp:5.1f}°C [{temp_status}]")
        print(f"     Freq:  {freq['current']:.0f} MHz  |  Load: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}")
        
        if sample['cpu_percent_per_core']:
            cores = sample['cpu_percent_per_core']
            print(f"     Cores: {' | '.join(f'{c:5.1f}%' for c in cores)}")
        
        # Memory Section
        print("\n  💾 Memory")
        print(f"     Used:  {self.format_bytes(mem['used']):>8} / {self.format_bytes(mem['total'])} ({mem['percent']:.1f}%)")
        print(f"     Avail: {self.format_bytes(mem['available']):>8}  |  Swap: {mem.get('swap_percent', 0):.1f}%")
        
        # Network Section
        print("\n  🌐 Network")
        print(f"     RX: {self.format_bytes(net['rx_bytes_sec']):>10}/s  |  TX: {self.format_bytes(net['tx_bytes_sec']):>10}/s")
        print(f"     Total RX: {self.format_bytes(net['rx_total']):>10}  |  Total TX: {self.format_bytes(net['tx_total']):>10}")
        
        # Disk I/O Section
        print("\n  💽 Disk I/O")
        print(f"     Read:  {self.format_bytes(disk['read_bytes_sec']):>10}/s")
        print(f"     Write: {self.format_bytes(disk['write_bytes_sec']):>10}/s")
        
        # GhostHub Processes
        print("\n  👻 GhostHub Processes")
        print(f"     Count: {gh['count']}  |  CPU: {gh['total_cpu']:.1f}%  |  Mem: {gh['total_mem']:.1f}%")
        
        # Warnings
        warnings = []
        if temp >= 80:
            warnings.append("⚠️  CPU THROTTLING - Temperature critical!")
        if mem['percent'] >= 90:
            warnings.append("⚠️  MEMORY CRITICAL - >90% used!")
        elif mem['percent'] >= 80:
            warnings.append("⚠️  Memory warning - >80% used")
        if load[0] >= 4:  # 4 cores on Pi 4
            warnings.append("⚠️  HIGH LOAD - System may be overloaded")
        
        if warnings:
            print("\n  " + "-" * 66)
            for w in warnings:
                print(f"  {w}")
        
        print("\n" + "=" * 70)
        print("  Press Ctrl+C to stop monitoring")
    
    def save_results(self, test_name: str = "stress_test"):
        """Save collected data to CSV and JSON files."""
        if not self.data_points:
            print("No data to save.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{test_name}_{timestamp}"
        
        # Save JSON (full data)
        json_path = self.output_dir / f"{base_name}.json"
        with open(json_path, 'w') as f:
            json.dump({
                'test_name': test_name,
                'start_time': self.data_points[0]['timestamp'] if self.data_points else None,
                'end_time': self.data_points[-1]['timestamp'] if self.data_points else None,
                'sample_count': len(self.data_points),
                'interval_seconds': self.interval,
                'samples': self.data_points
            }, f, indent=2)
        print(f"Full data saved to: {json_path}")
        
        # Save CSV (simplified for analysis)
        csv_path = self.output_dir / f"{base_name}.csv"
        with open(csv_path, 'w') as f:
            headers = [
                'timestamp', 'elapsed_sec', 'cpu_percent', 'cpu_temp', 'cpu_freq',
                'mem_percent', 'mem_used_mb', 'swap_percent',
                'load_1m', 'load_5m', 'load_15m',
                'net_rx_mbps', 'net_tx_mbps',
                'disk_read_mbps', 'disk_write_mbps',
                'gh_proc_count', 'gh_cpu', 'gh_mem'
            ]
            f.write(','.join(headers) + '\n')
            
            for s in self.data_points:
                row = [
                    s['timestamp'],
                    f"{s['elapsed_seconds']:.1f}",
                    f"{s['cpu_percent']:.1f}",
                    f"{s['cpu_temp']:.1f}",
                    f"{s['cpu_freq']['current']:.0f}",
                    f"{s['memory']['percent']:.1f}",
                    f"{s['memory']['used'] / 1024 / 1024:.1f}",
                    f"{s['memory'].get('swap_percent', 0):.1f}",
                    f"{s['load_average'][0]:.2f}",
                    f"{s['load_average'][1]:.2f}",
                    f"{s['load_average'][2]:.2f}",
                    f"{s['network']['rx_bytes_sec'] / 1024 / 1024:.2f}",
                    f"{s['network']['tx_bytes_sec'] / 1024 / 1024:.2f}",
                    f"{s['disk_io']['read_bytes_sec'] / 1024 / 1024:.2f}",
                    f"{s['disk_io']['write_bytes_sec'] / 1024 / 1024:.2f}",
                    str(s['ghosthub_procs']['count']),
                    f"{s['ghosthub_procs']['total_cpu']:.1f}",
                    f"{s['ghosthub_procs']['total_mem']:.1f}"
                ]
                f.write(','.join(row) + '\n')
        
        print(f"CSV data saved to: {csv_path}")
        
        # Generate summary
        self.print_summary()
        return json_path, csv_path
    
    def print_summary(self):
        """Print a summary of collected metrics."""
        if not self.data_points:
            return
        
        cpu_vals = [s['cpu_percent'] for s in self.data_points]
        temp_vals = [s['cpu_temp'] for s in self.data_points]
        mem_vals = [s['memory']['percent'] for s in self.data_points]
        
        print("\n" + "=" * 70)
        print("  STRESS TEST SUMMARY")
        print("=" * 70)
        print(f"  Duration: {self.data_points[-1]['elapsed_seconds']:.1f} seconds")
        print(f"  Samples:  {len(self.data_points)}")
        print("-" * 70)
        print(f"  CPU Usage:    Min: {min(cpu_vals):5.1f}%  Max: {max(cpu_vals):5.1f}%  Avg: {sum(cpu_vals)/len(cpu_vals):5.1f}%")
        print(f"  CPU Temp:     Min: {min(temp_vals):5.1f}°C Max: {max(temp_vals):5.1f}°C Avg: {sum(temp_vals)/len(temp_vals):5.1f}°C")
        print(f"  Memory Usage: Min: {min(mem_vals):5.1f}%  Max: {max(mem_vals):5.1f}%  Avg: {sum(mem_vals)/len(mem_vals):5.1f}%")
        
        # Check for throttling events
        throttle_count = sum(1 for t in temp_vals if t >= 80)
        if throttle_count > 0:
            print(f"\n  ⚠️  THROTTLING DETECTED: {throttle_count} samples ({100*throttle_count/len(temp_vals):.1f}%) above 80°C")
        
        # Check for memory pressure
        mem_critical = sum(1 for m in mem_vals if m >= 90)
        if mem_critical > 0:
            print(f"  ⚠️  MEMORY CRITICAL: {mem_critical} samples ({100*mem_critical/len(mem_vals):.1f}%) above 90%")
        
        print("=" * 70)
    
    def run(self, duration: int = None, dashboard: bool = True, test_name: str = "stress_test"):
        """Run the monitoring loop."""
        self.running = True
        self.start_time = time.time()
        self.data_points = []
        
        # Initialize baseline measurements
        if HAS_PSUTIL:
            psutil.cpu_percent(interval=None)  # First call returns 0
        
        print(f"Starting system monitor (interval: {self.interval}s)")
        if duration:
            print(f"Will run for {duration} seconds")
        
        def signal_handler(sig, frame):
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                sample = self.collect_sample()
                self.data_points.append(sample)
                
                if dashboard:
                    self.print_dashboard(sample)
                
                # Check duration limit
                if duration and sample['elapsed_seconds'] >= duration:
                    print(f"\nDuration limit reached ({duration}s)")
                    break
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\nStopping monitor...")
        finally:
            self.running = False
            self.save_results(test_name)


def main():
    parser = argparse.ArgumentParser(description='GhostHub System Monitor Dashboard')
    parser.add_argument('-i', '--interval', type=float, default=1.0,
                        help='Sampling interval in seconds (default: 1.0)')
    parser.add_argument('-d', '--duration', type=int, default=None,
                        help='Duration to run in seconds (default: indefinite)')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Output directory for results (default: stress_tests/results)')
    parser.add_argument('-n', '--name', type=str, default='stress_test',
                        help='Test name for output files (default: stress_test)')
    parser.add_argument('--no-dashboard', action='store_true',
                        help='Disable live dashboard output')
    
    args = parser.parse_args()
    
    if not HAS_PSUTIL:
        print("ERROR: psutil is required. Install with: pip install psutil")
        sys.exit(1)
    
    monitor = SystemMonitor(output_dir=args.output, interval=args.interval)
    monitor.run(duration=args.duration, dashboard=not args.no_dashboard, test_name=args.name)


if __name__ == '__main__':
    main()
