/**
 * Request Cache & Deduplication Utility
 * Prevents simultaneous identical API calls by caching in-flight requests
 *
 * Problem: Multiple components calling the same API simultaneously causes:
 * - Wasted bandwidth (4+ calls/sec observed)
 * - Server load spikes
 * - Race conditions in state updates
 *
 * Solution: Track in-flight requests and return existing promise if available
 */

// In-flight request cache: URL -> Promise
const inFlightRequests = new Map();

// Default timeout for API requests (ms). Prevents indefinite hangs on slow connections.
const DEFAULT_TIMEOUT_MS = 15000;

/**
 * Deduplicating fetch wrapper
 * If an identical request is already in-flight, returns that promise instead
 *
 * @param {string} url - Request URL (used as cache key)
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>}
 *
 * @example
 * // Multiple calls to same URL will only make ONE network request
 * const p1 = cachedFetch('/api/categories');
 * const p2 = cachedFetch('/api/categories'); // Returns same promise as p1
 * const [r1, r2] = await Promise.all([p1, p2]); // Both get same response
 */
export async function cachedFetch(url, options = {}) {
    // Create cache key from URL + relevant options
    const cacheKey = getCacheKey(url, options);

    // Check if request is already in-flight
    if (inFlightRequests.has(cacheKey)) {
        console.log(`[RequestCache] Deduplicating request: ${url}`);
        // Return a fresh clone of the resolved response for this deduplicated caller
        return inFlightRequests.get(cacheKey).then(response => response.clone());
    }

    // Attach an AbortController with timeout so requests don't hang indefinitely
    const timeoutMs = options.timeout || DEFAULT_TIMEOUT_MS;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const fetchOptions = { ...options, signal: options.signal || controller.signal };
    delete fetchOptions.timeout;  // Not a valid fetch option

    // Make the request. We don't clone it here because a Promise resolves
    // to a single object identity. If we cloned it here, all concurrent
    // awaiters would still receive the ONE clone and crash when reading.
    const requestPromise = fetch(url, fetchOptions);

    // Track the promise so other callers can chain off it.
    // The finally block cleans up the cache when the request concludes.
    const cacheablePromise = requestPromise.finally(() => {
        clearTimeout(timeoutId);
        inFlightRequests.delete(cacheKey);
    });

    inFlightRequests.set(cacheKey, cacheablePromise);

    // The initial caller ALSO gets a clone. The original response body
    // is left untouched so that future .clone() calls by concurrent
    // deduplicated requests will succeed without "body already read" errors.
    return cacheablePromise.then(response => response.clone());
}

/**
 * Generate cache key from URL and relevant options
 * @param {string} url
 * @param {RequestInit} options
 * @returns {string}
 */
function getCacheKey(url, options) {
    // Include method and headers in cache key (body intentionally excluded for simplicity)
    const method = options.method || 'GET';
    const headersKey = options.headers ? JSON.stringify(options.headers) : '';
    return `${method}:${url}:${headersKey}`;
}

/**
 * Clear all cached in-flight requests
 * Useful for testing or force-refresh scenarios
 */
export function clearRequestCache() {
    inFlightRequests.clear();
}

/**
 * Get count of currently in-flight requests
 * Useful for debugging/monitoring
 * @returns {number}
 */
export function getInFlightCount() {
    return inFlightRequests.size;
}
