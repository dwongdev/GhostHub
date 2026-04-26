"""
Security regression tests for GhostStream controller routes.
"""

from unittest.mock import patch


class TestGhostStreamControllerSecurity:
    def test_public_transcode_rejects_arbitrary_source_urls(self, client, app_context):
        response = client.post('/api/ghoststream/transcode', json={
            'source': 'http://127.0.0.1:9999/internal.mkv',
        })

        assert response.status_code == 403
        assert 'administrators' in response.get_json()['error']

    def test_admin_may_transcode_arbitrary_source_urls(self, admin_client, app_context):
        with patch(
            'app.controllers.ghoststream.ghoststream_controller.ghoststream_service.transcode',
            return_value={
                'job_id': 'job-123',
                'status': 'processing',
                'progress': 0,
                'stream_url': '/api/ghoststream/stream/job-123/master.m3u8',
            },
        ):
            response = admin_client.post('/api/ghoststream/transcode', json={
                'source': 'http://127.0.0.1:9999/internal.mkv',
            })

        assert response.status_code == 200
        assert response.get_json()['job_id'] == 'job-123'

    def test_cache_serve_blocks_path_traversal(self, client, app_context, tmp_path):
        category_dir = tmp_path / 'category'
        cache_dir = category_dir / '.ghosthub' / 'transcodes'
        category_dir.mkdir()
        cache_dir.mkdir(parents=True)
        outside_file = tmp_path / 'secret.txt'
        outside_file.write_text('nope')

        with patch(
            'app.controllers.ghoststream.ghoststream_controller.get_category_by_id',
            return_value={'id': 'cat-1', 'path': str(category_dir)},
        ), patch(
            'app.controllers.ghoststream.ghoststream_controller.transcode_cache_service.get_cache_path',
            return_value=cache_dir,
        ):
            response = client.get('/api/ghoststream/cache/serve/cat-1/../../secret.txt')

        assert response.status_code == 404
