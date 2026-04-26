/**
 * Pi Optimization UI Module
 * Shows info about Pi optimization and resource management
 * Uses polling for reliable thumbnail progress updates
 */

import { videoIcon, refreshIcon, checkIcon } from '../../utils/icons.js';
import { Module, createElement, show, hide, $, $$ } from '../../libs/ragot.esm.min.js';
import { SOCKET_EVENTS } from '../../core/socketEvents.js';

// Track active processing to auto-hide stuck indicators
const processingTimeouts = {};
const PROCESSING_TIMEOUT_MS = 60000; // Auto-hide after 60 seconds if no update

// Track active polling intervals
const pollingIntervals = {};
const POLL_INTERVAL_MS = 3000; // Poll every 3 seconds
let pollStarterInterval = null;
let socketListenerAttached = false;
let piOptimizationLifecycle = null;

function schedulePiTimeout(callback, delayMs) {
    if (piOptimizationLifecycle) {
        return piOptimizationLifecycle.timeout(callback, delayMs);
    }
    return setTimeout(callback, delayMs);
}

function clearPiTimeout(timeoutId) {
    if (!timeoutId) return;
    if (piOptimizationLifecycle) {
        piOptimizationLifecycle.clearTimeout(timeoutId);
        return;
    }
    clearTimeout(timeoutId);
}

function schedulePiInterval(callback, delayMs) {
    if (piOptimizationLifecycle) {
        return piOptimizationLifecycle.interval(callback, delayMs);
    }
    return setInterval(callback, delayMs);
}

function clearPiInterval(intervalId) {
    if (!intervalId) return;
    if (piOptimizationLifecycle) {
        piOptimizationLifecycle.clearInterval(intervalId);
        return;
    }
    clearInterval(intervalId);
}

class PiOptimizationLifecycle extends Module {
    constructor() {
        super();
        this.handleThumbnailStatusUpdate = this.handleThumbnailStatusUpdate.bind(this);
    }

    onStart() {
        this.attachSocketListener();
        startPollingForVisibleCategories();
    }

    onStop() {
        if (pollStarterInterval) {
            this.clearInterval(pollStarterInterval);
            pollStarterInterval = null;
        }

        Object.keys(pollingIntervals).forEach(stopPollingCategory);
        Object.keys(processingTimeouts).forEach((categoryId) => {
            this.clearTimeout(processingTimeouts[categoryId]);
            delete processingTimeouts[categoryId];
        });
        socketListenerAttached = false;
    }

    attachSocketListener() {
        if (socketListenerAttached) return;

        const socket = window.ragotModules?.appStore?.get?.('socket', null);
        if (!socket) {
            this.timeout(() => this.attachSocketListener(), 500);
            return;
        }

        this.onSocket(socket, SOCKET_EVENTS.THUMBNAIL_STATUS_UPDATE, this.handleThumbnailStatusUpdate);
        socketListenerAttached = true;
    }

    handleThumbnailStatusUpdate(rawData) {
        const data = normalizeThumbnailData(rawData);
        const categoryId = data.categoryId;
        if (!categoryId) return;

        if (data.status === 'complete' || data.status === 'idle') {
            updateCategoryProcessingCompletion(categoryId, data);
            stopPollingCategory(categoryId);
            return;
        }

        if (data.status === 'generating' || data.status === 'pending') {
            updateCategoryProcessingStatus(categoryId, data);
            if (!pollingIntervals[categoryId]) {
                startPollingCategory(categoryId);
            }
        }
    }
}

// Create and show the Pi optimization notice
function showPiOptimizationNotice() {
    // Check if notice already exists
    if ($('.pi-optimization-notice')) {
        return;
    }

    // Create notice element
    const notice = createElement('div', { className: 'pi-optimization-notice', innerHTML: `<span class="indicator"></span><span class="text">Pi Optimization Active</span>` });

    // Add to body
    document.body.appendChild(notice);

    // Auto-hide after 10 seconds
    schedulePiTimeout(() => {
        notice.style.opacity = '0';
        schedulePiTimeout(() => {
            if (notice.parentNode) {
                notice.parentNode.removeChild(notice);
            }
        }, 1000);
    }, 10000);
}

// Initialize listeners for thumbnail status updates
function initPiOptimizationListeners() {
    // Show notice initially (disabled)
    // showPiOptimizationNotice();

    if (!piOptimizationLifecycle) {
        piOptimizationLifecycle = new PiOptimizationLifecycle();
    }
    piOptimizationLifecycle.start();

}

function normalizeThumbnailData(data) {
    return {
        categoryId: data?.categoryId || data?.category_id || null,
        status: data?.status || 'idle',
        total: Number(data?.total || 0),
        processed: Number(data?.processed || 0),
        progress: Number(data?.progress || 0),
        videoCount: Number(data?.videoCount || data?.video_count || 0),
        mediaType: data?.mediaType || data?.media_type || null,
        thumbnailUrl: data?.thumbnailUrl || data?.thumbnail_url || null
    };
}

// Poll for thumbnail status on cards that currently indicate thumbnail work.
function startPollingForVisibleCategories() {
    if (pollStarterInterval) return;
    // Check every 5 seconds for indicators that are pending/active/visible.
    pollStarterInterval = schedulePiInterval(() => {
        const indicators = $$('.thumbnail-processing-indicator[data-category-id]');
        indicators.forEach(indicator => {
            const categoryId = indicator.getAttribute('data-category-id');
            if (!categoryId || pollingIntervals[categoryId]) return;

            const isVisible = !indicator.classList.contains('hidden');
            const isPending = indicator.classList.contains('pending');
            const isActive = indicator.classList.contains('active');
            const isComplete = indicator.classList.contains('complete');
            if ((isVisible || isPending || isActive) && !isComplete) {
                startPollingCategory(categoryId);
            }
        });
    }, 5000);
}

// Start polling for a specific category
function startPollingCategory(categoryId) {
    if (pollingIntervals[categoryId]) return;

    const poll = async () => {
        try {
            const response = await fetch(`/api/categories/${categoryId}/thumbnail-status`);
            const data = await response.json();

            const normalizedData = normalizeThumbnailData({ ...data, categoryId });

            if (normalizedData.status === 'complete' || normalizedData.status === 'idle') {
                updateCategoryProcessingCompletion(categoryId, normalizedData);
                stopPollingCategory(categoryId);
            } else if (normalizedData.status === 'generating' || normalizedData.status === 'pending') {
                updateCategoryProcessingStatus(categoryId, normalizedData);
            }
        } catch (error) {
            console.warn(`Failed to poll thumbnail status for ${categoryId}:`, error);
        }
    };

    // Poll immediately, then on interval
    poll();
    pollingIntervals[categoryId] = schedulePiInterval(poll, POLL_INTERVAL_MS);
}

// Stop polling for a category
function stopPollingCategory(categoryId) {
    if (pollingIntervals[categoryId]) {
        clearPiInterval(pollingIntervals[categoryId]);
        delete pollingIntervals[categoryId];
    }
}

// Update category card with processing status info
function updateCategoryProcessingStatus(categoryId, data) {
    const indicator = $(`.thumbnail-processing-indicator[data-category-id="${categoryId}"]`);
    const percentageIndicator = $(`.thumbnail-percentage[data-category-id="${categoryId}"]`);

    if (!indicator) return;

    // Clear any existing timeout for this category
    if (processingTimeouts[categoryId]) {
        clearPiTimeout(processingTimeouts[categoryId]);
    }

    // Set a new timeout to auto-hide if stuck
    processingTimeouts[categoryId] = schedulePiTimeout(() => {
        // Auto-complete if stuck
        updateCategoryProcessingCompletion(categoryId, data);
        delete processingTimeouts[categoryId];
    }, PROCESSING_TIMEOUT_MS);

    // Make sure indicator is visible
    show(indicator);

    // Show indicator for active processing
    indicator.classList.add('active');
    indicator.classList.remove('pending', 'complete', 'error');

    // Check if we're processing a video thumbnail
    let isVideoThumbnail = false;
    if (data.mediaType === 'video' || (data.processed && data.videoCount && data.videoCount > 0)) {
        isVideoThumbnail = true;
    }

    // Add progress info if available (allow 0% instead of treating it as missing)
    if (data.total > 0 || data.videoCount > 0) {
        // Update the main indicator
        indicator.innerHTML = `
            <div class="processing-icon">${isVideoThumbnail ? videoIcon(18) : refreshIcon(18)}</div>
            <div class="processing-text">${isVideoThumbnail ? 'Processing video...' : 'Generating thumbnails...'} ${Math.max(0, data.progress)}%</div>
        `;

        // Update the percentage indicator in bottom right
        if (percentageIndicator) {
            percentageIndicator.textContent = `${Math.max(0, data.progress)}%`;
            show(percentageIndicator);
            percentageIndicator.classList.add('active');

            // Add color class based on progress
            percentageIndicator.classList.remove('progress-low', 'progress-medium', 'progress-high', 'progress-complete');
            if (data.progress < 30) {
                percentageIndicator.classList.add('progress-low');
            } else if (data.progress < 60) {
                percentageIndicator.classList.add('progress-medium');
            } else if (data.progress < 100) {
                percentageIndicator.classList.add('progress-high');
            } else {
                percentageIndicator.classList.add('progress-complete');
            }
        }
    } else {
        indicator.innerHTML = `
            <div class="processing-icon">${refreshIcon(18)}</div>
            <div class="processing-text">Generating thumbnails...</div>
        `;

        // Show 0% in the percentage indicator
        if (percentageIndicator) {
            percentageIndicator.textContent = '0%';
            percentageIndicator.classList.add('active', 'progress-low');
        }
    }

    // If the thumbnail has already been generated, refresh the category thumbnail
    if (data.thumbnailUrl) {
        const thumbnail = $(`.category-item[data-category-id="${categoryId}"] .thumbnail`);
        if (thumbnail && thumbnail.dataset) {
            thumbnail.dataset.src = data.thumbnailUrl;
            if (thumbnail.src) {
                thumbnail.src = data.thumbnailUrl;
            }
            console.log(`Updated thumbnail for ${categoryId} to ${data.thumbnailUrl}`);
        }
    }
}

// Update category card when processing is complete
function updateCategoryProcessingCompletion(categoryId, data) {
    // Clear any timeout for this category
    if (processingTimeouts[categoryId]) {
        clearPiTimeout(processingTimeouts[categoryId]);
        delete processingTimeouts[categoryId];
    }

    const indicator = $(`.thumbnail-processing-indicator[data-category-id="${categoryId}"]`);
    const percentageIndicator = $(`.thumbnail-percentage[data-category-id="${categoryId}"]`);

    if (!indicator) return;

    // If indicator was never actively processing, just hide it immediately
    const wasActive = indicator.classList.contains('active');
    if (!wasActive) {
        hide(indicator);
        if (percentageIndicator) {
            percentageIndicator.classList.remove('active');
        }
        return;
    }

    // Show completion state briefly, then fade out
    indicator.classList.remove('active', 'pending', 'error');
    indicator.classList.add('complete');

    indicator.innerHTML = `
        <div class="processing-icon">${checkIcon(18)}</div>
        <div class="processing-text">Thumbnails ready</div>
    `;

    // Update percentage indicator to show 100%
    if (percentageIndicator) {
        percentageIndicator.textContent = '100%';
        percentageIndicator.classList.remove('progress-low', 'progress-medium', 'progress-high');
        percentageIndicator.classList.add('progress-complete');

        // Hide percentage indicator after a delay
        schedulePiTimeout(() => {
            percentageIndicator.classList.remove('active');
            hide(percentageIndicator);
        }, 2000);
    }

    // If we have a thumbnail URL, update it
    if (data && data.thumbnailUrl) {
        const thumbnail = $(`.category-item[data-category-id="${categoryId}"] .thumbnail`);
        if (thumbnail) {
            thumbnail.src = data.thumbnailUrl;
            thumbnail.dataset.src = data.thumbnailUrl;
        }
    }

    // Hide after a delay
    schedulePiTimeout(() => {
        indicator.classList.remove('active', 'complete');
        schedulePiTimeout(() => {
            hide(indicator);
        }, 500);
    }, 2000);
}

function cleanupPiOptimization() {
    if (piOptimizationLifecycle) {
        piOptimizationLifecycle.stop();
        piOptimizationLifecycle = null;
    }
}

export {
    initPiOptimizationListeners,
    cleanupPiOptimization,
    showPiOptimizationNotice,
    updateCategoryProcessingStatus,
    updateCategoryProcessingCompletion
};
