"""
Tests for File Utilities
------------------------
Comprehensive tests for file operations including:
- Category loading/saving (SQLite-backed)
- Directory size checking
"""
import pytest
from unittest.mock import patch


class TestCategoryFileOperations:
    """Tests for category file operations (now SQLite-backed)."""
    
    def test_load_categories_empty(self, app_context, test_db):
        """Test loading categories when none exist."""
        from app.utils.file_utils import load_categories
        
        categories = load_categories()
        
        assert isinstance(categories, list)
        # May be empty or have some depending on test setup
    
    def test_save_categories(self, app_context, test_db):
        """Test saving categories."""
        from app.utils.file_utils import save_categories, load_categories
        
        categories = [
            {'id': 'cat-1', 'name': 'Category One', 'path': '/path/one'},
            {'id': 'cat-2', 'name': 'Category Two', 'path': '/path/two'},
        ]
        
        result = save_categories(categories)
        
        assert result is True
        
        # Verify they were saved
        loaded = load_categories()
        assert len(loaded) == 2
    
    def test_save_categories_replaces_existing(self, app_context, test_db):
        """Test that saving categories replaces existing ones."""
        from app.utils.file_utils import save_categories, load_categories
        
        # Save initial categories
        save_categories([
            {'id': 'old-1', 'name': 'Old', 'path': '/old'}
        ])
        
        # Save new categories
        save_categories([
            {'id': 'new-1', 'name': 'New One', 'path': '/new/one'},
            {'id': 'new-2', 'name': 'New Two', 'path': '/new/two'},
        ])
        
        loaded = load_categories()
        cat_ids = [c['id'] for c in loaded]
        
        assert 'old-1' not in cat_ids
        assert 'new-1' in cat_ids
        assert 'new-2' in cat_ids
    
    def test_save_empty_categories(self, app_context, test_db):
        """Test saving empty category list."""
        from app.utils.file_utils import save_categories, load_categories
        
        # First save some categories
        save_categories([
            {'id': 'temp', 'name': 'Temp', 'path': '/temp'}
        ])
        
        # Then save empty list
        result = save_categories([])
        
        assert result is True
        
        loaded = load_categories()
        assert len(loaded) == 0
    
    def test_load_categories_error_returns_empty_list(self, app_context):
        """Test that load_categories returns empty list on error."""
        from app.utils.file_utils import load_categories
        
        with patch('app.services.media.category_persistence_service.load_categories', side_effect=Exception("DB error")):
            categories = load_categories()
            
            assert categories == []


class TestDirectorySize:
    """Tests for directory size checking."""
    
    def test_is_large_directory_small(self, app_context, tmp_path):
        """Test is_large_directory for small directory."""
        from app.utils.file_utils import is_large_directory
        
        # Create directory with few files
        small_dir = tmp_path / 'small'
        small_dir.mkdir()
        for i in range(5):
            (small_dir / f'file{i}.jpg').write_bytes(b'content')
        
        result = is_large_directory(str(small_dir), threshold=50)
        
        assert result is False
    
    def test_is_large_directory_large(self, app_context, tmp_path):
        """Test is_large_directory for large directory."""
        from app.utils.file_utils import is_large_directory
        
        # Create directory with many files
        large_dir = tmp_path / 'large'
        large_dir.mkdir()
        for i in range(100):
            (large_dir / f'file{i}.jpg').write_bytes(b'content')
        
        result = is_large_directory(str(large_dir), threshold=50)
        
        assert result is True
    
    def test_is_large_directory_nonexistent(self, app_context):
        """Test is_large_directory with non-existent directory."""
        from app.utils.file_utils import is_large_directory
        
        result = is_large_directory('/nonexistent/path', threshold=50)
        
        assert result is False
    
    def test_is_large_directory_default_threshold(self, app_context, tmp_path):
        """Test is_large_directory with default threshold."""
        from app.utils.file_utils import is_large_directory
        
        test_dir = tmp_path / 'threshold_test'
        test_dir.mkdir()
        
        # Create exactly 50 files (default threshold is 50)
        for i in range(50):
            (test_dir / f'file{i}.jpg').write_bytes(b'x')
        
        # 50 files should NOT be considered large (threshold is > 50)
        result = is_large_directory(str(test_dir))
        
        assert result is False


class TestCategoriesFilepath:
    """Tests for categories filepath utilities."""
    
    def test_get_categories_filepath(self, app_context):
        """Test getting categories file path."""
        from app.utils.file_utils import get_categories_filepath
        
        filepath = get_categories_filepath()
        
        assert isinstance(filepath, str)
        assert 'media_categories.json' in filepath
    
    def test_init_categories_file_is_noop(self, app_context):
        """Test that init_categories_file is a no-op (SQLite migration)."""
        from app.utils.file_utils import init_categories_file
        
        # Should not raise any errors
        init_categories_file()


class TestEdgeCases:
    """Tests for edge cases in file utilities."""

    def test_categories_with_special_paths(self, app_context, test_db):
        """Test categories with special characters in paths."""
        from app.utils.file_utils import save_categories, load_categories
        
        categories = [
            {'id': 'special-1', 'name': 'Special', 'path': '/path/with spaces/category'},
            {'id': 'special-2', 'name': 'Unicode', 'path': '/путь/到/folder'},
        ]
        
        save_categories(categories)
        loaded = load_categories()
        
        paths = [c['path'] for c in loaded]
        assert '/path/with spaces/category' in paths
        assert '/путь/到/folder' in paths
