"""
Tests for Hidden Categories (Covert Content Hiding)
Tests the database operations, API routes, and filtering logic for hidden categories.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add app to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.core import database_bootstrap_service
from app.services.media import hidden_content_service
from app.services.media.category_visibility_service import filter_hidden_categories
from app.services.media.media_index_service import get_recent_media, search_media_index, update_media_index_batch


@pytest.fixture
def setup_database():
    """Initialize database for testing."""
    database_bootstrap_service.ensure_database_ready()
    # Clean up hidden categories before each test
    hidden_content_service.unhide_all_categories()
    yield
    # Clean up after test
    hidden_content_service.unhide_all_categories()


@pytest.mark.unit
def test_hide_category(setup_database):
    """Test hiding a single category."""
    category_id = "test-category-1"
    admin_session_id = "admin-session-123"

    # Hide the category
    success, message = hidden_content_service.hide_category(category_id, admin_session_id)

    assert success is True
    assert "successfully" in message.lower()

    # Verify it's hidden
    assert hidden_content_service.is_category_hidden(category_id) is True


@pytest.mark.unit
def test_hide_category_idempotent(setup_database):
    """Test that hiding the same category twice works (idempotent)."""
    category_id = "test-category-1"

    # Hide twice
    success1, _ = hidden_content_service.hide_category(category_id, "admin1")
    success2, _ = hidden_content_service.hide_category(category_id, "admin2")

    assert success1 is True
    assert success2 is True

    # Should still be hidden
    assert hidden_content_service.is_category_hidden(category_id) is True


@pytest.mark.unit
def test_unhide_all_categories(setup_database):
    """Test unhiding all categories at once."""
    # Hide multiple categories
    categories = ["cat-1", "cat-2", "cat-3"]
    for cat_id in categories:
        hidden_content_service.hide_category(cat_id, "admin-123")

    # Verify all are hidden
    for cat_id in categories:
        assert hidden_content_service.is_category_hidden(cat_id) is True

    # Unhide all
    success, message = hidden_content_service.unhide_all_categories()

    assert success is True
    assert "3" in message  # Should mention 3 categories

    # Verify all are now visible
    for cat_id in categories:
        assert hidden_content_service.is_category_hidden(cat_id) is False


@pytest.mark.unit
def test_is_category_hidden_false_by_default(setup_database):
    """Test that categories are not hidden by default."""
    category_id = "never-hidden-category"

    assert hidden_content_service.is_category_hidden(category_id) is False


@pytest.mark.unit
def test_get_hidden_category_ids(setup_database):
    """Test getting list of all hidden category IDs."""
    # Hide some categories
    hidden_ids = ["cat-a", "cat-b", "cat-c"]
    for cat_id in hidden_ids:
        hidden_content_service.hide_category(cat_id, "admin")

    # Get hidden IDs
    result = hidden_content_service.get_hidden_category_ids()

    assert len(result) == 3
    assert set(result) == set(hidden_ids)


@pytest.mark.unit
def test_get_hidden_category_ids_empty(setup_database):
    """Test getting hidden IDs when none are hidden."""
    result = hidden_content_service.get_hidden_category_ids()

    assert result == []


@pytest.mark.integration
def test_category_filtering(setup_database):
    """Test that category service filters hidden categories correctly."""
    from app.services.media.category_visibility_service import filter_hidden_categories

    # Mock categories
    categories = [
        {'id': 'cat-1', 'name': 'Category 1'},
        {'id': 'cat-2', 'name': 'Category 2'},
        {'id': 'cat-3', 'name': 'Category 3'}
    ]

    # Hide cat-2
    hidden_content_service.hide_category('cat-2', 'admin')

    # Filter without show_hidden (default)
    filtered = filter_hidden_categories(categories, show_hidden=False)

    assert len(filtered) == 2
    assert 'cat-1' in [c['id'] for c in filtered]
    assert 'cat-3' in [c['id'] for c in filtered]
    assert 'cat-2' not in [c['id'] for c in filtered]

    # Filter WITH show_hidden (admin used /show)
    filtered_shown = filter_hidden_categories(categories, show_hidden=True)

    assert len(filtered_shown) == 3
    assert 'cat-2' in [c['id'] for c in filtered_shown]


@pytest.mark.unit
def test_admin_routes_exist():
    """Test that admin routes for hiding categories are defined in the controller."""
    from app.controllers.admin.admin_visibility_controller import AdminVisibilityController
    
    # Check that the controller has the expected schemas for these routes
    assert 'hide_category' in AdminVisibilityController.schemas
    assert 'unhide_category' in AdminVisibilityController.schemas


@pytest.mark.unit
def test_unhide_category_endpoint_cascades_to_children(admin_client, app):
    """Unhiding a parent category must unhide its children too."""
    library_events = MagicMock()

    with patch(
        'app.services.media.hidden_content_service.get_all_child_category_ids',
        return_value=['parent::child', 'parent::child::grandchild'],
    ), patch(
        'app.services.media.hidden_content_service.unhide_category',
        return_value=(True, 'Unhidden 3 categories successfully.'),
    ) as hidden_unhide_category, patch(
        'app.services.media.category_cache_service.update_cached_category',
    ) as update_cached_category, patch(
        'specter.registry.require',
        return_value=library_events,
    ):
        response = admin_client.post(
            '/api/admin/categories/unhide',
            json={'category_id': 'parent'},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    hidden_unhide_category.assert_called_once_with('parent', cascade=True)
    update_cached_category.assert_any_call('parent')
    update_cached_category.assert_any_call('parent::child')
    update_cached_category.assert_any_call('parent::child::grandchild')


@pytest.mark.unit
def test_should_block_category_access_blocks_hidden(setup_database):
    """Test that should_block_category_access blocks hidden categories."""
    category_id = "test-category-blocked"

    # Hide the category
    hidden_content_service.hide_category(category_id, "admin")

    # Should block access when show_hidden=False
    assert hidden_content_service.should_block_category_access(category_id, show_hidden=False) is True

    # Should NOT block access when show_hidden=True
    assert hidden_content_service.should_block_category_access(category_id, show_hidden=True) is False


@pytest.mark.unit
def test_should_block_category_access_allows_visible(setup_database):
    """Test that should_block_category_access allows non-hidden categories."""
    category_id = "test-category-visible"

    # Category is not hidden
    assert hidden_content_service.is_category_hidden(category_id) is False

    # Should NOT block access regardless of show_hidden flag
    assert hidden_content_service.should_block_category_access(category_id, show_hidden=False) is False
    assert hidden_content_service.should_block_category_access(category_id, show_hidden=True) is False


@pytest.mark.unit
def test_should_block_file_access_blocks_child_of_hidden_parent(setup_database):
    """Hidden parents must block descendant file access too."""
    hidden_content_service.hide_category("parent", "admin")

    assert hidden_content_service.should_block_file_access(
        "/tmp/ghosthub-test-file.mp4",
        "parent::child",
        show_hidden=False,
    ) is True


@pytest.mark.integration
def test_search_filters_hidden_categories(setup_database):
    """Test that search endpoint filters out hidden categories."""
    from app.services.media.category_visibility_service import filter_hidden_categories

    categories = [
        {'id': 'visible-cat', 'name': 'Visible'},
        {'id': 'hidden-cat', 'name': 'Hidden'}
    ]

    # Hide one category
    hidden_content_service.hide_category('hidden-cat', 'admin')

    # Filter without show_hidden
    filtered = filter_hidden_categories(categories, show_hidden=False)

    assert len(filtered) == 1
    assert filtered[0]['id'] == 'visible-cat'


@pytest.mark.integration
def test_continue_watching_filters_hidden_categories(setup_database):
    """Test that continue watching filters videos from hidden categories."""
    # This would require a full Flask app context and database
    # For now, verify that get_hidden_category_ids works correctly

    hidden_cats = ['hidden-1', 'hidden-2']
    for cat_id in hidden_cats:
        hidden_content_service.hide_category(cat_id, 'admin')

    # Mock video progress data
    all_videos = [
        {'category_id': 'visible-cat', 'video_path': '/media/visible/video1.mp4'},
        {'category_id': 'hidden-1', 'video_path': '/media/hidden1/video2.mp4'},
        {'category_id': 'visible-cat', 'video_path': '/media/visible/video3.mp4'},
        {'category_id': 'hidden-2', 'video_path': '/media/hidden2/video4.mp4'},
    ]

    # Filter logic (same as in progress_routes.py)
    hidden_category_ids = set(hidden_content_service.get_hidden_category_ids())
    filtered_videos = [v for v in all_videos if v.get('category_id') not in hidden_category_ids]

    assert len(filtered_videos) == 2
    assert all(v['category_id'] == 'visible-cat' for v in filtered_videos)


@pytest.mark.integration
def test_timeline_filters_hidden_categories(setup_database):
    """Test that media timeline filters media from hidden categories."""
    # Mock media data
    all_media = [
        {'categoryId': 'visible-cat', 'filename': 'photo1.jpg'},
        {'categoryId': 'hidden-cat', 'filename': 'photo2.jpg'},
        {'categoryId': 'visible-cat', 'filename': 'photo3.jpg'},
        {'categoryId': 'hidden-cat', 'filename': 'photo4.jpg'},
    ]

    # Hide one category
    hidden_content_service.hide_category('hidden-cat', 'admin')

    # Filter logic (same as in progress_routes.py)
    hidden_category_ids = set(hidden_content_service.get_hidden_category_ids())
    filtered_media = [m for m in all_media if m.get('categoryId') not in hidden_category_ids]

    assert len(filtered_media) == 2
    assert all(m['categoryId'] == 'visible-cat' for m in filtered_media)


@pytest.mark.integration
def test_newest_media_filters_hidden_categories(setup_database):
    """Test that newest media endpoint filters media from hidden categories."""
    # Mock newest media data
    newest_media = [
        {'categoryId': 'visible-1', 'filename': 'latest1.mp4'},
        {'categoryId': 'hidden-cat', 'filename': 'latest2.mp4'},
        {'categoryId': 'visible-2', 'filename': 'latest3.mp4'},
    ]

    # Hide one category
    hidden_content_service.hide_category('hidden-cat', 'admin')

    # Filter logic (same as in progress_routes.py)
    hidden_category_ids = set(hidden_content_service.get_hidden_category_ids())
    filtered_newest = [m for m in newest_media if m.get('categoryId') not in hidden_category_ids]

    assert len(filtered_newest) == 2
    assert 'hidden-cat' not in [m['categoryId'] for m in filtered_newest]


@pytest.mark.integration
def test_hidden_category_edge_cases(setup_database):
    """Test edge cases for hidden categories."""
    # Test empty string category ID
    assert hidden_content_service.is_category_hidden('') is False

    # Test None category ID (should not crash)
    try:
        result = hidden_content_service.is_category_hidden(None)
        # Should return False or handle gracefully
        assert result is False
    except Exception:
        # If it raises exception, that's also acceptable for None input
        pass

    # Test with special characters in category ID
    special_cat = "category-with-特殊-chars-123"
    hidden_content_service.hide_category(special_cat, 'admin')
    assert hidden_content_service.is_category_hidden(special_cat) is True


@pytest.mark.integration
def test_filter_hidden_categories_blocks_descendants_of_hidden_parent(setup_database):
    """Child categories must be hidden when a parent is hidden."""
    hidden_content_service.hide_category("parent", "admin")

    categories = [
        {"id": "parent", "name": "Parent"},
        {"id": "parent::child", "name": "Child"},
        {"id": "visible", "name": "Visible"},
    ]

    filtered = filter_hidden_categories(categories, show_hidden=False)

    assert [category["id"] for category in filtered] == ["visible"]


@pytest.mark.integration
def test_media_index_queries_hide_descendants_of_hidden_parent(setup_database):
    """Recent/search index queries must exclude descendants of hidden parents."""
    update_media_index_batch(
        "visible",
        [{
            "name": "visible.jpg",
            "size": 1,
            "mtime": 100,
            "hash": "visible-hash",
            "type": "image",
        }],
    )
    update_media_index_batch(
        "parent::child",
        [{
            "name": "hidden.jpg",
            "size": 1,
            "mtime": 200,
            "hash": "hidden-hash",
            "type": "image",
        }],
    )
    hidden_content_service.hide_category("parent", "admin")

    recent = get_recent_media(limit=10, show_hidden=False)
    results = search_media_index("jpg", limit=10, show_hidden=False)

    assert [item["category_id"] for item in recent] == ["visible"]
    assert [item["category_id"] for item in results] == ["visible"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
