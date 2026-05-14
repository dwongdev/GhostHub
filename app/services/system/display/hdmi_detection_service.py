"""HDMI hardware detection and reinitialization ownership."""

import logging
import os
import re
import shutil
import subprocess

import gevent

logger = logging.getLogger(__name__)


def _check_hdmi_via_drm():
    """Read `/sys/class/drm/card*-HDMI*/status`.

    Returns (decided, connected):
      decided=True  -> kernel told us authoritatively; trust `connected`
      decided=False -> no readable DRM HDMI connector node; caller may fall back
    """
    import glob

    paths = set(glob.glob('/sys/class/drm/card*-HDMI*/status'))
    paths.update([
        '/sys/class/drm/card0-HDMI-A-1/status',
        '/sys/class/drm/card0-HDMI-A-2/status',
        '/sys/class/drm/card1-HDMI-A-1/status',
        '/sys/class/drm/card1-HDMI-A-2/status',
    ])

    any_readable = False
    any_connected = False
    for path in paths:
        try:
            with open(path, 'r') as handle:
                status = handle.read().strip().lower()
        except FileNotFoundError:
            continue
        except OSError as err:
            logger.debug("DRM status read failed for %s: %s", path, err)
            continue

        any_readable = True
        if status == 'connected':
            logger.info("HDMI connected via DRM sysfs (%s)", path)
            any_connected = True
            break
        logger.debug("DRM sysfs reports %s on %s", status, path)

    if any_readable:
        return True, any_connected
    return False, False


def _check_hdmi_via_vcgencmd():
    """Pi firmware probe.

    On the Pi firmware HDMI stack (which is what bullseye-arm64 with the
    `vc4-fkms-v3d` overlay falls back to), `vcgencmd display_power` is the
    only reliable signal: it reports 0 when no live HDMI pipeline exists
    (cable unplugged, or sink powered down), and 1 when a powered display is
    actually attached.

    Returns (decided, connected). `decided=False` means the tool is absent or
    returned no parseable value.
    """
    try:
        result = subprocess.run(
            ['vcgencmd', 'display_power'],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as err:
        logger.debug("vcgencmd unavailable: %s", err)
        return False, False
    except OSError as err:
        logger.debug("vcgencmd invocation failed: %s", err)
        return False, False

    output = result.stdout.strip()
    logger.debug("vcgencmd display_power output: %s", output)

    if 'display_power=0' in output:
        logger.info("HDMI inactive via vcgencmd (display_power=0)")
        return True, False
    if 'display_power=1' in output:
        logger.info("HDMI active via vcgencmd (display_power=1)")
        return True, True
    return False, False


def _check_hdmi_via_tvservice():
    """Legacy firmware probe for armhf bullseye where DRM sysfs is unavailable.

    Conservative parser: only return connected=True when tvservice reports an
    active mode line. A bare state code (e.g. `state 0x120001 [TV is off]`)
    is treated as disconnected, because on bullseye-arm64 with FKMS the
    firmware can report stale state bits even with no cable attached.

    Returns (decided, connected). `decided=False` means the tool is missing or
    produced no parseable output; the caller should not infer a state from this.
    """
    try:
        result = subprocess.run(
            ['tvservice', '-s'],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as err:
        logger.debug("tvservice unavailable: %s", err)
        return False, False
    except OSError as err:
        logger.debug("tvservice invocation failed: %s", err)
        return False, False

    output = result.stdout.strip()
    logger.debug("tvservice output: %s", output)
    lowered = output.lower()

    if 'unplugged' in lowered or 'no device' in lowered or 'tv is off' in lowered:
        logger.info("HDMI disconnected via tvservice (%s)", output)
        return True, False

    if 'state 0x40001' in output:
        logger.info("HDMI disconnected via tvservice (NTSC default state 0x40001)")
        return True, False

    if '@' in output and 'Hz' in output:
        logger.info("HDMI connected via tvservice (mode line)")
        return True, True

    if any(tok in output for tok in (' DVI ', ' HDMI ', ' CEA ', ' DMT ')):
        logger.info("HDMI connected via tvservice (mode descriptor)")
        return True, True

    logger.debug("tvservice output had no active-mode signal; not asserting connected")
    return False, False


def check_hdmi_status():
    """Return True when HDMI is physically connected and a live sink is present.

    Both shipped GhostHub images (bullseye armhf and bullseye arm64) target
    `dtoverlay=vc4-fkms-v3d` per install_ghosthub.sh. On FKMS the firmware
    HDMI stack owns the connection state, so `vcgencmd display_power` is the
    canonical signal across both architectures.

    Probe order (first authoritative result wins):
      1. `vcgencmd display_power` — primary signal on the supported FKMS
         images. 0 = no live pipeline; 1 = sink attached and powered.
      2. DRM sysfs `/sys/class/drm/card*-HDMI*/status` — defensive fallback
         for any future full-KMS image where vcgencmd is unavailable.
      3. `tvservice -s` — last resort; conservative parser that requires an
         active mode line before asserting connected.
    """
    if os.environ.get('GHOSTHUB_TESTING') == 'true':
        return False

    try:
        decided, connected = _check_hdmi_via_vcgencmd()
        if decided:
            return connected

        decided, connected = _check_hdmi_via_drm()
        if decided:
            return connected

        decided, connected = _check_hdmi_via_tvservice()
        if decided:
            return connected

        logger.warning("HDMI status unknown: no vcgencmd, DRM, or tvservice signal; reporting disconnected")
        return False
    except Exception as err:
        logger.error("Error checking HDMI status: %s", err)
        return False


def _tvservice_reinit():
    """Legacy firmware HDMI re-init (armhf bullseye). Returns True if it ran."""
    if shutil.which('tvservice') is None:
        return False

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
        logger.debug("HDMI status after tvservice re-init: %s", status)

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

        if shutil.which('fbset') is not None:
            subprocess.run(['fbset', '-depth', '8'], capture_output=True, timeout=5, check=False)
            subprocess.run(['fbset', '-depth', '16'], capture_output=True, timeout=5, check=False)

        logger.info("tvservice HDMI re-init completed")
        return True
    except subprocess.TimeoutExpired as err:
        logger.warning("tvservice re-init timed out: %s", err)
        return False
    except OSError as err:
        logger.warning("tvservice re-init failed: %s", err)
        return False


def _kms_reinit():
    """KMS HDMI re-init (arm64 bullseye, or armhf with full KMS).

    The kernel KMS driver owns hotplug — there is no firmware blob to kick.
    `udevadm trigger` on the DRM subsystem re-evaluates connectors, which is
    the cleanest "reinit" available without a custom DRM ioctl.

    Returns True if anything was triggered.
    """
    udevadm = shutil.which('udevadm')
    if udevadm is None:
        return False

    try:
        subprocess.run(
            [udevadm, 'trigger', '--subsystem-match=drm', '--action=change'],
            capture_output=True,
            timeout=5,
            check=False,
        )
        gevent.sleep(1)
        logger.info("KMS HDMI re-init completed (udevadm DRM trigger)")
        return True
    except subprocess.TimeoutExpired as err:
        logger.warning("udevadm DRM trigger timed out: %s", err)
        return False
    except OSError as err:
        logger.warning("udevadm DRM trigger failed: %s", err)
        return False


def force_hdmi_reinit():
    """Force HDMI re-initialization to clear hotplug glitches.

    Dispatches to whichever mechanism is available on this image:
    - armhf bullseye with the legacy firmware HDMI stack -> tvservice
    - arm64 bullseye / full-KMS armhf -> udevadm DRM retrigger

    Returns True if a reinit path actually ran, False if no mechanism was
    available on the host. The caller should not treat a False return as a
    fatal error — KMS hotplug normally needs no kick.
    """
    try:
        logger.info("Forcing HDMI re-initialization...")
        if _tvservice_reinit():
            return True
        if _kms_reinit():
            return True
        logger.info("HDMI re-init skipped: no tvservice and no udevadm available")
        return False
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
