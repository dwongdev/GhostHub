"""Admin USB user-data export/import controller."""

import logging

from flask import request
from specter import Controller, Field, Schema, registry

from app.services.system.user_data_transfer_service import UserDataTransferError
from app.utils.auth import admin_required

logger = logging.getLogger(__name__)


class AdminUserDataTransferController(Controller):
    """Own admin-only USB user data transfer routes."""

    name = 'admin_user_data_transfer'
    url_prefix = '/api/admin/user-data'

    schemas = {
        'drive_action': Schema('admin_user_data_transfer.drive_action', {
            'drive_id': Field(str, required=True),
        }, strict=True),
        'file_action': Schema('admin_user_data_transfer.file_action', {
            'drive_id': Field(str, required=True),
            'filename': Field(str, required=True),
        }, strict=True),
    }

    def build_routes(self, router):
        @router.route('/drives', methods=['GET'])
        @admin_required
        def list_drives():
            return self.list_drives()

        @router.route('/exports', methods=['GET'])
        @admin_required
        def list_exports():
            return self.list_exports()

        @router.route('/export', methods=['POST'])
        @admin_required
        def start_export():
            return self.start_export()

        @router.route('/import', methods=['POST'])
        @admin_required
        def start_import():
            return self.start_import()

        @router.route('/jobs/<job_id>', methods=['GET'])
        @admin_required
        def get_job(job_id):
            return self.get_job(job_id)

        @router.route('/export', methods=['DELETE'])
        @admin_required
        def delete_export():
            return self.delete_export()

    def list_drives(self):
        try:
            service = registry.require('user_data_transfer')
            return {'drives': service.list_drives()}
        except Exception as exc:
            logger.error("Error listing user-data drives: %s", exc)
            return {'error': 'Failed to list drives'}, 500

    def list_exports(self):
        drive_id = request.args.get('drive_id', '')
        if not drive_id:
            return {'error': 'drive_id parameter is required'}, 400

        try:
            service = registry.require('user_data_transfer')
            return {'exports': service.list_exports(drive_id)}
        except UserDataTransferError as exc:
            return {'error': str(exc)}, 400
        except Exception as exc:
            logger.error("Error listing user-data exports: %s", exc)
            return {'error': 'Failed to list exports'}, 500

    def start_export(self):
        payload = request.get_json(silent=True)
        if not payload:
            return {'error': 'Request body is required'}, 400
        payload = self.schema('drive_action').require(payload)

        try:
            service = registry.require('user_data_transfer')
            job_id = service.start_export(payload['drive_id'])
            return {'success': True, 'job_id': job_id}
        except UserDataTransferError as exc:
            return {'success': False, 'error': str(exc)}, 400
        except Exception as exc:
            logger.error("Error starting user-data export: %s", exc)
            return {'error': 'Failed to start export'}, 500

    def start_import(self):
        payload = request.get_json(silent=True)
        if not payload:
            return {'error': 'Request body is required'}, 400
        payload = self.schema('file_action').require(payload)

        try:
            service = registry.require('user_data_transfer')
            job_id = service.start_import(payload['drive_id'], payload['filename'])
            return {'success': True, 'job_id': job_id}
        except UserDataTransferError as exc:
            return {'success': False, 'error': str(exc)}, 400
        except Exception as exc:
            logger.error("Error starting user-data import: %s", exc)
            return {'error': 'Failed to start import'}, 500

    def get_job(self, job_id):
        try:
            service = registry.require('user_data_transfer')
            job = service.get_job(job_id)
            if not job:
                return {'error': 'Job not found'}, 404
            return {'job': job}
        except Exception as exc:
            logger.error("Error getting user-data job: %s", exc)
            return {'error': 'Failed to get job'}, 500

    def delete_export(self):
        payload = request.get_json(silent=True)
        if not payload:
            return {'error': 'Request body is required'}, 400
        payload = self.schema('file_action').require(payload)

        try:
            service = registry.require('user_data_transfer')
            service.delete_export(payload['drive_id'], payload['filename'])
            return {'success': True}
        except UserDataTransferError as exc:
            return {'success': False, 'error': str(exc)}, 400
        except Exception as exc:
            logger.error("Error deleting user-data export: %s", exc)
            return {'error': 'Failed to delete export'}, 500
