"""
Tests for Database Service
--------------------------
Comprehensive tests for SQLite database operations including:
- Database initialization and migrations
- Progress CRUD operations
- Category CRUD operations
- Video progress tracking (per-video mode)
- Thread safety and connection management
"""
import pytest
import time
import threading
import sqlite3
from unittest.mock import patch, MagicMock


class TestDatabaseInitialization:
    """Tests for database initialization and schema management."""
    
    def test_init_database_creates_tables(self, test_db):
        """Test that init_database creates all required tables."""
        with test_db.get_db() as conn:
            # Check schema_info table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_info'"
            )
            assert cursor.fetchone() is not None
            
            # Check categories table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
            )
            assert cursor.fetchone() is not None
            
            # Check video_progress table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='video_progress'"
            )
            assert cursor.fetchone() is not None

            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'"
            )
            assert cursor.fetchone() is not None

            profile_columns = {
                row['name']
                for row in conn.execute("PRAGMA table_info(profiles)").fetchall()
            }
            assert 'preferences_json' in profile_columns
            assert 'avatar_icon' in profile_columns

            foreign_keys = conn.execute(
                "PRAGMA foreign_key_list(video_progress)"
            ).fetchall()
            assert any(
                row['from'] == 'profile_id' and
                row['table'] == 'profiles' and
                str(row['on_delete']).upper() == 'CASCADE'
                for row in foreign_keys
            )
    
    def test_init_database_sets_schema_version(self, test_db):
        """Test that schema version is set correctly."""
        with test_db.get_db() as conn:
            cursor = conn.execute(
                "SELECT value FROM schema_info WHERE key = 'version'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert int(row['value']) == test_db.SCHEMA_VERSION
    
    def test_database_has_correct_indexes(self, test_db):
        """Test that required indexes are created."""
        with test_db.get_db() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = {row['name'] for row in cursor.fetchall()}
            
            assert 'idx_categories_path' in indexes
            assert 'idx_categories_is_manual' in indexes
            assert 'idx_profiles_name' in indexes
            assert 'idx_video_progress_category' in indexes
            assert 'idx_video_progress_last_watched' in indexes

    def test_ensure_database_ready_rejects_pre_baseline_schema(self, test_db):
        """Schema 15 is the baseline; older databases require an explicit future migration."""
        from app.services.core.database_bootstrap_service import ensure_database_ready

        with test_db.get_db() as conn:
            conn.execute("DELETE FROM schema_info WHERE key = 'version'")
            conn.execute(
                "INSERT INTO schema_info (key, value) VALUES (?, ?)",
                ('version', '14'),
            )

        with pytest.raises(RuntimeError) as exc_info:
            ensure_database_ready()

        assert 'Unsupported database schema version 14' in str(exc_info.value)
        with test_db.get_db() as conn:
            conn.execute(
                "INSERT INTO schema_info (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ('version', str(test_db.SCHEMA_VERSION)),
            )
    
    def test_get_connection_returns_same_connection_for_thread(self, test_db):
        """Test that get_connection returns the same connection in a single thread."""
        conn1 = test_db.get_connection()
        conn2 = test_db.get_connection()
        assert conn1 is conn2
    
    def test_close_connection_clears_thread_local(self, test_db):
        """Test that close_connection properly clears the connection."""
        conn1 = test_db.get_connection()
        test_db.close_connection()
        conn2 = test_db.get_connection()
        # After close, should get a new connection
        assert conn1 is not conn2

    def test_dynamic_pragma_settings_pro(self, test_db, mock_config):
        """Test that PRO tier applies aggressive pragmas."""
        mock_config('AUTO_OPTIMIZE_FOR_HARDWARE', True)
        
        with patch('app.services.system.system_stats_service.get_hardware_tier', return_value='PRO'):
            # Force a new connection to apply pragmas
            test_db.close_connection()
            conn = test_db.get_connection()
            
            # Check cache_size (128MB = 131072 sectors)
            cursor = conn.execute("PRAGMA cache_size")
            row = cursor.fetchone()
            assert row[0] == -131072
            
            # Check mmap_size (1GB)
            cursor = conn.execute("PRAGMA mmap_size")
            row = cursor.fetchone()
            assert row[0] == 1073741824

    def test_dynamic_pragma_settings_standard(self, test_db, mock_config):
        """Test that STANDARD tier applies enhanced pragmas."""
        mock_config('AUTO_OPTIMIZE_FOR_HARDWARE', True)
        
        with patch('app.services.system.system_stats_service.get_hardware_tier', return_value='STANDARD'):
            # Force a new connection to apply pragmas
            test_db.close_connection()
            conn = test_db.get_connection()
            
            # Check cache_size (32MB = 32768 sectors)
            cursor = conn.execute("PRAGMA cache_size")
            row = cursor.fetchone()
            assert row[0] == -32768
            
            # Check mmap_size (256MB)
            cursor = conn.execute("PRAGMA mmap_size")
            row = cursor.fetchone()
            assert row[0] == 268435456

    def test_dynamic_pragma_settings_disabled(self, test_db, mock_config):
        """Test that default pragmas are applied when auto-optimize is disabled."""
        mock_config('AUTO_OPTIMIZE_FOR_HARDWARE', False)
        
        # Force a new connection to apply pragmas
        test_db.close_connection()
        conn = test_db.get_connection()
        
        # Check cache_size (Default 8MB = 8000 sectors)
        cursor = conn.execute("PRAGMA cache_size")
        row = cursor.fetchone()
        assert row[0] == -8000
        
        # Check mmap_size (Default 64MB)
        cursor = conn.execute("PRAGMA mmap_size")
        row = cursor.fetchone()
        assert row[0] == 67108864




class TestIndexCleanupSafety:
    """Safety tests for stale/aggressive media_index cleanup paths."""

    def test_cleanup_stale_deletes_unresolved_auto_categories(self, test_db):
        """Unresolved auto:: category paths must be deleted, as it implies the USB is unplugged."""
        test_db.upsert_media_index_entry(
            category_id='auto::ghost::missing_drive::movies',
            category_path='',
            rel_path='folder/file.mp4',
            size=123,
            mtime=time.time(),
            file_hash='hash-a',
            file_type='video'
        )

        with patch('app.services.media.media_index_service._resolve_category_path_from_id', return_value=None):
            deleted = test_db.cleanup_stale_media_index_entries(limit=100)

        assert deleted == 1
        with test_db.get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM media_index WHERE category_id = ?",
                ('auto::ghost::missing_drive::movies',)
            ).fetchone()
            assert row['count'] == 0

    def test_aggressive_cleanup_deletes_unresolved_auto_categories(self, test_db):
        """Aggressive cleanup must purge unresolved auto:: categories (unplugged USBs)."""
        test_db.upsert_media_index_entry(
            category_id='auto::ghost::another_missing::tv',
            category_path='',
            rel_path='season1/ep1.mp4',
            size=456,
            mtime=time.time(),
            file_hash='hash-b',
            file_type='video'
        )

        with patch('app.services.media.media_index_service._resolve_category_path_from_id', return_value=None):
            deleted = test_db.cleanup_media_index_by_category_path_check()

        assert deleted == 1
        with test_db.get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM media_index WHERE category_id = ?",
                ('auto::ghost::another_missing::tv',)
            ).fetchone()
            assert row['count'] == 0
        


class TestCategoryOperations:
    """Tests for category CRUD operations."""
    
    def test_save_category(self, test_db):
        """Test saving a new category."""
        success = test_db.save_category(
            category_id='manual-cat-1',
            name='My Photos',
            path='/home/user/photos'
        )
        
        assert success is True
    
    def test_load_categories(self, test_db):
        """Test loading saved categories."""
        # Save some categories
        test_db.save_category('cat-1', 'Category One', '/path/one')
        test_db.save_category('cat-2', 'Category Two', '/path/two')
        
        categories = test_db.load_categories()
        
        assert len(categories) >= 2
        cat_ids = [c['id'] for c in categories]
        assert 'cat-1' in cat_ids
        assert 'cat-2' in cat_ids
    
    def test_delete_category(self, test_db):
        """Test deleting a category."""
        test_db.save_category('cat-to-delete', 'Delete Me', '/path/delete')
        
        # Verify it exists
        categories = test_db.load_categories()
        assert any(c['id'] == 'cat-to-delete' for c in categories)
        
        # Delete it
        result = test_db.delete_category('cat-to-delete')
        assert result is True
        
        # Verify it's gone
        categories = test_db.load_categories()
        assert not any(c['id'] == 'cat-to-delete' for c in categories)
    
    def test_delete_nonexistent_category_returns_false(self, test_db):
        """Test that deleting non-existent category returns False."""
        result = test_db.delete_category('nonexistent-category-id')
        assert result is False
    
    def test_category_exists_by_path(self, test_db):
        """Test checking if category exists by path."""
        test_db.save_category('path-check', 'Path Check', '/unique/test/path')
        
        assert test_db.category_exists_by_path('/unique/test/path') is True
        assert test_db.category_exists_by_path('/nonexistent/path') is False
    
    def test_save_categories_bulk(self, test_db):
        """Test bulk saving categories."""
        categories = [
            {'id': 'bulk-1', 'name': 'Bulk One', 'path': '/bulk/one'},
            {'id': 'bulk-2', 'name': 'Bulk Two', 'path': '/bulk/two'},
            {'id': 'bulk-3', 'name': 'Bulk Three', 'path': '/bulk/three'},
        ]
        
        success = test_db.save_categories_bulk(categories)
        assert success is True
        
        loaded = test_db.load_categories()
        assert len(loaded) == 3
    
    def test_save_categories_bulk_replaces_existing(self, test_db):
        """Test that bulk save replaces existing categories."""
        # Save initial categories
        test_db.save_categories_bulk([
            {'id': 'old-1', 'name': 'Old One', 'path': '/old/one'},
        ])
        
        # Bulk save new categories (should replace)
        test_db.save_categories_bulk([
            {'id': 'new-1', 'name': 'New One', 'path': '/new/one'},
            {'id': 'new-2', 'name': 'New Two', 'path': '/new/two'},
        ])
        
        loaded = test_db.load_categories()
        cat_ids = [c['id'] for c in loaded]
        
        assert 'old-1' not in cat_ids
        assert 'new-1' in cat_ids
        assert 'new-2' in cat_ids


class TestVideoProgressOperations:
    """Tests for per-video progress tracking mode.

    All progress is scoped by (video_path, profile_id) composite key.
    """

    PROFILE_A = 'test-profile'
    PROFILE_B = 'other-profile'

    def test_save_video_progress(self, test_db, mock_config):
        """Test saving video-specific progress with explicit profile_id."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        success, message = test_db.save_video_progress(
            video_path='/media/movie.mp4',
            category_id='movies',
            video_timestamp=1200.5,
            video_duration=7200.0,
            thumbnail_url='/thumbnails/movie.jpg',
            profile_id=self.PROFILE_A,
        )

        assert success is True

    def test_save_video_progress_disabled_when_wrong_mode(self, test_db, mock_config):
        """Test video progress is disabled in category mode."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        success, message = test_db.save_video_progress(
            video_path='/media/movie.mp4',
            category_id='movies',
            video_timestamp=100.0,
            profile_id=self.PROFILE_A,
        )

        assert success is True
        assert 'saved' in message.lower()

    def test_get_video_progress(self, test_db, mock_config):
        """Test retrieving video-specific progress with explicit profile_id."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        test_db.save_video_progress(
            video_path='/media/test_video.mp4',
            category_id='test-cat',
            video_timestamp=500.0,
            video_duration=2000.0,
            profile_id=self.PROFILE_A,
        )

        progress = test_db.get_video_progress('/media/test_video.mp4', profile_id=self.PROFILE_A)

        assert progress is not None
        assert progress['video_timestamp'] == 500.0
        assert progress['video_duration'] == 2000.0

    def test_get_category_video_progress(self, test_db, mock_config):
        """Test retrieving all video progress for a category."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        test_db.save_video_progress('/media/video1.mp4', 'my-category', 100.0, profile_id=self.PROFILE_A)
        test_db.save_video_progress('/media/video2.mp4', 'my-category', 200.0, profile_id=self.PROFILE_A)
        test_db.save_video_progress('/media/video3.mp4', 'other-category', 300.0, profile_id=self.PROFILE_A)

        progress = test_db.get_category_video_progress('my-category', profile_id=self.PROFILE_A)

        assert len(progress) == 2
        assert '/media/video1.mp4' in progress
        assert '/media/video2.mp4' in progress
        assert '/media/video3.mp4' not in progress

    def test_get_all_video_progress(self, test_db, mock_config):
        """Test retrieving all video progress sorted by last_watched."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        for i in range(5):
            test_db.save_video_progress(
                f'/media/video{i}.mp4',
                f'category-{i}',
                float(i * 100),
                profile_id=self.PROFILE_A,
            )
            time.sleep(0.01)

        all_progress = test_db.get_all_video_progress(limit=3, profile_id=self.PROFILE_A)

        assert len(all_progress) == 3
        # Most recent should be first
        assert all_progress[0]['video_path'] == '/media/video4.mp4'

    def test_delete_all_video_progress(self, test_db, mock_config):
        """Test deleting all video progress for a profile."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        test_db.save_video_progress('/media/v1.mp4', 'cat', 100.0, profile_id=self.PROFILE_A)
        test_db.save_video_progress('/media/v2.mp4', 'cat', 200.0, profile_id=self.PROFILE_A)

        result = test_db.delete_all_video_progress(profile_id=self.PROFILE_A)
        assert result['success'] is True

        assert test_db.get_video_progress('/media/v1.mp4', profile_id=self.PROFILE_A) is None

    def test_get_most_recent_video_progress(self, test_db, mock_config):
        """Test getting most recent video progress for a category."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        test_db.save_video_progress('/media/old.mp4', 'test-cat', 50.0, profile_id=self.PROFILE_A)
        time.sleep(0.01)
        test_db.save_video_progress('/media/recent.mp4', 'test-cat', 100.0, profile_id=self.PROFILE_A)

        progress = test_db.get_most_recent_video_progress('test-cat', profile_id=self.PROFILE_A)

        assert progress is not None
        assert progress['video_timestamp'] == 100.0

    def test_cross_profile_progress_isolation(self, test_db, mock_config):
        """Progress for one profile must NOT leak to another profile.

        The composite PK (video_path, profile_id) ensures each profile
        has its own independent progress for the same video.
        """
        mock_config('SAVE_VIDEO_PROGRESS', True)
        video = '/media/shared_movie.mp4'

        # Profile A watches to 500s
        test_db.save_video_progress(video, 'movies', 500.0, video_duration=3600.0, profile_id=self.PROFILE_A)
        # Profile B watches to 1200s
        test_db.save_video_progress(video, 'movies', 1200.0, video_duration=3600.0, profile_id=self.PROFILE_B)

        progress_a = test_db.get_video_progress(video, profile_id=self.PROFILE_A)
        progress_b = test_db.get_video_progress(video, profile_id=self.PROFILE_B)

        assert progress_a is not None
        assert progress_b is not None
        assert progress_a['video_timestamp'] == 500.0
        assert progress_b['video_timestamp'] == 1200.0

    def test_delete_profile_progress_does_not_affect_other_profiles(self, test_db, mock_config):
        """Deleting progress for one profile must leave other profiles' progress intact."""
        mock_config('SAVE_VIDEO_PROGRESS', True)
        video = '/media/isolation_test.mp4'

        test_db.save_video_progress(video, 'cat', 100.0, profile_id=self.PROFILE_A)
        test_db.save_video_progress(video, 'cat', 200.0, profile_id=self.PROFILE_B)

        # Delete only profile A's progress
        test_db.delete_all_video_progress(profile_id=self.PROFILE_A)

        assert test_db.get_video_progress(video, profile_id=self.PROFILE_A) is None
        progress_b = test_db.get_video_progress(video, profile_id=self.PROFILE_B)
        assert progress_b is not None
        assert progress_b['video_timestamp'] == 200.0
    

class TestThreadSafety:
    """Tests for thread safety and concurrent access."""
    
    def test_concurrent_video_progress_saves(self, test_db, mock_config):
        """Test that concurrent video progress saves don't cause issues."""
        mock_config('SAVE_VIDEO_PROGRESS', True)

        errors = []

        def save_progress_thread(thread_id):
            try:
                profile_id = f'thread-profile-{thread_id}'
                for i in range(10):
                    test_db.save_video_progress(
                        video_path=f'/media/thread-{thread_id}-video-{i}.mp4',
                        category_id=f'cat-{thread_id}',
                        video_timestamp=float(i * 10),
                        profile_id=profile_id,
                    )
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=save_progress_thread, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors occurred: {errors}"
    
    def test_concurrent_category_operations(self, test_db):
        """Test concurrent category operations."""
        errors = []
        
        def category_operations(thread_id):
            try:
                for i in range(5):
                    test_db.save_category(
                        f'concurrent-{thread_id}-{i}',
                        f'Category {thread_id}-{i}',
                        f'/path/{thread_id}/{i}'
                    )
                # Read operations
                test_db.load_categories()
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=category_operations, args=(i,)) for i in range(3)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors occurred: {errors}"




class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_unicode_in_category_name(self, test_db):
        """Test handling of unicode characters in category names."""
        success = test_db.save_category(
            'unicode-cat',
            'カテゴリー 日本語 🎬',
            '/path/to/unicode'
        )
        
        assert success is True
        
        categories = test_db.load_categories()
        cat = next((c for c in categories if c['id'] == 'unicode-cat'), None)
        assert cat is not None
        assert cat['name'] == 'カテゴリー 日本語 🎬'
    
    def test_very_long_path(self, test_db):
        """Test handling of very long file paths."""
        long_path = '/very/long/' + 'subdir/' * 50 + 'final'
        
        success = test_db.save_category('long-path-cat', 'Long Path', long_path)
        assert success is True
        
        assert test_db.category_exists_by_path(long_path) is True
    


class TestMediaIndexBatchUpserts:
    """Tests for batch media_index upsert helper."""

    def test_batch_upsert_media_index_entries(self, test_db):
        """Should insert multiple rows in one call."""
        # Ensure category exists for consistency
        test_db.save_category('batch-cat', 'Batch Cat', '/tmp/batch-cat')

        ok, written = test_db.batch_upsert_media_index_entries(
            category_id='batch-cat',
            category_path='/tmp/batch-cat',
            file_entries=[
                {'name': 'a.mp4', 'size': 10, 'mtime': 1.0, 'type': 'video', 'hash': 'h1'},
                {'name': 'b.jpg', 'size': 20, 'mtime': 2.0, 'type': 'image', 'hash': 'h2'},
            ]
        )

        assert ok is True
        assert written == 2

        with test_db.get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM media_index WHERE category_id = ?",
                ('batch-cat',)
            ).fetchone()
            assert row['count'] == 2


class TestMediaIndexSearch:
    """Tests for media_index search behavior."""

    def test_search_media_index_matches_nested_rel_path(self, test_db):
        """Folder-name searches should match rel_path, not just basename."""
        now = time.time()
        with test_db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO media_index
                (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'search-cat:1',
                    'search-cat',
                    'Anime/Season1/Episode01.mkv',
                    'Anime/Season1',
                    'Episode01.mkv',
                    123,
                    now,
                    'h-search-1',
                    'video',
                    0,
                    now,
                    now,
                ),
            )

        results = test_db.search_media_index('season1', limit=25, show_hidden=True)
        assert len(results) == 1
        assert results[0]['rel_path'] == 'Anime/Season1/Episode01.mkv'

    def test_search_media_index_honors_limit(self, test_db):
        """Search results should honor the caller's limit."""
        now = time.time()
        with test_db.get_db() as conn:
            for i in range(5):
                conn.execute(
                    """
                    INSERT INTO media_index
                    (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f'search-limit:{i}',
                        'search-limit',
                        f'Shows/Deep/file{i}.mp4',
                        'Shows/Deep',
                        f'file{i}.mp4',
                        100 + i,
                        now + i,
                        f'h-limit-{i}',
                        'video',
                        0,
                        now + i,
                        now + i,
                    ),
                )

        results = test_db.search_media_index('deep', limit=2, show_hidden=True)
        assert len(results) == 2

    def test_search_media_paths_for_folder_matches_honors_limit(self, test_db):
        """Folder path helper should honor caller-provided limits."""
        now = time.time()
        with test_db.get_db() as conn:
            for i in range(4):
                conn.execute(
                    """
                    INSERT INTO media_index
                    (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f'folder-scan:{i}',
                        'folder-scan',
                        f'Shows/Deep/Nested{i}/file{i}.mp4',
                        f'Shows/Deep/Nested{i}',
                        f'file{i}.mp4',
                        100 + i,
                        now + i,
                        f'h-folder-{i}',
                        'video',
                        0,
                        now + i,
                        now + i,
                    ),
                )

        paths = test_db.search_media_paths_for_folder_matches('deep', limit=2, show_hidden=True)
        assert len(paths) == 2

    def test_search_media_category_ids_matches_auto_hierarchy(self, test_db):
        """Category-ID helper should find deep auto:: folder matches."""
        now = time.time()
        with test_db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO media_index
                (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'cat-id-search:1',
                    'auto::ghost::sda2::TV::ShowA::Season1',
                    'episode01.mkv',
                    '',
                    'episode01.mkv',
                    123,
                    now,
                    'h-cat-id-1',
                    'video',
                    0,
                    now,
                    now,
                ),
            )

        category_rows = test_db.search_media_category_ids('showa', limit=10, show_hidden=True)
        assert len(category_rows) == 1
        assert category_rows[0]['category_id'] == 'auto::ghost::sda2::TV::ShowA::Season1'

    def test_search_media_category_ids_honors_limit(self, test_db):
        """Category-ID helper should honor caller-provided limits."""
        now = time.time()
        with test_db.get_db() as conn:
            for i in range(4):
                conn.execute(
                    """
                    INSERT INTO media_index
                    (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f'cat-id-limit:{i}',
                        f'auto::ghost::sda2::TV::ShowA::Season{i}',
                        f'episode{i}.mkv',
                        '',
                        f'episode{i}.mkv',
                        100 + i,
                        now + i,
                        f'h-cat-id-limit-{i}',
                        'video',
                        0,
                        now + i,
                        now + i,
                    ),
                )

        category_rows = test_db.search_media_category_ids('showa', limit=2, show_hidden=True)
        assert len(category_rows) == 2

    def test_get_indexed_category_ids_honors_limit(self, test_db):
        """Indexed category ID helper should honor caller-provided limits."""
        now = time.time()
        with test_db.get_db() as conn:
            for i in range(4):
                conn.execute(
                    """
                    INSERT INTO media_index
                    (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f'indexed-cats-limit:{i}',
                        f'auto::ghost::sda2::TV::Show{i}',
                        f'episode{i}.mkv',
                        '',
                        f'episode{i}.mkv',
                        100 + i,
                        now + i,
                        f'h-indexed-cats-{i}',
                        'video',
                        0,
                        now + i,
                        now + i,
                    ),
                )

        category_ids = test_db.get_indexed_category_ids(show_hidden=True, limit=2)
        assert len(category_ids) == 2

    def test_get_indexed_category_ids_filters_hidden_categories(self, test_db):
        """Hidden categories should be excluded when show_hidden is false."""
        now = time.time()
        visible_id = 'auto::ghost::sda2::TV::Visible'
        hidden_id = 'auto::ghost::sda2::TV::Hidden'

        with test_db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO media_index
                (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'indexed-cats-visible',
                    visible_id,
                    'visible.mkv',
                    '',
                    'visible.mkv',
                    120,
                    now,
                    'h-indexed-visible',
                    'video',
                    0,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO media_index
                (id, category_id, rel_path, parent_path, name, size, mtime, hash, type, is_hidden, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'indexed-cats-hidden',
                    hidden_id,
                    'hidden.mkv',
                    '',
                    'hidden.mkv',
                    121,
                    now + 1,
                    'h-indexed-hidden',
                    'video',
                    0,
                    now + 1,
                    now + 1,
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO hidden_categories (category_id, hidden_at, hidden_by) VALUES (?, ?, ?)",
                (hidden_id, now + 2, 'test'),
            )

        visible_only = test_db.get_indexed_category_ids(show_hidden=False, limit=50)
        with_hidden = test_db.get_indexed_category_ids(show_hidden=True, limit=50)

        assert visible_id in visible_only
        assert hidden_id not in visible_only
        assert hidden_id in with_hidden
