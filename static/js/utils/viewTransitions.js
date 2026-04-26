/**
 * viewTransitions.js
 * Small helper around document.startViewTransition with a CSS fallback.
 */

function supportsMatchMedia() {
    return typeof window !== 'undefined' && typeof window.matchMedia === 'function';
}

export function prefersReducedMotion() {
    if (typeof document !== 'undefined' && document.documentElement.getAttribute('data-motion') === 'reduced') {
        return true;
    }
    if (!supportsMatchMedia()) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function canUseViewTransitions() {
    return typeof document !== 'undefined'
        && typeof document.startViewTransition === 'function'
        && !prefersReducedMotion();
}

function withFallbackClass(updateFn, fallbackClass = '', durationMs = 220) {
    const root = document?.documentElement;
    if (!root || !fallbackClass) {
        return updateFn();
    }

    root.classList.add(fallbackClass);
    const clearClass = () => root.classList.remove(fallbackClass);

    try {
        const result = updateFn();
        window.setTimeout(clearClass, durationMs);
        return result;
    } catch (error) {
        clearClass();
        throw error;
    }
}

export function withOptionalViewTransition(updateFn, options = {}) {
    if (typeof updateFn !== 'function') {
        throw new Error('updateFn must be a function');
    }

    const {
        fallbackClass = '',
        durationMs = 220,
    } = options;

    if (!canUseViewTransitions()) {
        return withFallbackClass(updateFn, fallbackClass, durationMs);
    }

    return document.startViewTransition(() => updateFn());
}
