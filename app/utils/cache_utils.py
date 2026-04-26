"""
Cache Utilities
--------------
Provides caching mechanisms for media files to improve performance.
"""
# app/utils/cache_utils.py

import os
import time
import logging

logger = logging.getLogger(__name__)

# Small file threshold - files smaller than this will be served from memory
# Reduced from 8MB to 4MB for Pi 4 memory optimization
SMALL_FILE_THRESHOLD = 4 * 1024 * 1024  # 4MB

# Cache of recently accessed files to speed up repeated access
# Structure: {filepath: (last_access_time, file_data, file_size, mime_type, etag)}
small_file_cache = {}

# Cache of file metadata for large files (no open file descriptors)
# Structure: {filepath: (last_access_time, file_size, mime_type, etag, mtime)}
# Note: We cache only metadata, not file descriptors, to avoid concurrency issues.
# The OS kernel page cache + fadvise provides the real I/O performance benefit.
metadata_cache = {}

# Maximum number of metadata entries to cache
# Metadata is cheap (just a few integers/strings per entry)
MAX_METADATA_CACHE_SIZE = 100

# Maximum number of small files to hold in memory.
# Each entry can be up to SMALL_FILE_THRESHOLD (4MB), so cap tightly for LITE hardware.
MAX_SMALL_FILE_CACHE_SIZE = 50

# Cache expiry time in seconds
# Reduced from 10 minutes to 5 minutes for Pi 4 memory optimization
CACHE_EXPIRY = 300  # 5 minutes

def clean_caches():
    """Remove expired entries from file caches to prevent memory leaks."""
    current_time = time.time()
    
    # Clean small file cache
    expired_keys = [k for k, (access_time, _, _, _, _) in small_file_cache.items() 
                   if current_time - access_time > CACHE_EXPIRY]
    for k in expired_keys:
        del small_file_cache[k]
    
    # Clean metadata cache
    expired_metadata_keys = [k for k, (access_time, _, _, _, _) in metadata_cache.items() 
                            if current_time - access_time > CACHE_EXPIRY]
    for k in expired_metadata_keys:
        del metadata_cache[k]
    
    # If metadata cache is still too large, remove the least recently used ones
    if len(metadata_cache) > MAX_METADATA_CACHE_SIZE:
        # Sort by access time (oldest first)
        sorted_items = sorted(metadata_cache.items(), key=lambda x: x[1][0])
        # Remove oldest entries until we're under the limit
        for k, _ in sorted_items[:len(metadata_cache) - MAX_METADATA_CACHE_SIZE]:
            del metadata_cache[k]

def get_from_small_cache(filepath):
    """
    Get a file from the small file cache if it exists and has not expired.

    Args:
        filepath: Path to the file

    Returns:
        Tuple of (file_data, file_size, mime_type, etag) or None if not in cache or expired
    """
    if filepath in small_file_cache:
        access_time, file_data, file_size, mime_type, etag = small_file_cache[filepath]
        now = time.time()
        # Evict expired entries on read to prevent stale data
        if now - access_time > CACHE_EXPIRY:
            del small_file_cache[filepath]
            logger.debug(f"Evicted expired small file cache entry: {filepath}")
            return None
        # Update access time (LRU touch)
        small_file_cache[filepath] = (now, file_data, file_size, mime_type, etag)
        logger.debug(f"Serving small file from cache: {filepath}")
        return file_data, file_size, mime_type, etag
    return None

def add_to_small_cache(filepath, file_data, file_size, mime_type, etag):
    """
    Add a file to the small file cache.
    
    Args:
        filepath: Path to the file
        file_data: Binary data of the file
        file_size: Size of the file in bytes
        mime_type: MIME type of the file
        etag: ETag for the file
    """
    # Evict oldest entry when at capacity to prevent unbounded memory growth on LITE hardware
    if len(small_file_cache) >= MAX_SMALL_FILE_CACHE_SIZE:
        oldest_key = min(small_file_cache, key=lambda k: small_file_cache[k][0])
        del small_file_cache[oldest_key]

    small_file_cache[filepath] = (time.time(), file_data, file_size, mime_type, etag)
    logger.debug(f"Loaded small file into cache: {filepath} ({file_size} bytes)")

def get_from_metadata_cache(filepath):
    """
    Get file metadata from the cache if it exists and is still valid.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Tuple of (file_size, mime_type, etag, mtime) or None if not in cache or invalid
    """
    if filepath in metadata_cache:
        access_time, file_size, mime_type, etag, cached_mtime = metadata_cache[filepath]
        
        # Verify the file hasn't changed by checking mtime
        try:
            current_mtime = os.path.getmtime(filepath)
            if current_mtime == cached_mtime:
                # Update access time
                metadata_cache[filepath] = (time.time(), file_size, mime_type, etag, cached_mtime)
                logger.debug(f"Using cached metadata for: {filepath}")
                return file_size, mime_type, etag, cached_mtime
            else:
                # File has changed, invalidate cache entry
                logger.debug(f"Cached metadata stale for {filepath}, mtime changed")
                del metadata_cache[filepath]
        except Exception as e:
            logger.warning(f"Error validating cached metadata for {filepath}: {e}")
            # Remove invalid cache entry
            if filepath in metadata_cache:
                del metadata_cache[filepath]
    return None

def add_to_metadata_cache(filepath, file_size, mime_type, etag, mtime):
    """
    Add file metadata to the cache.
    
    Args:
        filepath: Path to the file
        file_size: Size of the file in bytes
        mime_type: MIME type of the file
        etag: ETag for the file
        mtime: File modification time
    """
    # If cache is full, clean it first
    if len(metadata_cache) >= MAX_METADATA_CACHE_SIZE:
        clean_caches()
    
    metadata_cache[filepath] = (time.time(), file_size, mime_type, etag, mtime)
    logger.debug(f"Cached metadata for: {filepath}")
