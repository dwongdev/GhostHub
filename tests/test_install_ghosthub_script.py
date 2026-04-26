"""Regression checks for installer/update shell behavior."""

from pathlib import Path


INSTALL_SCRIPT = Path(__file__).resolve().parents[1] / "install_ghosthub.sh"


def test_extract_app_update_clears_stale_root_dir_files_and_preserves_dotfiles():
    """Root-folder ZIP extraction must replace app code and keep hidden preserved files."""
    script = INSTALL_SCRIPT.read_text()

    assert 'cp -a "$TMP_DIR/Ghosthub_pi_github/." "$APP_DIR/"' in script
    assert 'echo "[*] Clearing stale app files before copying fresh package..."' in script
    assert "! -name '.headscale_version'" in script


def test_download_app_update_uses_github_releases_and_pinned_versions():
    """Installer should download release ZIPs from GitHub by default."""
    script = INSTALL_SCRIPT.read_text()

    assert 'GITHUB_REPO="${GITHUB_REPO:-BleedingXiko/GhostHub}"' in script
    assert 'https://github.com/${GITHUB_REPO}/releases/${RELEASE_PATH}/${ZIP_FILE}' in script
    assert 'RELEASE_PATH="latest/download"' in script
    assert 'RELEASE_PATH="download/$REQUESTED_VERSION"' in script
    assert '--version)' in script


def test_download_app_update_supports_local_zip_and_compat_local_only():
    """Local update paths should support explicit ZIPs and the legacy temp ZIP."""
    script = INSTALL_SCRIPT.read_text()

    assert '--local-zip)' in script
    assert 'LOCAL_ZIP_PATH="$2"' in script
    assert 'cp "$LOCAL_ZIP_PATH" "$ZIP_FILE"' in script
    assert 'Local only mode: expecting ZIP in /tmp/ghosthub_deploy.zip' in script


def test_handle_downloads_warns_when_local_mode_has_no_headscale_binary():
    """Local deployments should say plainly when Headscale is unavailable."""
    script = INSTALL_SCRIPT.read_text()

    assert 'echo "[!] Local Mode: headscale binary is missing or not executable at $APP_DIR/headscale"' in script


def test_handle_downloads_validates_downloaded_headscale_is_elf():
    """The installer should refuse to treat the shell install() function as /usr/bin/install."""
    script = INSTALL_SCRIPT.read_text()

    assert 'command install -m 755 "$hs_stage_bin" "$HS_BIN"' in script


def test_update_rebuilds_virtualenv_when_runtime_is_missing():
    """Updates must recover when the existing venv is missing gunicorn or pip."""
    script = INSTALL_SCRIPT.read_text()

    assert 'ensure_python_runtime() {' in script
    assert '[ ! -x "$APP_DIR/venv/bin/gunicorn" ]' in script
    assert 'echo "[*] Python runtime missing or incomplete, rebuilding virtualenv..."' in script
    assert 'if ensure_python_runtime "$NEW_HASH"; then' in script
    assert 'elif [ "$NEW_HASH" != "$OLD_HASH" ]; then' in script


def test_service_uses_python_module_gunicorn_entrypoint():
    """Systemd should invoke Gunicorn through the venv Python, not the wrapper script."""
    script = INSTALL_SCRIPT.read_text()

    assert 'ExecStart=$APP_DIR/venv/bin/python -m gunicorn -c $APP_DIR/gunicorn_config.py wsgi:app' in script


def test_update_rewrites_service_definitions_before_restart():
    """Updates must refresh the systemd unit instead of relying on a stale prior install."""
    script = INSTALL_SCRIPT.read_text()

    update_block = script.split('update() {', 1)[1].split('# ==== 5. MAIN ENTRY POINT ====', 1)[0]

    assert 'setup_services' in update_block
    assert update_block.index('setup_services') < update_block.index('sudo systemctl restart ghosthub')


def test_private_update_and_provisioning_strings_are_absent():
    """OSS installer must not depend on private OTA credentials or provisioning."""
    script = INSTALL_SCRIPT.read_text()

    private_strings = [
        "WORKER_URL",
        "CREDS_FILE",
        "device_secret",
        "provision_device.sh",
        "ghosthub-ota-auth",
    ]
    for private_string in private_strings:
        assert private_string not in script
