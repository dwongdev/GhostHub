"""Tests for admin USB user data transfer routes."""

from tests.conftest import register_test_storage_drive


def test_user_data_routes_require_admin(client, app_context):
    response = client.get('/api/admin/user-data/drives')
    assert response.status_code in (401, 403)


def test_drives_route_returns_registered_drive(admin_client, app_context, tmp_path):
    drive = register_test_storage_drive(tmp_path, name='BackupDrive', writable=True, device_key='drive-route')

    response = admin_client.get('/api/admin/user-data/drives')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['drives'][0]['id'] == drive['id']
    assert payload['drives'][0]['writable'] is True
    assert 'free_formatted' in payload['drives'][0]


def test_export_route_returns_pollable_job(admin_client, app_context, tmp_path):
    drive = register_test_storage_drive(tmp_path, writable=True, device_key='drive-job')

    response = admin_client.post('/api/admin/user-data/export', json={'drive_id': drive['id']})

    assert response.status_code == 200
    job_id = response.get_json()['job_id']
    job_response = admin_client.get(f'/api/admin/user-data/jobs/{job_id}')
    assert job_response.status_code == 200
    assert job_response.get_json()['job']['id'] == job_id


def test_export_route_rejects_non_writable_drive(admin_client, app_context, tmp_path):
    drive = register_test_storage_drive(tmp_path, writable=False, device_key='drive-readonly-route')

    response = admin_client.post('/api/admin/user-data/export', json={'drive_id': drive['id']})

    assert response.status_code == 400
    assert response.get_json()['success'] is False
    assert 'not writable' in response.get_json()['error']


def test_delete_route_rejects_non_export_zip(admin_client, app_context, tmp_path):
    drive = register_test_storage_drive(tmp_path, writable=True, device_key='drive-delete-route')
    backup_dir = tmp_path / 'GhostHubBackups'
    backup_dir.mkdir()
    export_path = backup_dir / 'ghosthub-user-data-20260514-130000.zip'
    export_path.write_text('not a zip', encoding='utf-8')

    response = admin_client.delete(
        '/api/admin/user-data/export',
        json={'drive_id': drive['id'], 'filename': export_path.name},
    )

    assert response.status_code == 400
    assert export_path.exists()
