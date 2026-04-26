# app/services/subtitle_service.py
"""
Subtitle Service for GhostHub
-----------------------------
Handles subtitle detection, extraction, and conversion for video files.
- Detects embedded subtitle tracks in any container (MP4, MKV, etc.) using ffprobe
- Extracts text-based subtitle tracks to .vtt using ffmpeg
- Detects external .srt or .vtt files matching video filename
- Converts .srt → .vtt when needed
- Marks image-based subtitles (PGS, VobSub) as unsupported
- Caches extracted tracks to avoid repeat processing
"""

import os
import json
import logging
import subprocess
import hashlib
import re
from pathlib import Path

from app.services.core.runtime_config_service import get_runtime_config_value, get_runtime_instance_path

logger = logging.getLogger(__name__)

# Cache version - bump this when conversion logic changes to auto-invalidate old caches
SUBTITLE_CACHE_VERSION = 7

# Supported subtitle file extensions
SUBTITLE_EXTENSIONS = ['.srt', '.vtt', '.ass', '.ssa', '.sub']

# Text-based subtitle codecs (can be extracted/converted to WebVTT)
TEXT_SUBTITLE_CODECS = ['subrip', 'srt', 'webvtt', 'ass', 'ssa', 'mov_text']

# Image-based subtitle codecs (cannot be converted to WebVTT - require OCR)
IMAGE_SUBTITLE_CODECS = ['hdmv_pgs_subtitle', 'dvd_subtitle', 'dvdsub', 'pgssub']

# All supported subtitle codecs for detection
ALL_SUBTITLE_CODECS = TEXT_SUBTITLE_CODECS + IMAGE_SUBTITLE_CODECS


def is_subtitles_enabled():
    """Check if subtitles feature is enabled in config."""
    return get_runtime_config_value('ENABLE_SUBTITLES', False)


def get_subtitle_cache_dir():
    """Get the directory for caching extracted subtitles."""
    cache_dir = os.path.join(get_runtime_instance_path(), 'subtitle_cache')
    if not os.path.exists(cache_dir):
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create subtitle cache directory: {e}")
    return cache_dir


def get_video_hash(video_path):
    """Generate a hash for a video file based on path and mtime for cache invalidation."""
    try:
        stat = os.stat(video_path)
        # Use path + mtime + size for a unique but stable hash
        hash_input = f"{video_path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    except OSError:
        # Fallback to just path hash
        return hashlib.md5(video_path.encode()).hexdigest()[:16]


def get_cached_subtitle_path(video_path, track_index, format='vtt'):
    """Get the path for a cached subtitle file. Includes cache version for auto-invalidation."""
    video_hash = get_video_hash(video_path)
    video_name = Path(video_path).stem
    cache_dir = get_subtitle_cache_dir()
    # Create a safe filename with cache version
    safe_name = re.sub(r'[^\w\-_.]', '_', video_name)[:50]
    return os.path.join(cache_dir, f"{safe_name}_{video_hash}_v{SUBTITLE_CACHE_VERSION}_track{track_index}.{format}")


def get_video_start_time(video_path):
    """
    Get the video stream's start time offset.
    Many containers (especially MKV) have non-zero start times that cause subtitle desync.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_entries', 'format=start_time',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            start_time = float(data.get('format', {}).get('start_time', 0))
            if start_time > 0:
                logger.debug(f"Video has start_time offset: {start_time}s")
            return start_time
    except Exception as e:
        logger.debug(f"Could not get video start time: {e}")
    return 0.0


def run_ffprobe(video_path):
    """
    Run ffprobe to get subtitle stream information from a video file.
    Returns list of subtitle tracks with their metadata.
    """
    if not os.path.exists(video_path):
        logger.warning(f"Video file not found for ffprobe: {video_path}")
        return []
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-select_streams', 's',  # Only subtitle streams
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.debug(f"ffprobe returned non-zero for {video_path}: {result.stderr}")
            return []
        
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        
        subtitle_tracks = []
        for i, stream in enumerate(streams):
            codec_name = stream.get('codec_name', '').lower()
            if codec_name in ALL_SUBTITLE_CODECS or stream.get('codec_type') == 'subtitle':
                tags = stream.get('tags', {})
                # Try to get a meaningful label
                label = (
                    tags.get('title') or 
                    tags.get('language') or 
                    tags.get('handler_name') or
                    f"Track {i + 1}"
                )
                
                # Map language codes to readable names if possible
                lang_code = tags.get('language', '')
                if lang_code and len(lang_code) <= 3:
                    label = f"{get_language_name(lang_code)} ({label})" if label != f"Track {i + 1}" else get_language_name(lang_code)
                
                # Determine if codec is text-based (extractable) or image-based (unsupported)
                is_text_based = codec_name in TEXT_SUBTITLE_CODECS
                
                subtitle_tracks.append({
                    'index': stream.get('index', i),
                    'stream_index': i,
                    'codec': codec_name,
                    'label': label,
                    'language': lang_code,
                    'disposition': stream.get('disposition', {}),
                    'type': 'embedded',
                    'is_text_based': is_text_based
                })
        
        logger.debug(f"Found {len(subtitle_tracks)} embedded subtitle tracks in {video_path}")
        return subtitle_tracks
        
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out for {video_path}")
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse ffprobe output for {video_path}: {e}")
        return []
    except FileNotFoundError:
        logger.warning("ffprobe not found. Please install ffmpeg.")
        return []
    except Exception as e:
        logger.error(f"Error running ffprobe on {video_path}: {e}")
        return []


def get_language_name(code):
    """Convert ISO 639 language codes to readable names."""
    language_map = {
        'eng': 'English', 'en': 'English',
        'spa': 'Spanish', 'es': 'Spanish',
        'fra': 'French', 'fr': 'French',
        'deu': 'German', 'de': 'German',
        'ita': 'Italian', 'it': 'Italian',
        'por': 'Portuguese', 'pt': 'Portuguese',
        'rus': 'Russian', 'ru': 'Russian',
        'jpn': 'Japanese', 'ja': 'Japanese',
        'kor': 'Korean', 'ko': 'Korean',
        'zho': 'Chinese', 'zh': 'Chinese',
        'chi': 'Chinese',
        'ara': 'Arabic', 'ar': 'Arabic',
        'hin': 'Hindi', 'hi': 'Hindi',
        'nld': 'Dutch', 'nl': 'Dutch',
        'pol': 'Polish', 'pl': 'Polish',
        'swe': 'Swedish', 'sv': 'Swedish',
        'nor': 'Norwegian', 'no': 'Norwegian',
        'dan': 'Danish', 'da': 'Danish',
        'fin': 'Finnish', 'fi': 'Finnish',
        'tur': 'Turkish', 'tr': 'Turkish',
        'und': 'Unknown',
    }
    return language_map.get(code.lower(), code.upper() if code else 'Unknown')


def extract_subtitle_track(video_path, stream_index, output_path):
    """
    Extract a subtitle track from a video file to VTT format.
    Compensates for video start_time offset to ensure proper sync.
    Returns True if successful, False otherwise.
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Get video start time to compensate for container offset
        start_time = get_video_start_time(video_path)
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-i', video_path,
            '-map', f'0:s:{stream_index}',  # Select specific subtitle stream
            '-c:s', 'webvtt',  # Convert to WebVTT
        ]
        
        # If video has a start time offset, shift subtitles back to sync with playback
        if start_time > 0:
            cmd.extend(['-output_ts_offset', f'-{start_time}'])
            logger.info(f"Applying subtitle offset: -{start_time}s to compensate for video start_time")
        
        cmd.append(output_path)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout for extraction
        )
        
        if result.returncode != 0:
            logger.warning(f"ffmpeg subtitle extraction failed: {result.stderr[:500]}")
            return False
        
        # Verify output file was created and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            # Post-process VTT to fix formatting (offset already applied by ffmpeg)
            _fix_vtt_formatting(output_path)
            logger.info(f"Extracted subtitle track {stream_index} to {output_path}")
            return True
        else:
            logger.warning(f"Subtitle extraction produced empty or missing file: {output_path}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.warning(f"Subtitle extraction timed out for {video_path}")
        return False
    except FileNotFoundError:
        logger.warning("ffmpeg not found. Please install ffmpeg.")
        return False
    except Exception as e:
        logger.error(f"Error extracting subtitle track: {e}")
        return False


def _fix_vtt_formatting(vtt_path):
    """Post-process VTT file to ensure proper formatting."""
    try:
        with open(vtt_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        lines = content.split('\n')
        fixed_lines = []
        prev_was_blank = False
        
        for line in lines:
            if '-->' in line:
                # Ensure consistent timestamp format (HH:MM:SS.mmm)
                line = re.sub(
                    r'(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,3})',
                    lambda m: f"{int(m.group(1)):02d}:{m.group(2)}:{m.group(3)}.{m.group(4).ljust(3, '0')[:3]}",
                    line
                )
                # Ensure there's a blank line before timestamp if not at start
                if fixed_lines and fixed_lines[-1].strip() and not prev_was_blank:
                    fixed_lines.append('')
            
            # Avoid multiple consecutive blank lines
            is_blank = not line.strip()
            if is_blank and prev_was_blank:
                continue
            
            fixed_lines.append(line)
            prev_was_blank = is_blank
        
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))
            
    except Exception as e:
        logger.debug(f"Could not fix VTT formatting: {e}")


def convert_srt_to_vtt(srt_path, vtt_path):
    """
    Convert an SRT subtitle file to VTT format.
    Simple, robust conversion that preserves all cues.
    Returns True if successful, False otherwise.
    """
    try:
        with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
            srt_content = f.read()
        
        # Normalize line endings and clean up
        srt_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove BOM if present
        if srt_content.startswith('\ufeff'):
            srt_content = srt_content[1:]
        
        # Split into blocks (cues are separated by blank lines)
        blocks = re.split(r'\n\s*\n', srt_content.strip())
        
        vtt_lines = ["WEBVTT", ""]
        cue_count = 0
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            lines = block.split('\n')
            if len(lines) < 2:
                continue
            
            # Find the timestamp line (contains ' --> ')
            ts_line_idx = -1
            for i, line in enumerate(lines):
                if ' --> ' in line or '-->' in line:
                    ts_line_idx = i
                    break
            
            if ts_line_idx == -1:
                continue  # No timestamp found, skip block
            
            # Parse timestamp line
            ts_line = lines[ts_line_idx]
            ts_match = re.match(
                r'(\d{1,2}:\d{2}:\d{2}[,.:]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.:]\d{1,3})(.*)?',
                ts_line
            )
            
            if not ts_match:
                continue
            
            start_time = ts_match.group(1).replace(',', '.')
            end_time = ts_match.group(2).replace(',', '.')
            extra = ts_match.group(3) or ''
            
            # Normalize timestamps
            start_time = _normalize_vtt_timestamp(start_time)
            end_time = _normalize_vtt_timestamp(end_time)
            
            # Get text (everything after timestamp line)
            text_lines = lines[ts_line_idx + 1:]
            text = '\n'.join(text_lines).strip()
            
            if not text:
                continue
            
            # Add cue to VTT
            vtt_lines.append(f"{start_time} --> {end_time}{extra}")
            vtt_lines.append(text)
            vtt_lines.append("")
            cue_count += 1
        
        if cue_count == 0:
            logger.warning(f"No valid cues found in SRT file: {srt_path}")
            return False
        
        vtt_content = '\n'.join(vtt_lines)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(vtt_path), exist_ok=True)
        
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write(vtt_content)
        
        logger.info(f"Converted SRT to VTT: {srt_path} -> {vtt_path} ({cue_count} cues)")
        return True
        
    except Exception as e:
        logger.error(f"Error converting SRT to VTT: {e}")
        return False


def _normalize_vtt_timestamp(ts):
    """
    Normalize a timestamp to VTT format (HH:MM:SS.mmm).
    Handles various input formats from SRT files.
    """
    # Replace comma with dot (SRT uses comma)
    ts = ts.replace(',', '.')
    
    # Parse components
    match = re.match(r'(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})', ts)
    if match:
        hours, mins, secs, ms = match.groups()
        return f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}.{ms}"
    
    return ts  # Return as-is if parsing fails


def _parse_srt_simple(content):
    """
    Simple fallback SRT parser using line-by-line processing.
    More robust for malformed SRT files.
    """
    lines = content.split('\n')
    cues = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and cue numbers
        if not line or re.match(r'^\d+$', line):
            i += 1
            continue
        
        # Look for timestamp line
        timestamp_match = re.match(
            r'(\d{1,2}:\d{2}:\d{2}[,.:]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.:]\d{3})(.*)',
            line
        )
        
        if timestamp_match:
            start_time = timestamp_match.group(1).replace(',', '.')
            end_time = timestamp_match.group(2).replace(',', '.')
            position_info = timestamp_match.group(3).strip()
            
            # Normalize timestamps
            start_time = _normalize_vtt_timestamp(start_time)
            end_time = _normalize_vtt_timestamp(end_time)
            
            # Collect text lines until empty line or next cue
            i += 1
            text_lines = []
            while i < len(lines):
                text_line = lines[i]
                # Stop at empty line or if next line looks like a cue number followed by timestamp
                if not text_line.strip():
                    break
                if re.match(r'^\d+$', text_line.strip()):
                    # Check if next line is timestamp
                    if i + 1 < len(lines) and '-->' in lines[i + 1]:
                        break
                text_lines.append(text_line)
                i += 1
            
            text = '\n'.join(text_lines).strip()
            if text:
                cues.append({
                    'start': start_time,
                    'end': end_time,
                    'position': position_info,
                    'text': text
                })
        else:
            i += 1
    
    return cues


def find_external_subtitles(video_path):
    """
    Find external subtitle files that match the video filename.
    Returns list of subtitle file info.
    """
    video_dir = os.path.dirname(video_path)
    video_name = Path(video_path).stem
    
    external_subs = []
    
    try:
        for ext in SUBTITLE_EXTENSIONS:
            # Check for exact match (video.srt)
            sub_path = os.path.join(video_dir, video_name + ext)
            if os.path.exists(sub_path):
                external_subs.append({
                    'path': sub_path,
                    'filename': os.path.basename(sub_path),
                    'format': ext[1:],  # Remove leading dot
                    'label': 'External',
                    'language': '',
                    'type': 'external'
                })
            
            # Check for language-tagged files (video.en.srt, video.eng.srt)
            for entry in os.scandir(video_dir):
                if not entry.is_file():
                    continue
                name = entry.name.lower()
                # Match patterns like: video.en.srt, video.eng.srt, video.english.srt
                if name.startswith(video_name.lower()) and name.endswith(ext):
                    # Extract language from filename
                    middle_part = name[len(video_name):-len(ext)].strip('.')
                    if middle_part and middle_part != video_name.lower():
                        lang_label = get_language_name(middle_part)
                        external_subs.append({
                            'path': entry.path,
                            'filename': entry.name,
                            'format': ext[1:],
                            'label': lang_label,
                            'language': middle_part,
                            'type': 'external'
                        })
    except Exception as e:
        logger.error(f"Error finding external subtitles for {video_path}: {e}")
    
    # Remove duplicates based on path
    seen_paths = set()
    unique_subs = []
    for sub in external_subs:
        if sub['path'] not in seen_paths:
            seen_paths.add(sub['path'])
            unique_subs.append(sub)
    
    logger.debug(f"Found {len(unique_subs)} external subtitle files for {video_path}")
    return unique_subs


def get_subtitles_for_video(video_path, category_id=None):
    """
    Get all available subtitles for a video file.
    Returns list of subtitle tracks with URLs for the client.
    
    This is the main entry point for the subtitle API.
    """
    # Check if subtitles are enabled
    if not is_subtitles_enabled():
        return []
    
    if not os.path.exists(video_path):
        logger.warning(f"Video not found for subtitle detection: {video_path}")
        return []
    
    subtitles = []
    
    # 1. Find external subtitle files
    external_subs = find_external_subtitles(video_path)
    for i, sub in enumerate(external_subs):
        sub_format = sub['format'].lower()
        
        if sub_format == 'vtt':
            # VTT files can be served directly
            subtitles.append({
                'url': f"/api/subtitles/external?path={sub['path']}",
                'label': sub['label'],
                'language': sub.get('language', ''),
                'type': 'external',
                'default': i == 0
            })
        elif sub_format == 'srt':
            # SRT needs conversion - check cache first
            cache_path = get_cached_subtitle_path(sub['path'], f"ext{i}", 'vtt')
            
            if not os.path.exists(cache_path):
                if not convert_srt_to_vtt(sub['path'], cache_path):
                    continue
            
            subtitles.append({
                'url': f"/api/subtitles/cache?file={os.path.basename(cache_path)}",
                'label': sub['label'],
                'language': sub.get('language', ''),
                'type': 'external_converted',
                'default': i == 0 and len(subtitles) == 0
            })
    
    # 2. Detect and extract embedded subtitle tracks
    embedded_tracks = run_ffprobe(video_path)
    for track in embedded_tracks:
        stream_idx = track['stream_index']
        
        # Only extract text-based subtitles (image-based ones cannot be converted to VTT)
        if track.get('is_text_based', False):
            cache_path = get_cached_subtitle_path(video_path, stream_idx, 'vtt')
            
            # Check if we need to extract
            if not os.path.exists(cache_path):
                if not extract_subtitle_track(video_path, stream_idx, cache_path):
                    continue
            
            subtitles.append({
                'url': f"/api/subtitles/cache?file={os.path.basename(cache_path)}",
                'label': track['label'],
                'language': track.get('language', ''),
                'type': 'embedded',
                'default': len(subtitles) == 0
            })
        else:
            # Image-based subtitle (PGS, VobSub) - mark as unsupported
            codec_label = track.get('codec', 'unknown').upper()
            subtitles.append({
                'label': f"{track['label']} ({codec_label} - unsupported)",
                'language': track.get('language', ''),
                'type': 'embedded_image',
                'supported': False,
                'codec': track.get('codec', 'unknown')
            })
    
    logger.info(f"Found {len(subtitles)} subtitles for {os.path.basename(video_path)}")
    return subtitles


def get_cached_subtitle_file(filename):
    """Get the full path of a cached subtitle file."""
    cache_dir = get_subtitle_cache_dir()
    file_path = os.path.join(cache_dir, filename)
    
    # Security check - prevent path traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(cache_dir)):
        logger.warning(f"Attempted path traversal in subtitle request: {filename}")
        return None
    
    if os.path.exists(file_path):
        return file_path
    return None


def cleanup_old_cache(max_age_days=30):
    """Remove cached subtitle files older than max_age_days."""
    cache_dir = get_subtitle_cache_dir()
    if not os.path.exists(cache_dir):
        return
    
    import time
    now = time.time()
    max_age_seconds = max_age_days * 24 * 60 * 60
    
    try:
        for entry in os.scandir(cache_dir):
            if entry.is_file() and entry.name.endswith('.vtt'):
                if now - entry.stat().st_mtime > max_age_seconds:
                    os.remove(entry.path)
                    logger.debug(f"Removed old cached subtitle: {entry.name}")
    except Exception as e:
        logger.error(f"Error cleaning up subtitle cache: {e}")
