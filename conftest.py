"""
Root conftest.py for GhostHub test suite

Registers custom pytest markers used across all tests.
"""

import pytest


def pytest_configure(config):
    """Register custom markers"""

    # E2E test markers
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end integration tests (requires running GhostHub instance)"
    )

    # Existing markers from unit tests
    config.addinivalue_line(
        "markers",
        "slow: Tests that take >10 seconds to run"
    )

    config.addinivalue_line(
        "markers",
        "integration: Integration tests that test multiple services together"
    )
