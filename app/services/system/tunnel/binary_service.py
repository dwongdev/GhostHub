"""Tunnel binary and SSH-key ownership."""

import logging
import os
import platform
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


def find_cloudflared_path():
    """Cross-platform search for the cloudflared executable."""
    env_path = os.environ.get('CLOUDFLARED_PATH')
    if env_path and os.path.exists(env_path):
        logger.info("Found cloudflared from CLOUDFLARED_PATH: %s", env_path)
        return env_path

    exe_names = ['cloudflared']
    if platform.system() == 'Windows':
        exe_names.append('cloudflared.exe')

    for exe_name in exe_names:
        found = shutil.which(exe_name)
        if found:
            logger.info("Found cloudflared in PATH: %s", found)
            return found

    app_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    repo_root = os.path.dirname(app_dir)
    for base_dir, label in ((app_dir, "app dir"), (repo_root, "repo root")):
        for exe_name in exe_names:
            candidate = os.path.join(base_dir, exe_name)
            if os.path.exists(candidate):
                logger.info("Found cloudflared in %s: %s", label, candidate)
                return candidate

    system_paths = ['/usr/local/bin/cloudflared', '/usr/bin/cloudflared']
    if platform.system() == 'Windows':
        system_paths.extend([
            os.path.join(
                os.environ.get('ProgramFiles', ''),
                'cloudflared',
                'cloudflared.exe',
            ),
            os.path.join(
                os.environ.get('ProgramFiles(x86)', ''),
                'cloudflared',
                'cloudflared.exe',
            ),
        ])
    for path in system_paths:
        if path and os.path.exists(path):
            logger.info("Found cloudflared in system path: %s", path)
            return path

    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        for exe_name in exe_names:
            candidate = os.path.join(base_path, exe_name)
            if os.path.exists(candidate):
                logger.info("Found bundled cloudflared at: %s", candidate)
                return candidate

    logger.warning("cloudflared executable not found in any known location.")
    return None


def ensure_pinggy_ssh_key():
    """Ensure the Pinggy SSH key exists."""
    try:
        ssh_key_path = os.path.expanduser("~/.ssh/id_rsa_gh_pinggy")
        ssh_dir = os.path.dirname(ssh_key_path)
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, exist_ok=True)
            if sys.platform != 'win32':
                os.chmod(ssh_dir, 0o700)

        if os.path.exists(ssh_key_path):
            logger.info("Using existing SSH key: %s", ssh_key_path)
            return

        keygen_command = [
            "ssh-keygen", "-t", "rsa", "-b", "2048", "-N", "", "-f", ssh_key_path,
        ]
        logger.info("Generating SSH key for Pinggy: %s", ssh_key_path)
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        keygen_process = subprocess.run(
            keygen_command,
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags,
        )
        if keygen_process.returncode == 0:
            logger.info("SSH key created successfully")
            if sys.platform != 'win32':
                os.chmod(ssh_key_path, 0o600)
                if os.path.exists(ssh_key_path + ".pub"):
                    os.chmod(ssh_key_path + ".pub", 0o644)
            return

        logger.warning("ssh-keygen failed: %s", keygen_process.stderr)
    except Exception as err:
        logger.error("SSH key preparation failed: %s", err)
