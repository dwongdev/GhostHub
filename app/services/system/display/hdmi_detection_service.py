"""HDMI hardware detection and reinitialization ownership."""

import logging
import os
import re
import subprocess

import gevent

logger = logging.getLogger(__name__)


def check_hdmi_status():
    """Return True when HDMI appears physically connected."""
    if os.environ.get('GHOSTHUB_TESTING') == 'true':
        return False
    try:
        try:
            result = subprocess.run(
                ['tvservice', '-s'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.strip()
            logger.debug("tvservice output: %s", output)

            if 'unplugged' in output.lower() or 'no device' in output.lower():
                logger.info("HDMI cable physically disconnected (tvservice unplugged)")
                return False

            if 'state 0x40001' in output:
                logger.info("HDMI disconnected (NTSC default state 0x40001)")
                return False

            if 'state 0x' in output:
                logger.info("HDMI cable connected (detected via tvservice state code)")
                return True

            if '@' in output and 'Hz' in output:
                logger.info("HDMI connected (detected via tvservice resolution)")
                return True

            if 'DVI' in output or 'HDMI' in output or 'CEA' in output or 'DMT' in output:
                logger.info("HDMI connected (detected via tvservice mode)")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as err:
            logger.debug("tvservice check failed or not applicable: %s", err)

        import glob

        glob_files = glob.glob('/sys/class/drm/card*-HDMI*/status')
        fallback_files = [
            '/sys/class/drm/card0-HDMI-A-1/status',
            '/sys/class/drm/card0-HDMI-A-2/status',
            '/sys/class/drm/card1-HDMI-A-1/status',
            '/sys/class/drm/card1-HDMI-A-2/status',
        ]
        status_files = list(set(glob_files + fallback_files))
        for status_file in status_files:
            try:
                if os.path.exists(status_file):
                    with open(status_file, 'r') as handle:
                        status = handle.read().strip()
                        if status == 'connected':
                            logger.info("HDMI detected as 'connected' via %s", status_file)
                            return True
            except Exception as err:
                logger.debug("DRM status file check failed for %s: %s", status_file, err)

        try:
            env = {'DISPLAY': ':0'}
            result = subprocess.run(
                ['xrandr'],
                capture_output=True,
                text=True,
                timeout=2,
                env=env,
            )
            if ' connected ' in result.stdout:
                logger.info("HDMI detected via xrandr")
                return True
        except Exception as err:
            logger.debug("xrandr check failed: %s", err)

        try:
            result = subprocess.run(
                ['vcgencmd', 'display_power'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if 'display_power=1' in result.stdout:
                logger.info("HDMI detected via vcgencmd")
                return True
        except Exception as err:
            logger.debug("vcgencmd check failed: %s", err)

        logger.warning("All HDMI detection methods returned negative - HDMI appears disconnected")
        return False
    except Exception as err:
        logger.error("Error checking HDMI status: %s", err)
        return False


def force_hdmi_reinit():
    """Force HDMI re-initialization to fix hotplug issues."""
    try:
        logger.info("Forcing HDMI re-initialization...")

        try:
            subprocess.run(['tvservice', '-o'], capture_output=True, timeout=5, check=False)
            gevent.sleep(1)
            subprocess.run(['tvservice', '-p'], capture_output=True, timeout=5, check=False)
            gevent.sleep(2)

            result = subprocess.run(
                ['tvservice', '-s'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            status = result.stdout.strip()
            logger.debug("HDMI status after re-init: %s", status)

            if 'state 0x' in status:
                result = subprocess.run(
                    ['tvservice', '-m', 'CEA'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and 'mode' in result.stdout:
                    match = re.search(r'mode (\d+)', result.stdout)
                    if match:
                        mode = match.group(1)
                        logger.info("Setting preferred CEA mode: %s", mode)
                        subprocess.run(
                            ['tvservice', '-e', f'CEA {mode}'],
                            capture_output=True,
                            timeout=5,
                            check=False,
                        )

            logger.info("tvservice HDMI re-init completed")
        except (FileNotFoundError, subprocess.TimeoutExpired) as err:
            logger.debug("tvservice re-init failed: %s", err)

        try:
            subprocess.run(['fbset', '-depth', '8'], capture_output=True, timeout=5, check=False)
            subprocess.run(['fbset', '-depth', '16'], capture_output=True, timeout=5, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.info("HDMI re-initialization completed")
        return True
    except Exception as err:
        logger.error("Failed to force HDMI re-initialization: %s", err)
        return False


def wake_tv_via_cec(enabled):
    """Send CEC wake commands when CEC wake is enabled."""
    try:
        if not enabled:
            return False

        result = subprocess.run(['which', 'cec-client'], capture_output=True, timeout=2)
        if result.returncode != 0:
            return False

        commands = ['on 0', 'as 0', 'tx 10:04:41:01']
        for command in commands:
            subprocess.run(
                f'echo {command} | cec-client -s -d 1',
                shell=True,
                capture_output=True,
                timeout=3,
            )

        logger.info("CEC wake command sent to TV")
        return True
    except Exception as err:
        logger.debug("CEC wake failed: %s", err)
        return False
