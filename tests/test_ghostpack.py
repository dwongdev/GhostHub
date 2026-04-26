"""Tests for GhostPack bootstrap validation helpers."""

import os


def test_ghostpack_expected_service_manifest_matches_app_bootstrap():
    """GhostPack validation should read the live service manifest at runtime."""
    from scripts.ghostpack import build_dist_validation_script

    script = build_dist_validation_script()

    assert "from app.app_bootstrap import build_specter_services" in script
    assert "service_names = [service.name for service in build_specter_services()]" in script


def test_ghostpack_expected_controller_manifest_matches_controller_bootstrap():
    """GhostPack validation should read the live controller manifest at runtime."""
    from scripts.ghostpack import build_dist_validation_script

    script = build_dist_validation_script()

    assert "from app.controllers import build_controller_classes" in script
    assert "controller_names = [controller.__name__ for controller in build_controller_classes()]" in script


def test_ghostpack_validation_script_checks_services_controllers_and_runtime_imports():
    """GhostPack validation should cover both manifests and key runtime imports."""
    from scripts.ghostpack import build_dist_validation_script

    script = build_dist_validation_script()

    assert "build_specter_services" in script
    assert "build_controller_classes" in script
    assert "GhostHubRuntime" in script
    assert '_socketio' in script
    assert "initialize_app" in script
    assert "Dist build only registered" in script
    assert "Duplicate service names in dist build" in script
    assert "Duplicate controller names in dist build" in script
    assert "stale or incorrect" in script


def test_ghostpack_bytecode_importer_loads_from_pycache_without_stub_markers():
    """GhostPack should no longer depend on # compiled stub files."""
    from scripts.ghostpack import BYTECODE_IMPORTER_TEMPLATE

    assert "__pycache__" in BYTECODE_IMPORTER_TEMPLATE
    assert "# compiled" not in BYTECODE_IMPORTER_TEMPLATE
    assert "name != 'app' and not name.startswith('app.')" in BYTECODE_IMPORTER_TEMPLATE


def test_ghostpack_validation_prefers_project_venv_python(tmp_path, monkeypatch):
    """Dist validation should use the project venv when it exists."""
    from scripts import ghostpack

    venv_python = tmp_path / "venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n")
    os.chmod(venv_python, 0o755)

    monkeypatch.setattr(ghostpack, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ghostpack.sys, "executable", "/usr/bin/python3")

    assert ghostpack.get_validation_python() == str(venv_python)


def test_ghostpack_validation_falls_back_to_current_python(monkeypatch, tmp_path):
    """Dist validation should fall back cleanly when no project venv exists."""
    from scripts import ghostpack

    fallback_python = str(tmp_path / "python3")
    tmp_exec = tmp_path / "python3"
    tmp_exec.write_text("#!/bin/sh\n")
    os.chmod(tmp_exec, 0o755)

    monkeypatch.setattr(ghostpack, "PROJECT_ROOT", tmp_path / "missing-root")
    monkeypatch.setattr(ghostpack.sys, "executable", fallback_python)

    assert ghostpack.get_validation_python() == fallback_python
