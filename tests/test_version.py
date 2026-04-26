"""
Tests for Version Module
------------------------
Version string is used in update checks, install scripts, and
API responses. Must be a valid semver string.
"""
import re
import pytest
from app.version import VERSION


class TestVersion:
    """Version module contract tests."""

    def test_version_is_string(self):
        assert isinstance(VERSION, str)

    def test_version_is_valid_semver(self):
        """Must follow major.minor.patch format."""
        assert re.match(r"^\d+\.\d+\.\d+$", VERSION), (
            f"VERSION '{VERSION}' is not valid semver (expected X.Y.Z)"
        )

    def test_version_components_are_reasonable(self):
        """Major should be >= 1 (this is a released product)."""
        major, minor, patch = [int(x) for x in VERSION.split(".")]
        assert major >= 1
        assert minor >= 0
        assert patch >= 0

    def test_version_not_empty(self):
        assert len(VERSION) > 0
