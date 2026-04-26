"""
Playlist Service
--------------
Manages a shared session-based playlist (virtual category).
Items are stored in memory and cleared when the server restarts.
"""
import logging
import json
import os

from app.services.core.runtime_config_service import get_runtime_instance_path

logger = logging.getLogger(__name__)

class PlaylistService:
    _filename = 'session_playlist.json'
    
    @classmethod
    def _get_filepath(cls):
        """Get the absolute path to the playlist file in the instance folder."""
        return os.path.join(get_runtime_instance_path(), cls._filename)

    @classmethod
    def _load_playlist(cls):
        """Load playlist from JSON file."""
        filepath = cls._get_filepath()
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading playlist: {e}")
            return []

    @classmethod
    def _save_playlist(cls, playlist):
        """Save playlist to JSON file."""
        filepath = cls._get_filepath()
        try:
            # Ensure instance directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(playlist, f)
            return True
        except Exception as e:
            logger.error(f"Error saving playlist: {e}")
            return False

    @classmethod
    def get_playlist(cls):
        return cls._load_playlist()
        
    @classmethod
    def add_item(cls, media_item):
        """
        Add an item to the shared playlist.
        media_item should be a dict with at least 'name', 'url', 'type'.
        """
        playlist = cls._load_playlist()
        
        # Avoid duplicates based on URL/path
        if any(item.get('url') == media_item.get('url') for item in playlist):
            return False, "Item already in playlist"
            
        playlist.append(media_item)
        if cls._save_playlist(playlist):
            logger.info(f"Added item to session playlist: {media_item.get('name')}")
            return True, "Item added to playlist"
        return False, "Failed to save playlist"
        
    @classmethod
    def remove_item(cls, media_url):
        """
        Remove an item from the playlist by URL.
        Returns (success, message) tuple.
        """
        playlist = cls._load_playlist()
        original_len = len(playlist)
        
        playlist = [item for item in playlist if item.get('url') != media_url]
        
        if len(playlist) == original_len:
            return False, "Item not found in playlist"
        
        if cls._save_playlist(playlist):
            logger.info(f"Removed item from session playlist: {media_url}")
            return True, "Item removed from playlist"
        return False, "Failed to save playlist"
        
    @classmethod
    def clear_playlist(cls):
        if cls._save_playlist([]):
            return True
        return False
        
    @classmethod
    def get_virtual_category(cls):
        """Return the playlist as a virtual category object."""
        playlist = cls._load_playlist()
        count = len(playlist)
        if count == 0:
            return None
            
        # Use the first image as thumbnail, or first item
        thumbnail_url = None
        contains_video = False
        
        for item in playlist:
            if item.get('type') == 'video':
                contains_video = True
            if not thumbnail_url and item.get('type') == 'image':
                thumbnail_url = item.get('url')
                
        if not thumbnail_url and playlist:
            thumbnail_url = playlist[0].get('thumbnailUrl') or playlist[0].get('url')

        return {
            'id': 'session-playlist',
            'name': 'Shared Session Playlist',
            'path': 'virtual://session-playlist',
            'mediaCount': count,
            'thumbnailUrl': thumbnail_url,
            'containsVideo': contains_video,
            'is_virtual': True
        }
