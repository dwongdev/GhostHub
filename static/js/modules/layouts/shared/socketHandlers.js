import { Module, $ } from '../../../libs/ragot.esm.min.js';
import { isUploadInProgress } from '../../../utils/uploadManager.js';

/**
 * Shared socket handler manager for layout modules.
 * Handles debounced refresh scheduling and common socket events.
 *
 * @param {Object} options
 * @param {Function} options.isActive
 * @param {Function} options.refresh
 * @param {Function} options.handleProgressUpdate
 * @param {Function} options.syncShowHiddenFromEvent
 * @param {boolean} [options.forceRefreshOnShowHiddenToggle=false]
 * @returns {{register: Function, cleanup: Function}}
 */
export function createLayoutSocketHandlerManager({
    isActive,
    refresh,
    handleProgressUpdate = null,
    syncShowHiddenFromEvent,
    forceRefreshOnShowHiddenToggle = false,
    shouldScheduleCategoryRefresh = null
}) {
    let socketLifecycle = null;
    let pendingForceRefresh = false;
    let pendingRefreshCategoryList = false;
    let refreshTimer = null;

    function cleanup() {
        if (socketLifecycle) {
            socketLifecycle.stop();
            socketLifecycle = null;
        }
        pendingForceRefresh = false;
        pendingRefreshCategoryList = false;
        refreshTimer = null;
    }

    /**
     * Cancel any pending debounced refresh without running it.
     * Call this when the user explicitly triggers a load (e.g. filter click, pagination)
     * so the socket-driven debounce does not fire afterwards and clobber the user action.
     */
    function cancelPendingRefresh() {
        if (refreshTimer && socketLifecycle) {
            socketLifecycle.clearTimeout(refreshTimer);
            refreshTimer = null;
        }
        pendingForceRefresh = false;
        pendingRefreshCategoryList = false;
    }

    function scheduleRefresh(forceRefresh, delayMs, refreshCategoryList = false) {
        pendingForceRefresh = pendingForceRefresh || forceRefresh;
        pendingRefreshCategoryList = pendingRefreshCategoryList || refreshCategoryList;
        if (refreshTimer) socketLifecycle.clearTimeout(refreshTimer);
        refreshTimer = socketLifecycle.timeout(() => {
            const force = pendingForceRefresh;
            const refreshCatList = pendingRefreshCategoryList;
            pendingForceRefresh = false;
            pendingRefreshCategoryList = false;
            refreshTimer = null;
            if (!isActive()) return;
            window.ragotModules?.mediaLoader?.clearMediaCache?.();
            window.ragotModules?.cacheManager?.clearCache?.();
            refresh(force, false, refreshCatList);
        }, Math.max(0, delayMs));
    }

    function register(socket) {
        cleanup();
        socketLifecycle = new Module();
        socketLifecycle.start();

        socketLifecycle.onSocket(socket, 'category_updated', async (data) => {
            if (!isActive()) return;
            try {
                const isVisibilityReason = data.reason === 'show_hidden_enabled' ||
                    data.reason === 'show_hidden_disabled' ||
                    data.reason === 'category_hidden' ||
                    data.reason === 'category_unhidden';

                if (isVisibilityReason) {
                    await syncShowHiddenFromEvent(data);
                }

                const isVisibilityToggle = isVisibilityReason ||
                    data.reason === 'file_hidden' ||
                    data.reason === 'file_unhidden';

                const isDbChange = data.reason === 'category_hidden' ||
                    data.reason === 'category_unhidden' ||
                    data.reason === 'file_hidden' ||
                    data.reason === 'file_unhidden';

                const isUploadOrIndexChange = data.reason === 'upload_complete' ||
                    data.reason === 'chunked_upload' ||
                    data.reason === 'index_updated';
                if (isUploadOrIndexChange && isUploadInProgress()) {
                    return;
                }

                const isShowHiddenToggle = data.reason === 'show_hidden_enabled' ||
                    data.reason === 'show_hidden_disabled';

                const forceRefresh = (data?.force_refresh === true) ||
                    isDbChange ||
                    isUploadOrIndexChange ||
                    (forceRefreshOnShowHiddenToggle && isShowHiddenToggle);

                const mediaViewerEl = $('#media-viewer');
                if (mediaViewerEl && !mediaViewerEl.classList.contains('hidden')) return;

                if (typeof shouldScheduleCategoryRefresh === 'function' &&
                    shouldScheduleCategoryRefresh(data) === false) {
                    return;
                }

                if (!data.session_only || isVisibilityToggle) {
                    const delay = data.reason === 'index_updated' ? 2500 : 800;
                    scheduleRefresh(forceRefresh, delay, isShowHiddenToggle);
                }
            } catch (e) {
                console.error('[LayoutSocketHandlers] Error handling category_updated:', e);
            }
        });

        if (typeof handleProgressUpdate === 'function') {
            socketLifecycle.onSocket(socket, 'progress_update', (data) => {
                if (isActive()) handleProgressUpdate(data);
            });
        }

        socketLifecycle.onSocket(socket, 'usb_mounts_changed', (data) => {
            if (!isActive()) return;
            cancelPendingRefresh();
            window.ragotModules?.mediaLoader?.clearMediaCache?.();
            window.ragotModules?.cacheManager?.clearCache?.();
            refresh(data?.force_refresh === true, false, true);
        });

        socketLifecycle.onSocket(socket, 'content_visibility_changed', (data) => {
            if (isActive()) refresh(data?.force_refresh === true);
        });
    }

    return {
        register,
        cleanup,
        cancelPendingRefresh
    };
}
