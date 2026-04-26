/**
 * Shared media utility constants and helpers.
 */

import { createLazyLoader, createElement, append } from '../libs/ragot.esm.min.js';

export const THUMBNAIL_PENDING_SRC = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22 preserveAspectRatio=%22none%22%3E%3Crect width=%2216%22 height=%229%22 fill=%22%23161a20%22/%3E%3C/svg%3E';
export const THUMBNAIL_PLACEHOLDER_LAYER_CLASS = 'gh-thumbnail-placeholder-layer';
export const THUMBNAIL_LOADING_OVERLAY_CLASS = 'gh-thumbnail-loading-overlay';

function findThumbnailPlaceholderLayer(target) {
    if (!target) return null;
    if (target.classList?.contains(THUMBNAIL_PLACEHOLDER_LAYER_CLASS)) return target;
    return target.closest?.('[data-thumbnail-host]')?.querySelector(`.${THUMBNAIL_PLACEHOLDER_LAYER_CLASS}`) || null;
}

function findThumbnailLoadingOverlay(target) {
    if (!target) return null;
    if (target.classList?.contains(THUMBNAIL_LOADING_OVERLAY_CLASS)) return target;
    return target.closest?.('[data-thumbnail-host]')?.querySelector(`.${THUMBNAIL_LOADING_OVERLAY_CLASS}`) || null;
}

function isLoadingThumbnailState(state = '') {
    return state === 'pending' || state === 'generating';
}

function clearInlineThumbnailPresentation(img) {
    if (!img) return;
    img.style.objectFit = '';
    img.style.padding = '';
    img.style.background = '';
}

export { clearInlineThumbnailPresentation };

export function buildThumbnailPlaceholderLayerAttrs({
    className = '',
    state = 'pending',
    hidden = false
} = {}) {
    const attrs = {
        className: `${THUMBNAIL_PLACEHOLDER_LAYER_CLASS} ${className}`.trim(),
        'aria-hidden': 'true',
        'data-thumbnail-visual': 'ghosthub',
        'data-thumbnail-state': state
    };

    if (hidden) attrs.hidden = 'hidden';
    return attrs;
}

export function createThumbnailLoadingOverlay({
    className = '',
    hidden = false
} = {}) {
    return createElement('div', {
        className: `${THUMBNAIL_LOADING_OVERLAY_CLASS} ${className}`.trim(),
        'aria-hidden': 'true',
        ...(hidden ? { hidden: 'hidden' } : {})
    }, [
        createElement('div', { className: 'gh-thumbnail-loading-meta' }, [
            createElement('div', { className: 'gh-thumbnail-loading-line' }),
            createElement('div', { className: 'gh-thumbnail-loading-line short' })
        ])
    ]);
}

export function createThumbnailShell({
    shellClassName = '',
    placeholderClassName = '',
    loadingOverlayClassName = '',
    imageClassName = '',
    finalSrc = null,
    includePlaceholder = true,
    includeLoadingOverlay = true,
    alt = '',
    placeholderState = 'pending',
    eager = false,
    eagerMode = 'placeholder',
    fetchPriority = 'low',
    showPendingState = true,
    shellDataset = null
} = {}) {
    const shell = createElement('div', {
        className: `gh-thumbnail-shell ${shellClassName}`.trim(),
        dataset: { thumbnailHost: '', ...(shellDataset || {}) }
    });

    if (includePlaceholder) {
        append(shell, createElement('div', buildThumbnailPlaceholderLayerAttrs({
            className: placeholderClassName,
            state: placeholderState
        })));
    }

    if (includeLoadingOverlay) {
        append(shell, createThumbnailLoadingOverlay({
            className: loadingOverlayClassName,
            hidden: !isLoadingThumbnailState(placeholderState)
        }));
    }

    if (finalSrc) {
        append(shell, createElement('img', buildThumbnailImageAttrs({
            className: `gh-thumbnail-image ${imageClassName}`.trim(),
            finalSrc,
            alt,
            eager,
            eagerMode,
            fetchPriority,
            showPendingState
        })));
    }

    return shell;
}

export function setThumbnailPlaceholderState(target, {
    visible = true,
    state = 'pending'
} = {}) {
    const layer = findThumbnailPlaceholderLayer(target);
    const overlay = findThumbnailLoadingOverlay(target);
    if (layer) {
        layer.dataset.thumbnailState = state;
        if (visible) layer.removeAttribute('hidden');
        else layer.setAttribute('hidden', 'hidden');
    }
    if (overlay) {
        if (visible && isLoadingThumbnailState(state)) overlay.removeAttribute('hidden');
        else overlay.setAttribute('hidden', 'hidden');
    }
    return layer;
}

export function setThumbnailImageState(img, state = null) {
    if (!img) return;
    if (state) img.dataset.imageState = state;
    else delete img.dataset.imageState;
}

export function applyThumbnailPlaceholder(img, { state = 'error' } = {}) {
    if (!img) return;
    clearInlineThumbnailPresentation(img);
    setThumbnailImageState(img, state);
    setThumbnailPlaceholderState(img, { visible: true, state });
    img.removeAttribute('src');
    img.removeAttribute('srcset');
}

export function isGeneratedThumbnailSrc(src) {
    return typeof src === 'string' && src.includes('/thumbnails/');
}

export function withThumbnailRetryParam(url, attempt) {
    if (!url) return url;
    try {
        const parsed = new URL(url, window.location.origin);
        parsed.searchParams.set('_r', String(attempt));
        return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch (_) {
        const stripped = url.replace(/([?&])_r=\d+(&?)/, '$1').replace(/[?&]$/, '');
        const hasQuery = stripped.includes('?');
        return `${stripped}${hasQuery ? '&' : '?'}_r=${attempt}`;
    }
}

export function createThumbnailLazyLoader(owner, {
    selector = '[data-src]',
    root = null,
    rootMargin = '1000px',
    concurrency = 6,
    retry = null,
    onLoad = null,
    onError = null
} = {}) {
    return createLazyLoader(owner, {
        selector,
        root,
        rootMargin,
        concurrency,
        retry,
        onStateChange: (img, state) => {
            setThumbnailImageState(img, state);
            setThumbnailPlaceholderState(img, {
                visible: state !== 'loaded',
                state
            });
        },
        onLoad,
        onError: (img, ctx) => {
            applyThumbnailPlaceholder(img, { state: 'error' });
            if (typeof onError === 'function') onError(img, ctx);
        }
    });
}

export function hydrateEagerThumbnailImage(img, {
    finalSrc = '',
    retryThumbnails = true,
    maxRetries = 5,
    baseDelayMs = 2000,
    onLoad = null
} = {}) {
    if (!img || !finalSrc) return;
    setThumbnailImageState(img, 'pending');

    const loadAttempt = (src, attempt = 0) => {
        const preload = new Image();
        preload.decoding = 'async';

        preload.onload = () => {
            clearInlineThumbnailPresentation(img);
            img.src = src;
            setThumbnailImageState(img, 'loaded');
            if (typeof onLoad === 'function') onLoad(img);
        };

        preload.onerror = () => {
            const canRetry = retryThumbnails &&
                src.includes('/thumbnails/') &&
                attempt < maxRetries;
            if (canRetry) {
                const delay = baseDelayMs * Math.pow(2, attempt);
                setTimeout(() => {
                    loadAttempt(withThumbnailRetryParam(finalSrc, attempt + 1), attempt + 1);
                }, delay);
                return;
            }
            applyThumbnailPlaceholder(img);
        };

        preload.src = src;
    };

    loadAttempt(finalSrc, 0);
}

export function attachDirectEagerThumbnail(img, {
    finalSrc = '',
    retryThumbnails = true,
    maxRetries = 5,
    baseDelayMs = 2000,
    onLoad = null,
    onPending = null,
    onError = null,
    preservePlaceholderOnError = false
} = {}) {
    if (!img || !finalSrc) return;

    const setPendingState = () => {
        setThumbnailImageState(img, 'pending');
        if (typeof onPending === 'function') onPending(img);
    };

    const clearPendingState = () => {
        if (img.dataset.imageState === 'pending') {
            delete img.dataset.imageState;
        }
    };

    const resetToPlaceholderShell = () => {
        clearPendingState();
        img.removeAttribute('src');
        img.removeAttribute('srcset');
        if (typeof onError === 'function') onError(img);
    };

    const applySrc = (src, attempt = 0) => {
        setPendingState();

        img.onload = () => {
            clearPendingState();
            clearInlineThumbnailPresentation(img);
            setThumbnailImageState(img, 'loaded');
            if (typeof onLoad === 'function') onLoad(img);
        };

        img.onerror = () => {
            const canRetry = retryThumbnails &&
                src.includes('/thumbnails/') &&
                attempt < maxRetries;
            if (canRetry) {
                // Keep shimmer alive during retries: remove broken src but
                // leave the placeholder in pending state so the shimmer
                // animation continues instead of showing a static grey box.
                img.removeAttribute('src');
                img.removeAttribute('srcset');
                if (!preservePlaceholderOnError) {
                    applyThumbnailPlaceholder(img);
                    if (typeof onError === 'function') onError(img);
                }
                const delay = baseDelayMs * Math.pow(2, attempt);
                setTimeout(() => {
                    applySrc(withThumbnailRetryParam(finalSrc, attempt + 1), attempt + 1);
                }, delay);
                return;
            }
            if (preservePlaceholderOnError) {
                resetToPlaceholderShell();
                return;
            }
            applyThumbnailPlaceholder(img);
            if (typeof onError === 'function') onError(img);
        };

        img.src = src;

        if (img.complete) {
            if (img.naturalWidth > 0 || img.naturalHeight > 0) {
                img.onload?.();
            } else {
                img.onerror?.();
            }
        }
    };

    if (img.complete && (img.naturalWidth > 0 || img.naturalHeight > 0) && (img.currentSrc || img.src) === finalSrc) {
        clearPendingState();
        clearInlineThumbnailPresentation(img);
        setThumbnailImageState(img, 'loaded');
        if (typeof onLoad === 'function') onLoad(img);
        return;
    }

    applySrc(finalSrc, 0);
}

export function buildThumbnailImageAttrs({
    className = '',
    finalSrc = null,
    alt = '',
    eager = false,
    eagerMode = 'placeholder',
    fetchPriority = 'low',
    showPendingState = true
} = {}) {
    const attrs = {
        className: className.trim(),
        alt,
        decoding: 'async',
        'data-thumbnail-visual': 'ghosthub'
    };

    if (!finalSrc) {
        attrs.src = THUMBNAIL_PENDING_SRC;
        if (showPendingState) attrs['data-image-state'] = 'pending';
        attrs['aria-hidden'] = alt ? undefined : 'true';
        return attrs;
    }

    if (eager) {
        attrs.loading = 'eager';
        attrs.fetchpriority = fetchPriority;
        attrs.dataset = { eagerSrc: finalSrc };
        if (eagerMode === 'direct') {
            if (showPendingState) attrs['data-image-state'] = 'pending';
        } else {
            if (showPendingState) attrs['data-image-state'] = 'pending';
        }
        return attrs;
    }

    if (showPendingState) attrs['data-image-state'] = 'pending';
    attrs.dataset = { src: finalSrc };
    attrs.loading = 'lazy';
    attrs.fetchpriority = fetchPriority;
    attrs.className = `${attrs.className} lazy lazy-load`.trim();
    return attrs;
}

/**
 * Compute an adaptive IntersectionObserver rootMargin based on device memory
 * and network conditions. Pi-tier aware.
 *
 * @param {Object} distances
 * @param {number} distances.low           - px distance for devices with <= 2GB RAM
 * @param {number} distances.base          - px distance for devices with <= 4GB RAM
 * @param {number} distances.high          - px distance for devices with > 4GB RAM
 * @param {number} distances.saveDataFloor - minimum px when saveData is active
 * @param {number} [distances.saveDataMult=0.65] - multiplier applied when saveData is active
 * @returns {string} rootMargin string e.g. "2200px"
 */
export function getAdaptiveRootMargin({ low, base, high, saveDataFloor, saveDataMult = 0.65 }) {
    const deviceMemory = navigator.deviceMemory || 4;
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const effectiveType = connection?.effectiveType || '';
    const saveData = connection?.saveData === true;

    let distance = base;
    if (deviceMemory <= 2) distance = low;
    else if (deviceMemory <= 4) distance = base;
    else distance = high;

    if (effectiveType.includes('2g')) distance += 800;
    else if (effectiveType === '3g') distance += 500;

    if (saveData) distance = Math.max(saveDataFloor, Math.floor(distance * saveDataMult));
    return `${distance}px`;
}
