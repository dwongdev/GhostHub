import { describe, it, expect } from 'vitest';
import {
    buildThumbnailImageAttrs,
    buildThumbnailPlaceholderLayerAttrs
} from '../../utils/mediaUtils.js';

describe('thumbnail visuals', () => {
    it('applies the shared GhostHub visual marker to lazy thumbnails', () => {
        const attrs = buildThumbnailImageAttrs({
            className: 'gallery-item-thumbnail',
            finalSrc: '/thumbnails/cat-1/item.jpeg'
        });

        expect(attrs['data-thumbnail-visual']).toBe('ghosthub');
        expect(attrs['data-image-state']).toBe('pending');
        expect(attrs.className).toContain('lazy-load');
        expect(attrs.src).toBeUndefined();
    });

    it('applies the shared GhostHub visual marker to eager thumbnails', () => {
        const attrs = buildThumbnailImageAttrs({
            className: 'streaming-hero-backdrop',
            finalSrc: '/thumbnails/cat-1/hero.jpeg',
            eager: true,
            eagerMode: 'direct',
            showPendingState: false
        });

        expect(attrs['data-thumbnail-visual']).toBe('ghosthub');
        expect(attrs['data-image-state']).toBeUndefined();
        expect(attrs.dataset.eagerSrc).toBe('/thumbnails/cat-1/hero.jpeg');
        expect(attrs.src).toBeUndefined();
    });

    it('applies the shared GhostHub visual marker to placeholder layers', () => {
        const attrs = buildThumbnailPlaceholderLayerAttrs({
            className: 'streaming-card-thumbnail-placeholder'
        });

        expect(attrs['data-thumbnail-visual']).toBe('ghosthub');
        expect(attrs['data-thumbnail-state']).toBe('pending');
        expect(attrs.className).toContain('gh-thumbnail-placeholder-layer');
    });
});
