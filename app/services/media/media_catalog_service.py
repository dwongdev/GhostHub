"""Media catalog loading and indexing orchestration."""

import logging
import os
import traceback

import gevent

from app.services.media import media_index_service
from app.services.media.category_query_service import get_category_by_id
from app.services.core.runtime_config_service import get_runtime_config_value
from specter import registry
from app.utils.file_utils import is_large_directory
from app.utils.hash_utils import generate_collection_hash, generate_file_hash
from app.utils.media_utils import get_media_type, is_media_file

logger = logging.getLogger(__name__)

INDEXED_FETCH_BATCH_SIZE = 5000


def _require_indexing_runtime():
    return registry.require('indexing_runtime')


def _fetch_indexed_media_rows(category_id, subfolder='__all__', filter_type='all',
                              show_hidden=True, sort_by='name', sort_order='ASC',
                              deduplicate_by_hash=False):
    """
    Fetch all media_index rows for a category in batches without a hard cap.
    """
    rows = []
    offset = 0
    while True:
        batch = media_index_service.get_paginated_media(
            category_id=category_id,
            subfolder=subfolder,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=INDEXED_FETCH_BATCH_SIZE,
            offset=offset,
            filter_type=filter_type,
            show_hidden=show_hidden,
            deduplicate_by_hash=deduplicate_by_hash,
        )
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < INDEXED_FETCH_BATCH_SIZE:
            break
        offset += INDEXED_FETCH_BATCH_SIZE
        gevent.sleep(0)
    return rows


class MediaCatalogService:
    """Own category media index loading, rebuilding, and async index orchestration."""

    @staticmethod
    def start_async_indexing(category_id, category_path, category_name, force_refresh=False):
        """Delegate category indexing startup to the Specter-owned runtime."""
        return _require_indexing_runtime().start_async_indexing(
            category_id,
            category_path,
            category_name,
            force_refresh=force_refresh,
        )

    @staticmethod
    def get_async_index_status(category_id):
        """Return current async indexing status for a category."""
        return _require_indexing_runtime().get_async_index_status(category_id)

    @staticmethod
    def get_async_index_threshold():
        """Return the large-directory threshold for async indexing."""
        return _require_indexing_runtime().get_indexing_threshold()

    @staticmethod
    def ensure_category_indexed(category_id, force_refresh=False):
        """
        Ensure a category has index data available, starting async work when appropriate.
        """
        if not force_refresh:
            try:
                if media_index_service.has_media_index_entries(
                    category_id,
                    show_hidden=True,
                ):
                    return []
            except Exception:
                pass

        category = get_category_by_id(category_id)
        if category:
            try:
                MediaCatalogService.start_async_indexing(
                    category_id,
                    category['path'],
                    category.get('name', category_id),
                    force_refresh=force_refresh,
                )
                return None
            except Exception:
                pass

        category = get_category_by_id(category_id)
        if not category:
            return None

        return MediaCatalogService.load_or_rebuild_category_index(
            category_path=category['path'],
            category_name=category['name'],
            category_id=category_id,
            force_refresh=force_refresh,
            cache_expiry=get_runtime_config_value('CACHE_EXPIRY', 300),
        )

    @staticmethod
    def load_or_rebuild_category_index(category_path, category_name, category_id,
                                       force_refresh=False, cache_expiry=None):
        """
        Load media metadata from the SQLite index or rebuild it from disk when needed.
        """
        del cache_expiry  # The SQLite index is the source of truth for catalog data.
        all_files_metadata = None

        if not os.path.exists(category_path):
            logger.warning(
                "Category path does not exist (drive unmounted?): %s",
                category_path,
            )
            try:
                deleted = media_index_service.delete_media_index_for_category(
                    category_id,
                )
                if deleted > 0:
                    logger.info(
                        "Cleaned up %s stale media_index entries for unmounted category '%s'",
                        deleted,
                        category_name,
                    )
            except Exception as cleanup_err:
                logger.debug(
                    "Could not cleanup media_index for unmounted category: %s",
                    cleanup_err,
                )
            return None

        if not os.path.isdir(category_path):
            logger.error("Category path is not a directory: %s", category_path)
            return None

        if not force_refresh:
            try:
                if media_index_service.get_media_count(
                    category_id,
                    show_hidden=True,
                ) > 0:
                    indexed_rows = _fetch_indexed_media_rows(
                        category_id=category_id,
                        subfolder='__all__',
                        filter_type='all',
                        show_hidden=True,
                        sort_by='name',
                        sort_order='ASC',
                        deduplicate_by_hash=False,
                    )
                    all_files_metadata = [
                        {
                            'name': row.get('rel_path') or row.get('name'),
                            'size': row.get('size', 0),
                            'mtime': row.get('mtime', 0),
                            'hash': row.get('hash', ''),
                            'type': row.get('type', 'video'),
                        }
                        for row in indexed_rows
                        if row.get('rel_path') or row.get('name')
                    ]
                    logger.info(
                        "Using SQLite index for '%s' (%s files)",
                        category_name,
                        len(all_files_metadata),
                    )
            except Exception as db_err:
                logger.debug(
                    "SQLite index load failed for %s: %s",
                    category_name,
                    db_err,
                )

        if all_files_metadata is None:
            if force_refresh:
                logger.info("Forcing index refresh for '%s'", category_name)
            else:
                logger.info("Index not found or invalid, building index for '%s'", category_name)

            try:
                logger.info(
                    "Scanning all files for '%s' to create index (recursive)",
                    category_name,
                )
                current_files_metadata = []
                all_hashes = []
                file_count = 0

                for root, dirs, files in os.walk(category_path):
                    dirs[:] = [
                        directory for directory in dirs
                        if not directory.startswith('.')
                        and directory.lower() not in [
                            '.ghosthub',
                            '.ghosthub_uploads',
                            '$recycle.bin',
                            'system volume information',
                        ]
                    ]

                    for filename in files:
                        if not is_media_file(filename):
                            continue
                        try:
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, category_path).replace('\\', '/')
                            stats = os.stat(full_path)
                            file_hash = generate_file_hash(rel_path, stats.st_size, stats.st_mtime)
                            all_hashes.append(file_hash)
                            current_files_metadata.append({
                                'name': rel_path,
                                'size': stats.st_size,
                                'mtime': stats.st_mtime,
                                'hash': file_hash,
                                'type': get_media_type(rel_path),
                            })
                            file_count += 1
                            if file_count % 200 == 0:
                                gevent.sleep(0)
                        except FileNotFoundError:
                            logger.warning("File disappeared during indexing: %s", filename)
                        except Exception as stat_error:
                            logger.warning(
                                "Could not get stats for file %s: %s",
                                filename,
                                stat_error,
                            )

                all_files_metadata = current_files_metadata
                collection_hash = generate_collection_hash(all_hashes)

                media_index_service.update_media_index_batch(
                    category_id,
                    all_files_metadata,
                    version_hash=collection_hash,
                )

                if is_large_directory(
                    category_path,
                    MediaCatalogService.get_async_index_threshold(),
                    known_file_count=len(all_files_metadata),
                ):
                    logger.info(
                        "Large directory detected for '%s', starting async indexing",
                        category_name,
                    )
                    MediaCatalogService.start_async_indexing(
                        category_id,
                        category_path,
                        category_name,
                        force_refresh,
                    )
            except PermissionError:
                logger.error("Permission denied accessing directory: %s", category_path)
                return None
            except Exception as exc:
                logger.error(
                    "Error scanning directory or building index for %s: %s",
                    category_path,
                    exc,
                )
                logger.debug(traceback.format_exc())
                return None

        return all_files_metadata


def start_async_indexing(category_id, category_path, category_name, force_refresh=False):
    """Module-level compatibility wrapper for async indexing startup."""
    return MediaCatalogService.start_async_indexing(
        category_id,
        category_path,
        category_name,
        force_refresh=force_refresh,
    )


def get_async_index_status(category_id):
    """Module-level compatibility wrapper for async index status."""
    return MediaCatalogService.get_async_index_status(category_id)



def get_async_index_threshold():
    """Module-level compatibility wrapper for index threshold lookup."""
    return MediaCatalogService.get_async_index_threshold()


def ensure_category_indexed(category_id, force_refresh=False):
    """Module-level compatibility wrapper for category indexing checks."""
    return MediaCatalogService.ensure_category_indexed(
        category_id,
        force_refresh=force_refresh,
    )


def load_or_rebuild_category_index(
    category_path,
    category_name,
    category_id,
    force_refresh=False,
    cache_expiry=None,
):
    """Module-level compatibility wrapper for catalog rebuilds."""
    return MediaCatalogService.load_or_rebuild_category_index(
        category_path=category_path,
        category_name=category_name,
        category_id=category_id,
        force_refresh=force_refresh,
        cache_expiry=cache_expiry,
    )
