"""Category payload enrichment and summary shaping helpers."""

from app.services.core.runtime_config_service import get_runtime_config_value
from specter import registry


def build_manual_categories(categories, summaries):
    """Attach summary-derived media details to persisted manual categories."""
    manual_categories = []

    for category in categories:
        category_id = category.get("id")
        category_path = category.get("path")
        category_name = category.get("name")
        if not category_id or not category_path or not category_name:
            continue

        summary = summaries.get(category_id) or {}
        full_count = int(summary.get("count", 0) or 0)
        contains_video = bool(summary.get("contains_video", False))

        thumbnail_url = None
        image_rel = summary.get("image_rel_path")
        video_rel = summary.get("video_rel_path")
        if image_rel:
            from app.utils.media_utils import get_thumbnail_url

            thumbnail_url = get_thumbnail_url(category_id, image_rel)
        elif video_rel:
            from app.utils.media_utils import get_thumbnail_url

            thumbnail_url = get_thumbnail_url(category_id, video_rel)

        manual_categories.append({
            "id": category_id,
            "name": category_name,
            "path": category_path,
            "mediaCount": full_count,
            "thumbnailUrl": thumbnail_url,
            "containsVideo": contains_video,
            "auto_detected": False,
        })

    return manual_categories


def enrich_categories_with_runtime_data(categories):
    """Attach progress and thumbnail runtime status to category payloads."""
    if not categories:
        return

    save_video_progress = get_runtime_config_value("SAVE_VIDEO_PROGRESS", False)
    category_ids = [category.get("id") for category in categories if category.get("id")]
    thumbnail_runtime = registry.resolve('thumbnail_runtime')

    all_video_progress = {}
    if save_video_progress and category_ids:
        progress_controller = registry.resolve('progress')
        if progress_controller is not None:
            all_video_progress = progress_controller.get_video_progress_batch(
                category_ids,
            )

    for category in categories:
        category_id = category.get("id")
        if save_video_progress:
            category["tracking_mode"] = "video"
            video_progress = all_video_progress.get(category_id, {})
            if video_progress:
                category["video_progress_count"] = len(video_progress)

        status = None
        if thumbnail_runtime is not None:
            status = thumbnail_runtime.get_thumbnail_status(category_id)
        if status and status.get("status") in ("generating", "pending"):
            category["processingStatus"] = "generating"
            category["processingData"] = status
        else:
            category.pop("processingStatus", None)
            category.pop("processingData", None)
