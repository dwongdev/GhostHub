"""
Tests for Playlist Service
--------------------------
Tests for the shared session playlist functionality.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock

class TestPlaylistService:
    """Tests for PlaylistService operations."""
    
    @pytest.fixture
    def empty_playlist(self, app_context, tmp_path):
        """Clear playlist before test."""
        from app.services.media.playlist_service import PlaylistService
        # Patch the filepath to use a temp file
        with patch.object(PlaylistService, '_get_filepath', return_value=str(tmp_path / 'test_playlist.json')):
            PlaylistService.clear_playlist()
            yield PlaylistService

    def test_add_item(self, empty_playlist):
        """Test adding an item to the playlist."""
        item = {
            'name': 'Test Video',
            'url': '/media/test/video.mp4',
            'type': 'video',
            'thumbnailUrl': '/thumb.jpg'
        }
        
        success, message = empty_playlist.add_item(item)
        
        assert success is True
        playlist = empty_playlist.get_playlist()
        assert len(playlist) == 1
        assert playlist[0]['name'] == 'Test Video'

    def test_add_duplicate_item(self, empty_playlist):
        """Test adding a duplicate item fails."""
        item = {
            'name': 'Test Video',
            'url': '/media/test/video.mp4',
            'type': 'video'
        }
        
        empty_playlist.add_item(item)
        success, message = empty_playlist.add_item(item)
        
        assert success is False
        assert 'already in playlist' in message.lower()
        assert len(empty_playlist.get_playlist()) == 1

    def test_remove_item(self, empty_playlist):
        """Test removing an item from the playlist."""
        item = {
            'name': 'Test Video',
            'url': '/media/test/video.mp4',
            'type': 'video'
        }
        empty_playlist.add_item(item)
        
        success, message = empty_playlist.remove_item(item['url'])
        
        assert success is True
        assert len(empty_playlist.get_playlist()) == 0

    def test_remove_nonexistent_item(self, empty_playlist):
        """Test removing an item that doesn't exist."""
        success, message = empty_playlist.remove_item('/fake/url')
        
        assert success is False
        assert 'not found' in message.lower()

    def test_clear_playlist(self, empty_playlist):
        """Test clearing the playlist."""
        empty_playlist.add_item({'name': 'Item 1', 'url': '1', 'type': 'video'})
        empty_playlist.add_item({'name': 'Item 2', 'url': '2', 'type': 'video'})
        
        assert len(empty_playlist.get_playlist()) == 2
        
        empty_playlist.clear_playlist()
        
        assert len(empty_playlist.get_playlist()) == 0

    def test_get_virtual_category(self, empty_playlist):
        """Test getting the playlist as a virtual category."""
        # Empty playlist should return None
        assert empty_playlist.get_virtual_category() is None
        
        # Add item
        item = {
            'name': 'Test Video',
            'url': '/media/test/video.mp4',
            'type': 'video',
            'thumbnailUrl': '/thumb.jpg'
        }
        empty_playlist.add_item(item)
        
        category = empty_playlist.get_virtual_category()
        
        assert category is not None
        assert category['id'] == 'session-playlist'
        assert category['mediaCount'] == 1
        assert category['thumbnailUrl'] == '/thumb.jpg'
        assert category['containsVideo'] is True
        assert category['is_virtual'] is True
