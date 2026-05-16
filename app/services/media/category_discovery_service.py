"""Filesystem-backed auto-category discovery and auto-path resolution."""

import logging
import os

from app.services.core.runtime_config_service import (
    get_runtime_config_value,
    get_runtime_root_path,
)
from app.services.media import media_index_service
from app.utils.media_utils import find_thumbnail, is_media_file

logger = logging.getLogger(__name__)

SYSTEM_FOLDERS_TO_SKIP = frozenset([
    "$RECYCLE.BIN",
    "$Recycle.Bin",
    "System Volume Information",
    "RECYCLER",
    ".Trashes",
    ".Spotlight-V100",
    ".fseventsd",
    "@eaDir",
    "lost+found",
    ".ghosthub",
    "GhostHubBackups",
    "#recycle",
    "@Recycle",
])

ROOT_FOLDERS_TO_HIDE = frozenset([
    "ghost",
])


def _is_hidden_root_segment(segment):
    """Return True when *segment* is an internal mount root users should not see."""
    return str(segment or "").strip().lower() in ROOT_FOLDERS_TO_HIDE


def get_visible_auto_parent_chain(parent_chain):
    """Drop hidden mount-root segments from an auto-category parent chain."""
    return [
        segment for segment in list(parent_chain or [])
        if not _is_hidden_root_segment(segment)
    ]


def _replace_first_labeled_segment(segments, drive_folder_labels):
    """Return *segments* with the first drive-backed segment replaced by its label."""
    labels = drive_folder_labels or {}
    if not segments or not labels:
        return list(segments or [])

    replaced = list(segments)
    for index, segment in enumerate(replaced):
        label = labels.get(segment)
        if label:
            replaced[index] = label
            break
    return replaced


def get_valid_usb_paths() -> set:
    """Return the currently mounted storage roots when available."""
    try:
        from app.services.storage import storage_drive_service

        return storage_drive_service.get_current_mount_paths()
    except Exception as exc:
        logger.debug("Could not get current mount paths: %s", exc)
        return set()


def format_category_display_name(name, parent_chain, level, drive_folder_labels=None):
    """Build a display name for an auto-category, substituting drive labels when available.

    *drive_folder_labels* is an optional {folder_name: label} map.  When the
    top-level drive folder name has a user-defined label, the label replaces
    the raw folder name in the breadcrumb portion. Hidden mount roots like
    ``ghost`` are removed from the visible breadcrumb chain.
    """
    labels = drive_folder_labels or {}
    labeled_name = labels.get(name, name)
    visible_parent_chain = get_visible_auto_parent_chain(parent_chain)
    labeled_chain = _replace_first_labeled_segment(visible_parent_chain, labels)
    effective_level = len(visible_parent_chain) + 1

    if effective_level <= 1:
        label = labels.get(name)
        return label if label else f"{name} (USB)"
    elif effective_level == 2:
        parent_display = labeled_chain[-1] if labeled_chain else labeled_name
        return f"{labeled_name} ({parent_display})"
    else:
        display_chain = list(reversed(labeled_chain))
        breadcrumb = " › ".join(display_chain)
        return f"{labeled_name} ({breadcrumb})"


def discover_auto_categories(all_summaries_map, drive_folder_labels=None):
    """Discover auto categories from filesystem roots using indexed summaries first."""
    processed_paths = set()
    auto_categories = []

    def process_directory(path, name, summaries, parent_chain=None, level=1):
        if path in processed_paths:
            return
        processed_paths.add(path)

        if parent_chain is None:
            parent_chain = []

        if level == 1 and name.lower() in ROOT_FOLDERS_TO_HIDE:
            return

        id_parts = ["auto"] + parent_chain + [name]
        category_id = "::".join(id_parts)

        display_name = format_category_display_name(name, parent_chain, level, drive_folder_labels)

        try:
            summary = summaries.get(category_id)
            full_count = int(summary.get("count", 0) or 0) if summary else 0
            if full_count > 0:
                image_rel = summary.get("image_rel_path")
                video_rel = summary.get("video_rel_path")
                contains_video = bool(summary.get("contains_video", False))
                thumbnail_url = None
                if image_rel:
                    from app.utils.media_utils import get_thumbnail_url

                    thumbnail_url = get_thumbnail_url(category_id, image_rel)
                elif video_rel:
                    from app.utils.media_utils import get_thumbnail_url

                    thumbnail_url = get_thumbnail_url(category_id, video_rel)

                auto_categories.append({
                    "id": category_id,
                    "name": display_name,
                    "path": path,
                    "mediaCount": full_count,
                    "thumbnailUrl": thumbnail_url,
                    "containsVideo": contains_video,
                    "auto_detected": True,
                })
                logger.info(
                    "Added category from index: %s (%s) with %s media files",
                    display_name,
                    path,
                    full_count,
                )
                return
        except Exception as exc:
            logger.debug("Indexed summary lookup failed for %s: %s", category_id, exc)

        media_files = []
        media_sample_limit = 256
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.name.startswith('.') or not entry.is_file(follow_symlinks=False):
                        continue
                    if is_media_file(entry.name):
                        media_files.append(entry.name)
                        if len(media_files) >= media_sample_limit:
                            break
        except Exception as exc:
            logger.debug("Error scanning %s: %s", path, exc)
            return

        if not media_files:
            return

        try:
            full_count, thumbnail_url, contains_video = find_thumbnail(
                path,
                category_id,
                name,
                media_files=media_files,
                allow_queue=False,
            )
            if full_count > 0:
                auto_categories.append({
                    "id": category_id,
                    "name": display_name,
                    "path": path,
                    "mediaCount": full_count,
                    "thumbnailUrl": thumbnail_url,
                    "containsVideo": contains_video,
                    "auto_detected": True,
                })
                logger.info(
                    "Added category: %s (%s) with %s media files",
                    display_name,
                    path,
                    full_count,
                )
        except Exception as exc:
            logger.error("Error processing category details for %s: %s", path, exc)

    def scan_directory_recursive(dir_path, parent_chain, current_level, summaries):
        max_depth = get_runtime_config_value("MAX_CATEGORY_SCAN_DEPTH", 0)
        if max_depth > 0 and current_level > max_depth:
            return

        try:
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        name_lower = entry.name.lower()
                        if (
                            name_lower in ("$recycle.bin", "system volume information", "recycler")
                            or entry.name in SYSTEM_FOLDERS_TO_SKIP
                        ):
                            continue

                        sub_path = entry.path
                        sub_name = entry.name
                        process_directory(
                            sub_path,
                            sub_name,
                            summaries,
                            parent_chain=parent_chain,
                            level=current_level,
                        )
                        scan_directory_recursive(
                            sub_path,
                            parent_chain + [sub_name],
                            current_level + 1,
                            summaries,
                        )
        except Exception as exc:
            logger.debug("Error scanning directory %s: %s", dir_path, exc)

    for scan_root in _get_category_scan_roots():
        try:
            scan_directory_recursive(
                scan_root,
                parent_chain=[],
                current_level=1,
                summaries=all_summaries_map,
            )
        except Exception as exc:
            logger.error("Error scanning root %s: %s", scan_root, exc)

    return auto_categories


def resolve_auto_category(category_id):
    """Resolve an auto:: category ID to a filesystem path."""
    if not category_id.startswith("auto::"):
        return None

    id_parts = category_id[len("auto::"):].split("::")
    if not id_parts:
        logger.error("Category ID %s has no parts after prefix", category_id)
        return None

    name = id_parts[-1]
    relative_path = "/".join(id_parts)
    candidate_roots = _get_auto_category_lookup_roots()
    candidate_paths = [
        os.path.join(root, relative_path).replace("\\", "/")
        for root in candidate_roots
    ]

    logger.debug(
        "resolve_auto_category(%s): checking paths: %s",
        category_id,
        candidate_paths,
    )

    for candidate_path in candidate_paths:
        if os.path.exists(candidate_path):
            logger.info("Found category %s at: %s", category_id, candidate_path)
            return {"id": category_id, "name": name, "path": candidate_path}

    logger.error("Category %s not found. Tried paths: %s", category_id, candidate_paths)
    return None


def _get_category_scan_roots():
    usb_roots = ["/media", "/media/usb", "/media/ghost", "/mnt"]
    active_roots = sorted(
        [root for root in usb_roots if os.path.exists(root)],
        key=len,
    )
    valid_roots = []

    for root in active_roots:
        is_subpath = False
        for checked in valid_roots:
            if root.startswith(checked + os.sep) or root == checked:
                is_subpath = True
                break
        if not is_subpath:
            valid_roots.append(root)

    return valid_roots


def _get_auto_category_lookup_roots():
    try:
        from app.services.storage import storage_drive_service

        usb_roots = list(storage_drive_service.get_current_mount_paths())
    except Exception:
        usb_roots = []

    for root in ["/media", "/media/usb", "/media/ghost", "/mnt"]:
        if root not in usb_roots:
            usb_roots.append(root)

    local_media = os.path.abspath(os.path.join(get_runtime_root_path(), "..", "media"))
    if local_media not in usb_roots:
        usb_roots.append(local_media)

    return usb_roots
