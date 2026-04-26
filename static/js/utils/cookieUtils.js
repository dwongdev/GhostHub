/**
 * Cookie Utilities
 */

/**
 * Get a cookie value by name.
 * @param {string} name - Cookie name
 * @returns {string|null} - Cookie value or null if not found
 */
export function getCookieValue(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    if (!match) return null;
    let value = match[2];
    // Strip leading/trailing double quotes if they exist (standard for some cookie parsers)
    if (value.startsWith('"') && value.endsWith('"')) {
        value = value.substring(1, value.length - 1);
    }
    return value;
}

/**
 * Set a cookie value.
 * @param {string} name - Cookie name
 * @param {string} value - Cookie value
 * @param {number} maxAge - Max age in seconds (default 7 days)
 */
export function setCookie(name, value, maxAge = 604800) {
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${name}=${value}; Max-Age=${maxAge}; Path=/; SameSite=Lax${secure}`;
}

/**
 * Ensures a session_id cookie exists.
 * If missing, generates a UUID and sets it.
 * @returns {string} - The existing or newly created session ID
 */
export function ensureSessionId() {
    let sessionId = getCookieValue('session_id');
    if (!sessionId) {
        // Fallback for non-secure contexts (HTTP) where crypto.randomUUID is unavailable
        if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
            sessionId = crypto.randomUUID();
        } else {
            // Standard UUID4 fallback for non-secure contexts
            sessionId = ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
                (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
            );
        }

        console.log('Generating new client-side session ID:', sessionId);
        setCookie('session_id', sessionId);
    }
    return sessionId;
}
