"""ZIP/archive download helpers for storage-backed transfers."""

import io
import logging
import os
import platform
import subprocess
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.system.system_stats_service import get_hardware_tier

logger = logging.getLogger(__name__)

STREAM_CHUNK_SIZE = 2 * 1024 * 1024
PIPE_SIZE_LIMIT = 4 * 1024 * 1024 * 1024
MAX_ZIP_PART_SIZE = 200 * 1024 * 1024


def _storage_io():
    from app.services.storage import storage_io_service

    return storage_io_service


def _is_managed_storage_path(path: str) -> bool:
    """Return True when a path belongs to a mounted GhostHub storage root."""
    from app.services.storage.storage_drive_service import is_managed_storage_path

    return is_managed_storage_path(path)


def stream_zip_from_pipe(file_paths: List[str], folder_path: str):
    """Stream a ZIP directly from the system zip command when possible."""
    if platform.system() == 'Windows':
        yield from _stream_zip_windows_fallback(file_paths, folder_path)
        return

    try:
        cmd = ['zip', '-0', '-q', '-j', '-']
        cmd.extend(file_paths)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=folder_path,
            close_fds=True,
        )

        while True:
            chunk = process.stdout.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

        process.wait()
        if process.returncode != 0:
            stderr = process.stderr.read().decode()
            logger.error("zip command failed: %s", stderr)
    except FileNotFoundError:
        logger.error("zip command not found - install with: sudo apt install zip")
    except Exception as exc:
        logger.error("Error streaming ZIP: %s", exc)


def stream_zip_from_temp_file(file_paths: List[str], folder_path: str):
    """Create a ZIP in a temp file and then stream it."""
    zip_path = None
    try:
        fd, zip_path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)

        if platform.system() != 'Windows':
            try:
                os.unlink(zip_path)
                cmd = ['zip', '-0', '-q', '-j', zip_path]
                cmd.extend(file_paths)

                result = subprocess.run(
                    cmd,
                    cwd=folder_path,
                    capture_output=True,
                    timeout=600,
                )

                if result.returncode != 0:
                    logger.error("zip command failed: %s", result.stderr.decode())
                    return
            except Exception as exc:
                logger.error("System zip to file failed: %s", exc)
                return
        else:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zip_file:
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        zip_file.write(file_path, os.path.basename(file_path))

        if os.path.exists(zip_path):
            with open(zip_path, 'rb') as handle:
                while True:
                    chunk = handle.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
    except Exception as exc:
        logger.error("Temp file ZIP error: %s", exc)
    finally:
        if zip_path:
            try:
                os.unlink(zip_path)
            except OSError:
                pass


def _stream_zip_windows_fallback(file_paths: List[str], folder_path: str):
    """Windows fallback using temp-file ZIP creation."""
    yield from stream_zip_from_temp_file(file_paths, folder_path)


def stream_folder_zip(folder_path: str):
    """Stream a folder as a ZIP, choosing pipe or temp-file mode by size."""
    if not _is_managed_storage_path(folder_path):
        return
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return

    files_list = get_folder_file_list(folder_path)
    if not files_list:
        return

    file_paths = [file_path for file_path, _, _ in files_list]
    total_size = sum(size for _, _, size in files_list)

    if total_size < PIPE_SIZE_LIMIT:
        logger.info("ZIP streaming via pipe (%s)", _storage_io().format_bytes(total_size))
        yield from stream_zip_from_pipe(file_paths, folder_path)
        return

    logger.info("ZIP streaming via temp file (%s)", _storage_io().format_bytes(total_size))
    yield from stream_zip_from_temp_file(file_paths, folder_path)


def get_max_zip_part_size() -> int:
    """Return a hardware-aware ZIP part size budget."""
    if not get_runtime_config_value('AUTO_OPTIMIZE_FOR_HARDWARE'):
        return 200 * 1024 * 1024

    tier = get_hardware_tier()
    if tier == 'PRO':
        return 1024 * 1024 * 1024
    if tier == 'STANDARD':
        return 512 * 1024 * 1024
    return 200 * 1024 * 1024


def get_folder_zip_info(folder_path: str) -> Tuple[bool, str, int, int, List[dict]]:
    """Return ZIP/download metadata for a folder."""
    try:
        if not _is_managed_storage_path(folder_path):
            return False, "Access denied", 0, 0, []
        if not os.path.exists(folder_path):
            return False, "Folder not found", 0, 0, []
        if not os.path.isdir(folder_path):
            return False, "Path is not a folder", 0, 0, []

        folder_name = os.path.basename(folder_path)
        files_list = get_folder_file_list(folder_path)
        if not files_list:
            return True, folder_name, 0, 0, []

        total_size = sum(size for _, _, size in files_list)
        parts = split_files_into_parts(files_list, max_size=get_max_zip_part_size())

        parts_info = []
        for part in parts:
            part_size = sum(size for _, _, size in part)
            is_single = len(part) == 1
            part_info = {
                'size': part_size,
                'size_formatted': _storage_io().format_bytes(part_size),
                'is_single': is_single,
                'file_count': len(part),
            }
            if is_single:
                file_path, arcname, _ = part[0]
                part_info['filename'] = arcname
                part_info['filepath'] = file_path
            parts_info.append(part_info)

        return True, folder_name, total_size, len(parts), parts_info
    except Exception as exc:
        logger.error("Error getting folder info: %s", exc)
        return False, str(exc), 0, 0, []


def get_folder_file_list(folder_path: str) -> List[Tuple[str, str, int]]:
    """Return immediate visible files in a folder with sizes."""
    files_list = []

    try:
        if not _is_managed_storage_path(folder_path):
            logger.warning("Rejected folder file listing outside managed storage roots: %s", folder_path)
            return files_list
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if entry.name.startswith('.') or not entry.is_file(follow_symlinks=False):
                    continue
                try:
                    files_list.append((entry.path, entry.name, entry.stat().st_size))
                except OSError:
                    pass
    except OSError:
        pass

    return files_list


def split_files_into_parts(
    files_list: List[Tuple[str, str, int]],
    max_size: int = MAX_ZIP_PART_SIZE,
) -> List[List[Tuple[str, str, int]]]:
    """Split files into size-bounded download parts."""
    parts = []
    current_part = []
    current_size = 0

    for file_path, arcname, file_size in files_list:
        if file_size > max_size:
            if current_part:
                parts.append(current_part)
                current_part = []
                current_size = 0
            parts.append([(file_path, arcname, file_size)])
        elif current_size + file_size > max_size:
            if current_part:
                parts.append(current_part)
            current_part = [(file_path, arcname, file_size)]
            current_size = file_size
        else:
            current_part.append((file_path, arcname, file_size))
            current_size += file_size

    if current_part:
        parts.append(current_part)

    return parts if parts else [[]]


def stream_folder_zip_part(folder_path: str, part_num: int, total_parts: int):
    """Stream a specific ZIP part from a folder download."""
    if not _is_managed_storage_path(folder_path):
        return
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return

    files_list = get_folder_file_list(folder_path)
    parts = split_files_into_parts(files_list, max_size=get_max_zip_part_size())
    if part_num < 1 or part_num > len(parts):
        return

    files_to_zip = parts[part_num - 1]
    file_paths = [file_path for file_path, _, _ in files_to_zip]
    part_size = sum(size for _, _, size in files_to_zip)

    if part_size < PIPE_SIZE_LIMIT:
        yield from stream_zip_from_pipe(file_paths, folder_path)
        return

    yield from stream_zip_from_temp_file(file_paths, folder_path)


def stream_zip_from_file_list(file_list: List[Tuple[str, str]]):
    """Stream a ZIP for an arbitrary list of files."""
    if not file_list:
        return

    total_size = 0
    valid_files = []
    for file_path, arcname in file_list:
        if not _is_managed_storage_path(file_path):
            continue
        if not os.path.isfile(file_path):
            continue
        try:
            total_size += os.path.getsize(file_path)
            valid_files.append((file_path, arcname))
        except OSError:
            pass

    if not valid_files:
        return

    if total_size < PIPE_SIZE_LIMIT:
        logger.info(
            "Gallery ZIP streaming via pipe (%s, %s files)",
            _storage_io().format_bytes(total_size),
            len(valid_files),
        )
        yield from _stream_zip_file_list_pipe(valid_files)
        return

    logger.info(
        "Gallery ZIP streaming via temp file (%s, %s files)",
        _storage_io().format_bytes(total_size),
        len(valid_files),
    )
    yield from _stream_zip_file_list_temp(valid_files)


def _stream_zip_file_list_pipe(file_list: List[Tuple[str, str]]):
    """Stream a smaller file list ZIP from memory."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_STORED) as zip_file:
        for file_path, arcname in file_list:
            try:
                zip_file.write(file_path, arcname)
            except Exception as exc:
                logger.warning("Error adding %s to zip: %s", file_path, exc)

    zip_buffer.seek(0)
    while True:
        chunk = zip_buffer.read(STREAM_CHUNK_SIZE)
        if not chunk:
            break
        yield chunk


def _stream_zip_file_list_temp(file_list: List[Tuple[str, str]]):
    """Stream a larger file list ZIP from a temp file."""
    zip_path = None
    try:
        fd, zip_path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zip_file:
            for file_path, arcname in file_list:
                try:
                    zip_file.write(file_path, arcname)
                except Exception as exc:
                    logger.warning("Error adding %s to zip: %s", file_path, exc)

        if os.path.exists(zip_path):
            with open(zip_path, 'rb') as handle:
                while True:
                    chunk = handle.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
    except Exception as exc:
        logger.error("Temp file ZIP error: %s", exc)
    finally:
        if zip_path:
            try:
                os.unlink(zip_path)
            except OSError:
                pass


def stream_file_direct(file_path: str):
    """Stream a single file directly without ZIP overhead."""
    if not _is_managed_storage_path(file_path):
        return
    if not os.path.isfile(file_path):
        return

    try:
        with open(file_path, 'rb') as handle:
            while True:
                chunk = handle.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
    except Exception as exc:
        logger.error("Error streaming file %s: %s", file_path, exc)


def get_file_info(file_path: str) -> Optional[Dict]:
    """Return file metadata for direct-download responses."""
    if not _is_managed_storage_path(file_path):
        return None
    if not os.path.isfile(file_path):
        return None

    try:
        stat = os.stat(file_path)
        return {
            'name': os.path.basename(file_path),
            'size': stat.st_size,
            'size_formatted': _storage_io().format_bytes(stat.st_size),
            'path': file_path,
        }
    except OSError:
        return None
