/**
 * Progress Database Module
 * Handles IndexedDB-based progress storage for Guest mode.
 * Active profiles use server-side profile storage instead.
 */

import { bus } from '../libs/ragot.esm.min.js';
import { APP_EVENTS } from '../core/appEvents.js';
import { hasActiveProfile } from './profileUtils.js';

// IndexedDB for session-based progress (scales to 5K+ entries)
const DB_NAME = 'ghosthub_progress';
const DB_VERSION = 2; // v2 adds video_progress store
const STORE_NAME = 'progress';
const VIDEO_STORE_NAME = 'video_progress'; // For per-video tracking mode

// In-memory caches for instant sync reads
const progressCache = {};
const videoProgressCache = {}; // Cache for per-video progress
let dbInstance = null;
let dbReady = false;
let initPromise = null;

function toNormalizedVideoPath(url) {
    if (!url || typeof url !== 'string') return '';
    let value = url;
    try {
        value = decodeURIComponent(value);
    } catch (e) { /* ignore */ }
    value = value.split('#')[0].split('?')[0];
    try {
        if (/^https?:\/\//i.test(value)) {
            value = new URL(value).pathname;
        }
    } catch (e) { /* ignore */ }
    return value;
}

function resolveVideoProgressEntry(videoUrl) {
    if (!videoUrl) return null;

    const candidates = new Set();
    const base = videoUrl.split('#')[0].split('?')[0];
    candidates.add(videoUrl);
    candidates.add(base);
    try { candidates.add(decodeURIComponent(videoUrl)); } catch (e) { /* ignore */ }
    try { candidates.add(decodeURIComponent(base)); } catch (e) { /* ignore */ }
    try { candidates.add(encodeURI(videoUrl)); } catch (e) { /* ignore */ }
    try { candidates.add(encodeURI(base)); } catch (e) { /* ignore */ }

    for (const key of candidates) {
        if (key && videoProgressCache[key]) {
            return videoProgressCache[key];
        }
    }

    const targetNormalized = toNormalizedVideoPath(videoUrl);
    if (!targetNormalized) return null;

    for (const [cachedUrl, cachedEntry] of Object.entries(videoProgressCache)) {
        if (toNormalizedVideoPath(cachedUrl) === targetNormalized) {
            return cachedEntry;
        }
    }

    return null;
}

function preferNewerProgress(existingEntry, incomingEntry) {
    if (!existingEntry) return incomingEntry;
    if (!incomingEntry) return existingEntry;
    const existingUpdated = Number(existingEntry.last_updated || 0);
    const incomingUpdated = Number(incomingEntry.last_updated || 0);
    return incomingUpdated >= existingUpdated ? incomingEntry : existingEntry;
}

function flushCachesToIndexedDB() {
    if (!dbInstance) return;

    try {
        const categoryTx = dbInstance.transaction(STORE_NAME, 'readwrite');
        const categoryStore = categoryTx.objectStore(STORE_NAME);
        Object.values(progressCache).forEach((entry) => {
            if (entry && entry.category_id) {
                categoryStore.put(entry);
            }
        });
    } catch (e) {
        console.warn('Failed to flush category progress cache to IndexedDB:', e);
    }

    if (dbInstance.objectStoreNames.contains(VIDEO_STORE_NAME)) {
        try {
            const videoTx = dbInstance.transaction(VIDEO_STORE_NAME, 'readwrite');
            const videoStore = videoTx.objectStore(VIDEO_STORE_NAME);
            Object.values(videoProgressCache).forEach((entry) => {
                if (entry && entry.video_url) {
                    videoStore.put(entry);
                }
            });
        } catch (e) {
            console.warn('Failed to flush video progress cache to IndexedDB:', e);
        }
    }
}

function buildThumbnailUrlFromVideoUrl(videoUrl) {
    if (!videoUrl || !videoUrl.startsWith('/media/')) return null;

    const parts = videoUrl.split('/');
    if (parts.length < 4) return null;

    const categoryId = parts[2];
    const filename = decodeURIComponent(parts.slice(3).join('/'));
    if (!categoryId || !filename) return null;

    const baseName = filename
        .replace(/[/\\]/g, '_')
        .replace(/\.[^.]+$/, '')
        .replace(/[?&%#'!$"()\[\]{}+=, ;]/g, '_');

    return `/thumbnails/${categoryId}/${encodeURIComponent(baseName)}.jpeg`;
}

function updateCategoryProgressThumbnails(oldVideoUrl, newVideoUrl) {
    if (!oldVideoUrl || !newVideoUrl) return;

    const oldThumbUrl = buildThumbnailUrlFromVideoUrl(oldVideoUrl);
    const newThumbUrl = buildThumbnailUrlFromVideoUrl(newVideoUrl);

    for (const [categoryId, entry] of Object.entries(progressCache)) {
        if (!entry || !entry.thumbnail_url) continue;

        if (entry.thumbnail_url === oldVideoUrl) {
            entry.thumbnail_url = newVideoUrl;
        } else if (oldThumbUrl && entry.thumbnail_url === oldThumbUrl && newThumbUrl) {
            entry.thumbnail_url = newThumbUrl;
        }

        if (dbInstance && entry.thumbnail_url && (entry.thumbnail_url === newVideoUrl || entry.thumbnail_url === newThumbUrl)) {
            try {
                const tx = dbInstance.transaction(STORE_NAME, 'readwrite');
                const store = tx.objectStore(STORE_NAME);
                store.put(entry);
            } catch (e) {
                console.warn('Failed to persist category progress thumbnail update:', e);
            }
        }
    }
}

function applyVideoUrlMapping(oldVideoUrl, newVideoUrl) {
    if (!oldVideoUrl || !newVideoUrl || oldVideoUrl === newVideoUrl) {
        return;
    }

    const entry = videoProgressCache[oldVideoUrl];
    if (entry) {
        const updatedEntry = {
            ...entry,
            video_url: newVideoUrl,
            thumbnail_url: buildThumbnailUrlFromVideoUrl(newVideoUrl) || entry.thumbnail_url
        };
        videoProgressCache[newVideoUrl] = updatedEntry;
        delete videoProgressCache[oldVideoUrl];

        if (dbInstance && dbInstance.objectStoreNames.contains(VIDEO_STORE_NAME)) {
            try {
                const transaction = dbInstance.transaction(VIDEO_STORE_NAME, 'readwrite');
                const store = transaction.objectStore(VIDEO_STORE_NAME);
                store.delete(oldVideoUrl);
                store.put(updatedEntry);
            } catch (e) {
                console.warn('Failed to update video progress in IndexedDB:', e);
            }
        }
    }

    updateCategoryProgressThumbnails(oldVideoUrl, newVideoUrl);
}

function getMatchingVideoProgressKeys(videoUrl) {
    if (!videoUrl) return [];

    const keys = new Set();
    const base = videoUrl.split('#')[0].split('?')[0];
    keys.add(videoUrl);
    keys.add(base);
    try { keys.add(decodeURIComponent(videoUrl)); } catch (e) { /* ignore */ }
    try { keys.add(decodeURIComponent(base)); } catch (e) { /* ignore */ }
    try { keys.add(encodeURI(videoUrl)); } catch (e) { /* ignore */ }
    try { keys.add(encodeURI(base)); } catch (e) { /* ignore */ }

    const normalized = toNormalizedVideoPath(videoUrl);
    if (normalized) {
        for (const cachedUrl of Object.keys(videoProgressCache)) {
            if (toNormalizedVideoPath(cachedUrl) === normalized) {
                keys.add(cachedUrl);
            }
        }
    }

    return [...keys].filter(Boolean);
}

function deleteVideoProgressEntry(videoUrl) {
    if (!videoUrl) return;

    const matchingKeys = getMatchingVideoProgressKeys(videoUrl);
    matchingKeys.forEach((key) => {
        if (videoProgressCache[key]) {
            delete videoProgressCache[key];
        }
    });

    if (dbInstance && dbInstance.objectStoreNames.contains(VIDEO_STORE_NAME)) {
        try {
            const transaction = dbInstance.transaction(VIDEO_STORE_NAME, 'readwrite');
            const store = transaction.objectStore(VIDEO_STORE_NAME);
            matchingKeys.forEach((key) => store.delete(key));
        } catch (e) {
            console.warn('Failed to delete video progress in IndexedDB:', e);
        }
    }

    bus.emit(APP_EVENTS.LOCAL_PROGRESS_UPDATE, {
        video_url: videoUrl,
        video_progress_deleted: true
    });
}

/**
 * Initialize IndexedDB and load cache
 * ONLY for sessions without an active profile.
 * @returns {Promise<IDBDatabase|null>}
 */
function initProgressDB() {
    // Return existing promise if already initializing
    if (initPromise) {
        return initPromise;
    }

    initPromise = new Promise((resolve, reject) => {
        // Profile-backed progress lives on the server for every user.
        if (hasActiveProfile()) {
            console.log('[IndexedDB] Skipping - active profile uses server progress');
            dbReady = false;
            initPromise = null;
            resolve(null);
            return;
        }

        if (dbReady) {
            resolve(dbInstance);
            return;
        }

        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onerror = () => {
            console.warn('IndexedDB not available, falling back to memory-only');
            dbReady = true;
            initPromise = null;
            resolve(null);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'category_id' });
            }
            // v2: Add video_progress store for per-video tracking
            if (!db.objectStoreNames.contains(VIDEO_STORE_NAME)) {
                const videoStore = db.createObjectStore(VIDEO_STORE_NAME, { keyPath: 'video_url' });
                videoStore.createIndex('category_id', 'category_id', { unique: false });
            }
        };

        request.onsuccess = (event) => {
            dbInstance = event.target.result;

            // Load all progress into cache
            const transaction = dbInstance.transaction(STORE_NAME, 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const getAllRequest = store.getAll();

            getAllRequest.onsuccess = () => {
                getAllRequest.result.forEach(item => {
                    if (!item?.category_id) return;
                    const merged = preferNewerProgress(progressCache[item.category_id], item);
                    progressCache[item.category_id] = merged;
                });

                // Also load video progress into cache
                if (dbInstance.objectStoreNames.contains(VIDEO_STORE_NAME)) {
                    const videoTx = dbInstance.transaction(VIDEO_STORE_NAME, 'readonly');
                    const videoStore = videoTx.objectStore(VIDEO_STORE_NAME);
                    const videoRequest = videoStore.getAll();
                    videoRequest.onsuccess = () => {
                        videoRequest.result.forEach(item => {
                            if (!item?.video_url) return;
                            const merged = preferNewerProgress(videoProgressCache[item.video_url], item);
                            videoProgressCache[item.video_url] = merged;
                        });
                        console.log(`[IndexedDB] Loaded ${Object.keys(progressCache).length} category + ${Object.keys(videoProgressCache).length} video progress entries`);

                        // Mark as ready ONLY after all caches are populated
                        dbReady = true;
                        initPromise = null;
                        flushCachesToIndexedDB();

                        // Resolve stale paths in the background (non-blocking)
                        resolveStaleProgress();

                        resolve(dbInstance);
                    };
                    videoRequest.onerror = () => {
                        dbReady = true;
                        initPromise = null;
                        resolve(dbInstance);
                    };
                } else {
                    console.log(`[IndexedDB] Loaded ${Object.keys(progressCache).length} progress entries into cache`);
                    dbReady = true;
                    initPromise = null;
                    flushCachesToIndexedDB();
                    resolve(dbInstance);
                }
            };

            getAllRequest.onerror = () => {
                dbReady = true;
                initPromise = null;
                resolve(dbInstance);
            };
        };
    });
}

/**
 * Save progress to IndexedDB for no-profile guest/session mode only.
 * Uses in-memory cache for instant writes, async persist to IndexedDB
 * Broadcasts local progress updates for streaming layout and other listeners
 * @param {string} categoryId
 * @param {number} index
 * @param {number} totalCount
 * @param {number|null} videoTimestamp
 * @param {number|null} videoDuration
 * @param {string|null} thumbnailUrl
 */
function saveLocalProgress(categoryId, index, totalCount, videoTimestamp, videoDuration, thumbnailUrl) {
    if (hasActiveProfile()) {
        return;
    }

    const progressData = {
        category_id: categoryId,
        index,
        total_count: totalCount,
        thumbnail_url: thumbnailUrl,
        last_updated: Date.now()
    };

    // Only include video progress if > 0
    if (videoTimestamp && videoTimestamp > 0) {
        progressData.video_timestamp = videoTimestamp;
        progressData.video_duration = videoDuration;
    }

    // Update cache immediately (sync)
    progressCache[categoryId] = progressData;

    // Persist to IndexedDB (async, non-blocking)
    if (dbInstance) {
        try {
            const transaction = dbInstance.transaction(STORE_NAME, 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            store.put(progressData);
        } catch (e) {
            console.warn('Failed to persist progress to IndexedDB:', e);
        }
    }

    // Broadcast local IndexedDB progress so listeners can refresh in real time.
    bus.emit(APP_EVENTS.LOCAL_PROGRESS_UPDATE, {
        category_id: categoryId,
        index,
        total_count: totalCount,
        video_timestamp: videoTimestamp,
        video_duration: videoDuration,
        thumbnail_url: thumbnailUrl
    });
}

/**
 * Load progress from cache for no-profile guest/session mode only.
 * Instant sync read from in-memory cache
 * @param {string} categoryId
 * @returns {Object|null}
 */
function getLocalProgress(categoryId) {
    if (hasActiveProfile()) {
        return null;
    }

    const data = progressCache[categoryId];
    if (!data) return null;

    // Return without the category_id key (match old format)
    return {
        index: data.index,
        total_count: data.total_count,
        thumbnail_url: data.thumbnail_url,
        video_timestamp: data.video_timestamp,
        video_duration: data.video_duration,
        last_updated: data.last_updated
    };
}

/**
 * Save video-specific progress to IndexedDB for no-profile guest/session mode only.
 * @param {string} videoUrl
 * @param {string} categoryId
 * @param {number} videoTimestamp
 * @param {number} videoDuration
 * @param {string|null} thumbnailUrl
 */
function saveVideoLocalProgress(videoUrl, categoryId, videoTimestamp, videoDuration, thumbnailUrl) {
    if (hasActiveProfile()) {
        return;
    }

    if (!videoTimestamp || videoTimestamp <= 0) return;
    const progressData = {
        video_url: videoUrl,
        category_id: categoryId,
        video_timestamp: videoTimestamp,
        video_duration: videoDuration,
        thumbnail_url: thumbnailUrl,
        last_updated: Date.now()
    };

    // Update cache immediately (sync)
    videoProgressCache[videoUrl] = progressData;

    // Persist to IndexedDB (async, non-blocking)
    if (dbInstance && dbInstance.objectStoreNames.contains(VIDEO_STORE_NAME)) {
        try {
            const transaction = dbInstance.transaction(VIDEO_STORE_NAME, 'readwrite');
            const store = transaction.objectStore(VIDEO_STORE_NAME);
            store.put(progressData);
            console.log(`[IndexedDB] Saved video progress: ${videoUrl.split('/').pop()}, time=${videoTimestamp}`);
        } catch (e) {
            console.warn('Failed to persist video progress to IndexedDB:', e);
        }
    }

    // Broadcast video progress saves for real-time Continue Watching updates.
    bus.emit(APP_EVENTS.LOCAL_PROGRESS_UPDATE, {
        category_id: categoryId,
        video_url: videoUrl,
        video_timestamp: videoTimestamp,
        video_duration: videoDuration,
        thumbnail_url: thumbnailUrl
    });
}

/**
 * Get video-specific progress from cache (for per-video tracking mode)
 * @param {string} videoUrl
 * @returns {Object|null}
 */
function getVideoLocalProgress(videoUrl) {
    if (hasActiveProfile()) {
        return null;
    }

    const data = resolveVideoProgressEntry(videoUrl);
    if (!data) return null;

    return {
        video_timestamp: data.video_timestamp,
        video_duration: data.video_duration,
        thumbnail_url: data.thumbnail_url,
        last_updated: data.last_updated
    };
}

/**
 * Get all video progress for a category (for per-video tracking mode)
 * @param {string} categoryId
 * @returns {Object}
 */
function getCategoryVideoLocalProgress(categoryId) {
    if (hasActiveProfile()) {
        return {};
    }

    const result = {};
    for (const [url, data] of Object.entries(videoProgressCache)) {
        if (data.category_id === categoryId && data.video_timestamp > 0) {
            result[url] = {
                video_timestamp: data.video_timestamp,
                video_duration: data.video_duration,
                thumbnail_url: data.thumbnail_url
            };
        }
    }
    return result;
}

/**
 * Get ALL video progress (for streaming layout Continue Watching)
 * Returns array of {video_url, category_id, video_timestamp, video_duration, thumbnail_url}
 * @returns {Array}
 */
function getAllVideoLocalProgress() {
    if (hasActiveProfile()) {
        return [];
    }

    const normalizedEntries = new Map();
    for (const [url, data] of Object.entries(videoProgressCache)) {
        if (data.video_timestamp > 0) {
            const entry = {
                video_url: url,
                category_id: data.category_id,
                video_timestamp: data.video_timestamp,
                video_duration: data.video_duration,
                thumbnail_url: data.thumbnail_url,
                last_updated: data.last_updated || 0
            };
            const normalized = toNormalizedVideoPath(url) || url;
            const existing = normalizedEntries.get(normalized);
            normalizedEntries.set(normalized, preferNewerProgress(existing, entry));
        }
    }

    const result = [...normalizedEntries.values()];

    // Sort by last_updated descending (most recently watched first) - matches admin API behavior
    result.sort((a, b) => (b.last_updated || 0) - (a.last_updated || 0));

    return result;
}

/**
 * Rename video progress entry when file path changes
 * Updates both IndexedDB and in-memory cache
 * Used when admin renames a file and guest is online
 * @param {string} oldVideoUrl
 * @param {string} newVideoUrl
 */
function renameVideoProgress(oldVideoUrl, newVideoUrl) {
    if (hasActiveProfile()) {
        return;
    }

    applyVideoUrlMapping(oldVideoUrl, newVideoUrl);
    console.log(`[IndexedDB] Renamed progress: ${oldVideoUrl.split('/').pop()} -> ${newVideoUrl.split('/').pop()}`);
}

/**
 * Resolve stale paths in IndexedDB when returning to app
 * Called on app load to update progress with current file paths
 * @returns {Promise<void>}
 */
async function resolveStaleProgress() {
    const pathsToResolve = Object.keys(videoProgressCache);
    if (pathsToResolve.length === 0) return;

    try {
        const response = await fetch('/api/progress/resolve-paths', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: pathsToResolve })
        });

        if (response.ok) {
            const result = await response.json();
            const mappings = result.mappings || {};
            const stale = result.stale || [];

            for (const [oldPath, newPath] of Object.entries(mappings)) {
                if (newPath && newPath !== oldPath) {
                    applyVideoUrlMapping(oldPath, newPath);
                }
            }

            if (Array.isArray(stale) && stale.length > 0) {
                stale.forEach((path) => {
                    deleteVideoProgressEntry(path);
                });
            }

            const resolvedCount = Object.keys(mappings).length;
            if (resolvedCount > 0) {
                console.log(`[IndexedDB] Resolved ${resolvedCount} stale progress paths`);
            }
            if (Array.isArray(stale) && stale.length > 0) {
                console.log(`[IndexedDB] Pruned ${stale.length} stale progress entries`);
            }
        }
    } catch (e) {
        console.warn('Failed to resolve stale progress paths:', e);
    }
}

/**
 * Check if user is admin
 * @returns {boolean}
 */
function isUserAdmin() {
    return window.ragotModules?.appStore?.get?.('isAdmin') === true;
}

/**
 * Legacy compatibility helper.
 * Guest progress is now always enabled when no profile is active.
 * @returns {boolean}
 */
function isSessionProgressEnabled() {
    return true;
}

/**
 * Check if IndexedDB is ready (cache is populated)
 * @returns {boolean}
 */
function isProgressDBReady() {
    return dbReady;
}

/**
 * Clear all video progress (Continue Watching data)
 * Preserves category progress for "Resume Category" functionality
 * @returns {Promise<number>} Number of entries cleared
 */
async function clearAllVideoProgress() {
    if (hasActiveProfile()) {
        console.warn('[progressDB] Profile-backed progress should be cleared through the server endpoint');
        return 0;
    }

    const clearedCount = Object.keys(videoProgressCache).length;

    // Clear in-memory cache
    Object.keys(videoProgressCache).forEach(key => delete videoProgressCache[key]);

    // Clear IndexedDB store
    if (dbInstance && dbInstance.objectStoreNames.contains(VIDEO_STORE_NAME)) {
        try {
            const transaction = dbInstance.transaction(VIDEO_STORE_NAME, 'readwrite');
            const store = transaction.objectStore(VIDEO_STORE_NAME);
            await new Promise((resolve, reject) => {
                const clearRequest = store.clear();
                clearRequest.onsuccess = () => resolve();
                clearRequest.onerror = () => reject(clearRequest.error);
            });
            console.log(`[progressDB] Cleared ${clearedCount} video progress entries`);
        } catch (e) {
            console.error('[progressDB] Failed to clear video progress:', e);
            throw e;
        }
    }

    // Broadcast so Continue Watching listeners can refresh immediately.
    bus.emit(APP_EVENTS.LOCAL_PROGRESS_UPDATE, { cleared_all_video_progress: true });

    return clearedCount;
}

/**
 * Check if a profile-backed TV cast is currently authoritative for a category.
 * Profile casts should not double-save from the browser while TV reports progress.
 * Guest casts do not trigger this because Guest progress stays in IndexedDB.
 * @param {string} categoryId
 * @returns {boolean}
 */
function isTvAuthorityForCategory(categoryId) {
    if (!hasActiveProfile()) {
        return false;
    }

    // Access via global appModules to avoid circular dependency
    const tvCastManager = window.ragotModules?.tvCastManager;
    if (tvCastManager && typeof tvCastManager.isCastingToCategory === 'function') {
        return tvCastManager.isCastingToCategory(categoryId);
    }
    return false;
}

export {
    initProgressDB,
    saveLocalProgress,
    getLocalProgress,
    saveVideoLocalProgress,
    deleteVideoProgressEntry as deleteVideoLocalProgress,
    getVideoLocalProgress,
    getCategoryVideoLocalProgress,
    getAllVideoLocalProgress,
    clearAllVideoProgress,
    renameVideoProgress,
    resolveStaleProgress,
    isUserAdmin,
    isSessionProgressEnabled,
    isProgressDBReady,
    isTvAuthorityForCategory
};
