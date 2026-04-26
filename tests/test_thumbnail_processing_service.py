"""Tests for thumbnail processing preflight behavior."""

import os
from unittest.mock import MagicMock, patch


class TestThumbnailProcessingService:
    """Regression coverage for thumbnail queue selection."""

    def test_force_refresh_skips_up_to_date_existing_thumbnail(self, app_context, tmp_path):
        """Index refresh should not requeue media whose thumbnail is already current."""
        from app.services.media.thumbnail_processing_service import (
            process_category_thumbnails_smart,
        )

        category_path = tmp_path / 'Movies'
        thumbnail_dir = category_path / '.ghosthub' / 'thumbnails'
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        media_path = category_path / 'clip.mp4'
        media_path.write_bytes(b'video-bytes')
        media_mtime = media_path.stat().st_mtime

        thumb_path = thumbnail_dir / 'clip.jpeg'
        thumb_path.write_bytes(b'jpeg-bytes')
        os.utime(thumb_path, (media_mtime + 60, media_mtime + 60))

        runtime = MagicMock()
        with patch(
            'app.services.media.thumbnail_processing_service.registry.require',
            return_value=runtime,
        ):
            stats = process_category_thumbnails_smart(
                str(category_path),
                [],
                'movies',
                force_refresh=True,
                files_to_process=[{
                    'name': 'clip.mp4',
                    'size': media_path.stat().st_size,
                    'mtime': media_mtime,
                }],
            )

        assert stats == {'checked': 1, 'queued': 0, 'skipped': 0, 'existing': 1}
        runtime.start_thumbnail_batch.assert_not_called()
        runtime.queue_thumbnail.assert_not_called()

    def test_force_refresh_respects_permanent_failure_marker(self, app_context, tmp_path):
        """A permanently failed file should not be requeued just because indexing was forced."""
        from app.services.media.thumbnail_processing_service import (
            process_category_thumbnails_smart,
        )
        from app.utils.media_utils import _create_permanent_failure_marker

        category_path = tmp_path / 'Movies'
        thumbnail_dir = category_path / '.ghosthub' / 'thumbnails'
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        media_path = category_path / 'broken.mp4'
        media_path.write_bytes(b'broken-video')
        _create_permanent_failure_marker(str(thumbnail_dir / 'broken.jpeg'), 'no_video_stream')

        runtime = MagicMock()
        with patch(
            'app.services.media.thumbnail_processing_service.registry.require',
            return_value=runtime,
        ):
            stats = process_category_thumbnails_smart(
                str(category_path),
                [],
                'movies',
                force_refresh=True,
                files_to_process=[{
                    'name': 'broken.mp4',
                    'size': media_path.stat().st_size,
                    'mtime': media_path.stat().st_mtime,
                }],
            )

        assert stats == {'checked': 1, 'queued': 0, 'skipped': 1, 'existing': 0}
        runtime.start_thumbnail_batch.assert_not_called()
        runtime.queue_thumbnail.assert_not_called()
