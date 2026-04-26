/**
 * Wake Lock Utility Module
 * Prevents screen sleep during video playback across all browsers and platforms.
 *
 * @module utils/wakeLock
 */
import { Module } from '../libs/ragot.esm.min.js';

let wakeLock = null;
let requestCount = 0; // Track multiple simultaneous requests
let wakeLockLifecycle = null;

class WakeLockLifecycle extends Module {
    constructor() {
        super();
        this.onVisibilityChange = this.onVisibilityChange.bind(this);
        this.onBeforeUnload = this.onBeforeUnload.bind(this);
    }

    onStart() {
        this.on(document, 'visibilitychange', this.onVisibilityChange);
        this.on(window, 'beforeunload', this.onBeforeUnload);
    }

    async onVisibilityChange() {
        if (document.visibilityState === 'visible' && requestCount > 0) {
            console.log('[WakeLock] Page visible again, re-requesting wake lock');
            wakeLock = null;
            await requestWakeLock();
        }
    }

    onBeforeUnload() {
        forceReleaseWakeLock();
    }
}

function ensureWakeLockLifecycle() {
    if (!wakeLockLifecycle) {
        wakeLockLifecycle = new WakeLockLifecycle();
    }
    wakeLockLifecycle.start();
}

/**
 * Request Screen Wake Lock to prevent sleep during playback
 * Safe to call multiple times - will only request once
 * @returns {Promise<boolean>} True if wake lock was acquired, false otherwise
 */
export async function requestWakeLock() {
    if (!('wakeLock' in navigator)) {
        console.warn('[WakeLock] Wake Lock API not supported in this browser');
        return false;
    }

    requestCount++;

    try {
        if (wakeLock) {
            console.log('[WakeLock] Wake Lock already active (request count:', requestCount, ')');
            return true; // Already active
        }

        wakeLock = await navigator.wakeLock.request('screen');

        const onRelease = () => {
            console.log('[WakeLock] Screen Wake Lock was released');
            wakeLock = null;
            requestCount = 0; // Reset count on release
        };
        wakeLock.addEventListener('release', onRelease);
        wakeLockLifecycle.addCleanup(() => wakeLock?.removeEventListener('release', onRelease));

        console.log('[WakeLock] Screen Wake Lock is active');
        return true;
    } catch (err) {
        console.error(`[WakeLock] Failed to acquire: ${err.name}, ${err.message}`);
        requestCount = Math.max(0, requestCount - 1); // Decrement on failure
        return false;
    }
}

/**
 * Release Screen Wake Lock
 * Safe to call even if wake lock is not active
 */
export function releaseWakeLock() {
    requestCount = Math.max(0, requestCount - 1);

    // Only release if no other components need it
    if (requestCount > 0) {
        console.log('[WakeLock] Not releasing - still needed by', requestCount, 'component(s)');
        return;
    }

    if (wakeLock) {
        wakeLock.release()
            .then(() => {
                console.log('[WakeLock] Wake Lock released successfully');
            })
            .catch((err) => {
                console.error('[WakeLock] Failed to release:', err);
            });
        wakeLock = null;
    }
}

/**
 * Check if wake lock is currently active
 * @returns {boolean} True if wake lock is active
 */
export function isWakeLockActive() {
    return wakeLock !== null;
}

/**
 * Force release wake lock regardless of request count
 * Use this when you need to guarantee wake lock is released
 */
export function forceReleaseWakeLock() {
    requestCount = 0;
    if (wakeLock) {
        wakeLock.release();
        wakeLock = null;
        console.log('[WakeLock] Force released');
    }
}

ensureWakeLockLifecycle();
