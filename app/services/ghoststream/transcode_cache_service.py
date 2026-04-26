"""
Transcode Cache Service
-----------------------
Manages cached transcoded files in .ghosthub folder alongside original media.
Supports batch pre-transcoding and automatic cache cleanup.
"""
import os
import json
import hashlib
import logging
import gevent
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from specter import Service, registry

from .transcode_cache_runtime_store import transcode_cache_runtime_store

logger = logging.getLogger(__name__)

# Cache folder name (hidden on Linux/Mac)
CACHE_FOLDER = ".ghosthub"
CACHE_SUBFOLDER = "transcoded"
CACHE_INDEX_FILE = "cache_index.json"

# Default cache settings
DEFAULT_MAX_CACHE_SIZE_GB = 50  # Max cache size in GB
DEFAULT_MAX_CACHE_AGE_DAYS = 30  # Max age of cached files
DEFAULT_CACHE_CLEANUP_INTERVAL = 3600  # Check for cleanup every hour

def _transcode_cache_runtime_access(reader):
    """Read transcode-cache runtime state atomically."""
    return transcode_cache_runtime_store.access(reader)


def _update_transcode_cache_runtime(mutator):
    """Mutate transcode-cache runtime state atomically."""
    return transcode_cache_runtime_store.update(mutator)


def get_cache_path(category_path: str) -> Path:
    """Get the cache path for a category (creates .ghosthub/transcoded if needed)."""
    cache_dir = Path(category_path) / CACHE_FOLDER / CACHE_SUBFOLDER
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_index_path(category_path: str) -> Path:
    """Get the cache index file path for a category."""
    return Path(category_path) / CACHE_FOLDER / CACHE_INDEX_FILE


def _generate_cache_key(filename: str, resolution: str = "original", 
                        video_codec: str = "h264", audio_codec: str = "aac") -> str:
    """Generate a unique cache key based on transcode settings."""
    key_str = f"{filename}_{resolution}_{video_codec}_{audio_codec}"
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


def _load_cache_index(category_path: str) -> Dict[str, Dict]:
    """Load the cache index for a category."""
    index_path = get_cache_index_path(category_path)
    if index_path.exists():
        try:
            with open(index_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache index from {index_path}: {e}")
    return {}


def _save_cache_index(category_path: str, index: Dict[str, Dict]):
    """Save the cache index for a category."""
    index_path = get_cache_index_path(category_path)
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save cache index to {index_path}: {e}")


def get_cached_file(category_path: str, filename: str, 
                    resolution: str = "original",
                    video_codec: str = "h264",
                    audio_codec: str = "aac") -> Optional[str]:
    """
    Get the path to a cached transcoded file if it exists.
    
    Returns:
        Path to cached file if exists and valid, None otherwise
    """
    cache_key = _generate_cache_key(filename, resolution, video_codec, audio_codec)
    index = _load_cache_index(category_path)
    
    if cache_key in index:
        entry = index[cache_key]
        cached_path = Path(entry.get("path", ""))
        
        if cached_path.exists():
            # Update last accessed time
            entry["last_accessed"] = datetime.now().isoformat()
            _save_cache_index(category_path, index)
            logger.info(f"[TranscodeCache] Cache hit: {filename} -> {cached_path}")
            return str(cached_path)
        else:
            # Cached file missing, remove from index
            del index[cache_key]
            _save_cache_index(category_path, index)
            logger.warning(f"[TranscodeCache] Cached file missing, removed from index: {cached_path}")
    
    return None


def add_cached_file(category_path: str, filename: str, cached_path: str,
                    resolution: str = "original",
                    video_codec: str = "h264", 
                    audio_codec: str = "aac",
                    file_size: int = 0,
                    source_size: int = 0) -> bool:
    """
    Add a transcoded file to the cache index.
    
    Args:
        category_path: Path to the category folder
        filename: Original filename
        cached_path: Path to the cached transcoded file
        resolution: Resolution used for transcoding
        video_codec: Video codec used
        audio_codec: Audio codec used
        file_size: Size of cached file in bytes
        source_size: Size of original source file in bytes
    
    Returns:
        True if added successfully
    """
    cache_key = _generate_cache_key(filename, resolution, video_codec, audio_codec)
    index = _load_cache_index(category_path)
    
    index[cache_key] = {
        "original_filename": filename,
        "path": cached_path,
        "resolution": resolution,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "file_size": file_size,
        "source_size": source_size,
        "created_at": datetime.now().isoformat(),
        "last_accessed": datetime.now().isoformat()
    }
    
    _save_cache_index(category_path, index)
    logger.info(f"[TranscodeCache] Added to cache: {filename} ({resolution}) -> {cached_path}")
    return True


def remove_cached_file(category_path: str, filename: str,
                       resolution: str = "original",
                       video_codec: str = "h264",
                       audio_codec: str = "aac") -> bool:
    """Remove a file from the cache (both index and actual file)."""
    cache_key = _generate_cache_key(filename, resolution, video_codec, audio_codec)
    index = _load_cache_index(category_path)
    
    if cache_key in index:
        entry = index[cache_key]
        cached_path = Path(entry.get("path", ""))
        
        # Delete the actual file
        if cached_path.exists():
            try:
                cached_path.unlink()
                logger.info(f"[TranscodeCache] Deleted cached file: {cached_path}")
            except Exception as e:
                logger.error(f"[TranscodeCache] Failed to delete cached file {cached_path}: {e}")
        
        # Remove from index
        del index[cache_key]
        _save_cache_index(category_path, index)
        return True
    
    return False


def get_cache_stats(category_path: str) -> Dict[str, Any]:
    """Get cache statistics for a category."""
    index = _load_cache_index(category_path)
    
    total_size = 0
    file_count = 0
    
    for entry in index.values():
        file_size = entry.get("file_size", 0)
        if isinstance(file_size, int):
            total_size += file_size
        file_count += 1
    
    return {
        "file_count": file_count,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "entries": list(index.values())
    }


def cleanup_old_cache(category_path: str, max_age_days: int = DEFAULT_MAX_CACHE_AGE_DAYS) -> int:
    """
    Clean up cache files older than max_age_days.
    
    Returns:
        Number of files cleaned up
    """
    index = _load_cache_index(category_path)
    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed_count = 0
    
    keys_to_remove = []
    
    for cache_key, entry in index.items():
        last_accessed_str = entry.get("last_accessed")
        if last_accessed_str:
            try:
                last_accessed = datetime.fromisoformat(last_accessed_str)
                if last_accessed < cutoff:
                    keys_to_remove.append(cache_key)
            except ValueError:
                pass
    
    for cache_key in keys_to_remove:
        entry = index[cache_key]
        cached_path = Path(entry.get("path", ""))
        
        if cached_path.exists():
            try:
                cached_path.unlink()
                logger.info(f"[TranscodeCache] Cleaned up old file: {cached_path}")
            except Exception as e:
                logger.error(f"[TranscodeCache] Failed to delete old file {cached_path}: {e}")
        
        del index[cache_key]
        removed_count += 1
    
    if removed_count > 0:
        _save_cache_index(category_path, index)
    
    return removed_count


def cleanup_cache_by_size(category_path: str, max_size_gb: float = DEFAULT_MAX_CACHE_SIZE_GB) -> int:
    """
    Clean up cache if it exceeds max_size_gb, removing oldest accessed files first.
    
    Returns:
        Number of files cleaned up
    """
    index = _load_cache_index(category_path)
    max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
    
    # Calculate current size
    current_size = sum(entry.get("file_size", 0) for entry in index.values())
    
    if current_size <= max_size_bytes:
        return 0
    
    # Sort by last_accessed (oldest first)
    sorted_entries = sorted(
        index.items(),
        key=lambda x: x[1].get("last_accessed", "")
    )
    
    removed_count = 0
    
    for cache_key, entry in sorted_entries:
        if current_size <= max_size_bytes:
            break
        
        cached_path = Path(entry.get("path", ""))
        file_size = entry.get("file_size", 0)
        
        if cached_path.exists():
            try:
                cached_path.unlink()
                logger.info(f"[TranscodeCache] Cleaned up for size: {cached_path}")
            except Exception as e:
                logger.error(f"[TranscodeCache] Failed to delete {cached_path}: {e}")
        
        del index[cache_key]
        current_size -= file_size
        removed_count += 1
    
    if removed_count > 0:
        _save_cache_index(category_path, index)
    
    return removed_count


def get_transcoded_filename(original_filename: str, resolution: str = "original",
                           video_codec: str = "h264") -> str:
    """Generate a filename for the transcoded version."""
    base, ext = os.path.splitext(original_filename)
    # Always use mp4 for transcoded files (universal browser support)
    suffix = f"_{resolution}_{video_codec}" if resolution != "original" else f"_{video_codec}"
    return f"{base}{suffix}.mp4"


def batch_transcode_to_cache(category_path: str, files: List[str],
                             resolution: str = "original",
                             video_codec: str = "h264",
                             audio_codec: str = "aac",
                             category_id: str = None,
                             ghosthub_base_url: str = None,
                             on_progress: callable = None) -> Dict[str, Any]:
    """
    Batch transcode files and save to cache.
    This triggers GhostStream batch mode for each file.
    
    Args:
        category_path: Path to the category
        files: List of filenames to transcode
        resolution: Target resolution
        video_codec: Target video codec
        audio_codec: Target audio codec
        category_id: Category ID for building source URLs
        ghosthub_base_url: GhostHub base URL (e.g., http://192.168.4.1:5000)
        on_progress: Callback function(filename, progress, status)
    
    Returns:
        Dict with results for each file
    """
    from app.services import ghoststream_service
    from urllib.parse import quote
    
    results = {
        "total": len(files),
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "files": {}
    }
    
    cache_dir = get_cache_path(category_path)
    
    for i, filename in enumerate(files):
        # Check if already cached
        cached = get_cached_file(category_path, filename, resolution, video_codec, audio_codec)
        if cached:
            results["skipped"] += 1
            results["files"][filename] = {"status": "skipped", "path": cached}
            if on_progress:
                on_progress(filename, 100, "skipped")
            continue
        
        # Start batch transcode job
        source_path = os.path.join(category_path, filename)
        if not os.path.exists(source_path):
            results["failed"] += 1
            results["files"][filename] = {"status": "error", "error": "Source file not found"}
            continue
        
        # Generate output filename
        output_filename = get_transcoded_filename(filename, resolution, video_codec)
        output_path = str(cache_dir / output_filename)
        
        # Build source URL - GhostStream needs HTTP URL to fetch the file
        if category_id and ghosthub_base_url:
            source_url = f"{ghosthub_base_url}/media/{category_id}/{quote(filename)}"
        else:
            # Fallback - won't work if GhostStream is on different machine
            logger.warning(f"[TranscodeCache] No category_id/base_url provided, using file:// URL")
            source_url = f"file://{source_path}"
        
        try:
            # Use batch mode to transcode to file
            job = ghoststream_service.transcode(
                source=source_url,
                mode="batch",
                format="mp4",
                video_codec=video_codec,
                audio_codec=audio_codec,
                resolution=resolution,
                bitrate="auto",
                hw_accel="auto"
            )
            
            if not job or job.get("error"):
                results["failed"] += 1
                results["files"][filename] = {
                    "status": "error",
                    "error": job.get("error") if job else "Failed to start job"
                }
                continue
            
            # Wait for job to complete
            job_id = job.get("job_id")
            ready_job = ghoststream_service.wait_for_ready(job_id, timeout=600)
            
            if ready_job and ready_job.get("status") == "ready":
                # Download the transcoded file from GhostStream
                download_url = ready_job.get("download_url")
                if download_url:
                    # Copy to cache
                    import httpx
                    with httpx.Client(timeout=300) as client:
                        resp = client.get(download_url)
                        if resp.status_code == 200:
                            with open(output_path, 'wb') as f:
                                f.write(resp.content)
                            
                            file_size = os.path.getsize(output_path)
                            source_size = os.path.getsize(source_path)
                            
                            add_cached_file(
                                category_path, filename, output_path,
                                resolution, video_codec, audio_codec,
                                file_size, source_size
                            )
                            
                            results["completed"] += 1
                            results["files"][filename] = {
                                "status": "completed",
                                "path": output_path,
                                "size": file_size
                            }
                            if on_progress:
                                on_progress(filename, 100, "completed")
                            continue
            
            results["failed"] += 1
            results["files"][filename] = {
                "status": "error",
                "error": ready_job.get("error_message") if ready_job else "Timeout"
            }
            
        except Exception as e:
            logger.error(f"[TranscodeCache] Batch transcode error for {filename}: {e}")
            results["failed"] += 1
            results["files"][filename] = {"status": "error", "error": str(e)}
    
    return results


class TranscodeCacheRuntimeService(Service):
    """Own GhostStream transcode-cache cleanup lifecycle."""

    def __init__(self):
        super().__init__('ghoststream_transcode_cache_runtime')
        self._cleanup_greenlet = None

    def start_cleanup(
        self,
        category_paths: List[str] = None,
        max_age_days: int = DEFAULT_MAX_CACHE_AGE_DAYS,
        max_size_gb: float = DEFAULT_MAX_CACHE_SIZE_GB,
        interval: int = DEFAULT_CACHE_CLEANUP_INTERVAL,
    ):
        """Start background cleanup under Specter lifecycle ownership."""
        if self._cleanup_greenlet is not None and not self._cleanup_greenlet.dead:
            return False

        _update_transcode_cache_runtime(lambda state: state.update({
            "cleanup_running": True,
            "cleanup_category_paths": list(category_paths or []),
            "cleanup_max_age_days": max_age_days,
            "cleanup_max_size_gb": max_size_gb,
            "cleanup_interval": interval,
        }))

        self._cleanup_greenlet = self.spawn(self._cleanup_worker, label='transcode-cache-cleanup')
        logger.info("[TranscodeCache] Started background cleanup thread")
        return True

    def stop_cleanup(self):
        """Stop background cleanup."""
        _update_transcode_cache_runtime(lambda state: state.update({
            "cleanup_running": False,
        }))

        if self._cleanup_greenlet is not None:
            self.cancel_greenlet(self._cleanup_greenlet)
            self._cleanup_greenlet = None

        logger.info("[TranscodeCache] Stopped background cleanup thread")
        return True

    def on_stop(self):
        """Stop cleanup on service shutdown."""
        self.stop_cleanup()

    def _cleanup_worker(self):
        try:
            while _transcode_cache_runtime_access(
                lambda state: state.get("cleanup_running", False)
            ):
                try:
                    cleanup_settings = _transcode_cache_runtime_access(lambda state: {
                        "category_paths": list(state.get("cleanup_category_paths", [])),
                        "max_age_days": state.get("cleanup_max_age_days", DEFAULT_MAX_CACHE_AGE_DAYS),
                        "max_size_gb": state.get("cleanup_max_size_gb", DEFAULT_MAX_CACHE_SIZE_GB),
                        "interval": state.get("cleanup_interval", DEFAULT_CACHE_CLEANUP_INTERVAL),
                    })

                    for path in cleanup_settings["category_paths"]:
                        cleanup_old_cache(path, cleanup_settings["max_age_days"])
                        cleanup_cache_by_size(path, cleanup_settings["max_size_gb"])
                except Exception as e:
                    logger.error(f"[TranscodeCache] Cleanup error: {e}")

                gevent.sleep(cleanup_settings["interval"])
        finally:
            self._cleanup_greenlet = None
            _update_transcode_cache_runtime(lambda state: state.update({
                "cleanup_running": False,
            }))


def start_cleanup_thread(category_paths: List[str] = None,
                        max_age_days: int = DEFAULT_MAX_CACHE_AGE_DAYS,
                        max_size_gb: float = DEFAULT_MAX_CACHE_SIZE_GB,
                        interval: int = DEFAULT_CACHE_CLEANUP_INTERVAL):
    """Start background cleanup through the registered runtime owner."""
    return registry.require('ghoststream_transcode_cache_runtime').start_cleanup(
        category_paths=category_paths,
        max_age_days=max_age_days,
        max_size_gb=max_size_gb,
        interval=interval,
    )


def stop_cleanup_thread():
    """Stop background cleanup through the registered runtime owner."""
    return registry.require('ghoststream_transcode_cache_runtime').stop_cleanup()
