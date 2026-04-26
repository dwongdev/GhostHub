import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from app.services.core import sqlite_runtime_service
from app.services.media import media_index_service, hidden_content_service

class TestMediaDeduplication:
    """Tests for media deduplication in global queries."""

    @pytest.fixture
    def mock_db(self):
        """Create a temporary in-memory database with duplicate media entries."""
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        
        # Create media_index table (Specter Schema v10)
        conn.execute('''
            CREATE TABLE media_index (
                id TEXT PRIMARY KEY,
                category_id TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                parent_path TEXT NOT NULL,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                hash TEXT NOT NULL,
                type TEXT NOT NULL,
                is_hidden INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        ''')
        
        # Create hidden_categories table (needed for queries)
        conn.execute('''
            CREATE TABLE hidden_categories (
                category_id TEXT PRIMARY KEY,
                hidden_at REAL NOT NULL DEFAULT 0,
                hidden_by TEXT
            )
        ''')
        
        # Insert duplicate media items
        # Same hash, different categories/paths, different mtimes
        conn.execute('''
            INSERT INTO media_index (id, category_id, name, rel_path, parent_path, type, size, mtime, hash, created_at, updated_at)
            VALUES 
            ('id1', 'cat1', 'movie.mp4', 'movie.mp4', '', 'video', 1000, 100.0, 'hash123', 100.0, 100.0),
            ('id2', 'cat2', 'movie_dup.mp4', 'sub/movie.mp4', 'sub', 'video', 1000, 200.0, 'hash123', 200.0, 200.0)
        ''')
        
        # Insert unique media item
        conn.execute('''
            INSERT INTO media_index (id, category_id, name, rel_path, parent_path, type, size, mtime, hash, created_at, updated_at)
            VALUES 
            ('id3', 'cat1', 'other.mp4', 'other.mp4', '', 'video', 500, 150.0, 'hash456', 150.0, 150.0)
        ''')
        
        conn.commit()
        
        # Invalidate Specter caches to ensure they use our mock_db
        hidden_content_service._invalidate_hidden_categories_cache()
        hidden_content_service._invalidate_hidden_files_cache()
        
        return conn

    def test_get_paginated_media_deduplication(self, mock_db):
        """Test that get_paginated_media deduplicates by hash when requested."""
        
        # Mock both media_index_service.get_db and hidden_content_service.get_db
        with patch('app.services.media.media_index_service.get_db') as mock_get_db1, \
             patch('app.services.media.hidden_content_service.get_db') as mock_get_db2:
            
            from contextlib import contextmanager
            @contextmanager
            def mock_get_db_wrapper():
                yield mock_db
            
            mock_get_db1.side_effect = mock_get_db_wrapper
            mock_get_db2.side_effect = mock_get_db_wrapper
            
            # 1. Without deduplication (should return all 3)
            results_all = media_index_service.get_paginated_media(
                category_id=None,
                subfolder=None,
                deduplicate_by_hash=False
            )
            assert len(results_all) == 3
            
            # 2. With deduplication (should return 2 unique hashes)
            results_dedup = media_index_service.get_paginated_media(
                category_id=None,
                subfolder=None,
                deduplicate_by_hash=True
            )
            assert len(results_dedup) == 2
            
            # Verify we got the latest version of the duplicate (mtime=200.0)
            dup_item = next(r for r in results_dedup if r['hash'] == 'hash123')
            # The mocked query uses MAX(mtime), so we expect the newer one
            assert dup_item['group_mtime'] == 200.0

    def test_get_media_count_deduplication(self, mock_db):
        """Test that get_media_count deduplicates count when requested."""
        
        with patch('app.services.media.media_index_service.get_db') as mock_get_db1, \
             patch('app.services.media.hidden_content_service.get_db') as mock_get_db2:
            
            from contextlib import contextmanager
            @contextmanager
            def mock_get_db_wrapper():
                yield mock_db
            
            mock_get_db1.side_effect = mock_get_db_wrapper
            mock_get_db2.side_effect = mock_get_db_wrapper
            
            # 1. Without deduplication
            count_all = media_index_service.get_media_count(
                category_id=None,
                subfolder=None,
                deduplicate_by_hash=False
            )
            assert count_all == 3
            
            # 2. With deduplication
            count_dedup = media_index_service.get_media_count(
                category_id=None,
                subfolder=None,
                deduplicate_by_hash=True
            )
            assert count_dedup == 2
