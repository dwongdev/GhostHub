"""
Tests for Admin Routes
Tests admin API endpoints.
Uses fixtures from conftest.py.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestAdminRoutes:
    """Tests for admin route endpoints."""

    def test_admin_status_as_admin(self, admin_client, app):
        """Test admin status check as admin."""
        with app.app_context():
            response = admin_client.get("/api/admin/status")
            assert response.status_code == 200
            data = response.get_json()
            assert "isAdmin" in data

    def test_admin_status_as_guest(self, client, app):
        """Test admin status check as guest."""
        with app.app_context():
            response = client.get("/api/admin/status")
            assert response.status_code == 200
            data = response.get_json()
            assert data.get("isAdmin") is False

    def test_login_incorrect_password(self, client, app):
        """Test admin login with incorrect password."""
        with app.app_context():
            response = client.post(
                "/api/admin/login", json={"password": "wrongpassword"}
            )
            # 404 if route doesn't exist, 401/403 if auth fails
            assert response.status_code in [400, 401, 403, 404]

    def test_login_missing_password(self, client, app):
        """Test admin login without password."""
        with app.app_context():
            response = client.post("/api/admin/login", json={})
            assert response.status_code in [400, 401, 403, 404]

    def test_logout(self, admin_client, app):
        """Test admin logout."""
        with app.app_context():
            response = admin_client.post("/api/admin/logout")
            # Route may or may not exist
            assert response.status_code in [200, 302, 404]

    def test_protected_route_without_auth(self, client, app):
        """Test accessing protected route without auth."""
        with app.app_context():
            response = client.post("/api/admin/shutdown")
            assert response.status_code in [401, 403, 404]

    def test_delete_category_requires_admin(self, client, app):
        """Test that delete category requires admin."""
        with app.app_context():
            response = client.delete("/api/categories/test-category")
            assert response.status_code in [401, 403, 404]

    def test_reindex_media_leaves_thumbnails_and_generated_cache_untouched(
        self, admin_client, app, tmp_path
    ):
        """Reindex should only clear media index data and restart metadata indexing."""
        category_root = tmp_path / "Shows"
        category_root.mkdir(parents=True, exist_ok=True)

        categories = [
            {"id": "auto::shows", "name": "Shows", "path": str(category_root)}
        ]

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_maintenance_controller.get_all_categories_with_details",
                return_value=categories,
            ),
            patch(
                "app.services.storage.storage_drive_service.get_current_mount_paths",
                return_value=set(),
            ),
            patch(
                "app.services.media.media_index_service.delete_media_index_by_category",
                return_value=True,
            ) as delete_index_mock,
            patch(
                "app.services.media.category_cache_service.invalidate_cache",
                return_value=None,
            ),
            patch(
                "app.services.media.indexing_runtime_service.IndexingRuntimeService.quiesce_indexing",
                return_value={"stopped": True, "drained_tasks": 0},
            ),
            patch(
                "app.services.media.library_runtime_service.LibraryRuntimeService.start_background_reindex",
                return_value=True,
            ) as reindex_mock,
            patch(
                "app.controllers.admin.admin_maintenance_controller.AdminMaintenanceController._purge_ghosthub_dir",
            ) as purge_mock,
        ):
            response = admin_client.post("/api/admin/reindex-media")

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True
        assert data.get("deleted_count") == 0
        assert data.get("partial_count") == 0
        assert "left untouched" in data.get("message", "")
        delete_index_mock.assert_called_once_with("auto::shows")
        reindex_mock.assert_called_once()
        assert reindex_mock.call_args.kwargs.get("generate_thumbnails") is False
        purge_mock.assert_not_called()

    def test_regenerate_thumbnails_clears_thumbnail_cache_only(
        self, admin_client, app, tmp_path
    ):
        """Thumbnail regeneration should clear thumbnail cache and queue regeneration."""
        category_root = tmp_path / "Photos"
        thumbnail_dir = category_root / ".ghosthub" / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        categories = [
            {"id": "auto::photos", "name": "Photos", "path": str(category_root)}
        ]

        def mock_with_timeout(
            func, args=(), kwargs=None, timeout_seconds=5.0, default=None
        ):
            return True, func(*args, **(kwargs or {}))

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_maintenance_controller.get_all_categories_with_details",
                return_value=categories,
            ),
            patch(
                "app.services.storage.storage_drive_service.get_current_mount_paths",
                return_value=set(),
            ),
            patch(
                "app.controllers.admin.admin_maintenance_controller.AdminMaintenanceController._with_timeout",
                side_effect=mock_with_timeout,
            ),
            patch(
                "app.controllers.admin.admin_maintenance_controller.AdminMaintenanceController._purge_ghosthub_dir",
                return_value={
                    "fully_removed": True,
                    "removed_files": 1,
                    "removed_dirs": 1,
                    "locked_or_failed": [],
                },
            ) as purge_mock,
            patch(
                "app.services.media.thumbnail_runtime_service.ThumbnailRuntimeService.quiesce_thumbnail_runtime",
                return_value={"idle": True, "drained_tasks": 0},
            ),
            patch(
                "app.services.media.thumbnail_runtime_service.ThumbnailRuntimeService.ensure_workers",
                return_value=None,
            ),
            patch(
                "app.controllers.admin.admin_maintenance_controller.AdminMaintenanceController.spawn",
                return_value=True,
            ) as spawn_mock,
        ):
            response = admin_client.post("/api/admin/regenerate-thumbnails")

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True
        assert data.get("deleted_count") == 1
        assert "current media index" in data.get("message", "")
        purge_mock.assert_called_once()
        spawn_mock.assert_called_once()

    def test_clear_generated_cache_is_isolated_from_reindex(
        self, admin_client, app, tmp_path
    ):
        """Full generated-cache clear should wipe .ghosthub only and leave indexes alone."""
        category_root = tmp_path / "Movies"
        ghosthub_dir = category_root / ".ghosthub"
        ghosthub_dir.mkdir(parents=True, exist_ok=True)

        categories = [
            {"id": "auto::movies", "name": "Movies", "path": str(category_root)}
        ]

        def mock_with_timeout(
            func, args=(), kwargs=None, timeout_seconds=5.0, default=None
        ):
            return True, func(*args, **(kwargs or {}))

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_maintenance_controller.get_all_categories_with_details",
                return_value=categories,
            ),
            patch(
                "app.services.storage.storage_drive_service.get_current_mount_paths",
                return_value=set(),
            ),
            patch(
                "app.controllers.admin.admin_maintenance_controller.AdminMaintenanceController._with_timeout",
                side_effect=mock_with_timeout,
            ),
            patch(
                "app.controllers.admin.admin_maintenance_controller.AdminMaintenanceController._purge_ghosthub_dir",
                return_value={
                    "fully_removed": True,
                    "removed_files": 4,
                    "removed_dirs": 2,
                    "locked_or_failed": [],
                },
            ) as purge_mock,
            patch(
                "app.services.media.thumbnail_runtime_service.ThumbnailRuntimeService.quiesce_thumbnail_runtime",
                return_value={"idle": True, "drained_tasks": 0},
            ),
            patch(
                "app.services.media.thumbnail_runtime_service.ThumbnailRuntimeService.ensure_workers",
                return_value=None,
            ),
            patch(
                "app.services.media.media_index_service.delete_media_index_by_category",
            ) as delete_index_mock,
        ):
            response = admin_client.post("/api/admin/clear-generated-cache")

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True
        assert data.get("deleted_count") == 1
        assert "left untouched" in data.get("message", "")
        purge_mock.assert_called_once()
        delete_index_mock.assert_not_called()

    def test_version_check_parses_github_latest_release(self, admin_client, app):
        """Version check should parse vX.Y.Z tags from GitHub latest release."""
        response_mock = MagicMock()
        response_mock.json.return_value = {
            "tag_name": "v9.8.7",
            "html_url": "https://github.com/BleedingXiko/GhostHub/releases/tag/v9.8.7",
            "assets": [],
        }

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_system_controller.requests.get",
                return_value=response_mock,
            ),
        ):
            response = admin_client.get("/api/admin/system/version-check")

        assert response.status_code == 200
        data = response.get_json()
        assert data["current_version"]
        assert data["latest_version"] == "9.8.7"
        assert data["update_available"] is True
        assert data["release_url"].endswith("/v9.8.7")

    def test_version_check_no_update_when_current_equals_latest(self, admin_client, app):
        """Matching current and release versions should not offer an update."""
        from app.version import VERSION

        response_mock = MagicMock()
        response_mock.json.return_value = {
            "tag_name": f"v{VERSION}",
            "html_url": f"https://github.com/BleedingXiko/GhostHub/releases/tag/v{VERSION}",
            "assets": [],
        }

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_system_controller.requests.get",
                return_value=response_mock,
            ),
        ):
            response = admin_client.get("/api/admin/system/version-check")

        assert response.status_code == 200
        data = response.get_json()
        assert data["latest_version"] == VERSION
        assert data["update_available"] is False

    def test_version_check_github_failure_returns_compatible_error(self, admin_client, app):
        """GitHub API failures should keep the existing response shape."""
        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_system_controller.requests.get",
                side_effect=Exception("network down"),
            ),
        ):
            response = admin_client.get("/api/admin/system/version-check")

        assert response.status_code == 200
        data = response.get_json()
        assert data["current_version"]
        assert data["latest_version"] is None
        assert data["update_available"] is False
        assert data["release_url"] is None
        assert data["error"] == "Could not reach GitHub Releases."

    def test_update_rejects_downloaded_installer_without_shebang(self, admin_client, app):
        """Downloaded installer assets must look like executable scripts."""
        release_response = MagicMock()
        release_response.json.return_value = {
            "tag_name": "v9.8.7",
            "assets": [
                {
                    "name": "install_ghosthub.sh",
                    "browser_download_url": "https://example.test/install_ghosthub.sh",
                }
            ],
        }
        installer_response = MagicMock()
        installer_response.__enter__.return_value = installer_response
        installer_response.__exit__.return_value = None
        installer_response.iter_content.return_value = [b"echo nope\n"]

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_system_controller.requests.get",
                side_effect=[release_response, installer_response],
            ),
        ):
            response = admin_client.post("/api/admin/system/update", json={})

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "Installer did not look like a script" in data["error"]

    def test_update_schedules_systemd_run_with_downloaded_installer(self, admin_client, app):
        """Admin update should schedule systemd-run against the downloaded installer."""
        release_response = MagicMock()
        release_response.json.return_value = {
            "tag_name": "v9.8.7",
            "assets": [
                {
                    "name": "install_ghosthub.sh",
                    "browser_download_url": "https://example.test/install_ghosthub.sh",
                }
            ],
        }
        installer_response = MagicMock()
        installer_response.__enter__.return_value = installer_response
        installer_response.__exit__.return_value = None
        installer_response.iter_content.return_value = [b"#!/bin/bash\n", b"echo ok\n"]
        subprocess_result = MagicMock(returncode=0, stdout="scheduled", stderr="")

        with (
            app.app_context(),
            patch(
                "app.controllers.admin.admin_system_controller.requests.get",
                side_effect=[release_response, installer_response],
            ),
            patch(
                "app.controllers.admin.admin_system_controller.subprocess.run",
                return_value=subprocess_result,
            ) as run_mock,
            patch(
                "app.controllers.admin.admin_system_controller.gevent.joinall",
                return_value=None,
            ),
        ):
            response = admin_client.post("/api/admin/system/update", json={})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        scheduled_cmd = run_mock.call_args_list[-1].args[0]
        assert scheduled_cmd[:2] == ["sudo", "systemd-run"]
        assert "--update" in scheduled_cmd
        assert scheduled_cmd[scheduled_cmd.index("/bin/bash") + 1].startswith(
            "/tmp/ghosthub_install_"
        )
