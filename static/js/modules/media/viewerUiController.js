/**
 * Viewer UI Controller
 * Single source of truth for floating media viewer actions visibility.
 */

import { Module, bus, $ } from '../../libs/ragot.esm.min.js';
import { ensureDownloadButton, setFloatingDownloadVisible } from './download.js';
import { ensureQuickActionsButton, setQuickActionsVisibility } from './quickActions.js';
import { APP_EVENTS } from '../../core/appEvents.js';

export const VIEWER_MODES = Object.freeze({
    MEDIA: 'media',
    VIDEO_CONTROLS: 'video_controls',
    PHOTO_VIEWER: 'photo_viewer'
});

const VALID_MODES = new Set(Object.values(VIEWER_MODES));

let currentViewerMode = VIEWER_MODES.MEDIA;
let viewerUiLifecycle = null;

class ViewerUiLifecycle extends Module {
    onStart() {
        this.listen(APP_EVENTS.VIEWER_SET_MODE, (payload) => {
            const mode = typeof payload === 'string' ? payload : payload?.mode;
            if (mode) setViewerMode(mode);
        });
        this.listen(APP_EVENTS.VIEWER_SYNC_UI, () => syncViewerUi());
    }
}

function normalizeMode(mode) {
    return VALID_MODES.has(mode) ? mode : VIEWER_MODES.MEDIA;
}

function shouldShowFloatingActions(mode) {
    return mode === VIEWER_MODES.MEDIA;
}

function applyViewerMode(mode) {
    const floatingVisible = shouldShowFloatingActions(mode);
    const mediaViewer = $('#media-viewer');
    if (mediaViewer) {
        mediaViewer.setAttribute('data-viewer-mode', mode);
        if (mode !== VIEWER_MODES.VIDEO_CONTROLS) {
            mediaViewer.removeAttribute('data-controls-visible');
        }
    }

    if (typeof document !== 'undefined' && document.body) {
        document.body.classList.toggle('photo-viewer-open', mode === VIEWER_MODES.PHOTO_VIEWER);
    }

    // Ensure containers exist before applying visibility.
    ensureDownloadButton();
    ensureQuickActionsButton();

    setFloatingDownloadVisible(floatingVisible);
    setQuickActionsVisibility(floatingVisible);

    bus.emit(APP_EVENTS.VIEWER_MODE_CHANGED, {
        mode,
        floatingVisible
    });
}

export function initViewerUiController() {
    if (!viewerUiLifecycle) {
        viewerUiLifecycle = new ViewerUiLifecycle();
    }
    const wasStarted = viewerUiLifecycle._isMounted === true;
    viewerUiLifecycle.start();
    if (!wasStarted) {
        applyViewerMode(currentViewerMode);
    }
}

export function cleanupViewerUiController() {
    if (viewerUiLifecycle) {
        viewerUiLifecycle.stop();
        viewerUiLifecycle = null;
    }
    const mediaViewer = $('#media-viewer');
    if (mediaViewer) {
        mediaViewer.removeAttribute('data-viewer-mode');
    }
    if (typeof document !== 'undefined' && document.body) {
        document.body.classList.remove('photo-viewer-open');
    }
    currentViewerMode = VIEWER_MODES.MEDIA;
}

export function setViewerMode(mode) {
    const nextMode = normalizeMode(mode);
    currentViewerMode = nextMode;
    initViewerUiController();
    applyViewerMode(nextMode);
}

export function syncViewerUi() {
    if (!viewerUiLifecycle) return;
    applyViewerMode(currentViewerMode);
}

export function getViewerMode() {
    return currentViewerMode;
}
