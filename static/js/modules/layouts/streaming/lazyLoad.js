import { getLazyLoadObserver, setLazyLoadObserver, streamingState } from './state.js';
import {
    createThumbnailLazyLoader,
    getAdaptiveRootMargin,
    isGeneratedThumbnailSrc,
    withThumbnailRetryParam
} from '../../../utils/mediaUtils.js';

let _loader = null;
let _loaderRoot = null;

const getRootMargin = () => getAdaptiveRootMargin({ low: 1600, base: 2200, high: 2800, saveDataFloor: 1000, saveDataMult: 0.7 });

/**
 * Initialize streaming layout lazy loading
 */
export function initLazyLoading(root = null) {
    if (_loader && _loaderRoot === root) return;

    if (_loader) {
        _loader.destroy();
        _loader = null;
    }

    _loaderRoot = root;

    _loader = createThumbnailLazyLoader(streamingState, {
        selector: '.streaming-card-thumbnail[data-src]',
        root,
        rootMargin: getRootMargin(),
        concurrency: (navigator.deviceMemory || 4) <= 2 ? 4 : 8,
        retry: {
            maxAttempts: 5,
            baseDelayMs: 2000,
            backoffFactor: 2,
            shouldRetry: (img) => isGeneratedThumbnailSrc(img.src || img.dataset.src || ''),
            getNextSrc: (_img, attempt, currentSrc) => withThumbnailRetryParam(currentSrc, attempt),
            schedule: (fn, delayMs) => streamingState.timeout(fn, delayMs)
        }
    });

    setLazyLoadObserver(_loader);
}

export function observeLazyImage(img) {
    if (_loader) _loader.observe(img);
}

export function resetLazyImage(img) {
    if (_loader) _loader.reset(img);
}

export function primeLazyImage(img, options = {}) {
    if (_loader) _loader.prime(img, options);
}

/**
 * Re-scan the streaming container for any newly-injected lazy images.
 * Call after morphDOM rerenders rows (e.g. after hidden-content reveal or setState).
 */
export function refreshLazyLoader() {
    if (_loader) _loader.refresh();
}

export function cleanupLazyLoading() {
    if (_loader) {
        _loader.destroy();
        _loader = null;
    }
    _loaderRoot = null;
    setLazyLoadObserver(null);
}
