"""
API Routes
---------
REST API endpoints for category and media management.
"""
# app/routes/api_routes.py
import logging
import traceback
import os

from flask import Blueprint, jsonify, request, current_app, session
from app.services.category_service import CategoryService
from app.services.media_service import MediaService
from app.services.sync_service import SyncService
from app.services import config_service
from app.services import progress_service # Added for saving/loading current index
from app.utils import server_utils

# Only import tkinter if not running in Docker
if os.getenv("DOCKER_ENV") != "true":
    import tkinter as tk
    from tkinter import filedialog


logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

# --- Configuration Management Endpoints ---

@api_bp.route('/config', methods=['GET'])
def get_config_route():
    """Get the current application configuration."""
    config_data, error = config_service.load_config()
    if error:
        # Log the error and return 500, but still provide default/last known config
        logger.warning(f"Error loading configuration for API response: {error}. Serving available config.")
        # Depending on severity, you might choose to return 500 immediately
        # return jsonify({'error': error, 'config_data_served': config_data}), 500
    
    # Add password protection status
    config_data['isPasswordProtectionActive'] = current_app.config.get('SESSION_PASSWORD', '') != ''
    return jsonify(config_data)

@api_bp.route('/config', methods=['POST'])
def save_config_route():
    """Save the application configuration."""
    new_config = request.json
    success, message = config_service.save_config(new_config)
    if success:
        # Update the live application config for SESSION_PASSWORD
        if 'python_config' in new_config and 'SESSION_PASSWORD' in new_config['python_config']:
            current_app.config['SESSION_PASSWORD'] = new_config['python_config']['SESSION_PASSWORD']
            logger.info(f"Live SESSION_PASSWORD updated in app config.")
        
        response_data = {
            'message': message,
            'isPasswordProtectionActive': current_app.config.get('SESSION_PASSWORD', '') != ''
        }
        return jsonify(response_data), 200
    else:
        return jsonify({'error': message}), 400 # Or 500 if it's a server-side save issue

@api_bp.route('/validate_session_password', methods=['POST'])
def validate_session_password():
    """Validate the submitted session password."""
    submitted_password = request.json.get('password')
    actual_password = current_app.config.get('SESSION_PASSWORD', '')

    if not actual_password: # If no password is set in config, access is always granted
        return jsonify({"valid": True, "message": "No password protection active."})

    if submitted_password == actual_password:
        return jsonify({"valid": True})
    else:
        return jsonify({"valid": False, "message": "Incorrect password."})

# --- Category and Media Endpoints ---

@api_bp.route('/categories', methods=['GET'])
def list_categories():
    """Get all categories with media counts and thumbnails."""
    try:
        categories = CategoryService.get_all_categories_with_details()
        return jsonify(categories)
    except Exception as e:
        logger.error(f"Error in list_categories endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': 'Failed to retrieve categories'}), 500

@api_bp.route('/categories', methods=['POST'])
def add_category():
    """Create new media category with name and path. Requires admin."""
    if not session.get('is_admin', False):
        logger.warning(f"Unauthorized attempt to add category by session: {request.cookies.get('session_id')}")
        return jsonify({'error': 'Administrator privileges required to add categories.'}), 403

    data = request.json
    if not data or 'name' not in data or 'path' not in data:
        return jsonify({'error': 'Name and path are required'}), 400

    name = data.get('name')
    path = data.get('path')

    try:
        new_category, error = CategoryService.add_category(name, path)
        # Start indexing category
        if new_category and 'id' in new_category:
            MediaService.start_async_indexing(new_category['id'], new_category['path'], new_category['name'])

        if error:
            # Determine appropriate status code based on error
            status_code = 400 if "exists" in error or "not a directory" in error else 500
            return jsonify({'error': error}), status_code
        return jsonify(new_category), 201
    except Exception as e:
        logger.error(f"Unexpected error adding category: Name='{name}', Path='{path}': {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': 'An unexpected error occurred while adding the category'}), 500

@api_bp.route('/categories/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Delete category and clear associated caches. Requires admin."""
    if not session.get('is_admin', False):
        logger.warning(f"Unauthorized attempt to delete category {category_id} by session: {request.cookies.get('session_id')}")
        return jsonify({'error': 'Administrator privileges required to delete categories.'}), 403

    try:
        success, error = CategoryService.delete_category(category_id)
        if not success:
            status_code = 404 if error == "Category not found" else 500
            return jsonify({'error': error}), status_code

        # Clear session tracker for the deleted category
        # We don't need to clear the media_file_cache anymore as we're using the index file
        MediaService.clear_session_tracker(category_id=category_id)
        logger.info(f"Cleared session tracker for deleted category: {category_id}")

        return '', 204
    except Exception as e:
        logger.error(f"Unexpected error deleting category ID {category_id}: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': 'An unexpected error occurred while deleting the category'}), 500

@api_bp.route('/categories/<category_id>/media', methods=['GET'])
def list_media(category_id):
    """Get paginated media files with optional shuffling and async indexing for large directories."""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', None, type=int) # Use None to default in service
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        # Default shuffle to config value, but override if sync mode is active
        default_shuffle = current_app.config.get('SHUFFLE_MEDIA', True)
        if SyncService.is_sync_enabled():
             default_shuffle = False # Don't shuffle in sync mode
             logger.info(f"Sync mode enabled, overriding shuffle to False for category {category_id}")

        shuffle = request.args.get('shuffle', str(default_shuffle)).lower() == 'true'
        

        # Use the async method for large directories
        # This will create and use the index file for every category
        logger.info(f"API route calling list_media_files_async for category {category_id}, page={page}, limit={limit}, force_refresh={force_refresh}")
        
        # Ensure page and limit are valid integers
        if page < 1:
            return jsonify({'error': 'Page number must be 1 or greater'}), 400
        
        if limit is not None and limit < 1:
            return jsonify({'error': 'Limit must be greater than 0'}), 400
        
        # Log the actual query parameters for debugging
        logger.info(f"Query parameters: {dict(request.args)}")
        
        
        # Use the async method which handles large directories more efficiently
        media_files, pagination, error, is_async = MediaService.list_media_files_async(
            category_id,
            page=page,
            limit=limit,
            force_refresh=force_refresh,
            shuffle=shuffle
        )

        if error:
            # Determine status code based on error message
            if "not found" in error:
                status_code = 404
            elif "Permission denied" in error:
                status_code = 403
            elif "Page number" in error or "Limit must be" in error:
                 status_code = 400
            else:
                status_code = 500
            return jsonify({'error': error}), status_code

        response_data = {
            'files': media_files,
            'pagination': pagination
        }
        
        # Add async indexing info if applicable
        if is_async:
            response_data['async_indexing'] = True
            # Include indexing progress if available
            if 'indexing_progress' in pagination:
                response_data['indexing_progress'] = pagination['indexing_progress']
                # Remove from pagination object to maintain backward compatibility
                del pagination['indexing_progress']

        # Add last known index if feature is enabled
        if current_app.config.get('SAVE_CURRENT_INDEX', False):
            last_known_index = progress_service.get_saved_index(category_id)
            if last_known_index is not None:
                response_data['last_known_index'] = last_known_index
                logger.info(f"Including last_known_index: {last_known_index} for category {category_id}")

        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error listing media for category {category_id}: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': f"Server error listing media: {str(e)}"}), 500


@api_bp.route('/browse-folders', methods=['GET'])
def browse_folders():
    """
    Open folder selection dialog on server.
    Returns Docker-specific message if in container.
    """
    # Check if running in Docker environment
    import os
    if os.path.exists('/.dockerenv'):
        logger.info("Running in Docker environment, folder browser not available")
        return jsonify({
            'error': 'Folder browser not available in Docker environment',
            'message': 'To add media directories in Docker, mount volumes in docker-compose.yml',
            'docker': True
        }), 501  # 501 Not Implemented
    
    # Check if running in a headless environment or if Tkinter is available
    try:
        # Attempt to import tkinter and create a root window
        root = tk.Tk()
        root.withdraw() # Hide the main window
        # Bring the dialog to the front
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title="Select Category Folder")
        root.destroy() # Clean up the Tkinter instance

        if folder_path:
            logger.info(f"Folder selected via Tkinter dialog: {folder_path}")
            return jsonify({'path': folder_path})
        else:
            logger.info("Folder browser cancelled or no folder selected.")
            return jsonify({'path': None}) # Return null path if cancelled
    except (ImportError, tk.TclError) as e:
         logger.error(f"Tkinter error opening folder browser: {str(e)}. This usually means the server environment doesn't support GUI operations.")
         return jsonify({'error': 'Server environment does not support graphical folder browser.'}), 501 # 501 Not Implemented
    except Exception as e:
        logger.error(f"Unexpected error opening folder browser: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': f'Failed to open folder browser: {str(e)}'}), 500

# --- Tunnel Management Endpoints ---

@api_bp.route('/tunnel/start', methods=['POST'])
def start_tunnel_route():
    """Start a tunnel based on provided parameters."""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'Request body is missing.'}), 400

        provider = data.get('provider')
        local_port = data.get('local_port', current_app.config.get('TUNNEL_LOCAL_PORT', 5000)) # Use from request or fallback
        
        if not provider or provider == 'none':
            return jsonify({'status': 'error', 'message': 'No tunnel provider specified.'}), 400

        if provider == 'cloudflare':
            cloudflared_exe_path = server_utils.find_cloudflared_path()
            if not cloudflared_exe_path:
                return jsonify({'status': 'error', 'message': 'cloudflared executable not found.'}), 500
            result = server_utils.start_cloudflare_tunnel(cloudflared_exe_path, int(local_port))
        elif provider == 'pinggy':
            token = data.get('pinggy_token', current_app.config.get('PINGGY_ACCESS_TOKEN')) # Use from request or fallback
            if not token:
                return jsonify({'status': 'error', 'message': 'Pinggy access token not provided or configured.'}), 400
            result = server_utils.start_pinggy_tunnel(int(local_port), token)
        else:
            return jsonify({'status': 'error', 'message': f"Unsupported tunnel provider: {provider}"}), 400
        
        return jsonify(result)
    except ValueError:
        logger.error(f"Error in start_tunnel_route: Invalid port number provided.")
        return jsonify({'status': 'error', 'message': 'Invalid port number provided.'}), 400
    except Exception as e:
        logger.error(f"Error in start_tunnel_route: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

@api_bp.route('/tunnel/stop', methods=['POST'])
def stop_tunnel_route():
    """Stop the currently active tunnel."""
    try:
        result = server_utils.stop_active_tunnel()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in stop_tunnel_route: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

@api_bp.route('/tunnel/status', methods=['GET'])
def tunnel_status_route():
    """Get the status of the currently active tunnel."""
    try:
        status = server_utils.get_active_tunnel_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error in tunnel_status_route: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}), 500

# --- Admin Lock Endpoints ---

@api_bp.route('/admin/claim', methods=['POST'])
def claim_admin():
    """Claim the admin role for the current session."""
    if not hasattr(current_app, 'ADMIN_SESSION_ID'):
        current_app.ADMIN_SESSION_ID = None # Initialize if not present due to hot reload or other reasons

    # Use request.cookies.get('session_id') as a fallback if session.sid is not available
    # This depends on how session.sid is populated (Flask-Session vs. custom)
    # For this app, 'session_id' cookie is manually set.
    current_session_id = request.cookies.get('session_id')
    if not current_session_id:
        logger.warning("Attempt to claim admin without a session_id cookie.")
        return jsonify(success=False, isAdmin=False, message="Session not found. Please refresh."), 400


    if current_app.ADMIN_SESSION_ID is None or current_app.ADMIN_SESSION_ID == current_session_id:
        current_app.ADMIN_SESSION_ID = current_session_id
        session['is_admin'] = True # Standard Flask session usage
        logger.info(f"Admin role claimed by session: {current_session_id}")
        return jsonify(success=True, isAdmin=True, message="Admin role claimed successfully.")
    else:
        # Check if the current user is already the admin but using a different session mechanism
        # This part might be redundant if session['is_admin'] is the source of truth for the user
        is_current_user_admin = session.get('is_admin', False) and current_app.ADMIN_SESSION_ID == current_session_id
        
        logger.warning(f"Admin role claim failed. Already claimed by: {current_app.ADMIN_SESSION_ID}. Current session: {current_session_id}")
        return jsonify(success=False, isAdmin=is_current_user_admin, message="Admin role already claimed by another user."), 403

@api_bp.route('/admin/status', methods=['GET'])
def admin_status():
    """Get the admin status for the current session."""
    if not hasattr(current_app, 'ADMIN_SESSION_ID'):
        current_app.ADMIN_SESSION_ID = None

    current_session_id = request.cookies.get('session_id')
    is_admin = session.get('is_admin', False)

    # Consistency check: if a global admin is set and it's not this session, then this session cannot be admin.
    if current_app.ADMIN_SESSION_ID is not None and current_app.ADMIN_SESSION_ID != current_session_id:
        if is_admin: # If session thought it was admin, but global lock says otherwise
            session['is_admin'] = False
            is_admin = False
            logger.info(f"Corrected admin status for session {current_session_id} to False due to global lock.")
    elif current_app.ADMIN_SESSION_ID is None and is_admin: # If no global admin, but session thought it was admin (e.g. server restart)
        session['is_admin'] = False
        is_admin = False
        logger.info(f"Corrected admin status for session {current_session_id} to False as global admin lock is not set.")


    role_claimed_by_anyone = current_app.ADMIN_SESSION_ID is not None
    # If the current user is admin, then the role is claimed by them (and thus by anyone)
    if is_admin:
        role_claimed_by_anyone = True
        
    logger.debug(f"Admin status check: session_id={current_session_id}, is_admin={is_admin}, global_admin_id={current_app.ADMIN_SESSION_ID}, role_claimed_by_anyone={role_claimed_by_anyone}")
    return jsonify(isAdmin=is_admin, roleClaimedByAnyone=role_claimed_by_anyone)

# --- Progress Endpoints ---
@api_bp.route('/progress/delete_all', methods=['POST'])
def delete_all_saved_progress():
    """Deletes all saved progress data."""
    # Consider adding admin check if this should be a protected action
    # if not session.get('is_admin', False):
    #     logger.warning(f"Unauthorized attempt to delete all progress by session: {request.cookies.get('session_id')}")
    #     return jsonify({'error': 'Administrator privileges required.'}), 403
    try:
        success, message = progress_service.delete_all_progress()
        if success:
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting all progress: {str(e)}")
        logger.debug(traceback.format_exc())
        return jsonify({'error': 'An unexpected error occurred while deleting progress data'}), 500

# API error handlers
@api_bp.app_errorhandler(404)
def api_not_found(e):
    """Handle 404 errors with JSON response."""
    logger.warning(f"API 404 Not Found: {request.path}")
    return jsonify(error="Resource not found"), 404

@api_bp.app_errorhandler(500)
def api_server_error(e):
    """Handle 500 errors with JSON response."""
    original_exception = getattr(e, "original_exception", e)
    logger.error(f"API 500 Internal Server Error: {original_exception}", exc_info=True)
    return jsonify(error="Internal server error"), 500

@api_bp.app_errorhandler(400)
def api_bad_request(e):
    """Handle 400 errors with JSON response."""
    logger.warning(f"API 400 Bad Request: {request.path} - {e.description}")
    return jsonify(error=e.description), 400

@api_bp.app_errorhandler(403)
def api_forbidden(e):
    """Handle 403 errors with JSON response."""
    logger.warning(f"API 403 Forbidden: {request.path} - {e.description}")
    return jsonify(error=e.description), 403
