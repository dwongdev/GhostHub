/**
 * Shared Thumbnail Progress Utility
 *
 * Provides a centralized system for tracking thumbnail generation progress
 * across all layouts (default, streaming, gallery).
 *
 * Features:
 * - Real-time socket-based updates (primary)
 * - Polling fallback for reliability
 * - Layout-agnostic callback system
 * - State management for all categories
 *
 * Usage:
 *   import ThumbnailProgress from './modules/shared/thumbnailProgress.js';
 *
 *   // Initialize with socket
 *   ThumbnailProgress.init(socket);
 *
 *   // Register a callback for updates
 *   ThumbnailProgress.registerCallback('category-123', (status) => {
 *       // Update UI with status
 *       console.log(status.progress, status.processed, status.total);
 *   });
 *
 *   // Start polling for visible categories (fallback)
 *   ThumbnailProgress.startPolling('category-123');
 *
 *   // Stop polling when category is no longer visible
 *   ThumbnailProgress.stopPolling('category-123');
 *
 *   // Get current status
 *   const status = ThumbnailProgress.getThumbnailStatus('category-123');
 */

import { Module } from '../../libs/ragot.esm.min.js';
import { SOCKET_EVENTS } from '../../core/socketEvents.js';

const POLL_INTERVAL_MS = 3000; // Poll every 3 seconds (fallback)
const MAX_CONCURRENT_POLLS = 5; // Limit simultaneous polling to avoid network spam

class ThumbnailProgressManager {
    constructor() {
        // State storage: categoryId -> status object
        this.thumbnailProcessingStatus = {};

        // Registered callbacks: categoryId -> Set of callback functions
        this.callbacks = {};

        // Global callbacks: notified for any category update
        this.globalCallbacks = new Set();

        // Polling intervals: categoryId -> interval ID
        this.pollingIntervals = {};

        // Socket instance
        this.socket = null;

        // Initialized flag
        this.initialized = false;

        // Lifecycle owner for listeners/timers
        this.lifecycle = new Module();
        this.lifecycle.start();
    }

    /**
     * Initialize the thumbnail progress manager with a socket connection
     * @param {Object} socket - Socket.IO client instance
     */
    init(socket) {
        if (this.initialized) {
            console.warn('[ThumbnailProgress] Already initialized');
            return;
        }

        this.socket = socket;
        this._setupSocketListeners();
        this.initialized = true;
        console.log('[ThumbnailProgress] Initialized with socket');
    }

    /**
     * Set up socket event listeners for thumbnail status updates
     * @private
     */
    _setupSocketListeners() {
        if (!this.socket) {
            console.error('[ThumbnailProgress] Socket not initialized');
            return;
        }

        // Listen for thumbnail status updates from backend
        this.lifecycle.onSocket(this.socket, SOCKET_EVENTS.THUMBNAIL_STATUS_UPDATE, (data) => {
            const categoryId = data.categoryId || data.category_id;

            if (!categoryId) {
                console.warn('[ThumbnailProgress] Received update without categoryId:', data);
                return;
            }

            // Normalize data format
            const normalizedData = this._normalizeStatusData(data);

            if (normalizedData.status === 'generating' || normalizedData.status === 'pending') {
                this._updateCategoryStatus(categoryId, normalizedData);
            } else if (normalizedData.status === 'complete' || normalizedData.status === 'idle' || normalizedData.status === 'error') {
                this._completeCategoryStatus(categoryId, normalizedData);
            }
        });

        console.log('[ThumbnailProgress] Socket listeners registered');
    }

    /**
     * Normalize status data from various formats (snake_case backend, camelCase frontend)
     * @private
     * @param {Object} data - Raw status data
     * @returns {Object} Normalized status data
     */
    _normalizeStatusData(data) {
        return {
            categoryId: data.categoryId || data.category_id,
            status: data.status,
            total: data.total || 0,
            processed: data.processed || 0,
            success: data.success || 0,
            failed: data.failed || 0,
            videoCount: data.videoCount || data.video_count || 0,
            progress: data.progress || 0,
            color: data.color || this._getProgressColor(data.progress || 0),
            thumbnailUrl: data.thumbnailUrl || data.thumbnail_url || null,
            mediaUrl: data.mediaUrl || data.media_url || null,
            filename: data.filename || data.file_name || null,
            timestamp: Date.now()
        };
    }

    /**
     * Mark a category as pending (awaiting generation)
     * @param {string} categoryId - Category ID
     */
    setPendingStatus(categoryId) {
        if (!categoryId) return;

        // Only set to pending if not already generating or complete
        if (this.thumbnailProcessingStatus[categoryId]) {
            return;
        }

        const pendingStatus = {
            categoryId,
            status: 'pending',
            progress: 0,
            processed: 0,
            total: 0,
            timestamp: Date.now()
        };

        this.thumbnailProcessingStatus[categoryId] = pendingStatus;
        this._notifyCallbacks(categoryId, pendingStatus);
    }

    /**
     * Calculate progress bar color based on percentage
     * @private
     * @param {number} progress - Progress percentage (0-100)
     * @returns {string} Color name
     */
    _getProgressColor(progress) {
        if (progress > 70) return 'green';
        if (progress > 30) return 'yellow';
        return 'orange';
    }

    /**
     * Update category processing status and notify callbacks
     * @private
     * @param {string} categoryId - Category ID
     * @param {Object} statusData - Normalized status data
     */
    _updateCategoryStatus(categoryId, statusData) {
        // Update state
        this.thumbnailProcessingStatus[categoryId] = statusData;

        // Notify registered callbacks (throttled)
        this._notifyCallbacks(categoryId, statusData);
    }

    /**
     * Mark category processing as complete and clean up
     * @private
     * @param {string} categoryId - Category ID
     * @param {Object} statusData - Normalized status data
     */
    _completeCategoryStatus(categoryId, statusData) {
        // Mark as complete in state
        const completeStatus = {
            ...statusData,
            status: 'complete',
            progress: 100
        };

        this.thumbnailProcessingStatus[categoryId] = completeStatus;

        // CRITICAL FIX: The complete event is processed synchronously, bypassing the 
        // requestAnimationFrame queue. If a 'generating' event is currently buffered 
        // in the rAF queue for this category, we MUST delete it now. Otherwise, the 
        // stale 'generating' event fires on the next frame and overwrites our 'complete' 
        // status forever, causing the UI banner to stick indefinitely at 100%.
        if (this._pendingNotifications && this._pendingNotifications.has(categoryId)) {
            this._pendingNotifications.delete(categoryId);
        }

        // Notify callbacks immediately for completion to ensure UI updates and cleanup
        this._notifyCallbacksImmediately(categoryId, completeStatus);

        // Stop polling if active
        this.stopPolling(categoryId);

        // Clean up state after a delay (allow callbacks to process)
        this.lifecycle.timeout(() => {
            delete this.thumbnailProcessingStatus[categoryId];
        }, 5000);
    }

    /**
     * Notify all registered callbacks for a category (throttled via rAF)
     * @private
     * @param {string} categoryId - Category ID
     * @param {Object} statusData - Status data to pass to callbacks
     */
    _notifyCallbacks(categoryId, statusData) {
        if (!this._pendingNotifications) {
            this._pendingNotifications = new Map();
        }

        this._pendingNotifications.set(categoryId, statusData);

        if (this._notificationRaf) return;

        this._notificationRaf = requestAnimationFrame(() => {
            this._notificationRaf = null;
            const pending = this._pendingNotifications;
            this._pendingNotifications = new Map();

            pending.forEach((data, catId) => {
                this._notifyCallbacksImmediately(catId, data);
            });
        });
    }

    /**
     * Execute callback notification immediately
     * @private
     */
    _notifyCallbacksImmediately(categoryId, statusData) {
        const callbackSet = this.callbacks[categoryId];
        if (callbackSet && callbackSet.size > 0) {
            callbackSet.forEach(entry => {
                try {
                    if (entry.mediaUrl && statusData.mediaUrl && statusData.mediaUrl !== entry.mediaUrl) {
                        return;
                    }
                    if (entry.mediaUrl && !statusData.mediaUrl && statusData.status !== 'complete' && statusData.status !== 'idle' && statusData.status !== 'error') {
                        return;
                    }
                    entry.callback(statusData);
                } catch (error) {
                    console.error(`[ThumbnailProgress] Callback error for category ${categoryId}:`, error);
                }
            });
        }

        this._notifyGlobalCallbacks(categoryId, statusData);
    }

    /**
     * Notify all registered global callbacks
     * @private
     * @param {string} categoryId - Category ID
     * @param {Object} statusData - Status data to pass to callbacks
     */
    _notifyGlobalCallbacks(categoryId, statusData) {
        if (!this.globalCallbacks || this.globalCallbacks.size === 0) {
            return;
        }

        this.globalCallbacks.forEach(callback => {
            try {
                callback({ categoryId, statusData });
            } catch (error) {
                console.error('[ThumbnailProgress] Global callback error:', error);
            }
        });
    }

    /**
     * Register a callback for thumbnail progress updates
     * @param {string} categoryId - Category ID to watch
     * @param {Function} callback - Callback function (receives statusData object)
     * @returns {Function} Unregister function
     */
    registerCallback(categoryId, callback, options = {}) {
        if (!this.callbacks[categoryId]) {
            this.callbacks[categoryId] = new Set();
        }

        const entry = {
            callback,
            mediaUrl: options.mediaUrl || null
        };

        this.callbacks[categoryId].add(entry);

        // If we already have status for this category, call immediately
        const currentStatus = this.thumbnailProcessingStatus[categoryId];
        if (currentStatus) {
            try {
                if (!entry.mediaUrl || (currentStatus.mediaUrl && currentStatus.mediaUrl === entry.mediaUrl)) {
                    callback(currentStatus);
                }
            } catch (error) {
                console.error(`[ThumbnailProgress] Initial callback error for category ${categoryId}:`, error);
            }
        }

        // Return unregister function
        return () => this.unregisterCallback(categoryId, entry);
    }

    /**
     * Register a callback for ALL thumbnail progress updates
     * @param {Function} callback - Callback function (receives { categoryId, statusData })
     * @returns {Function} Unregister function
     */
    registerGlobalCallback(callback) {
        if (typeof callback !== 'function') {
            throw new Error('callback must be a function');
        }

        this.globalCallbacks.add(callback);
        return () => {
            this.globalCallbacks.delete(callback);
        };
    }

    /**
     * Unregister a specific callback for a category
     * @param {string} categoryId - Category ID
     * @param {Function} callback - Callback function to remove
     */
    unregisterCallback(categoryId, callbackOrEntry) {
        const callbackSet = this.callbacks[categoryId];
        if (callbackSet) {
            for (const entry of callbackSet) {
                if (entry === callbackOrEntry || entry.callback === callbackOrEntry) {
                    callbackSet.delete(entry);
                }
            }

            // Clean up empty sets
            if (callbackSet.size === 0) {
                delete this.callbacks[categoryId];
            }
        }
    }

    /**
     * Unregister all callbacks for a category
     * @param {string} categoryId - Category ID
     */
    unregisterAllCallbacks(categoryId) {
        delete this.callbacks[categoryId];
    }

    /**
     * Get current thumbnail status for a category
     * @param {string} categoryId - Category ID
     * @returns {Object|null} Status object or null if not found
     */
    getThumbnailStatus(categoryId) {
        return this.thumbnailProcessingStatus[categoryId] || null;
    }

    /**
     * Check if a category is currently processing
     * @param {string} categoryId - Category ID
     * @returns {boolean} True if category is processing
     */
    isProcessing(categoryId) {
        const status = this.thumbnailProcessingStatus[categoryId];
        return status && (status.status === 'generating' || status.status === 'pending');
    }

    /**
     * Start polling for thumbnail status (fallback mechanism)
     * @param {string} categoryId - Category ID to poll
     */
    startPolling(categoryId) {
        // Don't start if already polling
        if (this.pollingIntervals[categoryId]) {
            return;
        }

        // Cap concurrent polls to avoid network spam with large libraries
        const activePolls = Object.keys(this.pollingIntervals).length;
        if (activePolls >= MAX_CONCURRENT_POLLS) {
            console.log(`[ThumbnailProgress] Max concurrent polls (${MAX_CONCURRENT_POLLS}) reached, skipping ${categoryId}`);
            return;
        }

        const poll = async () => {
            try {
                const response = await fetch(`/api/categories/${categoryId}/thumbnail-status`);

                if (!response.ok) {
                    console.warn(`[ThumbnailProgress] Polling failed for ${categoryId}: ${response.status}`);
                    return;
                }

                const data = await response.json();
                const normalizedData = this._normalizeStatusData(data);

                if (normalizedData.status === 'generating' || normalizedData.status === 'pending') {
                    this._updateCategoryStatus(categoryId, normalizedData);
                } else if (normalizedData.status === 'idle' || normalizedData.status === 'complete' || normalizedData.status === 'error') {
                    this._completeCategoryStatus(categoryId, normalizedData);
                    this.stopPolling(categoryId);
                }
            } catch (error) {
                console.error(`[ThumbnailProgress] Polling error for ${categoryId}:`, error);
            }
        };

        // Set up interval before the first poll so `stopPolling()` works even on the initial request.
        this.pollingIntervals[categoryId] = this.lifecycle.interval(poll, POLL_INTERVAL_MS);

        // Poll immediately
        poll();
        console.log(`[ThumbnailProgress] Started polling for category ${categoryId}`);
    }

    /**
     * Stop polling for a category
     * @param {string} categoryId - Category ID
     */
    stopPolling(categoryId) {
        const intervalId = this.pollingIntervals[categoryId];
        if (intervalId) {
            this.lifecycle.clearInterval(intervalId);
            delete this.pollingIntervals[categoryId];
            console.log(`[ThumbnailProgress] Stopped polling for category ${categoryId}`);
        }
    }

    /**
     * Stop all active polling
     */
    stopAllPolling() {
        Object.keys(this.pollingIntervals).forEach(categoryId => {
            this.stopPolling(categoryId);
        });
    }

    /**
     * Get all categories currently being tracked
     * @returns {Array<string>} Array of category IDs
     */
    getTrackedCategories() {
        return Object.keys(this.thumbnailProcessingStatus);
    }

    /**
     * Get statistics about current processing
     * @returns {Object} Statistics object
     */
    getStats() {
        const tracked = this.getTrackedCategories();
        const processing = tracked.filter(id => this.isProcessing(id));
        const polling = Object.keys(this.pollingIntervals);

        return {
            trackedCategories: tracked.length,
            processingCategories: processing.length,
            pollingCategories: polling.length,
            totalCallbacks: Object.values(this.callbacks).reduce((sum, set) => sum + set.size, 0)
        };
    }

    /**
     * Clean up all resources (call when app is closing)
     */
    destroy() {
        this.stopAllPolling();
        if (this._notificationRaf) {
            cancelAnimationFrame(this._notificationRaf);
            this._notificationRaf = null;
        }
        this._pendingNotifications = new Map();
        this.callbacks = {};
        this.globalCallbacks.clear();
        this.thumbnailProcessingStatus = {};
        this.initialized = false;
        this.lifecycle.stop();
        this.lifecycle = new Module();
        this.lifecycle.start();
        console.log('[ThumbnailProgress] Destroyed');
    }
}

// Export singleton instance
const ThumbnailProgress = new ThumbnailProgressManager();
export default ThumbnailProgress;
