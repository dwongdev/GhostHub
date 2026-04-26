#!/usr/bin/env python3
"""
GhostHub Test Verification Script
==================================
Verifies that all test systems are properly configured and functional.

Checks:
- Python (pytest) test infrastructure
- JavaScript (vitest) test infrastructure
- Stress test scripts and dependencies
- Pre-launch test suite readiness

Usage:
    python3 verify_tests.py              # Quick verification
    python3 verify_tests.py --full       # Full verification with sample test runs
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def log_success(msg: str):
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")


def log_warning(msg: str):
    print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}✗{Colors.END} {msg}")


def log_info(msg: str):
    print(f"{Colors.BLUE}ℹ{Colors.END} {msg}")


def check_python_dependencies() -> bool:
    """Check if required Python test dependencies are installed."""
    log_info("Checking Python test dependencies...")

    required_packages = [
        'pytest',
        'pytest-mock',
        'requests',
        'psutil',
        'socketio',
        'flask',
        'flask-socketio'
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)

    if missing:
        log_error(f"Missing Python packages: {', '.join(missing)}")
        log_info("Install with: pip install " + ' '.join(missing))
        return False

    log_success("All Python dependencies installed")
    return True


def check_javascript_dependencies() -> bool:
    """Check if JavaScript test dependencies are installed."""
    log_info("Checking JavaScript test dependencies...")

    js_dir = Path(__file__).parent.parent / 'static' / 'js'
    package_json = js_dir / 'package.json'
    node_modules = js_dir / 'node_modules'

    if not package_json.exists():
        log_error(f"package.json not found at {package_json}")
        return False

    if not node_modules.exists():
        log_warning("node_modules not found - run 'npm install' in static/js/")
        return False

    # Check for vitest
    vitest_bin = node_modules / '.bin' / 'vitest'
    if not vitest_bin.exists() and not (node_modules / '.bin' / 'vitest.cmd').exists():
        log_error("vitest not installed")
        log_info("Install with: cd static/js && npm install")
        return False

    log_success("JavaScript dependencies installed")
    return True


def check_pytest_config() -> bool:
    """Check if pytest configuration is correct."""
    log_info("Checking pytest configuration...")

    project_root = Path(__file__).parent.parent
    pytest_ini = project_root / 'pytest.ini'

    if not pytest_ini.exists():
        log_warning("pytest.ini not found - using default pytest config")
        return True

    # Verify custom markers are registered
    content = pytest_ini.read_text()
    required_markers = ['unit', 'integration', 'slow', 'e2e']

    for marker in required_markers:
        if marker not in content:
            log_warning(f"Marker '{marker}' not registered in pytest.ini")

    log_success("pytest configuration OK")
    return True


def count_test_files() -> Dict[str, int]:
    """Count test files in the project."""
    project_root = Path(__file__).parent.parent

    python_tests = list((project_root / 'tests').rglob('test_*.py'))
    js_tests = list((project_root / 'static' / 'js' / 'tests').rglob('*.test.js'))
    stress_tests = list((project_root / 'stress_tests').glob('*.py'))

    return {
        'python': len(python_tests),
        'javascript': len(js_tests),
        'stress': len(stress_tests) - 2  # Exclude verify_tests.py and __pycache__
    }


def run_sample_python_tests() -> Tuple[bool, int, int]:
    """Run a sample of Python tests to verify functionality."""
    log_info("Running sample Python tests...")

    project_root = Path(__file__).parent.parent

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short', '-x'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse output for counts
        output = result.stdout + result.stderr
        passed = output.count(' PASSED')
        failed = output.count(' FAILED')

        if result.returncode == 0:
            log_success(f"Sample Python tests passed ({passed} tests)")
            return True, passed, failed
        else:
            log_error(f"Some Python tests failed ({failed} failures)")
            # Print last 20 lines of output for debugging
            lines = output.split('\n')
            for line in lines[-20:]:
                if 'FAILED' in line or 'ERROR' in line:
                    print(f"  {line}")
            return False, passed, failed

    except subprocess.TimeoutExpired:
        log_error("Python tests timed out")
        return False, 0, 0
    except Exception as e:
        log_error(f"Error running Python tests: {e}")
        return False, 0, 0


def run_sample_js_tests() -> Tuple[bool, int, int]:
    """Run a sample of JavaScript tests to verify functionality."""
    log_info("Running sample JavaScript tests...")

    js_dir = Path(__file__).parent.parent / 'static' / 'js'

    try:
        result = subprocess.run(
            ['npm', 'test'],
            cwd=js_dir,
            capture_output=True,
            text=True,
            shell=True,
            timeout=120
        )

        # Parse output for counts
        output = result.stdout + result.stderr

        # Extract test counts from vitest output
        passed = 0
        failed = 0
        for line in output.split('\n'):
            if 'Test Files' in line and 'passed' in line:
                parts = line.split()
                try:
                    idx = parts.index('passed')
                    if idx > 0:
                        passed = int(parts[idx - 1])
                except (ValueError, IndexError):
                    pass
            if 'failed' in line.lower():
                parts = line.split()
                try:
                    # Look for pattern like "5 failed"
                    for i, part in enumerate(parts):
                        if part == 'failed' and i > 0:
                            try:
                                failed = int(parts[i - 1])
                                break
                            except ValueError:
                                pass
                except Exception:
                    pass

        if result.returncode == 0:
            log_success(f"Sample JavaScript tests passed ({passed} files)")
            return True, passed, failed
        else:
            log_error(f"Some JavaScript tests failed ({failed} failures)")
            return False, passed, failed

    except subprocess.TimeoutExpired:
        log_error("JavaScript tests timed out")
        return False, 0, 0
    except Exception as e:
        log_error(f"Error running JavaScript tests: {e}")
        return False, 0, 0


def check_stress_test_scripts() -> bool:
    """Verify stress test scripts are executable and configured."""
    log_info("Checking stress test scripts...")

    stress_dir = Path(__file__).parent
    required_scripts = [
        'critical_limits_test.py',
        'network_drop_recovery_test.py',
        'multi_hour_stability_test.py',
        'disk_full_test.py'
    ]

    all_good = True
    for script in required_scripts:
        script_path = stress_dir / script
        if not script_path.exists():
            log_error(f"Missing stress test: {script}")
            all_good = False
        elif not os.access(script_path, os.X_OK):
            log_warning(f"Stress test not executable: {script}")

    if all_good:
        log_success("All stress test scripts present")

    return all_good


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Verify GhostHub test infrastructure'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full verification including sample test execution'
    )

    args = parser.parse_args()

    print()
    print(f"{Colors.BOLD}GhostHub Test Infrastructure Verification{Colors.END}")
    print("=" * 50)
    print()

    all_checks_passed = True

    # Basic checks
    all_checks_passed &= check_python_dependencies()
    all_checks_passed &= check_javascript_dependencies()
    all_checks_passed &= check_pytest_config()
    all_checks_passed &= check_stress_test_scripts()

    print()

    # Count tests
    counts = count_test_files()
    log_info(f"Test inventory:")
    print(f"  Python unit tests: {counts['python']}")
    print(f"  JavaScript unit tests: {counts['javascript']}")
    print(f"  Stress test scripts: {counts['stress']}")

    print()

    # Sample test runs (if --full flag)
    if args.full:
        log_info("Running sample tests (this may take a moment)...")
        print()

        py_success, py_passed, py_failed = run_sample_python_tests()
        all_checks_passed &= py_success

        js_success, js_passed, js_failed = run_sample_js_tests()
        all_checks_passed &= js_success

    # Summary
    print()
    print("=" * 50)
    if all_checks_passed:
        print(f"{Colors.GREEN}{Colors.BOLD} All checks passed!{Colors.END}")
        print()
        print("Stress-test infrastructure is ready. Run release validation with:")
        print(f"  {Colors.BLUE}./stress_tests/run_all_tests.sh{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD} Some checks failed{Colors.END}")
        print()
        print("Fix the issues above before running tests.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
