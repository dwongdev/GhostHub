/**
 * Shared helpers for temporary live-seek preview during scrubbing.
 */

const SCRUB_PREVIEW_ATTR = 'data-scrub-preview-active';

export function isScrubPreviewActive(videoElement) {
    return videoElement?.getAttribute?.(SCRUB_PREVIEW_ATTR) === 'true';
}

export function setScrubPreviewActive(videoElement, active) {
    if (!videoElement?.setAttribute) return;
    if (active) {
        videoElement.setAttribute(SCRUB_PREVIEW_ATTR, 'true');
        return;
    }
    videoElement.removeAttribute(SCRUB_PREVIEW_ATTR);
}
