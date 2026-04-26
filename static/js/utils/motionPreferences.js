/**
 * Motion preference helpers.
 * User preference can force reduced motion or fall back to system settings.
 */

const MOTION_ATTR = 'data-motion';
const MOTION_PREF_ATTR = 'data-motion-preference';

function getMotionRoot() {
    return document.documentElement;
}

function getSystemReducedMotion() {
    return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function resolveMotionPreference(preference = null) {
    if (preference === 'reduced') return 'reduced';
    return getSystemReducedMotion() ? 'reduced' : 'default';
}

export function applyMotionPreference(preference = null) {
    const root = getMotionRoot();
    const resolved = resolveMotionPreference(preference);
    root.setAttribute(MOTION_ATTR, resolved);
    root.setAttribute(MOTION_PREF_ATTR, preference || 'system');
    return { preference: preference || 'system', resolved };
}

export function getAppliedMotionPreference() {
    return getMotionRoot().getAttribute(MOTION_PREF_ATTR) || 'system';
}

export function isReducedMotionActive() {
    return getMotionRoot().getAttribute(MOTION_ATTR) === 'reduced';
}
