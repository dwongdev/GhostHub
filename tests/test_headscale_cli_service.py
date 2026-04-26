"""Tests for Headscale binary resolution helpers."""

import os


def test_find_headscale_binary_ignores_directory_candidates(tmp_path, monkeypatch):
    """A directory named headscale must never be treated as the executable."""
    from app.services.system.headscale import cli_service

    app_root = tmp_path / "app" / "services" / "system"
    app_root.mkdir(parents=True)
    (app_root / "headscale").mkdir()

    monkeypatch.setattr(cli_service, "APP_ROOT", str(app_root))
    monkeypatch.setattr(cli_service.shutil, "which", lambda _: None)

    assert cli_service._find_headscale_binary() is None


def test_get_headscale_binary_refreshes_invalid_cached_path(tmp_path, monkeypatch):
    """Cached non-file paths should be discarded and replaced with a real binary."""
    from app.services.system.headscale import cli_service

    binary_path = tmp_path / "headscale"
    binary_path.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(binary_path, 0o755)

    invalid_cached_path = tmp_path / "app" / "services" / "system" / "headscale"
    invalid_cached_path.mkdir(parents=True)

    monkeypatch.setattr(cli_service, "APP_ROOT", str(tmp_path))
    monkeypatch.setattr(cli_service, "HS_BINARY", str(invalid_cached_path))
    monkeypatch.setattr(cli_service.shutil, "which", lambda _: None)

    assert cli_service.get_headscale_binary() == str(binary_path)


def test_find_headscale_binary_repairs_missing_exec_bits(tmp_path, monkeypatch):
    """A real binary should be made executable before being rejected as missing."""
    from app.services.system.headscale import cli_service

    binary_path = tmp_path / "headscale"
    binary_path.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(binary_path, 0o644)

    monkeypatch.setattr(cli_service, "APP_ROOT", str(tmp_path))
    monkeypatch.setattr(cli_service, "HS_BINARY", None)
    monkeypatch.setattr(cli_service.shutil, "which", lambda _: None)

    assert cli_service.get_headscale_binary() == str(binary_path)
    assert os.access(binary_path, os.X_OK)
