/**
 * Cache Manager Utility
 * Handles media caching, size management, and resource cleanup
 */
import { $$ } from '../libs/ragot.esm.min.js';

function requireAppRuntime() {
    const runtime = window.ragotModules?.appRuntime;
    if (!runtime) throw new Error('[cacheManager] appRuntime service is not registered');
    return runtime;
}

function requireAppState() {
    const appState = window.ragotModules?.appState;
    if (!appState) throw new Error('[cacheManager] appState service is not registered');
    return appState;
}

function requireAppCache() {
    const appCache = window.ragotModules?.appCache;
    if (!appCache) throw new Error('[cacheManager] appCache service is not registered');
    return appCache;
}

/**
 * Add an item to the media cache with size management
 * @param {string} key - The cache key (usually the media URL)
 * @param {HTMLElement} element - The element to cache
 */
function addToCache(key, element) {
    if (!key || !element) return;
    const appCache = requireAppCache();
    const { MAX_CACHE_SIZE } = requireAppRuntime();
    
    // Add to cache
    appCache.set(key, element);
    
    // Check if we need to prune the cache
    if (appCache.size > MAX_CACHE_SIZE) {
        pruneCache();
    }
}

/**
 * Get an item from the media cache
 * @param {string} key - The cache key to retrieve
 * @returns {HTMLElement|null} - The cached element or null if not found
 */
function getFromCache(key) {
    const appCache = requireAppCache();
    if (!key || !appCache.has(key)) return null;
    
    return appCache.get(key) || null;
}

/**
 * Check if an item exists in the cache
 * @param {string} key - The cache key to check
 * @returns {boolean} - Whether the item exists in cache
 */
function hasInCache(key) {
    return key && requireAppCache().has(key);
}

/**
 * Prune the cache when it exceeds the maximum size
 */
function pruneCache() {
    const appCache = requireAppCache();
    const { MAX_CACHE_SIZE } = requireAppRuntime();
    const keysToDelete = Array.from(appCache.keys()).slice(0, appCache.size - MAX_CACHE_SIZE);
    keysToDelete.forEach(key => appCache.delete(key));
}

/**
 * Clear the entire cache
 */
function clearCache() {
    requireAppCache().clear();
}

/**
 * Perform periodic cleanup of the cache
 * @param {boolean} aggressive - Whether to perform aggressive cleanup
 */
function performCacheCleanup(aggressive = false) {
    const now = Date.now();
    const appState = requireAppState();
    const { MOBILE_DEVICE, MOBILE_CLEANUP_INTERVAL } = requireAppRuntime();
    
    // Use the MEMORY_CLEANUP_INTERVAL from server config if available
    const cleanupInterval = (window.serverConfig && window.serverConfig.MEMORY_CLEANUP_INTERVAL) || 60000;
    
    // Use the mobile cleanup interval from appRuntime when on mobile
    const effectiveInterval = MOBILE_DEVICE ? MOBILE_CLEANUP_INTERVAL : cleanupInterval;
    
    if (aggressive || now - appState.lastCleanupTime > effectiveInterval) {
        clearCache();
        
        // Clear any media elements that might be detached but still referenced
        if (aggressive) {
            // Try to clear any detached media elements
            const mediaElements = $$('video, audio, img');
            mediaElements.forEach(element => {
                if (!document.body.contains(element) && element.parentNode) {
                    try {
                        // Remove from parent if it exists but is not in body
                        element.parentNode.removeChild(element);
                    } catch (e) {
                        // Ignore errors
                    }
                }
                
                // For videos and audio, explicitly release resources
                if (!document.body.contains(element)) {
                    try {
                        if (element.tagName === 'VIDEO' || element.tagName === 'AUDIO') {
                            element.pause();
                            element.removeAttribute('src');
                            element.srcObject = null;
                        }
                    } catch (e){
                        // ignore
                    }
                }
            });
        }
        
        // Request idle callback for garbage collection hint
        // Avoid creating objects which increases memory pressure on Pi 4
        try {
            if ('requestIdleCallback' in window) {
                // Use idle callback to hint GC during browser idle time
                window.requestIdleCallback(() => {
                    // Clear any object URLs that might be lingering
                    const blobUrls = $$('[src^="blob:"]');
                    blobUrls.forEach(el => {
                        if (!document.body.contains(el)) {
                            try { URL.revokeObjectURL(el.src); } catch(e) {}
                        }
                    });
                }, { timeout: 1000 });
            }
        } catch (e) {
            console.log('Memory cleanup operation completed');
        }
        
        appState.lastCleanupTime = now;
    }
}

export {
    addToCache,
    getFromCache,
    hasInCache,
    pruneCache,
    clearCache,
    performCacheCleanup
};

