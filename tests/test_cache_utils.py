"""
Tests for Cache Utilities
Tests file caching mechanisms.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time


class TestCacheUtils:
    """Tests for cache_utils module."""
    
    @pytest.fixture(autouse=True)
    def reset_caches(self):
        """Reset caches before each test."""
        import app.utils.cache_utils as cu
        cu.small_file_cache.clear()
        cu.metadata_cache.clear()
        yield
        cu.small_file_cache.clear()
        cu.metadata_cache.clear()
    
    def test_add_to_small_cache(self):
        """Test adding file to small file cache."""
        from app.utils.cache_utils import add_to_small_cache, small_file_cache
        
        add_to_small_cache('/path/to/file.jpg', b'file_data', 1000, 'image/jpeg', 'etag123')
        
        assert '/path/to/file.jpg' in small_file_cache
    
    def test_get_from_small_cache_hit(self):
        """Test getting file from cache when present."""
        from app.utils.cache_utils import add_to_small_cache, get_from_small_cache
        
        add_to_small_cache('/path/to/file.jpg', b'file_data', 1000, 'image/jpeg', 'etag123')
        
        result = get_from_small_cache('/path/to/file.jpg')
        
        assert result is not None
        file_data, file_size, mime_type, etag = result
        assert file_data == b'file_data'
        assert file_size == 1000
        assert mime_type == 'image/jpeg'
        assert etag == 'etag123'
    
    def test_get_from_small_cache_miss(self):
        """Test getting file from cache when not present."""
        from app.utils.cache_utils import get_from_small_cache
        
        result = get_from_small_cache('/path/to/nonexistent.jpg')
        
        assert result is None
    
    def test_add_to_metadata_cache(self):
        """Test adding file metadata to cache."""
        from app.utils.cache_utils import add_to_metadata_cache, metadata_cache
        
        add_to_metadata_cache('/path/to/file.mp4', 1000000, 'video/mp4', 'etag456', 1234567890.0)
        
        assert '/path/to/file.mp4' in metadata_cache
    
    @patch('app.utils.cache_utils.os.path.getmtime')
    def test_get_from_metadata_cache_hit(self, mock_getmtime):
        """Test getting metadata from cache when present and valid."""
        from app.utils.cache_utils import add_to_metadata_cache, get_from_metadata_cache
        
        mtime = 1234567890.0
        mock_getmtime.return_value = mtime
        add_to_metadata_cache('/path/to/file.mp4', 1000000, 'video/mp4', 'etag456', mtime)
        
        result = get_from_metadata_cache('/path/to/file.mp4')
        
        assert result is not None
        file_size, mime_type, etag, cached_mtime = result
        assert file_size == 1000000
        assert mime_type == 'video/mp4'
        assert etag == 'etag456'
        assert cached_mtime == mtime
    
    def test_get_from_metadata_cache_miss(self):
        """Test getting metadata from cache when not present."""
        from app.utils.cache_utils import get_from_metadata_cache
        
        result = get_from_metadata_cache('/path/to/nonexistent.mp4')
        
        assert result is None
    
    def test_clean_caches_removes_expired(self):
        """Test that clean_caches removes expired entries."""
        from app.utils.cache_utils import small_file_cache, clean_caches, CACHE_EXPIRY
        
        # Add entry with old timestamp
        old_time = time.time() - CACHE_EXPIRY - 100
        small_file_cache['/old/file.jpg'] = (old_time, b'data', 100, 'image/jpeg', 'etag')
        
        clean_caches()
        
        assert '/old/file.jpg' not in small_file_cache
    
    def test_clean_caches_keeps_fresh(self):
        """Test that clean_caches keeps fresh entries."""
        from app.utils.cache_utils import add_to_small_cache, small_file_cache, clean_caches
        
        add_to_small_cache('/fresh/file.jpg', b'data', 100, 'image/jpeg', 'etag')
        
        clean_caches()
        
        assert '/fresh/file.jpg' in small_file_cache
    
    def test_metadata_cache_eviction_on_full(self):
        """Test metadata cache evicts old entries when full."""
        from app.utils.cache_utils import add_to_metadata_cache, metadata_cache, MAX_METADATA_CACHE_SIZE, clean_caches
        
        # Fill cache beyond limit
        for i in range(MAX_METADATA_CACHE_SIZE + 5):
            add_to_metadata_cache(f'/file{i}.mp4', 1000, 'video/mp4', f'etag{i}', 1234567890.0)
        
        # Run cleanup to enforce limit
        clean_caches()
        
        # Cache should not exceed max size after cleanup
        assert len(metadata_cache) <= MAX_METADATA_CACHE_SIZE
    
    def test_small_file_threshold(self):
        """Test small file threshold constant."""
        from app.utils.cache_utils import SMALL_FILE_THRESHOLD
        
        assert SMALL_FILE_THRESHOLD == 4 * 1024 * 1024  # 4MB
