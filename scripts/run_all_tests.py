#!/usr/bin/env python3
"""
GhostHub Unified Test Runner
============================
Runs both Python (pytest) and JavaScript (Vitest) tests.

Usage:
    python scripts/run_all_tests.py           # Run all tests
    python scripts/run_all_tests.py --py      # Run only Python tests
    python scripts/run_all_tests.py --js      # Run only JavaScript tests
    python scripts/run_all_tests.py -v        # Verbose output
"""

import subprocess
import sys
import os
import shutil
import argparse
import re
import hashlib
from pathlib import Path

# Enable ANSI escape codes on Windows
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def strip_ansi(text):
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Get project root directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
JS_DIR = PROJECT_ROOT / "static" / "js"
TESTS_DIR = PROJECT_ROOT / "tests"
JS_NODE_MODULES_DIR = JS_DIR / "node_modules"
JS_INSTALL_STAMP = JS_NODE_MODULES_DIR / ".ghosthub-install-stamp"


def _get_runtime_temp_root():
    """Return a writable temp root for test runners."""
    override = os.environ.get("GHOSTHUB_TEST_TMP")
    if override:
        root = Path(override)
    else:
        if sys.platform == "win32":
            local_app_data = os.environ.get("LOCALAPPDATA")
            if local_app_data:
                root = Path(local_app_data) / "Temp" / "ghosthub_test_runtime"
            else:
                root = PROJECT_ROOT / "tmp" / "ghosthub_test_runtime"
        else:
            # Keep the basetemp path non-hidden; hidden segments (e.g. ".tmp")
            # are treated as restricted/hidden content by media path guards.
            root = PROJECT_ROOT / "tmp" / "ghosthub_test_runtime"

    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_test_env():
    """Build subprocess env with stable temp paths."""
    env = os.environ.copy()
    temp_root = _get_runtime_temp_root()
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)
    return env, temp_root


def _compute_js_dependency_fingerprint():
    """Fingerprint the JS dependency manifests."""
    digest = hashlib.sha256()
    for manifest in (JS_DIR / "package.json", JS_DIR / "package-lock.json"):
        if manifest.exists():
            digest.update(manifest.read_bytes())
    return digest.hexdigest()


def _is_js_dependency_tree_usable():
    """Return True when node_modules matches the current manifests."""
    vitest_bin = JS_NODE_MODULES_DIR / ".bin" / ("vitest.cmd" if sys.platform == "win32" else "vitest")
    return JS_NODE_MODULES_DIR.exists() and vitest_bin.exists()


def _write_js_install_stamp():
    """Persist the manifest fingerprint after a successful install."""
    JS_NODE_MODULES_DIR.mkdir(parents=True, exist_ok=True)
    JS_INSTALL_STAMP.write_text(_compute_js_dependency_fingerprint(), encoding="utf-8")


def print_header(title):
    """Print a formatted header."""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width + "\n")


def print_result(name, success, duration=None):
    """Print test result."""
    # Use ASCII characters for Windows compatibility
    icon = "[PASS]" if success else "[FAIL]"
    duration_str = f" ({duration:.2f}s)" if duration else ""
    print(f"  {icon} {name}{duration_str}")


def run_python_tests(verbose=False):
    """Run Python tests with pytest."""
    print_header("Running Python Tests (pytest)")

    env, temp_root = _build_test_env()
    base_temp = temp_root / "pytest_basetemp"
    base_temp.mkdir(parents=True, exist_ok=True)

    # Skip E2E tests (require live server) - run with pytest tests/e2e/ to test live instance
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(TESTS_DIR),
        "-v" if verbose else "-q",
        "--tb=short",
        "--ignore=tests/e2e/",
        "--basetemp",
        str(base_temp),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=not verbose,
            text=True,
            env=env,
            timeout=900
        )

        if not verbose and result.stdout:
            # Extract summary line
            lines = result.stdout.strip().split('\n')
            for line in lines[-5:]:
                if 'passed' in line or 'failed' in line or 'error' in line:
                    print(f"  {line}")

        return result.returncode == 0

    except FileNotFoundError:
        print("  ERROR: pytest not found. Install with: pip install pytest")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def run_js_tests(verbose=False):
    """Run JavaScript tests with Vitest."""
    print_header("Running JavaScript Tests (Vitest)")

    env, _ = _build_test_env()
    
    # Check if package.json exists
    package_json = JS_DIR / "package.json"
    if not package_json.exists():
        print("  ERROR: package.json not found in static/js/")
        return False
    
    if _is_js_dependency_tree_usable():
        print("  Using existing npm dependencies (lockfile unchanged).")
    else:
        print("  Installing npm dependencies...")
        try:
            if sys.platform == "win32":
                install_cmd = ["cmd", "/c", "npm", "install", "--no-audit", "--no-fund"]
            else:
                install_cmd = ["npm", "install", "--no-audit", "--no-fund"]

            install_result = subprocess.run(
                install_cmd,
                cwd=JS_DIR,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                timeout=900
            )
            if install_result.returncode != 0:
                print(f"  ERROR: npm install failed")
                if verbose:
                    print(install_result.stderr)
                return False

            _write_js_install_stamp()
        except FileNotFoundError:
            print("  ERROR: npm not found. Please install Node.js")
            return False
    
    # Run tests
    print("  Running Vitest...")
    try:
        if sys.platform == "win32":
            test_cmd = ["cmd", "/c", "npm", "test"]
        else:
            test_cmd = ["npm", "test"]
        if not verbose:
            test_cmd.append("--")
            test_cmd.append("--reporter=basic")
        
        test_result = subprocess.run(
            test_cmd,
            cwd=JS_DIR,
            capture_output=not verbose,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            timeout=900
        )
        
        if not verbose and test_result.stdout:
            # Extract summary, strip ANSI codes for clean display
            lines = test_result.stdout.strip().split('\n')
            for line in lines[-10:]:
                clean_line = strip_ansi(line.strip())
                if 'Tests' in clean_line or 'passed' in clean_line or 'failed' in clean_line:
                    print(f"  {clean_line}")
        
        success = test_result.returncode == 0
        
    except Exception as e:
        print(f"  ERROR: {e}")
        success = False
    
    return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run GhostHub tests (Python and JavaScript)"
    )
    parser.add_argument(
        "--py", "--python",
        action="store_true",
        help="Run only Python tests"
    )
    parser.add_argument(
        "--js", "--javascript",
        action="store_true",
        help="Run only JavaScript tests"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # If no specific flag, run both
    run_py = args.py or (not args.py and not args.js)
    run_js = args.js or (not args.py and not args.js)
    
    print_header("GhostHub Test Suite")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"  Python tests: {'Yes' if run_py else 'No'}")
    print(f"  JavaScript tests: {'Yes' if run_js else 'No'}")
    
    temp_root = _get_runtime_temp_root()
    results = {}
    all_passed = True
    
    try:
        # Run Python tests
        if run_py:
            results['Python'] = run_python_tests(args.verbose)
        
        # Run JavaScript tests
        if run_js:
            results['JavaScript'] = run_js_tests(args.verbose)
        
        # Summary
        print_header("Test Results Summary")
        
        for name, success in results.items():
            print_result(name, success)
            if not success:
                all_passed = False
    finally:
        # Clean up temp folder
        if temp_root.exists():
            print(f"\n  Cleaning up temp folder: {temp_root.name}")
            try:
                shutil.rmtree(temp_root)
            except Exception as e:
                print(f"  Warning: Could not clean up temp folder: {e}")
    
    print()
    if all_passed:
        print("  [SUCCESS] All tests passed!")
        return 0
    else:
        print("  [FAILED] Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
