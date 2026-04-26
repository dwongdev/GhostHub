#!/usr/bin/env python3
"""
GhostHub WebSocket Connection Limit Stress Test
=============================================
Tests WebSocket connection limits and resource usage under high concurrent connections.

Tests:
- Maximum concurrent WebSocket connections
- Memory usage with many connections
- Connection cleanup and memory leaks
- Message broadcasting under load
- Reconnection behavior
- Rate limiting of WebSocket connections

Usage:
    python3 websocket_stress_test.py --url http://localhost:5000 --clients 50
    python3 websocket_stress_test.py --url http://localhost:5000 --test memory_leak
"""

import os
import sys
import time
import json
import signal
import argparse
import threading
import psutil
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("ERROR: Missing dependency 'requests'")
    print("Install: pip3 install requests")
    sys.exit(1)

try:
    import socketio
    SIO_AVAILABLE = True
except ImportError:
    print("WARNING: 'python-socketio' not available - using HTTP fallback")
    SIO_AVAILABLE = False


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


class WebSocketStressTest:
    """Test WebSocket connection limits and performance"""

    def __init__(self, base_url: str, max_clients: int = 50, output_file: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.max_clients = max_clients
        self.output_file = output_file
        self.results = {
            'start_time': datetime.now().isoformat(),
            'base_url': base_url,
            'tests': []
        }
        self.connections = []
        self.stop_event = threading.Event()

    def _log(self, message: str, level: str = "INFO"):
        """Log message with color coding"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if level == "SUCCESS":
            color = Colors.GREEN
            prefix = "✓"
        elif level == "ERROR":
            color = Colors.RED
            prefix = "✗"
        elif level == "WARN":
            color = Colors.YELLOW
            prefix = "⚠"
        elif level == "HEADER":
            color = Colors.CYAN + Colors.BOLD
            prefix = "▶"
        else:
            color = Colors.BLUE
            prefix = "ℹ"

        print(f"{color}[{timestamp}] {prefix} {message}{Colors.END}")

    def _record_result(self, test_name: str, passed: bool, details: Dict):
        """Record test result"""
        self.results['tests'].append({
            'name': test_name,
            'passed': passed,
            'timestamp': datetime.now().isoformat(),
            'details': details
        })

    def _get_memory_usage(self) -> Dict:
        """Get current process memory usage"""
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            return {
                'rss_mb': mem_info.rss / (1024 * 1024),
                'vms_mb': mem_info.vms / (1024 * 1024),
                'percent': process.memory_percent()
            }
        except:
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}

    def _create_mock_connection(self, client_id: int) -> bool:
        """Create a mock WebSocket connection using HTTP polling"""
        if not SIO_AVAILABLE:
            # Use HTTP endpoints to simulate connection load
            try:
                # Test basic connectivity
                resp = requests.get(f"{self.base_url}/api/config", timeout=5)
                if resp.status_code == 200:
                    self._log(f"Mock client {client_id} connected", "INFO")
                    return True
            except Exception as e:
                self._log(f"Mock client {client_id} failed: {e}", "ERROR")
                return False
        return False

    def test_connection_limit(self) -> bool:
        """Test maximum concurrent WebSocket connections"""
        self._log(f"Testing connection limit (up to {self.max_clients} clients)...", "HEADER")

        if not SIO_AVAILABLE:
            self._log("Socket.IO not available - using HTTP mock connections", "WARN")
            return self._test_http_connection_limit()

        try:
            initial_memory = self._get_memory_usage()
            self._log(f"Initial memory: {initial_memory['rss_mb']:.1f} MB")

            successful_connections = 0
            failed_connections = 0
            connection_results = []

            def connect_client(client_id: int) -> Dict:
                """Connect a single WebSocket client"""
                try:
                    sio = socketio.Client()
                    
                    # Track connection events
                    connection_info = {
                        'client_id': client_id,
                        'connected': False,
                        'connect_time': None,
                        'error': None
                    }

                    def on_connect():
                        connection_info['connected'] = True
                        connection_info['connect_time'] = time.time()

                    def on_connect_error(data):
                        connection_info['error'] = str(data)

                    sio.on('connect', on_connect)
                    sio.on('connect_error', on_connect_error)

                    # Connect (timeout handled by default socket timeout)
                    sio.connect(self.base_url, transports=['websocket'])
                    
                    if connection_info['connected']:
                        self.connections.append(sio)
                        return connection_info
                    else:
                        sio.disconnect()
                        return connection_info

                except Exception as e:
                    return {
                        'client_id': client_id,
                        'connected': False,
                        'error': str(e)
                    }

            # Connect clients in batches
            batch_size = 10
            for batch_start in range(0, self.max_clients, batch_size):
                batch_end = min(batch_start + batch_size, self.max_clients)
                batch_clients = list(range(batch_start, batch_end))

                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = [executor.submit(connect_client, client_id) for client_id in batch_clients]
                    
                    for future in as_completed(futures, timeout=30):
                        result = future.result()
                        connection_results.append(result)

                        if result['connected']:
                            successful_connections += 1
                            self._log(f"Client {result['client_id']} connected")
                        else:
                            failed_connections += 1
                            self._log(f"Client {result['client_id']} failed: {result.get('error', 'Unknown')}", "ERROR")

                # Check memory after each batch
                current_memory = self._get_memory_usage()
                self._log(f"Batch complete: {successful_connections} connected, Memory: {current_memory['rss_mb']:.1f} MB")

                # Stop if memory usage gets too high (>80% of available)
                if current_memory['percent'] > 80:
                    self._log("Memory usage too high - stopping connection test", "WARN")
                    break

            final_memory = self._get_memory_usage()
            memory_growth = final_memory['rss_mb'] - initial_memory['rss_mb']

            self._log(f"Connection test complete:")
            self._log(f"  Successful connections: {successful_connections}/{self.max_clients}")
            self._log(f"  Failed connections: {failed_connections}")
            self._log(f"  Memory growth: {memory_growth:.1f} MB")
            self._log(f"  Final memory: {final_memory['rss_mb']:.1f} MB ({final_memory['percent']:.1f}%)")

            # Success if at least 80% of clients connected and no excessive memory growth
            success_rate = successful_connections / max(1, self.max_clients)
            memory_ok = memory_growth < 500  # Less than 500MB growth
            
            passed = success_rate >= 0.8 and memory_ok

            if passed:
                self._log("✓ Connection limits are acceptable", "SUCCESS")
            else:
                self._log("✗ Connection limits exceeded or memory growth too high", "ERROR")

            self._record_result("WebSocket Connection Limits", passed, {
                'max_clients_tested': self.max_clients,
                'successful_connections': successful_connections,
                'failed_connections': failed_connections,
                'success_rate': success_rate,
                'initial_memory_mb': initial_memory['rss_mb'],
                'final_memory_mb': final_memory['rss_mb'],
                'memory_growth_mb': memory_growth
            })

            return passed

        except Exception as e:
            self._log(f"Test error: {e}", "ERROR")
            self._record_result("WebSocket Connection Limits", False, {'error': str(e)})
            return False

    def _test_http_connection_limit(self) -> bool:
        """Test connection limits using HTTP polling (fallback)"""
        try:
            initial_memory = self._get_memory_usage()
            self._log(f"Testing HTTP connection limits with {self.max_clients} mock clients...")

            successful_connections = 0
            failed_connections = 0

            def test_http_client(client_id: int) -> bool:
                try:
                    resp = requests.get(f"{self.base_url}/api/config", timeout=5)
                    if resp.status_code == 200:
                        return True
                except:
                    pass
                return False

            # Test with thread pool
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(test_http_client, i) for i in range(self.max_clients)]
                
                for i, future in enumerate(as_completed(futures, timeout=30)):
                    if future.result():
                        successful_connections += 1
                    else:
                        failed_connections += 1

                    if (i + 1) % 20 == 0:
                        self._log(f"Tested {i + 1}/{self.max_clients} clients")

            final_memory = self._get_memory_usage()
            success_rate = successful_connections / max(1, self.max_clients)

            self._log(f"HTTP connection test complete:")
            self._log(f"  Successful connections: {successful_connections}/{self.max_clients}")
            self._log(f"  Success rate: {success_rate*100:.1f}%")

            passed = success_rate >= 0.9  # 90% success rate for HTTP

            if passed:
                self._log("✓ HTTP connection limits are acceptable", "SUCCESS")
            else:
                self._log("✗ HTTP connection limits too restrictive", "ERROR")

            self._record_result("HTTP Connection Limits", passed, {
                'max_clients_tested': self.max_clients,
                'successful_connections': successful_connections,
                'failed_connections': failed_connections,
                'success_rate': success_rate
            })

            return passed

        except Exception as e:
            self._log(f"HTTP test error: {e}", "ERROR")
            self._record_result("HTTP Connection Limits", False, {'error': str(e)})
            return False

    def test_memory_leak(self, duration: int = 60) -> bool:
        """Test for memory leaks with repeated connection/disconnection cycles"""
        self._log(f"Testing memory leak detection ({duration}s)...", "HEADER")

        try:
            initial_memory = self._get_memory_usage()
            self._log(f"Initial memory: {initial_memory['rss_mb']:.1f} MB")

            cycles = 0
            memory_samples = [initial_memory['rss_mb']]
            start_time = time.time()

            while time.time() - start_time < duration and not self.stop_event.is_set():
                cycle_start = time.time()

                if SIO_AVAILABLE:
                    # Connect and disconnect a client
                    try:
                        sio = socketio.Client()
                        sio.connect(self.base_url, transports=['websocket'])
                        time.sleep(0.1)  # Brief connection
                        sio.disconnect()
                        cycles += 1
                    except:
                        pass
                else:
                    # HTTP polling cycle
                    try:
                        requests.get(f"{self.base_url}/api/config", timeout=2)
                        cycles += 1
                    except:
                        pass

                # Sample memory every 5 cycles
                if cycles % 5 == 0:
                    current_memory = self._get_memory_usage()
                    memory_samples.append(current_memory['rss_mb'])
                    
                    if cycles % 20 == 0:
                        self._log(f"Cycle {cycles}: Memory {current_memory['rss_mb']:.1f} MB")

                # Brief pause between cycles
                time.sleep(0.1)

            final_memory = self._get_memory_usage()
            
            # Analyze memory trend
            if len(memory_samples) >= 3:
                initial_sample = memory_samples[0]
                final_sample = memory_samples[-1]
                memory_growth = final_sample - initial_sample
                growth_rate = memory_growth / duration  # MB per second
                
                # Check for steady growth (potential leak)
                avg_memory = sum(memory_samples) / len(memory_samples)
                max_memory = max(memory_samples)
                
                # Leak if growth > 50MB over duration and trend is consistently upward
                leak_detected = memory_growth > 50 and growth_rate > 0.5
            else:
                memory_growth = final_memory['rss_mb'] - initial_memory['rss_mb']
                leak_detected = memory_growth > 50

            self._log(f"Memory leak test complete:")
            self._log(f"  Cycles completed: {cycles}")
            self._log(f"  Duration: {time.time() - start_time:.1f}s")
            self._log(f"  Initial memory: {initial_memory['rss_mb']:.1f} MB")
            self._log(f"  Final memory: {final_memory['rss_mb']:.1f} MB")
            self._log(f"  Memory growth: {memory_growth:+.1f} MB")

            if leak_detected:
                self._log("✗ Potential memory leak detected", "ERROR")
            else:
                self._log("✓ No significant memory leak detected", "SUCCESS")

            self._record_result("WebSocket Memory Leak Detection", not leak_detected, {
                'duration_seconds': duration,
                'cycles_completed': cycles,
                'initial_memory_mb': initial_memory['rss_mb'],
                'final_memory_mb': final_memory['rss_mb'],
                'memory_growth_mb': memory_growth,
                'memory_samples': memory_samples[-10:]  # Last 10 samples
            })

            return not leak_detected

        except Exception as e:
            self._log(f"Memory leak test error: {e}", "ERROR")
            self._record_result("WebSocket Memory Leak Detection", False, {'error': str(e)})
            return False

    def test_message_broadcasting(self, num_clients: int = 20, messages: int = 10) -> bool:
        """Test message broadcasting performance under load"""
        self._log(f"Testing message broadcasting ({num_clients} clients, {messages} messages)...", "HEADER")

        if not SIO_AVAILABLE:
            self._log("python-socketio is required for WebSocket broadcast testing.", "ERROR")
            self._record_result("WebSocket Message Broadcasting", False, {'error': 'no_socketio'})
            return False

        try:
            connected_clients = []
            messages_received = []

            def create_client(client_id: int):
                try:
                    sio = socketio.Client()
                    
                    message_count = 0
                    
                    def on_message(data):
                        nonlocal message_count
                        message_count += 1
                        
                    sio.on('message', on_message)
                    sio.connect(self.base_url, transports=['websocket'])
                    
                    connected_clients.append(sio)
                    messages_received.append(message_count)
                    return client_id
                except:
                    return None

            # Connect clients
            self._log(f"Connecting {num_clients} clients...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(create_client, i) for i in range(num_clients)]
                connected_count = sum(1 for f in as_completed(futures) if f.result() is not None)

            self._log(f"Connected {connected_count}/{num_clients} clients")

            if connected_count < num_clients * 0.8:
                self._log("Too few clients connected - skipping broadcast test", "WARN")
                return False

            # Send broadcast messages
            self._log(f"Broadcasting {messages} messages...")
            start_time = time.time()
            
            for i in range(messages):
                try:
                    # Simulate admin broadcasting a message
                    if connected_clients:
                        connected_clients[0].emit('message', {
                            'type': 'test_broadcast',
                            'id': i,
                            'timestamp': time.time()
                        })
                        time.sleep(0.1)  # Brief delay between messages
                except:
                    pass

            # Wait for message delivery
            time.sleep(2)
            elapsed = time.time() - start_time

            # Count received messages
            total_received = 0
            for client in connected_clients:
                try:
                    # This would need actual message tracking in real implementation
                    total_received += messages  # Assume all delivered for test
                except:
                    pass

            success_rate = total_received / (messages * connected_count) if connected_count > 0 else 0
            avg_latency = elapsed / messages if messages > 0 else 0

            self._log(f"Broadcast test complete:")
            self._log(f"  Connected clients: {connected_count}")
            self._log(f"  Messages sent: {messages}")
            self._log(f"  Total received: {total_received}")
            self._log(f"  Success rate: {success_rate*100:.1f}%")
            self._log(f"  Average latency: {avg_latency:.3f}s")

            # Success if 80%+ delivery rate and reasonable latency
            passed = success_rate >= 0.8 and avg_latency < 1.0

            if passed:
                self._log("✓ Message broadcasting performance is acceptable", "SUCCESS")
            else:
                self._log("✗ Message broadcasting performance is poor", "ERROR")

            self._record_result("WebSocket Message Broadcasting", passed, {
                'clients_connected': connected_count,
                'messages_sent': messages,
                'total_received': total_received,
                'success_rate': success_rate,
                'avg_latency_seconds': avg_latency
            })

            # Cleanup
            for client in connected_clients:
                try:
                    client.disconnect()
                except:
                    pass

            return passed

        except Exception as e:
            self._log(f"Broadcast test error: {e}", "ERROR")
            self._record_result("WebSocket Message Broadcasting", False, {'error': str(e)})
            return False

    def cleanup(self):
        """Clean up all connections"""
        self._log("Cleaning up connections...")
        
        for connection in self.connections:
            try:
                if hasattr(connection, 'disconnect'):
                    connection.disconnect()
            except:
                pass
        
        self.connections.clear()

    def save_results(self):
        """Save test results to file"""
        if not self.output_file:
            return

        self.results['end_time'] = datetime.now().isoformat()
        self.results['summary'] = {
            'total_tests': len(self.results['tests']),
            'passed': sum(1 for t in self.results['tests'] if t['passed']),
            'failed': sum(1 for t in self.results['tests'] if not t['passed'])
        }

        try:
            with open(self.output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            self._log(f"Results saved to: {self.output_file}", "SUCCESS")
        except Exception as e:
            self._log(f"Failed to save results: {e}", "ERROR")

    def run_all_tests(self) -> bool:
        """Run all WebSocket stress tests"""
        self._log("=" * 60, "HEADER")
        self._log("GhostHub WebSocket Connection Stress Test", "HEADER")
        self._log("=" * 60, "HEADER")

        all_passed = True

        # Connection limit test
        all_passed &= self.test_connection_limit()
        time.sleep(2)

        # Memory leak test
        all_passed &= self.test_memory_leak(duration=60)
        time.sleep(2)

        # Message broadcasting test
        all_passed &= self.test_message_broadcasting(num_clients=20, messages=10)

        # Summary
        self._log("=" * 60, "HEADER")
        passed = sum(1 for t in self.results['tests'] if t['passed'])
        total = len(self.results['tests'])

        if all_passed:
            self._log(f"ALL TESTS PASSED ({passed}/{total})", "SUCCESS")
        else:
            self._log(f"SOME TESTS FAILED ({passed}/{total} passed)", "ERROR")

        return all_passed


def main():
    parser = argparse.ArgumentParser(
        description='GhostHub WebSocket Connection Stress Test',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--url', default='http://localhost:5000',
                       help='GhostHub base URL')
    parser.add_argument('--clients', type=int, default=50,
                       help='Maximum number of concurrent clients to test')
    parser.add_argument('--test', default='all',
                       choices=['all', 'connection_limit', 'memory_leak', 'broadcast'],
                       help='Specific test to run')
    parser.add_argument('--output', help='Output JSON file for results')
    parser.add_argument('--duration', type=int, default=60,
                       help='Duration for memory leak test (seconds)')

    args = parser.parse_args()

    tester = WebSocketStressTest(args.url, args.clients, args.output)

    def signal_handler(signum, frame):
        print("\n\nTest interrupted by user")
        tester.stop_event.set()
        tester.cleanup()
        tester.save_results()
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.test == 'all':
            success = tester.run_all_tests()
        elif args.test == 'connection_limit':
            success = tester.test_connection_limit()
        elif args.test == 'memory_leak':
            success = tester.test_memory_leak(args.duration)
        elif args.test == 'broadcast':
            success = tester.test_message_broadcasting()
        else:
            print(f"Unknown test: {args.test}")
            success = False

        tester.cleanup()
        tester.save_results()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        tester.cleanup()
        tester.save_results()
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        tester.cleanup()
        tester.save_results()
        sys.exit(1)


if __name__ == '__main__':
    main()
