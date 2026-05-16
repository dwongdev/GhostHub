"""Drive discovery and mount-monitoring workflows for storage domains."""

import hashlib
import logging
import os
import platform
import shutil
from typing import Dict, List, Optional

import gevent
from specter import Service, registry

try:
    import pyudev
except ImportError:
    pyudev = None

from app.services.storage.storage_io_service import is_path_within, is_path_writable
from app.services.storage.storage_runtime_store import storage_runtime_store

logger = logging.getLogger(__name__)

LINUX_MOUNT_ROOTS = ['/media', '/media/ghost', '/media/usb', '/mnt']
HIDDEN_PATHS = [
    '/media/ghost',
    '/media/usb',
    '/media',
    '/mnt',
    '/',
    '/boot',
    '/home',
]
WINDOWS_DRIVES = ['D:', 'E:', 'F:', 'G:', 'H:']


def _storage_runtime_access(reader):
    return storage_runtime_store.access(reader)


def _update_storage_runtime(mutator):
    return storage_runtime_store.update(mutator)


class StorageDriveRuntimeService(Service):
    """Own storage drive cache refresh and mount-monitor lifecycle."""

    def __init__(self):
        super().__init__('storage_drive_runtime')
        self.priority = 50
        self._monitor_greenlet = None

    def get_storage_drives(self, force_refresh: bool = False) -> List[Dict]:
        """Return cached storage drives and schedule refresh/monitor startup as needed."""
        drive_cache = _storage_runtime_access(lambda state: list(state.get('drive_cache', [])))
        if force_refresh or not drive_cache:
            self.refresh_drive_cache_async()

        self.ensure_monitoring()
        return [dict(drive) for drive in drive_cache]

    def get_storage_drives_fresh(self) -> List[Dict]:
        """Perform a synchronous drive scan and update the runtime cache."""
        drives = _scan_drives()
        _update_storage_runtime(lambda draft: draft.__setitem__('drive_cache', list(drives)))
        _update_mount_snapshot(drives)
        return [dict(drive) for drive in drives]

    def has_mounts_changed(self) -> bool:
        """Check whether USB mounts changed since the last read."""
        self.refresh_drive_cache_async()
        changed = False

        def _consume_mount_change(draft):
            nonlocal changed
            changed = bool(draft.get('mount_change_detected', False))
            draft['mount_change_detected'] = False

        _update_storage_runtime(_consume_mount_change)
        return changed

    def get_current_mount_paths(self) -> set:
        """Return the set of currently visible mount paths."""
        drives = self.get_storage_drives(force_refresh=False)
        return {drive['path'] for drive in drives}

    def refresh_drive_cache_async(self) -> bool:
        """Start an owned async drive-cache refresh when one is not already running."""
        scan_started = False

        def _mark_scan_started(draft):
            nonlocal scan_started
            if draft.get('drive_scan_in_progress', False):
                return
            draft['drive_scan_in_progress'] = True
            scan_started = True

        _update_storage_runtime(_mark_scan_started)
        if not scan_started:
            return False

        self.spawn(self._scan_worker, label='storage-drive-scan')
        return True

    def ensure_monitoring(self) -> bool:
        """Start udev-backed monitoring once under Specter ownership."""
        if pyudev is None:
            return False

        monitoring_started = False

        def _mark_monitoring(draft):
            nonlocal monitoring_started
            if draft.get('monitoring', False):
                return
            draft['monitoring'] = True
            monitoring_started = True

        _update_storage_runtime(_mark_monitoring)
        if not monitoring_started:
            return False

        self._monitor_greenlet = self.spawn(self._monitor_udev, label='storage-drive-monitor')
        logger.info("USB storage monitoring greenlet started")
        return True

    def on_stop(self):
        """Stop storage drive monitoring on Specter shutdown."""
        _update_storage_runtime(
            lambda draft: draft.update({
                'monitoring': False,
                'drive_scan_in_progress': False,
            }),
        )
        if self._monitor_greenlet is not None:
            self.cancel_greenlet(self._monitor_greenlet)
            self._monitor_greenlet = None

    def _scan_worker(self):
        try:
            drives = _scan_drives()
            _update_storage_runtime(
                lambda draft: draft.__setitem__('drive_cache', list(drives)),
            )
            _update_mount_snapshot(drives)
        finally:
            _update_storage_runtime(
                lambda draft: draft.__setitem__('drive_scan_in_progress', False),
            )

    def _monitor_udev(self):
        """Monitor udev events for USB hotplug."""
        try:
            import gevent.select

            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem='block')
            monitor.start()

            logger.info("Started gevent-friendly udev monitoring for USB drives")

            while _storage_runtime_access(lambda state: state.get('monitoring', False)):
                gevent.select.select([monitor], [], [])
                for device in iter(lambda: monitor.poll(timeout=0), None):
                    if device.action in ('add', 'remove', 'change'):
                        is_usb = device.get('ID_BUS') == 'usb' or 'ID_USB_DRIVER' in device
                        is_storage = device.get('DEVTYPE') in ('partition', 'disk')
                        if is_usb or is_storage:
                            logger.info(
                                "Block event detected: %s on %s (USB: %s, Storage: %s)",
                                device.action,
                                device.sys_name,
                                is_usb,
                                is_storage,
                            )
                            gevent.sleep(3 if device.action == 'remove' else 1)
                            self.refresh_drive_cache_async()
        except Exception as exc:
            logger.error("USB Monitor Error: %s", exc)
            _update_storage_runtime(lambda draft: draft.__setitem__('monitoring', False))


def get_storage_drives(force_refresh: bool = False) -> List[Dict]:
    """Return cached storage drives through the registered runtime owner."""
    return registry.require('storage_drive_runtime').get_storage_drives(force_refresh)


def get_storage_drives_fresh() -> List[Dict]:
    """Perform a synchronous drive scan through the registered runtime owner."""
    return registry.require('storage_drive_runtime').get_storage_drives_fresh()


def has_mounts_changed() -> bool:
    """Check whether USB mounts changed through the registered runtime owner."""
    return registry.require('storage_drive_runtime').has_mounts_changed()


def get_current_mount_paths() -> set:
    """Return current mount paths through the registered runtime owner."""
    return registry.require('storage_drive_runtime').get_current_mount_paths()


def get_current_mount_paths_fresh() -> set:
    """Return current mount paths from a direct storage scan without registry access."""
    drives = _scan_drives()
    return {drive['path'] for drive in drives}


def get_storage_drive_for_path(path: str, require_writable: bool = False) -> Optional[Dict]:
    """Return the mounted storage drive that owns *path*, if any."""
    if not path:
        return None

    drives = get_storage_drives(force_refresh=False)
    if not drives:
        drives = get_storage_drives_fresh()

    best_match = None
    best_match_len = -1
    for drive in drives:
        drive_path = drive.get('path')
        if not drive_path:
            continue
        if require_writable and not drive.get('writable', False):
            continue
        if not is_path_within(drive_path, path):
            continue

        drive_real = os.path.realpath(drive_path)
        if len(drive_real) > best_match_len:
            best_match = dict(drive)
            best_match_len = len(drive_real)

    return best_match


def is_managed_storage_path(path: str, require_writable: bool = False) -> bool:
    """Return True when *path* belongs to a mounted GhostHub storage root."""
    return get_storage_drive_for_path(path, require_writable=require_writable) is not None


def _scan_drives(include_hidden_only: bool = True) -> List[Dict]:
    if os.environ.get('GHOSTHUB_TESTING') == 'true':
        return []
    if platform.system() == 'Windows':
        return _get_windows_drives()
    return _get_linux_drives(include_hidden_only=include_hidden_only)


def _update_mount_snapshot(drives: List[Dict]):
    """Update mount snapshot and trigger cache/index cleanup on mount changes."""
    current_paths = {drive['path'] for drive in drives}
    mount_data = '|'.join(sorted(current_paths))
    new_hash = hashlib.md5(mount_data.encode()).hexdigest()

    should_notify = False
    mounted_paths = []
    unmounted_paths = []

    def _merge_mount_state(draft):
        nonlocal should_notify, mounted_paths, unmounted_paths
        if new_hash != draft.get('last_mount_hash'):
            old_hash = draft.get('last_mount_hash')
            old_snapshot = draft.get('last_mount_snapshot') or {}
            logger.info("USB mount state changed. Old: %s, New: %s", old_hash, new_hash)
            draft['last_mount_hash'] = new_hash
            draft['last_mount_snapshot'] = {drive['path']: drive['name'] for drive in drives}
            old_paths = set(old_snapshot.keys())
            mounted_paths = list(current_paths - old_paths)
            unmounted_paths = list(old_paths - current_paths)
            should_notify = old_hash is not None
            draft['mount_change_detected'] = should_notify

    _update_storage_runtime(_merge_mount_state)

    if not should_notify:
        return

    try:
        from specter import bus
        from app.constants import BUS_EVENTS

        # Decoupling: Storage emits the event; Media domain listens and performs cleanup/invalidation.
        # See MediaStorageEventHandlerService._handle_mount_changed for the cleanup logic.
        bus.emit(BUS_EVENTS['STORAGE_MOUNT_CHANGED'], {
            'mounted_paths': mounted_paths,
            'unmounted_paths': unmounted_paths
        })
    except Exception as exc:
        logger.error("Could not emit STORAGE_MOUNT_CHANGED: %s", exc)


def _is_hidden_path(path: str) -> bool:
    normalized = os.path.normpath(path)
    for hidden in HIDDEN_PATHS:
        if normalized == os.path.normpath(hidden):
            return True
    return False


def _get_usb_device_info() -> Dict[str, Dict]:
    """Map mount paths to USB device metadata (device_key, usb_port).

    Uses pyudev to enumerate USB block devices.  Returns an empty dict on
    non-Linux or when pyudev is unavailable.
    """
    if pyudev is None or platform.system() != 'Linux':
        return {}

    result: Dict[str, Dict] = {}

    # Build device-node → mount-point map from /proc/mounts.
    # Mount paths with spaces are encoded as \040 (octal escapes).
    dev_to_mount: Dict[str, str] = {}
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mount_path = parts[1].encode('raw_unicode_escape').decode('unicode_escape')
                    dev_to_mount[parts[0]] = mount_path
    except Exception:
        return {}

    # Pi 4 USB port topology: map sysfs hub-port segments to physical positions.
    # USB 2.0-only ports sit behind an internal hub (1-1.x); USB 3.0 ports
    # appear as root-hub ports (2-x).  Only entries verified against the
    # standard Pi 4B VL805 layout are included — unrecognised topologies
    # gracefully return None.
    _PI4_PORT_MAP = {
        '1-1.1': 0,  # top-left  (USB 2.0 only)
        '1-1.2': 1,  # bottom-left (USB 2.0 only)
        '2-1': 2,    # top-right  (USB 3.0)
        '2-2': 3,    # bottom-right (USB 3.0)
    }

    def _parse_usb_port(device_path: str):
        """Extract physical Pi 4 USB port index from a sysfs device path."""
        for segment, port in _PI4_PORT_MAP.items():
            if f'/{segment}/' in device_path or device_path.endswith(f'/{segment}'):
                return port
        return None

    try:
        context = pyudev.Context()
        for device in context.list_devices(subsystem='block'):
            devtype = device.get('DEVTYPE')
            if devtype not in ('partition', 'disk'):
                continue
            if device.get('ID_BUS') != 'usb' and 'ID_USB_DRIVER' not in device:
                continue

            dev_node = device.device_node
            if not dev_node:
                continue

            mount_path = dev_to_mount.get(dev_node)
            if not mount_path:
                continue

            # Determine a stable device key
            device_key = (
                device.get('ID_SERIAL_SHORT')
                or device.get('ID_FS_UUID')
                or f"{device.get('ID_VENDOR_ID', '0000')}:{device.get('ID_MODEL_ID', '0000')}"
            )

            usb_port = _parse_usb_port(device.device_path or '')

            result[mount_path] = {
                'device_key': device_key,
                'usb_port': usb_port,
            }
    except Exception as exc:
        logger.debug("Could not enumerate USB device info: %s", exc)

    return result


def filter_hidden_only_drives(drives: List[Dict]) -> List[Dict]:
    """Filter out drives whose visible contents are entirely hidden categories."""
    visible_drives = []
    for drive in drives:
        if _all_subfolders_hidden(drive['path']):
            continue
        visible_drives.append(dict(drive))
    return visible_drives


def _get_linux_drives(include_hidden_only: bool = True) -> List[Dict]:
    drives = []
    seen_paths = set()

    usb_device_info = _get_usb_device_info()

    ghosthub_roots = ['/media/ghost', '/media/usb']
    general_roots = ['/media', '/mnt']

    def add_drive_if_valid(path, name):
        if path in seen_paths or _is_hidden_path(path):
            return False

        dev_info = usb_device_info.get(path, {})
        drive_info = _get_drive_info(
            path, name,
            device_key=dev_info.get('device_key'),
            usb_port=dev_info.get('usb_port'),
        )
        if drive_info:
            seen_paths.add(path)
            if not include_hidden_only and _all_subfolders_hidden(path):
                return False
            drives.append(drive_info)
            return True
        return False

    for root in ghosthub_roots:
        if not os.path.exists(root):
            continue
        try:
            parent_dev = os.stat(root).st_dev
        except Exception:
            continue
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    if entry.is_dir() and not entry.name.startswith('.'):
                        try:
                            entry_dev = os.stat(entry.path).st_dev
                            if entry_dev == parent_dev:
                                logger.debug("Skipping unmounted folder: %s", entry.path)
                                continue
                        except Exception:
                            pass
                        add_drive_if_valid(entry.path, entry.name)
        except Exception as exc:
            logger.debug("Error scanning GhostHub root %s: %s", root, exc)

    for root in general_roots:
        if not os.path.exists(root):
            continue
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    if not entry.is_dir() or entry.name.startswith('.'):
                        continue
                    if os.ismount(entry.path):
                        add_drive_if_valid(entry.path, entry.name)
                    if entry.name in ['pi', 'ghost'] or entry.path in ghosthub_roots:
                        try:
                            with os.scandir(entry.path) as sub_entries:
                                for sub in sub_entries:
                                    if sub.is_dir() and not sub.name.startswith('.') and os.ismount(sub.path):
                                        add_drive_if_valid(sub.path, sub.name)
                        except Exception:
                            pass
        except Exception as exc:
            logger.debug("Error scanning general root %s: %s", root, exc)

    return drives


def _all_subfolders_hidden(path: str) -> bool:
    from app.services.media.hidden_content_service import get_hidden_category_ids

    path_normalized = os.path.normpath(path)
    usb_roots = ['/media', '/media/usb', '/media/ghost', '/mnt']
    base_root = None
    for root in usb_roots:
        root_normalized = os.path.normpath(root)
        if path_normalized.startswith(root_normalized + os.sep) or path_normalized == root_normalized:
            base_root = root_normalized
            break

    if not base_root:
        return False

    try:
        hidden_category_ids = set(get_hidden_category_ids())
    except Exception as exc:
        logger.error("Error fetching hidden categories: %s", exc)
        hidden_category_ids = set()

    try:
        has_visible = False
        has_subdirs = False
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir() and not entry.name.startswith('.'):
                    if entry.name.lower() in [
                        '$recycle.bin',
                        'system volume information',
                        '.ghosthub',
                        '.ghosthub_uploads',
                        'ghosthubbackups',
                    ]:
                        continue
                    has_subdirs = True
                    try:
                        entry_path_normalized = os.path.normpath(entry.path)
                        relative_path = os.path.relpath(entry_path_normalized, base_root)
                        path_parts = relative_path.replace(os.sep, '/').split('/')
                        category_id = 'auto::' + '::'.join(part for part in path_parts if part and part != '.')
                        if category_id not in hidden_category_ids:
                            has_visible = True
                            break
                    except Exception as exc:
                        logger.debug("Error checking category visibility for %s: %s", entry.name, exc)
                        has_visible = True
                        break
        return has_subdirs and not has_visible
    except Exception:
        return False


def _get_windows_drives() -> List[Dict]:
    drives = []
    for drive_letter in WINDOWS_DRIVES:
        drive_path = drive_letter + '\\'
        if os.path.exists(drive_path):
            try:
                drive_info = _get_drive_info(drive_path, drive_letter)
                if drive_info:
                    drives.append(drive_info)
            except Exception as exc:
                logger.debug("Error getting info for %s: %s", drive_letter, exc)
    return drives


def _get_drive_info(path: str, name: str, device_key: str = None, usb_port: int = None) -> Optional[Dict]:
    try:
        stat = shutil.disk_usage(path)
        writable = is_path_writable(path)
        if not writable and platform.system() != 'Windows':
            writable = _try_remount_rw(path)

        drive_id = path.replace('/', '_').replace('\\', '_').replace(':', '').strip('_')
        info = {
            'id': drive_id,
            'name': name,
            'path': path,
            'total': stat.total,
            'used': stat.used,
            'free': stat.free,
            'percent_used': round((stat.used / stat.total) * 100, 1) if stat.total > 0 else 0,
            'writable': writable,
        }
        # Always provide a device_key so labels can be assigned.  Prefer
        # the hardware-derived key from pyudev; fall back to a stable hash
        # of the mount path (works on macOS / Windows / missing pyudev).
        info['device_key'] = device_key or hashlib.md5(path.encode()).hexdigest()
        if usb_port is not None:
            info['usb_port'] = usb_port
        return info
    except (OSError, PermissionError) as exc:
        logger.debug("Cannot get disk usage for %s: %s", path, exc)
        return None


def _try_remount_rw(path: str) -> bool:
    import subprocess

    try:
        result = subprocess.run(
            ['sudo', 'mount', '-o', 'remount,rw', path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("Successfully remounted %s as read-write", path)
            return is_path_writable(path)

        logger.warning("Failed to remount %s: %s", path, result.stderr)
        logger.info("Drive %s may need filesystem repair (fsck)", path)
    except subprocess.TimeoutExpired:
        logger.warning("Timeout trying to remount %s", path)
    except Exception as exc:
        logger.debug("Cannot remount %s: %s", path, exc)

    return False
