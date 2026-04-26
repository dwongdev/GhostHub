#!/usr/bin/env python3
"""
JavaScript Test Runner
Installs npm dependencies, runs Vitest tests, then cleans up node_modules.
Keeps cloud storage small by not persisting node_modules.

Usage:
    python scripts/run_js_tests.py [--coverage] [--watch] [--keep]

Options:
    --coverage  Run tests with coverage report
    --watch     Run tests in watch mode (skips cleanup)
    --keep      Keep node_modules after tests (don't cleanup)
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def get_js_dir():
    """Get the static/js directory path."""
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    return project_root / "static" / "js"


def run_command(cmd, cwd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")
    
    try:
        # Use shell=True on Windows for npm commands
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            check=False,
            env={**os.environ, "FORCE_COLOR": "1"}  # Enable colored output
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def check_node_installed():
    """Check if Node.js is installed."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            shell=(sys.platform == "win32")
        )
        if result.returncode == 0:
            print(f"Node.js version: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("ERROR: Node.js is not installed or not in PATH")
    print("Please install Node.js from https://nodejs.org/")
    return False


def check_npm_installed():
    """Check if npm is installed."""
    # On Windows, npm is often npm.cmd
    npm_commands = ["npm", "npm.cmd"] if sys.platform == "win32" else ["npm"]
    
    for npm_cmd in npm_commands:
        try:
            result = subprocess.run(
                [npm_cmd, "--version"],
                capture_output=True,
                text=True,
                shell=(sys.platform == "win32")
            )
            if result.returncode == 0:
                print(f"npm version: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            continue
    
    print("ERROR: npm is not installed or not in PATH")
    print("If Node.js is installed, try restarting your terminal.")
    return False


def install_dependencies(js_dir):
    """Install npm dependencies."""
    return run_command("npm install", js_dir, "Installing npm dependencies...")


def run_tests(js_dir, coverage=False, watch=False):
    """Run the Vitest tests."""
    if watch:
        cmd = "npm run test:watch"
        desc = "Running tests in watch mode (Ctrl+C to exit)..."
    elif coverage:
        cmd = "npm run test:coverage"
        desc = "Running tests with coverage..."
    else:
        cmd = "npm test"
        desc = "Running tests..."
    
    return run_command(cmd, js_dir, desc)


def cleanup_node_modules(js_dir):
    """Remove node_modules directory to save space."""
    node_modules = js_dir / "node_modules"
    package_lock = js_dir / "package-lock.json"
    
    print(f"\n{'='*60}")
    print("  Cleaning up node_modules...")
    print(f"{'='*60}\n")
    
    try:
        if node_modules.exists():
            shutil.rmtree(node_modules)
            print(f"Removed: {node_modules}")
        
        if package_lock.exists():
            package_lock.unlink()
            print(f"Removed: {package_lock}")
        
        print("\nCleanup complete! Cloud storage stays small.")
        return True
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run JavaScript tests with automatic cleanup"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Run tests in watch mode (skips cleanup)"
    )
    parser.add_argument(
        "--keep", "-k",
        action="store_true",
        help="Keep node_modules after tests"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  GhostHub JavaScript Test Runner")
    print("="*60)
    
    # Check prerequisites
    if not check_node_installed():
        sys.exit(1)
    
    if not check_npm_installed():
        sys.exit(1)
    
    js_dir = get_js_dir()
    
    if not js_dir.exists():
        print(f"ERROR: JavaScript directory not found: {js_dir}")
        sys.exit(1)
    
    print(f"\nTest directory: {js_dir}")
    
    # Install dependencies
    if not install_dependencies(js_dir):
        print("\nERROR: Failed to install dependencies")
        sys.exit(1)
    
    # Run tests
    tests_passed = run_tests(js_dir, coverage=args.coverage, watch=args.watch)
    
    # Cleanup (unless --keep or --watch)
    if not args.keep and not args.watch:
        cleanup_node_modules(js_dir)
    else:
        if args.keep:
            print("\n--keep flag set, skipping cleanup")
        if args.watch:
            print("\nWatch mode, skipping cleanup")
    
    # Final result
    print("\n" + "="*60)
    if tests_passed:
        print("  ✓ All tests passed!")
    else:
        print("  ✗ Some tests failed")
    print("="*60 + "\n")
    
    sys.exit(0 if tests_passed else 1)


if __name__ == "__main__":
    main()
