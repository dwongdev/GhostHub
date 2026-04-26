"""
Streaming Service
---------------
Provides optimized streaming capabilities for media files.
"""
# app/services/streaming_service.py

import os
import io
import time
import gevent
import random
import logging
import traceback
import socket
from flask import Response, request, jsonify
from app.services.system.network_detection_service import is_tailscale_connection
from app.services.core.runtime_config_service import get_runtime_config_value
from app.utils.media_utils import get_mime_type
from app.utils.cache_utils import (
    get_from_small_cache, add_to_small_cache,
    get_from_metadata_cache, add_to_metadata_cache,
    clean_caches, SMALL_FILE_THRESHOLD
)
import app.services.system.rate_limit_service as rate_limit_service

logger = logging.getLogger(__name__)

# Note: We rely on gevent's timeout mechanisms instead of global socket timeout
# to avoid affecting other parts of the application (discovery, GhostStream, etc.)

# ============== Kernel Readahead Support (posix_fadvise) ==============
# Use os.posix_fadvise if available (available in Python 3.3+ on Unix)
# This is much safer than manual ctypes which can cause SEGV on 32-bit ARM
HAS_FADVISE = hasattr(os, 'posix_fadvise')

if HAS_FADVISE:
    POSIX_FADV_SEQUENTIAL = os.POSIX_FADV_SEQUENTIAL
    POSIX_FADV_WILLNEED = os.POSIX_FADV_WILLNEED
    logger.info("os.posix_fadvise available - kernel readahead enabled")
else:
    logger.info("os.posix_fadvise not available - kernel readahead disabled")

# Optimized chunk sizes for progressive loading (Pi 4 optimized)
# Reduced sizes to minimize memory pressure on Pi 4 with 4GB RAM
INITIAL_CHUNK_SIZE = 128 * 1024  # 128KB for fast initial loading
SUBSEQUENT_CHUNK_SIZE = 256 * 1024  # 256KB for subsequent chunks
MAX_CHUNK_SIZE = 512 * 1024  # 512KB maximum chunk size

# Tailscale-optimized chunk sizes (smaller to reduce latency jitter)
TAILSCALE_CHUNK_SIZE = 64 * 1024  # 64KB base chunk for Tailscale
TAILSCALE_CHUNK_SIZE_LARGE = 128 * 1024  # 128KB max for Tailscale

# Video file extensions for special handling
VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.wmv', '.flv']

# Special MIME type mapping for formats that mimetypes module may misidentify
SPECIAL_MIME_TYPES = {
    '.mov': 'video/quicktime',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.avi': 'video/x-msvideo',
    '.mkv': 'video/x-matroska',
    '.flv': 'video/x-flv',
    '.wmv': 'video/x-ms-wmv',
    '.m4v': 'video/mp4',
    '.m4a': 'audio/mp4',
    '.flac': 'audio/flac',
    '.ogg': 'audio/ogg',
    '.opus': 'audio/opus',
    '.webp': 'image/webp',
    '.avif': 'image/avif',
    '.heic': 'image/heic',
    '.heif': 'image/heif',
}

# Ultra-small initial chunk for immediate playback start
# Reduced for Pi 4 to minimize memory allocation overhead
ULTRA_FAST_CHUNK_SIZE = 16 * 1024  # 16KB for immediate response

# gevent.sleep() optimization - reduce context switching overhead
# Sleep every N chunks instead of every chunk (4x reduction in sleep() calls)
SLEEP_EVERY_N_CHUNKS = 4  # Sleep every 4 chunks (~1MB for 256KB chunks)
SLEEP_EVERY_N_BYTES = 1 * 1024 * 1024  # Or every 1MB, whichever comes first

# Socket error handling
SOCKET_ERRORS = (ConnectionError, ConnectionResetError, ConnectionAbortedError,
                BrokenPipeError, socket.timeout, socket.error)


def _get_stream_limits():
    """
    Fetch stream timeout/cancellation limits from config.

    Returns:
        tuple(float, float): (max_duration_seconds, read_timeout_seconds)
    """
    try:
        max_duration = float(get_runtime_config_value('STREAM_MAX_DURATION_SECONDS', 0) or 0)
    except Exception:
        max_duration = 0.0
    try:
        read_timeout = float(get_runtime_config_value('STREAM_READ_TIMEOUT_SECONDS', 15) or 15)
    except Exception:
        read_timeout = 15.0
    return max_duration, max(1.0, read_timeout)

def enable_readahead(file_obj, file_size, offset=0):
    """
    Enable kernel readahead for sequential file access.

    Uses posix_fadvise to hint the kernel about access patterns:
    - POSIX_FADV_SEQUENTIAL: Kernel doubles readahead window
    - POSIX_FADV_WILLNEED: Start async prefetch immediately

    This reduces I/O wait significantly, especially on SD cards and
    when serving multiple concurrent streams.

    Args:
        file_obj: Open file object
        file_size: Total file size in bytes
        offset: Starting offset (default 0)

    Returns:
        True if readahead enabled, False otherwise
    """
    if not HAS_FADVISE:
        return False

    try:
        fd = file_obj.fileno()

        # Tell kernel: we'll read sequentially from offset to end
        # This makes kernel double its readahead window (typically 128KB → 256KB+)
        os.posix_fadvise(fd, offset, file_size - offset, POSIX_FADV_SEQUENTIAL)

        # Tell kernel: start prefetching the first chunk NOW
        # Prefetch first 10MB or entire file, whichever is smaller
        prefetch_size = min(10 * 1024 * 1024, file_size - offset)
        os.posix_fadvise(fd, offset, prefetch_size, POSIX_FADV_WILLNEED)

        logger.debug(f"Kernel readahead enabled: sequential mode, prefetch {prefetch_size} bytes")
        return True

    except Exception as e:
        logger.debug(f"Failed to enable readahead: {e}")
        return False

def _set_common_response_headers(response, filepath, mime_type, file_size, etag, is_video, is_range_request=False, range_start=None, range_end=None):
    """Helper function to set common headers for streaming responses."""
    response.headers['Content-Length'] = file_size if not is_range_request else (range_end - range_start + 1)
    response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache for 1 day
    if etag:
        response.headers['ETag'] = etag
    
    filename = os.path.basename(filepath)
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    response.headers['Connection'] = 'keep-alive'

    if is_video:
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Play-Immediately'] = 'true'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept'
        response.headers['Cache-Control'] = 'public, max-age=86400, immutable' # More specific for videos

        if mime_type == 'video/mp4':
            # Don't hardcode codecs - let browser detect them to support all MP4 variants
            response.headers['Content-Type'] = mime_type
        elif mime_type == 'video/quicktime':
            response.headers['Content-Type'] = mime_type # Keep original
            response.headers['X-Video-Codec'] = 'h264' # Hint codec
        # else, Content-Type is already set by mimetype in Response constructor
    else:
        response.headers['Accept-Ranges'] = 'none'

    if is_range_request:
        response.status_code = 206  # Partial Content
        response.headers['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
    
    # For non-range requests that are videos, ensure Content-Type is set correctly if not already modified
    elif is_video and mime_type not in ['video/mp4', 'video/quicktime']:
         response.headers['Content-Type'] = mime_type


def serve_small_file(filepath, mime_type, etag, is_video=False):
    """
    Serve small files from memory cache with optimized headers.
    Special handling for video files to improve playback.
    """
    # Check if file is in cache
    cache_result = get_from_small_cache(filepath)
    
    if cache_result:
        file_data, file_size, cached_mime_type, cached_etag = cache_result
    else:
        # Load file into memory
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
            file_size = len(file_data)
            # Cache the file data
            add_to_small_cache(filepath, file_data, file_size, mime_type, etag)
        except Exception as e:
            logger.error(f"Error reading small file {filepath}: {e}")
            return jsonify({'error': f'Error reading file: {str(e)}'}), 500
    
    # Create response
    response = Response(
        file_data,
        mimetype=mime_type # Initial mimetype
    )
    
    _set_common_response_headers(response, filepath, mime_type, file_size, etag, is_video)
    
    # Specific logging for small video files
    if is_video:
        logger.info(f"Serving small video with optimized headers: {filepath}")

    return response

def is_video_file(filename):
    """Check if file has a video extension."""
    _, ext = os.path.splitext(filename.lower())
    return ext in VIDEO_EXTENSIONS

def parse_range_header(range_header, file_size):
    """
    Parse HTTP Range header for partial content requests.

    Returns (start_byte, end_byte, is_valid) tuple.
    is_valid: True = valid range, False = no range header, 'invalid' = unsatisfiable range (416)
    """
    if not range_header or not range_header.startswith('bytes='):
        return 0, file_size - 1, False

    try:
        # Remove 'bytes=' prefix and get the range
        ranges_str = range_header[6:].strip()

        # We only support a single range for now (most browsers only request one)
        if ',' in ranges_str:
            logger.warning(f"Multiple ranges requested, but only supporting first range: {ranges_str}")
            ranges_str = ranges_str.split(',')[0].strip()

        # Parse the range
        range_parts = ranges_str.split('-')

        # Handle different range formats: bytes=X-Y, bytes=X-, bytes=-Y
        if range_parts[0]:
            start_byte = int(range_parts[0])
            end_byte = int(range_parts[1]) if range_parts[1] else file_size - 1
        else:
            # Handle suffix range: bytes=-Y (last Y bytes)
            suffix_length = int(range_parts[1])
            start_byte = max(0, file_size - suffix_length)
            end_byte = file_size - 1

        # Clamp end_byte to file_size - 1 (RFC 7233 says server MAY ignore invalid end)
        end_byte = min(end_byte, file_size - 1)

        # Validate range - start beyond file size is unsatisfiable (RFC 7233 Section 4.4)
        if start_byte < 0 or start_byte > end_byte or start_byte >= file_size:
            logger.warning(f"Invalid range requested: {range_header} for file size {file_size}")
            return 0, file_size - 1, 'invalid'

        return start_byte, end_byte, True
    except (ValueError, IndexError) as e:
        logger.warning(f"Error parsing range header '{range_header}': {e}")
        return 0, file_size - 1, 'invalid'

def stream_video_file(filepath, mime_type, file_size, etag=None):
    """
    Stream video with HTTP Range support for efficient seeking.
    Sets optimal headers for smooth browser playback.
    Adapts chunk size based on client connection type (Tailscale, LAN, etc).
    """
    # Detect client connection type and adjust chunk size
    client_ip = request.remote_addr
    is_loopback = client_ip in ('127.0.0.1', '::1')

    # Check if Tailscale connection (needs smaller chunks for low jitter)
    if is_tailscale_connection(client_ip):
        CHUNK_SIZE = TAILSCALE_CHUNK_SIZE
        logger.debug(f"Using Tailscale chunk size {CHUNK_SIZE} for client {client_ip}")
    else:
        # Default chunk size for streaming (256KB is a good balance)
        # Loopback (kiosk on same Pi) benefits from larger chunks to reduce Python overhead/jitter.
        CHUNK_SIZE = 1024 * 1024 if is_loopback else 256 * 1024

    # Check for Range header
    range_header = request.headers.get('Range')
    start_byte, end_byte, range_status = parse_range_header(range_header, file_size)

    # RFC 7233: Return 416 Range Not Satisfiable for invalid ranges
    if range_status == 'invalid':
        return Response(
            'Range Not Satisfiable',
            status=416,
            headers={'Content-Range': f'bytes */{file_size}'}
        )

    is_range_request = (range_status is True)

    # Calculate content length
    content_length = end_byte - start_byte + 1
    
    # Handle If-Range header (conditional range requests)
    if_range = request.headers.get('If-Range', '')
    if is_range_request and etag and if_range and if_range != etag:
        # If the entity is not unchanged, send entire entity
        start_byte, end_byte = 0, file_size - 1
        content_length = file_size
        is_range_request = False
    
    # Handle If-None-Match header (conditional GET)
    if_none_match = request.headers.get('If-None-Match', '')
    if etag and if_none_match and etag in [tag.strip() for tag in if_none_match.split(',')]:
        return '', 304  # Not Modified
    
    # Create response headers
    headers = {
        'Content-Type': mime_type,
        'Content-Length': content_length,
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'public, max-age=86400',  # Cache for 1 day
        'Connection': 'keep-alive'
    }
    
    # Add ETag if provided
    if etag:
        headers['ETag'] = etag
    
    # Set Content-Range header for range requests
    if is_range_request:
        headers['Content-Range'] = f'bytes {start_byte}-{end_byte}/{file_size}'
    
    # Set Content-Disposition to suggest inline display
    filename = os.path.basename(filepath)
    headers['Content-Disposition'] = f'inline; filename="{filename}"'

    # Capture client IP BEFORE generator starts (while in request context)
    client_ip = request.remote_addr

    # Define the generator function for streaming
    def generate():
        max_duration, read_timeout = _get_stream_limits()
        stream_start = time.time()
        timeout_obj = None
        try:
            with open(filepath, 'rb') as video_file:
                # Enable kernel readahead for faster I/O
                enable_readahead(video_file, file_size, offset=start_byte)

                # Seek to the starting byte for range requests
                video_file.seek(start_byte)

                # Track how many bytes we've sent
                bytes_sent = 0
                bytes_to_send = content_length

                # Track sleep frequency (optimization to reduce greenlet overhead)
                chunks_since_sleep = 0
                bytes_since_sleep = 0

                # Track timeout (reusable object to reduce GC pressure)
                timeout_obj = gevent.Timeout(read_timeout)

                # Stream the file in chunks
                try:
                    while bytes_to_send > 0:
                        if max_duration > 0 and (time.time() - stream_start) > max_duration:
                            logger.warning(
                                f"Stream duration limit reached for {filepath} (>{max_duration}s), closing stream"
                            )
                            break

                        # Read the appropriate chunk size
                        chunk_size = min(CHUNK_SIZE, bytes_to_send)
                        try:
                            timeout_obj.start()
                            try:
                                chunk = video_file.read(chunk_size)
                            finally:
                                timeout_obj.cancel()
                        except gevent.Timeout as t:
                            if t is timeout_obj:
                                logger.warning(f"Stream read timeout after {read_timeout}s for {filepath}")
                                break
                            raise

                        # If we've reached EOF, break
                        if not chunk:
                            break

                        # Rate limiting check - throttle if limit exceeded
                        # Loopback requests (kiosk) are exempted in rate_limit_service.
                        # Bounded retry: sleep once and continue to avoid stalling
                        # the stream with repeated 50ms busy-wait loops that cause
                        # playback jitter.
                        if not rate_limit_service.check_download_limit(client_ip, len(chunk)):
                            gevent.sleep(0.1)

                        # Update counters
                        bytes_sent += len(chunk)
                        bytes_to_send -= len(chunk)
                        chunks_since_sleep += 1
                        bytes_since_sleep += len(chunk)

                        # Yield the chunk
                        yield chunk

                        # Yield control to other greenlets (optimized frequency)
                        # Sleep every N chunks OR every N bytes (whichever comes first)
                        if chunks_since_sleep >= SLEEP_EVERY_N_CHUNKS or bytes_since_sleep >= SLEEP_EVERY_N_BYTES:
                            gevent.sleep(0)
                            chunks_since_sleep = 0
                            bytes_since_sleep = 0
                finally:
                    if timeout_obj:
                        try:
                            timeout_obj.close()
                        except (AttributeError, Exception):
                            pass

        except GeneratorExit:
            logger.debug(f"Client cancelled stream for {filepath}")
        except SOCKET_ERRORS as e:
            # Handle client disconnections gracefully
            logger.debug(f"Client disconnected during streaming of {filepath}: {e}")
        except Exception as e:
            logger.error(f"Error streaming file {filepath}: {e}")
            logger.debug(traceback.format_exc())
    
    # Create and return the streaming response
    status_code = 206 if is_range_request else 200
    return Response(
        generate(),
        status=status_code,
        headers=headers,
        direct_passthrough=True  # Don't buffer in Flask
    )

def serve_large_file_non_blocking(filepath, mime_type, file_size, etag, is_video=False, range_start=None, range_end=None):
    """
    Stream large files with progressive chunk sizes and non-blocking I/O.
    Optimized for video playback with prefetching and range support.
    Adapts chunk size based on client connection type (Tailscale, LAN, etc).
    """
    # Detect client connection type and adjust initial chunk size
    client_ip = request.remote_addr

    if is_tailscale_connection(client_ip):
        # Use smaller chunks for Tailscale to reduce latency jitter
        initial_chunk_size = TAILSCALE_CHUNK_SIZE
        subsequent_chunk_size = TAILSCALE_CHUNK_SIZE_LARGE
        max_chunk_size = TAILSCALE_CHUNK_SIZE_LARGE
        logger.debug(f"Using Tailscale chunk sizes for client {client_ip}")
    else:
        # Use default chunk sizes for LAN/WiFi
        initial_chunk_size = INITIAL_CHUNK_SIZE
        subsequent_chunk_size = SUBSEQUENT_CHUNK_SIZE
        max_chunk_size = MAX_CHUNK_SIZE

    # Handle range request
    is_range_request = range_start is not None and range_end is not None
    content_length = range_end - range_start + 1 if is_range_request else file_size
    
    # Check if we have cached metadata (avoids repeated os.stat calls)
    # Note: We cache only metadata, not file descriptors, to avoid concurrency issues
    cache_result = get_from_metadata_cache(filepath)
    
    if cache_result:
        cached_size, cached_mime, cached_etag, cached_mtime = cache_result
        # Verify metadata matches current file stats
        if cached_size != file_size or cached_etag != etag:
            # File has changed, metadata will be re-cached below
            logger.debug(f"Cached metadata stale for {filepath}")
            cache_result = None
    
    # Cache metadata if not already cached or stale
    if not cache_result:
        try:
            file_mtime = os.path.getmtime(filepath)
            add_to_metadata_cache(filepath, file_size, mime_type, etag, file_mtime)
        except Exception as e:
            logger.debug(f"Failed to cache metadata for {filepath}: {e}")

    # Clean caches periodically
    if random.random() < 0.05:  # ~5% chance on each request
        clean_caches()
    
    def generate():
        """Generator function that yields file chunks"""
        max_duration, read_timeout = _get_stream_limits()
        stream_start = time.time()
        timeout_obj = None
        # Open fresh file descriptor per request to avoid concurrency issues
        # The OS kernel page cache + fadvise provides the real I/O performance benefit
        try:
            f = open(filepath, 'rb')
        except Exception as e:
            logger.error(f"Error opening file {filepath}: {e}")
            return
        
        # For videos, preload a small buffer to speed up initial playback
        preload_buffer = None
        preload_size = 0
        if is_video and not is_range_request:
            try:
                preload_buffer = f.read(ULTRA_FAST_CHUNK_SIZE)
                preload_size = len(preload_buffer) if preload_buffer else 0
            except Exception as e:
                logger.debug(f"Failed to preload video buffer: {e}")
        
        try:
            # Enable kernel readahead for faster I/O
            enable_readahead(f, file_size, offset=range_start if is_range_request else 0)
            
            # Handle range request - seek to the start position
            if is_range_request:
                f.seek(range_start)
                bytes_sent = 0
                bytes_remaining = content_length
            else:
                # Send preloaded buffer first for videos (only for non-range requests)
                if is_video and preload_buffer:
                    yield preload_buffer
                    bytes_sent = preload_size
                    # File position is already at preload_size, no need to seek
                else:
                    bytes_sent = 0
                    # If we preloaded but didn't use it (non-video), seek back
                    if preload_size > 0:
                        f.seek(0)
                bytes_remaining = file_size - bytes_sent
            
            # Start with smaller chunks for MOV files which can be problematic
            if is_video and filepath.lower().endswith('.mov'):
                current_chunk_size = ULTRA_FAST_CHUNK_SIZE
            else:
                current_chunk_size = initial_chunk_size

            # Track sleep frequency (optimization to reduce greenlet overhead)
            chunks_since_sleep = 0
            bytes_since_sleep = 0

            # Track timeout (reusable object to reduce GC pressure)
            timeout_obj = gevent.Timeout(read_timeout)

            try:
                while bytes_remaining > 0:
                    if max_duration > 0 and (time.time() - stream_start) > max_duration:
                        logger.warning(
                            f"Large-file stream duration limit reached for {filepath} (>{max_duration}s), closing stream"
                        )
                        break

                    # Adjust chunk size for the last chunk
                    read_size = min(current_chunk_size, bytes_remaining)
                    try:
                        timeout_obj.start()
                        try:
                            chunk = f.read(read_size)
                        finally:
                            timeout_obj.cancel()
                    except gevent.Timeout as t:
                        if t is timeout_obj:
                            logger.warning(f"Large-file stream read timeout after {read_timeout}s for {filepath}")
                            break
                        raise

                    if not chunk:
                        break

                    yield chunk

                    chunk_size = len(chunk)
                    bytes_sent += chunk_size
                    bytes_remaining -= chunk_size
                    chunks_since_sleep += 1
                    bytes_since_sleep += chunk_size

                    # Progressively increase chunk size for better throughput
                    if bytes_sent > initial_chunk_size and current_chunk_size < max_chunk_size:
                        current_chunk_size = subsequent_chunk_size if not is_range_request else initial_chunk_size * 2

                    # Yield control to other greenlets (optimized frequency)
                    # Sleep every N chunks OR every N bytes (whichever comes first)
                    if chunks_since_sleep >= SLEEP_EVERY_N_CHUNKS or bytes_since_sleep >= SLEEP_EVERY_N_BYTES:
                        gevent.sleep(0)
                        chunks_since_sleep = 0
                        bytes_since_sleep = 0
            finally:
                timeout_obj.close()

        except GeneratorExit:
            logger.debug(f"Client cancelled large-file stream for {filepath}")
        except SOCKET_ERRORS as e:
            # Handle connection errors gracefully - browsers often abort during seeking
            logger.debug(f"Client disconnected during streaming: {e}")
        except Exception as e:
            logger.error(f"Error streaming file {filepath}: {e}")
        finally:
            # Always close the file descriptor and timeout
            if timeout_obj:
                try:
                    timeout_obj.close()
                except (AttributeError, Exception):
                    pass
            try:
                f.close()
            except (OSError, Exception):
                pass
    
    # Create streaming response
    response = Response(
        generate(),
        mimetype=mime_type, # Initial mimetype
        direct_passthrough=True
    )
    
    _set_common_response_headers(response, filepath, mime_type, file_size, etag, is_video, is_range_request, range_start, range_end)
    response.headers['X-Accel-Buffering'] = 'no' # Specific to this function for proxy interaction

    # Ensure status code is set correctly by helper or here
    if not is_range_request:
        response.status_code = 200
    
    return response
