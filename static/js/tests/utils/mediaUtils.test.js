/**
 * Media Utils Tests
 * -----------------
 * Tests the adaptive rootMargin calculation which directly controls
 * how aggressively thumbnails are lazy-loaded. Wrong values = blank
 * thumbnails on low-end devices (Pi) or wasted bandwidth on every load.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    THUMBNAIL_PENDING_SRC,
    applyThumbnailPlaceholder,
    buildThumbnailPlaceholderLayerAttrs,
    getAdaptiveRootMargin
} from '../../utils/mediaUtils.js';

// ─── Constants ────────────────────────────────────────────────────────────────

describe('THUMBNAIL_PENDING_SRC', () => {
    it('uses the inline dark pending svg transport', () => {
        expect(THUMBNAIL_PENDING_SRC.startsWith('data:image/svg+xml,')).toBe(true);
    });
});

// ─── buildThumbnailPlaceholderLayerAttrs ────────────────────────────────────

describe('buildThumbnailPlaceholderLayerAttrs', () => {
    it('returns the shared placeholder-layer attrs contract', () => {
        expect(buildThumbnailPlaceholderLayerAttrs({ state: 'pending' })).toMatchObject({
            className: expect.stringContaining('gh-thumbnail-placeholder-layer'),
            'data-thumbnail-visual': 'ghosthub',
            'data-thumbnail-state': 'pending'
        });
    });
});

// ─── applyThumbnailPlaceholder ───────────────────────────────────────────────

describe('applyThumbnailPlaceholder', () => {
    it('clears image sources and marks the image as errored', () => {
        const host = document.createElement('div');
        host.dataset.thumbnailHost = '';
        const layer = document.createElement('div');
        layer.className = 'gh-thumbnail-placeholder-layer';
        const img = document.createElement('img');
        img.src = '/thumbnails/cat-1/example.jpeg';
        host.append(layer, img);
        document.body.appendChild(host);

        applyThumbnailPlaceholder(img);

        expect(img.getAttribute('src')).toBe(null);
        expect(img.dataset.imageState).toBe('error');
        expect(layer.hidden).toBe(false);
        expect(layer.dataset.thumbnailState).toBe('error');
    });
});

// ─── getAdaptiveRootMargin ───────────────────────────────────────────────────

describe('getAdaptiveRootMargin', () => {
    const distances = {
        low: 800,
        base: 1500,
        high: 2500,
        saveDataFloor: 600,
        saveDataMult: 0.65
    };

    beforeEach(() => {
        // Reset navigator mocks
        Object.defineProperty(navigator, 'deviceMemory', {
            value: 4, writable: true, configurable: true
        });
        // Clear connection mock
        Object.defineProperty(navigator, 'connection', {
            value: undefined, writable: true, configurable: true
        });
    });

    it('returns base distance for 4GB RAM device', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 4, configurable: true });
        expect(getAdaptiveRootMargin(distances)).toBe('1500px');
    });

    it('returns low distance for Pi-tier (≤2GB) devices', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 2, configurable: true });
        expect(getAdaptiveRootMargin(distances)).toBe('800px');
    });

    it('returns low distance for 1GB devices', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 1, configurable: true });
        expect(getAdaptiveRootMargin(distances)).toBe('800px');
    });

    it('returns high distance for high-end (>4GB) devices', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 8, configurable: true });
        expect(getAdaptiveRootMargin(distances)).toBe('2500px');
    });

    it('defaults to base (4GB) when deviceMemory is unavailable', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: undefined, configurable: true });
        expect(getAdaptiveRootMargin(distances)).toBe('1500px');
    });

    it('adds 800px on 2g connections for extreme prefetch', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 4, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { effectiveType: '2g', saveData: false },
            configurable: true
        });
        expect(getAdaptiveRootMargin(distances)).toBe('2300px'); // 1500 + 800
    });

    it('adds 500px on 3g connections', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 4, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { effectiveType: '3g', saveData: false },
            configurable: true
        });
        expect(getAdaptiveRootMargin(distances)).toBe('2000px'); // 1500 + 500
    });

    it('does not add extra on 4g connections', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 4, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { effectiveType: '4g', saveData: false },
            configurable: true
        });
        expect(getAdaptiveRootMargin(distances)).toBe('1500px');
    });

    it('applies saveData multiplier and floor', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 4, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { effectiveType: '4g', saveData: true },
            configurable: true
        });
        // 1500 * 0.65 = 975, max(600, 975) = 975
        expect(getAdaptiveRootMargin(distances)).toBe('975px');
    });

    it('uses saveData floor when multiplied value is too low', () => {
        const lowDistances = {
            low: 200, base: 400, high: 800,
            saveDataFloor: 600, saveDataMult: 0.65
        };
        Object.defineProperty(navigator, 'deviceMemory', { value: 2, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { effectiveType: '4g', saveData: true },
            configurable: true
        });
        // 200 * 0.65 = 130, max(600, 130) = 600
        expect(getAdaptiveRootMargin(lowDistances)).toBe('600px');
    });

    it('respects custom saveDataMult', () => {
        const custom = { ...distances, saveDataMult: 0.5 };
        Object.defineProperty(navigator, 'deviceMemory', { value: 8, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { saveData: true },
            configurable: true
        });
        // 2500 * 0.5 = 1250, max(600, 1250) = 1250
        expect(getAdaptiveRootMargin(custom)).toBe('1250px');
    });

    it('combines slow connection + saveData correctly', () => {
        Object.defineProperty(navigator, 'deviceMemory', { value: 2, configurable: true });
        Object.defineProperty(navigator, 'connection', {
            value: { effectiveType: '2g', saveData: true },
            configurable: true
        });
        // low=800, +800 for 2g = 1600, *0.65 = 1040, max(600, 1040) = 1040
        expect(getAdaptiveRootMargin(distances)).toBe('1040px');
    });

    it('returns a properly formatted px string', () => {
        const result = getAdaptiveRootMargin(distances);
        expect(result).toMatch(/^\d+px$/);
    });
});
