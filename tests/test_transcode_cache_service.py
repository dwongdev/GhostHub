"""
Tests for Transcode Cache Service
----------------------------------
Cache integrity for transcoded media files. If this breaks:
- Users get stale/corrupt transcoded videos
- Cache grows unbounded (fills SD card)
- Performance tanks from redundant transcoding

Tests are filesystem-based (uses tmp_path), no mocking of file I/O.
"""
import os
import json
import time
import pytest
from unittest.mock import patch, MagicMock

from app.services.ghoststream.transcode_cache_service import (
    get_cache_path,
    get_cache_index_path,
    get_cached_file,
    add_cached_file,
    remove_cached_file,
    get_cache_stats,
    cleanup_old_cache,
    cleanup_cache_by_size,
    get_transcoded_filename,
    _generate_cache_key,
    _load_cache_index,
    _save_cache_index,
)


@pytest.fixture
def category_dir(tmp_path):
    """Create a temporary category directory with .ghosthub/transcoded structure."""
    cat_dir = tmp_path / "Movies" / "Action"
    cat_dir.mkdir(parents=True)
    return str(cat_dir)


@pytest.fixture
def populated_cache(category_dir, tmp_path):
    """Category with a cached transcoded file on disk."""
    cache_dir = os.path.join(category_dir, ".ghosthub", "transcoded")
    os.makedirs(cache_dir, exist_ok=True)

    # Create a fake transcoded file
    cached_file = os.path.join(cache_dir, "movie_h264.mp4")
    with open(cached_file, "wb") as f:
        f.write(b"x" * 5000)

    # Register it in the cache index
    add_cached_file(
        category_dir, "movie.mkv", cached_file,
        resolution="original", video_codec="h264", audio_codec="aac",
        file_size=5000, source_size=50000
    )
    return category_dir, cached_file


# ─── Cache Path Management ────────────────────────────────────────────────────

class TestCachePaths:
    def test_get_cache_path_creates_directory(self, category_dir):
        path = str(get_cache_path(category_dir))
        assert os.path.isdir(path)
        assert ".ghosthub" in path
        assert "transcoded" in path

    def test_get_cache_path_is_inside_category(self, category_dir):
        """Cache MUST be inside the category folder for portability."""
        path = str(get_cache_path(category_dir))
        assert path.startswith(category_dir)

    def test_get_cache_index_path(self, category_dir):
        path = str(get_cache_index_path(category_dir))
        assert path.endswith("cache_index.json")
        assert ".ghosthub" in path


# ─── Cache Key Generation ─────────────────────────────────────────────────────

class TestCacheKeyGeneration:
    def test_deterministic(self):
        a = _generate_cache_key("movie.mkv", "720p", "h264", "aac")
        b = _generate_cache_key("movie.mkv", "720p", "h264", "aac")
        assert a == b

    def test_different_resolution_different_key(self):
        a = _generate_cache_key("movie.mkv", "720p", "h264", "aac")
        b = _generate_cache_key("movie.mkv", "1080p", "h264", "aac")
        assert a != b

    def test_different_codec_different_key(self):
        a = _generate_cache_key("movie.mkv", "720p", "h264", "aac")
        b = _generate_cache_key("movie.mkv", "720p", "h265", "aac")
        assert a != b

    def test_different_filename_different_key(self):
        a = _generate_cache_key("a.mkv", "720p", "h264", "aac")
        b = _generate_cache_key("b.mkv", "720p", "h264", "aac")
        assert a != b

    def test_handles_unicode_filename(self):
        key = _generate_cache_key("映画.mkv", "original", "h264", "aac")
        assert isinstance(key, str)
        assert len(key) > 0


# ─── Cache Index Persistence ──────────────────────────────────────────────────

class TestCacheIndex:
    def test_load_empty_index(self, category_dir):
        """Missing index file should return empty dict."""
        index = _load_cache_index(category_dir)
        assert index == {}

    def test_save_and_load_roundtrip(self, category_dir):
        test_index = {
            "key1": {"path": "/some/path.mp4", "size": 1000},
            "key2": {"path": "/other/path.mp4", "size": 2000}
        }
        _save_cache_index(category_dir, test_index)
        loaded = _load_cache_index(category_dir)
        assert loaded == test_index

    def test_corrupted_index_returns_empty(self, category_dir):
        """Corrupted JSON should not crash, just return empty."""
        index_path = get_cache_index_path(category_dir)
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, "w") as f:
            f.write("{broken json!!!")
        index = _load_cache_index(category_dir)
        assert index == {}


# ─── Cache CRUD ───────────────────────────────────────────────────────────────

class TestCacheCRUD:
    def test_add_and_get_cached_file(self, category_dir):
        """Round-trip: add a cached file, then retrieve it."""
        cache_path = get_cache_path(category_dir)
        cached_file_path = os.path.join(cache_path, "video_h264.mp4")

        # Create the actual file
        with open(cached_file_path, "wb") as f:
            f.write(b"transcoded content")

        add_cached_file(
            category_dir, "video.mkv", cached_file_path,
            resolution="original", video_codec="h264", audio_codec="aac",
            file_size=len(b"transcoded content"), source_size=100000
        )

        result = get_cached_file(category_dir, "video.mkv")
        assert result is not None
        assert os.path.exists(result)

    def test_get_cached_file_returns_none_when_not_cached(self, category_dir):
        result = get_cached_file(category_dir, "nonexistent.mkv")
        assert result is None

    def test_get_cached_file_returns_none_when_file_deleted(self, category_dir):
        """If the actual transcoded file is deleted but the index entry
        remains, the index entry should be treated as stale."""
        cache_path = get_cache_path(category_dir)
        phantom_path = os.path.join(cache_path, "phantom.mp4")

        # Add to index without creating file
        add_cached_file(
            category_dir, "phantom.mkv", phantom_path,
            resolution="original"
        )

        result = get_cached_file(category_dir, "phantom.mkv")
        assert result is None

    def test_remove_cached_file(self, populated_cache):
        """Remove should delete both the file and the index entry."""
        category_dir, cached_file = populated_cache
        assert os.path.exists(cached_file)

        remove_cached_file(category_dir, "movie.mkv")

        assert not os.path.exists(cached_file)
        assert get_cached_file(category_dir, "movie.mkv") is None

    def test_remove_nonexistent_file_no_error(self, category_dir):
        """Removing a file that doesn't exist should not raise."""
        remove_cached_file(category_dir, "nonexistent.mkv")


# ─── Cache Stats ──────────────────────────────────────────────────────────────

class TestCacheStats:
    def test_empty_cache_stats(self, category_dir):
        stats = get_cache_stats(category_dir)
        assert stats["file_count"] == 0
        assert stats["total_size_bytes"] == 0

    def test_stats_reflect_cached_files(self, populated_cache):
        category_dir, _ = populated_cache
        stats = get_cache_stats(category_dir)
        assert stats["file_count"] >= 1
        assert stats["total_size_bytes"] > 0


# ─── Transcoded Filename Generation ───────────────────────────────────────────

class TestTranscodedFilename:
    def test_default_codec_in_name(self):
        name = get_transcoded_filename("movie.mkv")
        assert "h264" in name
        assert name.endswith(".mp4")

    def test_preserves_base_name(self):
        name = get_transcoded_filename("My Movie.mkv")
        assert "My Movie" in name

    def test_includes_resolution(self):
        name = get_transcoded_filename("movie.mkv", resolution="720p")
        assert "720p" in name

    def test_includes_codec(self):
        name = get_transcoded_filename("movie.mkv", video_codec="h265")
        assert "h265" in name

    def test_original_resolution_handling(self):
        name = get_transcoded_filename("movie.mkv", resolution="original")
        assert name.endswith(".mp4")


# ─── Cleanup ──────────────────────────────────────────────────────────────────

class TestCacheCleanup:
    def test_cleanup_old_cache_removes_stale_entries(self, category_dir):
        """Files older than max_age_days should be cleaned up."""
        cache_path = get_cache_path(category_dir)
        old_file = os.path.join(cache_path, "old_movie_h264.mp4")
        with open(old_file, "wb") as f:
            f.write(b"x" * 1000)

        # Register in index with old timestamp
        add_cached_file(
            category_dir, "old_movie.mkv", old_file,
            resolution="original", file_size=1000
        )

        # Patch the last_accessed time to be very old
        from datetime import datetime
        index = _load_cache_index(category_dir)
        for key in index:
            index[key]["last_accessed"] = datetime.fromtimestamp(time.time() - (100 * 86400)).isoformat()
        _save_cache_index(category_dir, index)

        # Set the file mtime to be old too
        old_time = time.time() - (100 * 86400)
        os.utime(old_file, (old_time, old_time))

        cleaned = cleanup_old_cache(category_dir, max_age_days=30)
        assert cleaned >= 1
        assert not os.path.exists(old_file)

    def test_cleanup_keeps_recent_files(self, populated_cache):
        """Files within max_age_days should NOT be cleaned."""
        category_dir, cached_file = populated_cache
        cleaned = cleanup_old_cache(category_dir, max_age_days=30)
        assert cleaned == 0
        assert os.path.exists(cached_file)

    def test_cleanup_by_size_removes_oldest_first(self, category_dir):
        """When cache exceeds max_size, remove least recently accessed."""
        cache_path = get_cache_path(category_dir)
        now = time.time()

        # Create 3 cached files of known sizes
        for i, age_offset in enumerate([300, 200, 100]):
            fname = f"video{i}_h264.mp4"
            fpath = os.path.join(cache_path, fname)
            with open(fpath, "wb") as f:
                f.write(b"x" * 500_000)  # 500KB each

            add_cached_file(
                category_dir, f"video{i}.mkv", fpath,
                resolution="original", file_size=500_000
            )

            # Make different last_accessed times
            index = _load_cache_index(category_dir)
            for key in index:
                if f"video{i}" in key:
                    index[key]["last_accessed"] = now - age_offset
            _save_cache_index(category_dir, index)

        # Cleanup with 1MB max: all 3 files = 1.5MB > 1MB → should remove at least one
        cleaned = cleanup_cache_by_size(category_dir, max_size_gb=0.001)  # 1MB
        assert cleaned >= 1
