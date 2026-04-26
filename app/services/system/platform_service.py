"""Shared platform-detection helpers for system services."""


def is_raspberry_pi() -> bool:
    """Return True when the current host looks like a Raspberry Pi."""
    try:
        with open('/proc/cpuinfo', 'r', encoding='utf-8') as handle:
            cpuinfo = handle.read()
    except OSError:
        return False

    return 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo
