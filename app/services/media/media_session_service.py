"""Session-order ownership for media browsing."""

import hashlib
import logging
import random
import time

import gevent

from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.core.runtime_config_service import get_runtime_config_value
from app.services.media import media_index_service
from app.services.media.category_query_service import get_category_by_id
from app.services.media.media_runtime_store import media_runtime_store
from specter import registry

logger = logging.getLogger(__name__)

INDEXED_FETCH_BATCH_SIZE = 5000
DEFAULT_MAX_SESSIONS_PER_CATEGORY = 50
SESSION_EXPIRY = 3600


def get_max_sessions_per_category():
    """Get dynamic session-cap limits based on hardware tier."""
    if not get_runtime_config_value('AUTO_OPTIMIZE_FOR_HARDWARE'):
        return DEFAULT_MAX_SESSIONS_PER_CATEGORY

    from app.services.system.system_stats_service import get_hardware_tier

    tier = get_hardware_tier()
    if tier == 'PRO':
        return 500
    if tier == 'STANDARD':
        return 200
    return DEFAULT_MAX_SESSIONS_PER_CATEGORY


def _media_runtime_access(reader):
    """Read media runtime state under the Specter store lock."""
    return media_runtime_store.access(reader)


def _update_media_runtime(mutator):
    """Mutate media runtime state through the Specter-owned store."""
    return media_runtime_store.update(mutator)


def _fetch_indexed_filenames(category_id):
    """Fetch deterministic indexed filenames for a category."""
    rows = []
    offset = 0
    while True:
        batch = media_index_service.get_paginated_media(
            category_id=category_id,
            subfolder='__all__',
            sort_by='name',
            sort_order='ASC',
            limit=INDEXED_FETCH_BATCH_SIZE,
            offset=offset,
            filter_type='all',
            show_hidden=True,
            deduplicate_by_hash=False,
        )
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < INDEXED_FETCH_BATCH_SIZE:
            break
        offset += INDEXED_FETCH_BATCH_SIZE
        gevent.sleep(0)

    return sorted(
        (
            row.get('rel_path') or row.get('name')
            for row in rows
            if row.get('rel_path') or row.get('name')
        ),
        key=lambda value: value.lower(),
    )


def determine_file_order(
    all_files_metadata,
    category_id,
    session_id,
    shuffle_preference,
    force_refresh,
    category_name,
):
    """Determine stable file ordering for a browsing session."""
    extracted_filenames = []
    for file_meta in all_files_metadata:
        filename = None
        if isinstance(file_meta, dict):
            filename = file_meta.get('name') or file_meta.get('rel_path')
        elif isinstance(file_meta, str):
            filename = file_meta
        elif hasattr(file_meta, 'get'):
            filename = file_meta.get('name') or file_meta.get('rel_path')

        if filename is not None:
            filename = str(filename).strip()
            if filename:
                extracted_filenames.append(filename)

    all_filenames = sorted(extracted_filenames, key=lambda value: value.lower())
    total_files_in_directory = len(all_filenames)
    filename_to_index = {name: i for i, name in enumerate(all_filenames)}
    order_basis_hasher = hashlib.sha1()
    for filename in all_filenames:
        order_basis_hasher.update(filename.encode('utf-8', errors='ignore'))
        order_basis_hasher.update(b'\0')
    order_basis_hash = order_basis_hasher.hexdigest()

    sync_active_order = None
    sync_controller = registry.require('sync')
    if sync_controller.is_sync_enabled():
        sync_active_order = sync_controller.get_sync_order(category_id)
        if sync_active_order:
            logger.info(
                "Using active sync session order for category %s with %s items",
                category_id,
                len(sync_active_order),
            )

            def _clear_sync_session(draft):
                seen_files_tracker = draft.setdefault('seen_files_tracker', {})
                if (
                    category_id in seen_files_tracker and
                    session_id in seen_files_tracker[category_id]
                ):
                    session_data = seen_files_tracker[category_id][session_id]
                    if session_data["order"] or session_data["seen"]:
                        session_data["order"] = []
                        session_data["seen"].clear()
                        logger.debug(
                            "Cleared session shuffle data for session %s in category %s due to active sync.",
                            session_id,
                            category_id,
                        )

            _update_media_runtime(_clear_sync_session)
            return sync_active_order

    result = []

    def _merge_runtime(draft):
        nonlocal result
        current_time = time.time()
        seen_files_tracker = draft.setdefault('seen_files_tracker', {})
        sync_mode_order = draft.setdefault('sync_mode_order', {})

        if category_id not in seen_files_tracker:
            seen_files_tracker[category_id] = {}
        if session_id not in seen_files_tracker[category_id]:
            seen_files_tracker[category_id][session_id] = {
                "seen": set(),
                "order": [],
                "last_access": current_time,
                "order_basis_hash": order_basis_hash,
            }
        else:
            seen_files_tracker[category_id][session_id]["last_access"] = current_time

        session_data = seen_files_tracker[category_id][session_id]

        try:
            raw_order = session_data.get("order") or []
            raw_seen = session_data.get("seen") or set()

            normalized_order = []
            for entry in raw_order:
                if isinstance(entry, int):
                    if 0 <= entry < total_files_in_directory:
                        normalized_order.append(entry)
                elif isinstance(entry, str):
                    idx = filename_to_index.get(entry)
                    if idx is not None:
                        normalized_order.append(idx)

            normalized_seen = set()
            for entry in raw_seen:
                if isinstance(entry, int):
                    if 0 <= entry < total_files_in_directory:
                        normalized_seen.add(entry)
                elif isinstance(entry, str):
                    idx = filename_to_index.get(entry)
                    if idx is not None:
                        normalized_seen.add(idx)

            session_data["order"] = normalized_order
            session_data["seen"] = normalized_seen
        except Exception:
            session_data["order"] = []
            session_data["seen"] = set()

        basis_changed = session_data.get("order_basis_hash") != order_basis_hash
        if basis_changed:
            session_data["order"] = []
            session_data["seen"] = set()
            session_data["order_basis_hash"] = order_basis_hash

        if shuffle_preference:
            ordered_indices_from_session = session_data["order"]
            seen_indices_from_session = session_data["seen"]
            if (
                not ordered_indices_from_session or
                len(seen_indices_from_session) >= total_files_in_directory
            ):
                if len(seen_indices_from_session) >= total_files_in_directory:
                    logger.info(
                        "All files seen for session %s in '%s', reshuffling.",
                        session_id,
                        category_name,
                    )
                    seen_indices_from_session.clear()

                order_indices = list(range(total_files_in_directory))
                random.shuffle(order_indices)
                session_data["order"] = order_indices
                session_data["order_basis_hash"] = order_basis_hash
                logger.info(
                    "Generated new shuffled order (%s files) for session %s in '%s'",
                    len(order_indices),
                    session_id,
                    category_name,
                )

            result = [
                all_filenames[i]
                for i in session_data["order"]
                if 0 <= i < total_files_in_directory
            ]
            return

        if force_refresh or category_id not in sync_mode_order:
            sync_mode_order[category_id] = list(all_filenames)
            log_message = "Refreshed" if force_refresh else "Generated"
            logger.info(
                "%s consistent sorted order for non-shuffle/sync mode in category '%s' (%s files)",
                log_message,
                category_name,
                len(sync_mode_order[category_id]),
            )

        if session_data["order"] or session_data["seen"]:
            session_data["order"] = []
            session_data["seen"].clear()
            logger.debug(
                "Cleared session shuffle data for session %s in category %s due to non-shuffle mode.",
                session_id,
                category_id,
            )

        result = list(sync_mode_order[category_id])

    _update_media_runtime(_merge_runtime)
    return result


def mark_page_seen(category_id, session_id, paginated_filenames, all_files_metadata):
    """Mark the current page as seen for session shuffle state."""
    if not paginated_filenames:
        return

    sync_controller = registry.require('sync')
    sync_active_order = (
        sync_controller.get_sync_order(category_id)
        if sync_controller.is_sync_enabled()
        else None
    )
    if sync_active_order:
        return

    sorted_filenames = sorted(
        (
            file_meta['name']
            for file_meta in all_files_metadata
            if file_meta.get('name')
        )
    )
    filename_to_index = {name: i for i, name in enumerate(sorted_filenames)}

    def _mark_seen(draft):
        session_data = (
            draft.get('seen_files_tracker', {})
            .get(category_id, {})
            .get(session_id)
        )
        if not session_data:
            return

        try:
            existing_seen = session_data.get("seen") or set()
            if existing_seen and isinstance(next(iter(existing_seen)), str):
                session_data["seen"] = {
                    filename_to_index[name]
                    for name in existing_seen
                    if name in filename_to_index
                }
        except Exception:
            session_data["seen"] = set()

        for filename in paginated_filenames:
            idx = filename_to_index.get(filename)
            if idx is not None:
                session_data["seen"].add(idx)

    _update_media_runtime(_mark_seen)


def clean_sessions():
    """Remove inactive sessions and enforce session limits."""
    current_time = time.time()
    cleanup_interval = 300
    should_cleanup = _media_runtime_access(
        lambda state: current_time - state.get('last_session_cleanup', 0) > cleanup_interval,
    )
    if not should_cleanup:
        return

    logger.info("Starting session tracker cleanup...")
    session_expiry = get_runtime_config_value('SESSION_EXPIRY', SESSION_EXPIRY)
    categories_cleaned = 0
    sessions_removed = 0

    def _cleanup_runtime(draft):
        nonlocal categories_cleaned, sessions_removed
        seen_files_tracker = draft.setdefault('seen_files_tracker', {})

        for category_id in list(seen_files_tracker.keys()):
            category_sessions = seen_files_tracker[category_id]
            expired_sessions = [
                session_id
                for session_id, data in category_sessions.items()
                if current_time - data.get("last_access", 0) > session_expiry
            ]

            for session_id in expired_sessions:
                del category_sessions[session_id]
                sessions_removed += 1

            max_sessions = get_max_sessions_per_category()
            if len(category_sessions) > max_sessions:
                sorted_sessions = sorted(
                    category_sessions.items(),
                    key=lambda item: item[1].get("last_access", 0),
                )
                sessions_to_remove = len(category_sessions) - max_sessions
                for session_id, _ in sorted_sessions[:sessions_to_remove]:
                    del category_sessions[session_id]
                    sessions_removed += 1

            if not category_sessions:
                del seen_files_tracker[category_id]
                categories_cleaned += 1

        draft['last_session_cleanup'] = current_time

    _update_media_runtime(_cleanup_runtime)
    logger.info(
        "Session cleanup complete: removed %s inactive sessions and %s empty categories.",
        sessions_removed,
        categories_cleaned,
    )


def get_session_order(category_id, session_id):
    """Get the current media order for a session in a category."""
    order = _media_runtime_access(
        lambda state: (
            state.get('seen_files_tracker', {})
            .get(category_id, {})
            .get(session_id, {})
            .get('order')
        ),
    )
    if order is None:
        return None
    if not order:
        return order
    if order and isinstance(order[0], str):
        return list(order)

    order_indices = list(order)
    try:
        category = get_category_by_id(category_id)
        if not category:
            return None
        all_filenames = _fetch_indexed_filenames(category['id'])
        if not all_filenames:
            return None
        return [
            all_filenames[i]
            for i in order_indices
            if 0 <= i < len(all_filenames)
        ]
    except Exception:
        return None


def clear_session_tracker(category_id=None, session_id=None):
    """Clear session tracking data for specified or all sessions/categories."""
    def _clear_runtime(draft):
        seen_files_tracker = draft.setdefault('seen_files_tracker', {})
        sync_mode_order = draft.setdefault('sync_mode_order', {})
        if category_id and session_id:
            if (
                category_id in seen_files_tracker and
                session_id in seen_files_tracker[category_id]
            ):
                del seen_files_tracker[category_id][session_id]
                logger.info(
                    "Cleared tracker for session %s in category %s",
                    session_id,
                    category_id,
                )
        elif category_id:
            if category_id in seen_files_tracker:
                del seen_files_tracker[category_id]
                logger.info(
                    "Cleared tracker for all sessions in category %s",
                    category_id,
                )
            if category_id in sync_mode_order:
                del sync_mode_order[category_id]
                logger.info("Cleared sync mode order for category %s", category_id)
        elif session_id:
            for cat_id in list(seen_files_tracker.keys()):
                if session_id in seen_files_tracker[cat_id]:
                    del seen_files_tracker[cat_id][session_id]
            logger.info(
                "Cleared tracker for session %s across all categories",
                session_id,
            )
        else:
            seen_files_tracker.clear()
            sync_mode_order.clear()
            logger.info("Cleared entire seen files tracker and sync mode orders.")

    _update_media_runtime(_clear_runtime)
