#!/usr/bin/env python3
"""
GhostHub Worst Case Scenario Test
---------------------------------
Runs all stress tests simultaneously to find the breaking point of
GhostHub on Raspberry Pi 4 (2GB RAM).

This test combines:
- Chunked file uploads
- Multiple video streams
- WebSocket spam
- Sync mode navigation
- Thumbnail generation
- API endpoint hammering
- TV casting cycles

Monitors system health and can auto-throttle or abort if critical.
"""

import os
import sys
import time
import json
import signal
import argparse
import threading
import concurrent.futures
import tempfile
import mmap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("ERROR: requests required. Install: pip install requests")
    sys.exit(1)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import socketio
    HAS_SOCKETIO = True
except ImportError:
    HAS_SOCKETIO = False


def print_dependency_status():
    """Print status of optional dependencies."""
    print("\n  📦 Dependencies:")
    print(f"     requests: ✓ installed")
    print(f"     psutil:   {'✓ installed' if HAS_PSUTIL else '⚠ not installed (limited monitoring)'}")
    print(f"     socketio: {'✓ installed' if HAS_SOCKETIO else '⚠ not installed (WebSocket tests skipped)'}")
    if not HAS_SOCKETIO:
        print("     └─ Install with: pip install python-socketio[client]")


@dataclass
class HealthMetrics:
    """System health metrics for monitoring."""
    cpu_percent: float = 0
    memory_percent: float = 0
    cpu_temp: float = 0
    is_throttling: bool = False
    is_critical: bool = False


class HealthMonitor:
    """Monitors system health during stress test."""
    
    THROTTLE_TEMP = 80.0
    CRITICAL_MEMORY = 95.0
    CRITICAL_TEMP = 85.0
    
    def __init__(self):
        self.metrics = HealthMetrics()
        self.running = False
        self.history = []
        self.callbacks = []
        self._lock = threading.Lock()
        self.temp_path = "/sys/class/thermal/thermal_zone0/temp"
    
    def get_cpu_temp(self) -> float:
        """Get CPU temperature."""
        try:
            if os.path.exists(self.temp_path):
                with open(self.temp_path, 'r') as f:
                    return int(f.read().strip()) / 1000.0
        except:
            pass
        return 0.0
    
    def check_health(self) -> HealthMetrics:
        """Collect current health metrics."""
        metrics = HealthMetrics()
        
        if HAS_PSUTIL:
            metrics.cpu_percent = psutil.cpu_percent(interval=None)
            metrics.memory_percent = psutil.virtual_memory().percent
        
        metrics.cpu_temp = self.get_cpu_temp()
        metrics.is_throttling = metrics.cpu_temp >= self.THROTTLE_TEMP
        metrics.is_critical = (
            metrics.cpu_temp >= self.CRITICAL_TEMP or
            metrics.memory_percent >= self.CRITICAL_MEMORY
        )
        
        return metrics
    
    def register_callback(self, callback):
        """Register callback for critical conditions."""
        self.callbacks.append(callback)
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            metrics = self.check_health()
            
            with self._lock:
                self.metrics = metrics
                self.history.append({
                    'timestamp': datetime.now().isoformat(),
                    'cpu': metrics.cpu_percent,
                    'mem': metrics.memory_percent,
                    'temp': metrics.cpu_temp
                })
            
            # Trigger callbacks on critical
            if metrics.is_critical:
                for cb in self.callbacks:
                    try:
                        cb(metrics)
                    except:
                        pass
            
            time.sleep(1)
    
    def start(self):
        """Start background monitoring."""
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        if hasattr(self, '_thread'):
            self._thread.join(timeout=2)
    
    def get_summary(self) -> Dict:
        """Get summary of collected metrics."""
        if not self.history:
            return {}
        
        cpu_vals = [h['cpu'] for h in self.history]
        mem_vals = [h['mem'] for h in self.history]
        temp_vals = [h['temp'] for h in self.history]
        
        return {
            'samples': len(self.history),
            'cpu': {
                'min': min(cpu_vals),
                'max': max(cpu_vals),
                'avg': sum(cpu_vals) / len(cpu_vals)
            },
            'memory': {
                'min': min(mem_vals),
                'max': max(mem_vals),
                'avg': sum(mem_vals) / len(mem_vals)
            },
            'temperature': {
                'min': min(temp_vals),
                'max': max(temp_vals),
                'avg': sum(temp_vals) / len(temp_vals),
                'throttle_events': sum(1 for t in temp_vals if t >= 80)
            }
        }


class WorstCaseTest:
    """Orchestrates all stress tests running simultaneously."""
    
    def __init__(self, base_url: str, admin_password: str = None):
        self.base_url = base_url.rstrip('/')
        self.admin_password = admin_password
        self.session = requests.Session()
        self.running = False
        self.results = {}
        self.health_monitor = HealthMonitor()
        self._abort = False
        
        # Register abort on critical
        self.health_monitor.register_callback(self._on_critical)
    
    def _on_critical(self, metrics: HealthMetrics):
        """Handle critical system state."""
        print(f"\n⚠️  CRITICAL: CPU={metrics.cpu_percent:.1f}%, Mem={metrics.memory_percent:.1f}%, Temp={metrics.cpu_temp:.1f}°C")
        # Don't abort automatically - just warn
    
    def authenticate(self) -> bool:
        """Authenticate as admin."""
        try:
            self.session.get(f"{self.base_url}/")
            if self.admin_password:
                resp = self.session.post(
                    f"{self.base_url}/api/validate_session_password",
                    json={'password': self.admin_password}
                )
                if resp.status_code == 200 and resp.json().get('valid'):
                    self.session.post(f"{self.base_url}/api/admin/claim")
            return True
        except Exception as e:
            print(f"Auth error: {e}")
            return False
    
    def get_test_data(self) -> Dict:
        """Get categories and media for testing."""
        try:
            resp = self.session.get(f"{self.base_url}/api/categories")
            categories = resp.json().get('categories', [])
            
            video_urls = []
            for cat in categories[:5]:
                media_resp = self.session.get(
                    f"{self.base_url}/api/categories/{cat['id']}/media",
                    params={'limit': 50}
                )
                for f in media_resp.json().get('files', []):
                    if f.get('type') == 'video':
                        video_urls.append(f"/media/{cat['id']}/{f['name']}")
            
            return {
                'categories': categories,
                'video_urls': video_urls[:10]
            }
        except Exception as e:
            print(f"Error getting test data: {e}")
            return {'categories': [], 'video_urls': []}
    
    def _run_streaming_load(self, video_urls: List[str], num_clients: int, duration: int):
        """Run streaming load test."""
        results = {'requests': 0, 'bytes': 0, 'errors': 0}
        
        def stream_client(url: str):
            nonlocal results
            try:
                start = time.time()
                while self.running and (time.time() - start) < duration:
                    resp = self.session.get(
                        f"{self.base_url}{url}",
                        headers={'Range': 'bytes=0-1048575'},  # 1MB
                        stream=True,
                        timeout=10
                    )
                    for chunk in resp.iter_content(chunk_size=65536):
                        results['bytes'] += len(chunk)
                    results['requests'] += 1
                    time.sleep(0.5)
            except Exception as e:
                results['errors'] += 1
        
        threads = []
        for i in range(num_clients):
            url = video_urls[i % len(video_urls)] if video_urls else '/api/config'
            t = threading.Thread(target=stream_client, args=(url,))
            t.start()
            threads.append(t)
        
        return threads, results
    
    def _run_websocket_load(self, num_clients: int, duration: int):
        """Run WebSocket chat spam (or HTTP fallback)."""
        results = {'messages': 0, 'errors': 0, 'skipped': False, 'mode': 'websocket'}
        
        if not HAS_SOCKETIO:
            # HTTP fallback - test chat-related API endpoints
            results['mode'] = 'http_fallback'
            print("  ℹ️  Using HTTP fallback for WebSocket test")
            
            def http_client(client_id: int):
                nonlocal results
                sess = requests.Session()
                start = time.time()
                while self.running and (time.time() - start) < duration:
                    try:
                        # Simulate API activity that would normally go through WebSocket
                        sess.get(f"{self.base_url}/api/config", timeout=5)
                        sess.get(f"{self.base_url}/api/categories", timeout=5)
                        results['messages'] += 2
                    except:
                        results['errors'] += 1
                    time.sleep(0.5)
            
            threads = []
            for i in range(min(num_clients, 5)):  # Limit HTTP clients
                t = threading.Thread(target=http_client, args=(i,))
                t.start()
                threads.append(t)
            return threads, results
        
        def ws_client(client_id: int):
            nonlocal results
            try:
                sio = socketio.Client()
                sio.connect(self.base_url, transports=['websocket'])
                sio.emit('join_chat')
                
                start = time.time()
                while self.running and (time.time() - start) < duration:
                    sio.emit('chat_message', {'message': f'[Stress {client_id}] Test message'})
                    results['messages'] += 1
                    time.sleep(0.5)
                
                sio.disconnect()
            except Exception as e:
                results['errors'] += 1
        
        threads = []
        for i in range(num_clients):
            t = threading.Thread(target=ws_client, args=(i,))
            t.start()
            threads.append(t)
        
        return threads, results
    
    def _run_api_load(self, duration: int):
        """Run API endpoint hammering."""
        results = {'requests': 0, 'errors': 0}
        
        endpoints = [
            '/api/config',
            '/api/categories',
            '/api/sync/status',
            '/api/progress/videos'
        ]
        
        def api_client():
            nonlocal results
            sess = requests.Session()
            start = time.time()
            while self.running and (time.time() - start) < duration:
                for endpoint in endpoints:
                    try:
                        resp = sess.get(f"{self.base_url}{endpoint}", timeout=5)
                        results['requests'] += 1
                    except:
                        results['errors'] += 1
                time.sleep(0.05)  # Reduced delay for more pressure
        
        threads = []
        for _ in range(5):  # 5 API clients for stress testing
            t = threading.Thread(target=api_client)
            t.start()
            threads.append(t)
        
        return threads, results
    
    def _run_progress_stress(self, categories: List[Dict], duration: int):
        """Stress SQLite with rapid progress saves - creates a test profile first."""
        results = {'saves': 0, 'reads': 0, 'errors': 0, 'profile_id': None}

        # Create a test profile for progress saves (profile_id required)
        profile_name = f'wcs-progress-{int(time.time())}'
        try:
            resp = self.session.post(
                f"{self.base_url}/api/profiles",
                json={'name': profile_name},
                timeout=10,
            )
            if resp.status_code == 201:
                results['profile_id'] = resp.json().get('profile', {}).get('id')
        except Exception:
            pass

        if not results['profile_id']:
            print("  ⚠ Could not create test profile for progress stress")
            return [], results

        # Select the profile so the session has an active profile_id
        try:
            self.session.post(
                f"{self.base_url}/api/profiles/select",
                json={'profile_id': results['profile_id']},
                timeout=10,
            )
        except Exception:
            pass

        def progress_worker(worker_id: int):
            nonlocal results
            start = time.time()
            cat_idx = 0

            while self.running and (time.time() - start) < duration:
                cat = categories[cat_idx % len(categories)]
                cat_id = cat.get('id', 'unknown')

                try:
                    # Save progress (SQLite write)
                    resp = self.session.post(
                        f"{self.base_url}/api/progress/{cat_id}",
                        json={
                            'index': worker_id * 10 + cat_idx,
                            'total_count': 100,
                            'video_timestamp': 120.5 + cat_idx,
                            'video_duration': 3600.0
                        },
                        timeout=5
                    )
                    if resp.status_code == 200:
                        results['saves'] += 1
                    else:
                        results['errors'] += 1

                    # Read progress (SQLite read)
                    resp = self.session.get(f"{self.base_url}/api/progress/{cat_id}", timeout=5)
                    if resp.status_code == 200:
                        results['reads'] += 1

                    cat_idx += 1
                except Exception:
                    results['errors'] += 1

                time.sleep(0.1)  # Brief sleep between operations

        # Use single worker with main session's profile auth
        threads = []
        t = threading.Thread(target=progress_worker, args=(0,))
        t.start()
        threads.append(t)

        return threads, results
    
    def _cleanup_test_data(self):
        """Clean up test data created during stress tests.

        Only removes test-created profiles (which cascades their progress).
        Never calls DELETE /api/progress/all — that would wipe real user data.
        """
        try:
            # Clean up test profile created by progress stress.
            # Deleting the profile also removes its progress entries via cascade.
            progress_profile_id = self.results.get('progress_db', {}).get('profile_id')
            if progress_profile_id:
                try:
                    self.session.delete(
                        f"{self.base_url}/api/profiles/{progress_profile_id}",
                        timeout=10,
                    )
                    print("  ✓ Cleaned up test profile and its progress")
                except Exception:
                    print("  ⚠ Could not delete test profile")

        except Exception as e:
            print(f"  ⚠ Cleanup error: {e}")
    
    def _run_category_scan_stress(self, duration: int):
        """Stress category scanning - simulates USB detection / page refreshes."""
        results = {'scans': 0, 'media_fetches': 0, 'errors': 0}
        
        def scan_worker():
            nonlocal results
            sess = requests.Session()
            start = time.time()
            
            while self.running and (time.time() - start) < duration:
                try:
                    # Force category rescan (what happens on page load)
                    resp = sess.get(f"{self.base_url}/api/categories", timeout=10)
                    if resp.status_code == 200:
                        results['scans'] += 1
                        cats = resp.json().get('categories', [])
                        
                        # Fetch media lists (pagination stress)
                        for cat in cats[:3]:
                            media_resp = sess.get(
                                f"{self.base_url}/api/categories/{cat['id']}/media",
                                params={'page': 1, 'limit': 50},
                                timeout=10
                            )
                            if media_resp.status_code == 200:
                                results['media_fetches'] += 1
                    else:
                        results['errors'] += 1
                except Exception:
                    results['errors'] += 1
                
                time.sleep(0.3)
        
        # Multiple clients refreshing
        threads = []
        for _ in range(3):
            t = threading.Thread(target=scan_worker)
            t.start()
            threads.append(t)
        
        return threads, results
    
    def _run_thumbnail_stress(self, categories: List[Dict], duration: int):
        """Stress thumbnail generation - triggers ffmpeg on Pi."""
        results = {'requests': 0, 'generated': 0, 'cached': 0, 'errors': 0}
        
        def thumb_worker(cat: Dict):
            nonlocal results
            sess = requests.Session()
            cat_id = cat.get('id', '')
            
            try:
                # Get media list for this category
                resp = sess.get(
                    f"{self.base_url}/api/categories/{cat_id}/media",
                    params={'limit': 100},
                    timeout=10
                )
                if resp.status_code != 200:
                    return
                
                files = resp.json().get('files', [])
                
                for f in files:
                    if not self.running:
                        break
                    
                    filename = f.get('name', '')
                    if not filename:
                        continue
                    
                    try:
                        # Request thumbnail (triggers ffmpeg if not cached)
                        thumb_resp = sess.get(
                            f"{self.base_url}/thumbnails/{cat_id}/{filename}",
                            timeout=30  # Longer timeout for generation
                        )
                        results['requests'] += 1
                        
                        if thumb_resp.status_code == 200:
                            # Check if it was generated fresh or cached
                            if 'X-Thumbnail-Generated' in thumb_resp.headers:
                                results['generated'] += 1
                            else:
                                results['cached'] += 1
                        else:
                            results['errors'] += 1
                    except Exception:
                        results['errors'] += 1
                    
                    time.sleep(0.1)
            except Exception:
                results['errors'] += 1
        
        threads = []
        for cat in categories[:3]:  # Test 3 categories
            t = threading.Thread(target=thumb_worker, args=(cat,))
            t.start()
            threads.append(t)
        
        return threads, results
    
    def _run_thumbnail_load(self, categories: List[Dict]):
        """Run thumbnail generation load."""
        results = {'requests': 0, 'generated': 0, 'errors': 0}
        
        def thumb_client(cat_id: str):
            nonlocal results
            try:
                media_resp = self.session.get(
                    f"{self.base_url}/api/categories/{cat_id}/media",
                    params={'limit': 100}
                )
                files = media_resp.json().get('files', [])
                
                for f in files:
                    if not self.running:
                        break
                    try:
                        resp = self.session.get(
                            f"{self.base_url}/thumbnails/{cat_id}/{f['name']}",
                            timeout=30
                        )
                        results['requests'] += 1
                        if resp.status_code == 200:
                            results['generated'] += 1
                    except:
                        results['errors'] += 1
                    time.sleep(0.2)
            except Exception:
                results['errors'] += 1
        
        threads = []
        for cat in categories[:3]:
            t = threading.Thread(target=thumb_client, args=(cat['id'],))
            t.start()
            threads.append(t)
        
        return threads, results
    
    def _run_sync_load(self, category_id: str, duration: int):
        """Run sync mode stress - uses HTTP API (works without socketio)."""
        results = {'navigations': 0, 'errors': 0}
        
        def sync_host_http():
            """HTTP-based sync stress test (no socketio required)."""
            nonlocal results
            sess = requests.Session()
            
            # First visit the main page to get a session cookie
            try:
                sess.get(f"{self.base_url}/", timeout=5)
            except:
                pass
            
            # Set a manual session_id cookie if none was set
            if 'session_id' not in sess.cookies:
                import uuid
                sess.cookies.set('session_id', str(uuid.uuid4()))
            
            try:
                # Enable sync (this session becomes the host)
                resp = sess.post(
                    f"{self.base_url}/api/sync/toggle",
                    json={'enabled': True, 'media': {
                        'category_id': category_id,
                        'file_url': '',
                        'index': 0
                    }},
                    timeout=5
                )
                if resp.status_code != 200:
                    results['errors'] += 1
                    return
                
                start = time.time()
                idx = 0
                while self.running and (time.time() - start) < duration:
                    idx = (idx + 1) % 100
                    # Use HTTP API to update sync state (same session = host)
                    resp = sess.post(
                        f"{self.base_url}/api/sync/update",
                        json={
                            'category_id': category_id,
                            'index': idx,
                            'file_url': f'/media/{category_id}/item_{idx}'
                        },
                        timeout=5
                    )
                    if resp.status_code == 200:
                        results['navigations'] += 1
                    else:
                        results['errors'] += 1
                    time.sleep(0.3)
                
                # Also test status endpoint
                sess.get(f"{self.base_url}/api/sync/status", timeout=5)
                sess.get(f"{self.base_url}/api/sync/current", timeout=5)
                
                # Disable sync
                sess.post(
                    f"{self.base_url}/api/sync/toggle",
                    json={'enabled': False},
                    timeout=5
                )
            except Exception as e:
                results['errors'] += 1
        
        t = threading.Thread(target=sync_host_http)
        t.start()
        return [t], results
    
    def run(self, duration: int = 60, stream_clients: int = 5, 
            ws_clients: int = 10) -> Dict:
        """Run the worst case scenario test."""
        print("\n" + "=" * 60)
        print("  GHOSTHUB WORST CASE SCENARIO TEST")
        print("=" * 60)
        print(f"  Duration: {duration}s")
        print(f"  Stream clients: {stream_clients}")
        print(f"  WebSocket clients: {ws_clients}")
        print_dependency_status()
        print("=" * 60 + "\n")
        
        # Setup
        if not self.authenticate():
            return {'error': 'Authentication failed'}
        
        test_data = self.get_test_data()
        if not test_data['categories']:
            print("WARNING: No categories found")
        
        # Start health monitoring
        self.health_monitor.start()
        self.running = True
        
        all_threads = []
        all_results = {}
        
        start_time = time.time()
        
        try:
            print("Starting all stress tests simultaneously...")
            
            # 1. Streaming load
            if test_data['video_urls']:
                threads, results = self._run_streaming_load(
                    test_data['video_urls'], stream_clients, duration
                )
                all_threads.extend(threads)
                all_results['streaming'] = results
                print(f"  ✓ Started {stream_clients} streaming clients")
            
            # 2. WebSocket load
            threads, results = self._run_websocket_load(ws_clients, duration)
            all_threads.extend(threads)
            all_results['websocket'] = results
            print(f"  ✓ Started {ws_clients} WebSocket clients")
            
            # 3. API load
            threads, results = self._run_api_load(duration)
            all_threads.extend(threads)
            all_results['api'] = results
            print("  ✓ Started API hammering")
            
            # 4. Thumbnail load
            if test_data['categories']:
                threads, results = self._run_thumbnail_load(test_data['categories'])
                all_threads.extend(threads)
                all_results['thumbnails'] = results
                print("  ✓ Started thumbnail generation")
            
            # 5. Sync load
            if test_data['categories']:
                threads, results = self._run_sync_load(
                    test_data['categories'][0]['id'], duration
                )
                all_threads.extend(threads)
                all_results['sync'] = results
                print("  ✓ Started sync mode stress")
            
            # 6. Progress/SQLite stress (admin authenticated)
            if test_data['categories']:
                threads, results = self._run_progress_stress(test_data['categories'], duration)
                all_threads.extend(threads)
                all_results['progress_db'] = results
                print("  ✓ Started progress/SQLite stress (admin)")
            
            # 7. Category scanning stress (simulates page refreshes, USB detection)
            threads, results = self._run_category_scan_stress(duration)
            all_threads.extend(threads)
            all_results['category_scan'] = results
            print("  ✓ Started category scan stress (3 clients)")
            
            # 8. Thumbnail generation stress (ffmpeg on Pi CPU)
            if test_data['categories']:
                threads, results = self._run_thumbnail_stress(test_data['categories'], duration)
                all_threads.extend(threads)
                all_results['thumbnails'] = results
                print("  ✓ Started thumbnail/ffmpeg stress")
            
            print(f"\n🔥 Running worst case scenario for {duration}s...")
            print("   Press Ctrl+C to abort early\n")
            
            # Progress display
            while time.time() - start_time < duration and self.running:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                metrics = self.health_monitor.metrics
                
                status = "⚠️ THROTTLING" if metrics.is_throttling else "✓"
                print(f"\r  [{elapsed:.0f}s/{duration}s] CPU: {metrics.cpu_percent:.1f}% | "
                      f"Mem: {metrics.memory_percent:.1f}% | "
                      f"Temp: {metrics.cpu_temp:.1f}°C {status}    ", end='', flush=True)
                
                time.sleep(1)
            
            print("\n\nStopping tests...")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Aborted by user")
        finally:
            self.running = False
        
        # Wait for all threads
        for t in all_threads:
            t.join(timeout=5)
        
        self.health_monitor.stop()
        
        # Clean up test data
        print("\n🧹 Cleaning up test data...")
        self._cleanup_test_data()
        
        total_duration = time.time() - start_time
        
        # Compile results
        final_results = {
            'duration_seconds': total_duration,
            'test_results': all_results,
            'health_summary': self.health_monitor.get_summary(),
            'timestamp': datetime.now().isoformat()
        }
        
        self._print_summary(final_results)
        
        return final_results
    
    def _print_summary(self, results: Dict):
        """Print test summary."""
        print("")
        print("╔" + "═" * 62 + "╗")
        print("║" + "  WORST CASE SCENARIO RESULTS".center(62) + "║")
        print("╚" + "═" * 62 + "╝")
        
        print(f"\n  ⏱  Duration: {results['duration_seconds']:.1f}s")
        
        # Test results
        print("\n  ┌─ Load Test Results ──────────────────────────────────────")
        for test_name, test_results in results.get('test_results', {}).items():
            if isinstance(test_results, dict):
                mode = test_results.get('mode', '')
                mode_str = f" [{mode}]" if mode else ""
                skipped = test_results.get('skipped', False)
                
                if skipped:
                    print(f"  │  {test_name}: SKIPPED")
                else:
                    # Format output based on test type
                    if test_name == 'progress_db':
                        print(f"  │  {test_name}: saves={test_results.get('saves', 0)}, reads={test_results.get('reads', 0)}, errors={test_results.get('errors', 0)}")
                    elif test_name == 'category_scan':
                        print(f"  │  {test_name}: scans={test_results.get('scans', 0)}, media_fetches={test_results.get('media_fetches', 0)}")
                    elif test_name == 'thumbnails':
                        print(f"  │  {test_name}: requests={test_results.get('requests', 0)}, generated={test_results.get('generated', 0)}, cached={test_results.get('cached', 0)}")
                    else:
                        display_items = {k: v for k, v in test_results.items() 
                                       if k not in ('skipped', 'mode')}
                        details = ", ".join(f"{k}={v}" for k, v in display_items.items())
                        print(f"  │  {test_name}{mode_str}: {details}")
        print("  └" + "─" * 56)
        
        # Health summary
        health = results.get('health_summary', {})
        if health:
            print("\n  ┌─ System Health ─────────────────────────────────────────")
            if 'cpu' in health:
                cpu = health['cpu']
                print(f"  │  CPU:  {cpu['avg']:.0f}% avg (max {cpu['max']:.0f}%)")
            if 'memory' in health:
                mem = health['memory']
                print(f"  │  RAM:  {mem['avg']:.0f}% avg (max {mem['max']:.0f}%)")
            if 'temperature' in health:
                temp = health['temperature']
                temp_color = "⚠️ " if temp['max'] >= 70 else ""
                print(f"  │  Temp: {temp_color}{temp['avg']:.0f}°C avg (max {temp['max']:.0f}°C)")
                if temp['throttle_events'] > 0:
                    print(f"  │  ⚠️  Throttling: {temp['throttle_events']} events")
            print("  └" + "─" * 56)
        
        # Verdict
        print("")
        health_ok = True
        issues = []
        
        if health.get('temperature', {}).get('max', 0) >= 85:
            issues.append("❌ Critical CPU temperature")
            health_ok = False
        elif health.get('temperature', {}).get('throttle_events', 0) > 0:
            issues.append("⚠️  Throttling occurred")
        
        if health.get('memory', {}).get('max', 0) >= 95:
            issues.append("❌ Critical memory usage")
            health_ok = False
        elif health.get('memory', {}).get('max', 0) >= 85:
            issues.append("⚠️  High memory usage")
        
        if issues:
            for issue in issues:
                print(f"  {issue}")
        
        if health_ok:
            print("  ✅ System handled worst case scenario successfully")
        
        print("\n" + "═" * 64)

    def evaluate_results(self, results: Dict) -> bool:
        """Return True when the worst-case run is healthy enough to pass."""
        health = results.get('health_summary', {})
        if health.get('temperature', {}).get('max', 0) >= 85:
            return False
        if health.get('memory', {}).get('max', 0) >= 95:
            return False
        return True


def main():
    parser = argparse.ArgumentParser(description='GhostHub Worst Case Scenario Test')
    parser.add_argument('--url', default='http://localhost:5000',
                        help='GhostHub base URL')
    parser.add_argument('--password', default=None,
                        help='Admin password')
    parser.add_argument('--duration', type=int, default=60,
                        help='Test duration in seconds')
    parser.add_argument('--stream-clients', type=int, default=5,
                        help='Number of streaming clients')
    parser.add_argument('--ws-clients', type=int, default=10,
                        help='Number of WebSocket clients')
    parser.add_argument('--output', default=None,
                        help='Output file for results JSON')
    
    args = parser.parse_args()
    
    test = WorstCaseTest(args.url, args.password)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        test.running = False
        print("\nAborting...")
    
    signal.signal(signal.SIGINT, signal_handler)
    
    results = test.run(
        duration=args.duration,
        stream_clients=args.stream_clients,
        ws_clients=args.ws_clients
    )
    
    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    else:
        # Default output
        output_dir = Path(__file__).parent / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"worst_case_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    sys.exit(0 if test.evaluate_results(results) else 1)


if __name__ == '__main__':
    main()
