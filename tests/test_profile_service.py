"""Tests for profile CRUD service."""

import pytest


class TestProfileService:
    def test_create_and_list_profile(self, app_context):
        from app.services.core import profile_service

        created = profile_service.create_profile('Alice Service List', avatar_icon='ghost')
        profiles = profile_service.list_profiles()

        assert created['id']
        assert created['name'] == 'Alice Service List'
        assert created['avatar_icon'] == 'ghost'
        assert any(profile['id'] == created['id'] for profile in profiles)

    def test_create_profile_rejects_case_insensitive_duplicate(self, app_context):
        from app.services.core import profile_service

        profile_service.create_profile('Alice Duplicate Service')

        with pytest.raises(ValueError):
            profile_service.create_profile('alice duplicate service')

    def test_rename_profile_updates_name(self, app_context):
        from app.services.core import profile_service

        created = profile_service.create_profile('Movie Night Rename')
        renamed = profile_service.rename_profile(created['id'], 'Family Night Rename')

        assert renamed is not None
        assert renamed['name'] == 'Family Night Rename'

    def test_update_profile_updates_name_color_and_icon(self, app_context):
        from app.services.core import profile_service

        created = profile_service.create_profile('Movie Night Update', '#112233', 'spark')
        updated = profile_service.update_profile(
            created['id'],
            name='Family Night Update',
            avatar_color='#445566',
            avatar_icon='orbit',
        )

        assert updated is not None
        assert updated['name'] == 'Family Night Update'
        assert updated['avatar_color'] == '#445566'
        assert updated['avatar_icon'] == 'orbit'

    def test_update_profile_rejects_invalid_avatar_icon(self, app_context):
        from app.services.core import profile_service

        created = profile_service.create_profile('Bad Icon Profile')

        with pytest.raises(ValueError):
            profile_service.update_profile(created['id'], avatar_icon='../../oops')

    def test_update_profile_updates_preferences(self, app_context):
        from app.services.core import profile_service

        created = profile_service.create_profile('Prefs User')
        updated = profile_service.update_profile(
            created['id'],
            preferences={
                'theme': 'midnight',
                'layout': 'gallery',
                'motion': 'reduced',
                'features': {
                    'chat': False,
                    'search': True,
                },
            },
        )

        assert updated is not None
        assert updated['preferences']['theme'] == 'midnight'
        assert updated['preferences']['layout'] == 'gallery'
        assert updated['preferences']['motion'] == 'reduced'
        assert updated['preferences']['features']['chat'] is False
        assert updated['preferences']['features']['search'] is True
        assert updated['preferences']['features']['syncButton'] is None

    def test_delete_profile_removes_profile_progress(self, app_context, mock_config):
        mock_config('SAVE_VIDEO_PROGRESS', True)

        from app.services.core import profile_service
        from app.services.media import video_progress_service

        created = profile_service.create_profile('Progress User')
        video_progress_service.save_video_progress(
            '/media/movie.mp4',
            'movies',
            123.0,
            profile_id=created['id'],
        )

        assert profile_service.delete_profile(created['id']) is True
        assert profile_service.get_profile(created['id']) is None
        assert video_progress_service.get_video_progress(
            '/media/movie.mp4',
            profile_id=created['id'],
        ) is None
