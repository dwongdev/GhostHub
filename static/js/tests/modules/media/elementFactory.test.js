/**
 * Tests for Element Factory Module
 * Tests creation of video, image, and placeholder DOM elements.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock dependencies
vi.mock('../../../core/app.js', () => ({
    MOBILE_DEVICE: false
}));

vi.mock('../../../utils/icons.js', () => ({
    videoIcon: vi.fn((size) => `<svg class="video-icon" width="${size}"></svg>`),
    imageIcon: vi.fn((size) => `<svg class="image-icon" width="${size}"></svg>`),
    fileIcon: vi.fn((size) => `<svg class="file-icon" width="${size}"></svg>`),
    clapperIcon: vi.fn((size) => `<svg class="clapper-icon" width="${size}"></svg>`)
}));

vi.mock('../../../modules/playback/autoPlay.js', () => ({
    isAutoPlayActive: vi.fn(() => false)
}));

import {
    UNPLAYABLE_FORMATS,
    requiresTranscoding,
    createCannotPlayElement,
    createVideoThumbnailElement,
    createImageElement,
    createPlaceholderElement,
    updateMediaInfoOverlay
} from '../../../modules/media/elementFactory.js';

describe('Element Factory Module', () => {
    let sampleFile;

    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = '';

        // Reset window.ragotModules
        window.ragotModules = {
            ghoststreamManager: null
        };

        sampleFile = {
            name: 'test-video.mp4',
            url: '/media/test-video.mp4',
            thumbnailUrl: '/thumbnails/test-video.jpg',
            type: 'video',
            size: 10485760, // 10 MB
            width: 1920,
            height: 1080,
            date: '2023-12-25'
        };
    });

    describe('UNPLAYABLE_FORMATS', () => {
        it('should include common unplayable formats', () => {
            expect(UNPLAYABLE_FORMATS).toContain('mkv');
            expect(UNPLAYABLE_FORMATS).toContain('avi');
            expect(UNPLAYABLE_FORMATS).toContain('wmv');
            expect(UNPLAYABLE_FORMATS).toContain('flv');
        });

        it('should be an array', () => {
            expect(Array.isArray(UNPLAYABLE_FORMATS)).toBe(true);
        });
    });

    describe('requiresTranscoding', () => {
        it('should return true for MKV files', () => {
            expect(requiresTranscoding('movie.mkv')).toBe(true);
            expect(requiresTranscoding('MOVIE.MKV')).toBe(true);
        });

        it('should return true for AVI files', () => {
            expect(requiresTranscoding('video.avi')).toBe(true);
        });

        it('should return false for MP4 files', () => {
            expect(requiresTranscoding('video.mp4')).toBe(false);
        });

        it('should return false for WebM files', () => {
            expect(requiresTranscoding('video.webm')).toBe(false);
        });

        it('should be case insensitive', () => {
            expect(requiresTranscoding('VIDEO.MKV')).toBe(true);
            expect(requiresTranscoding('Video.Mkv')).toBe(true);
        });

        it('should handle files with multiple dots', () => {
            expect(requiresTranscoding('my.video.file.mkv')).toBe(true);
            expect(requiresTranscoding('my.video.file.mp4')).toBe(false);
        });
    });

    describe('createCannotPlayElement', () => {
        it('should create a div with cannot-play-container class', () => {
            const element = createCannotPlayElement(sampleFile, 'Test reason');

            expect(element.tagName).toBe('DIV');
            expect(element.classList.contains('cannot-play-container')).toBe(true);
        });

        it('should display the file extension', () => {
            const file = { name: 'video.mkv' };
            const element = createCannotPlayElement(file, 'Test reason');

            expect(element.innerHTML).toContain('MKV');
        });

        it('should display the reason', () => {
            const element = createCannotPlayElement(sampleFile, 'No transcoding server');

            expect(element.innerHTML).toContain('No transcoding server');
        });

        it('should include error message', () => {
            const element = createCannotPlayElement(sampleFile, 'Test reason');

            expect(element.innerHTML).toContain('Cannot play this video');
        });

        it('should have appropriate styling', () => {
            const element = createCannotPlayElement(sampleFile, 'Test reason');
            expect(element.classList.contains('cannot-play-container')).toBe(true);
            expect(element.querySelector('.cannot-play-container__content')).not.toBeNull();
            expect(element.querySelector('.cannot-play-container__title')).not.toBeNull();
        });
    });

    describe('createVideoThumbnailElement', () => {
        it('should create thumbnail container for playable formats', () => {
            const element = createVideoThumbnailElement(sampleFile, false);

            expect(element.classList.contains('video-thumbnail-container')).toBe(true);
        });

        it('should add active class when isActive is true', () => {
            const element = createVideoThumbnailElement(sampleFile, true);

            expect(element.classList.contains('active')).toBe(true);
        });

        it('should not add active class when isActive is false', () => {
            const element = createVideoThumbnailElement(sampleFile, false);

            expect(element.classList.contains('active')).toBe(false);
        });

        it('should set data-video-src attribute', () => {
            const element = createVideoThumbnailElement(sampleFile, false);

            expect(element.getAttribute('data-video-src')).toBe('/media/test-video.mp4');
        });

        it('should store file info as JSON', () => {
            const element = createVideoThumbnailElement(sampleFile, false);
            const fileInfo = JSON.parse(element.getAttribute('data-file-info'));

            expect(fileInfo.name).toBe('test-video.mp4');
            expect(fileInfo.url).toBe('/media/test-video.mp4');
        });

        it('should create thumbnail image', () => {
            const element = createVideoThumbnailElement(sampleFile, false);
            const img = element.querySelector('.video-thumbnail-image');

            expect(img).not.toBeNull();
            expect(img.src).toContain('/thumbnails/test-video.jpg');
            expect(img.alt).toBe('test-video.mp4');
        });

        it('should use eager loading for active thumbnails', () => {
            const element = createVideoThumbnailElement(sampleFile, true);
            const img = element.querySelector('.video-thumbnail-image');

            expect(img.loading).toBe('eager');
        });

        it('should use lazy loading for inactive thumbnails', () => {
            const element = createVideoThumbnailElement(sampleFile, false);
            const img = element.querySelector('.video-thumbnail-image');

            expect(img.loading).toBe('lazy');
        });

        it('should include play overlay', () => {
            const element = createVideoThumbnailElement(sampleFile, false);
            const overlay = element.querySelector('.play-icon-overlay');

            expect(overlay).not.toBeNull();
        });

        it('should return cannot-play element for MKV without GhostStream', () => {
            const mkvFile = { ...sampleFile, name: 'video.mkv', url: '/media/video.mkv' };
            window.ragotModules.ghoststreamManager = null;

            const element = createVideoThumbnailElement(mkvFile, false);

            expect(element.classList.contains('cannot-play-container')).toBe(true);
        });

        it('should create thumbnail for MKV with GhostStream available', () => {
            const mkvFile = { ...sampleFile, name: 'video.mkv', url: '/media/video.mkv' };
            window.ragotModules.ghoststreamManager = {
                isAvailable: () => true
            };

            const element = createVideoThumbnailElement(mkvFile, false);

            expect(element.classList.contains('video-thumbnail-container')).toBe(true);
        });
    });

    describe('createImageElement', () => {
        it('should create an img element', () => {
            const element = createImageElement(sampleFile);

            expect(element.tagName).toBe('IMG');
        });

        it('should set src from file URL', () => {
            const element = createImageElement(sampleFile);

            expect(element.src).toContain('/media/test-video.mp4');
        });

        it('should set alt text from filename', () => {
            const element = createImageElement(sampleFile);

            expect(element.alt).toBe('test-video.mp4');
        });

        it('should use lazy loading', () => {
            const element = createImageElement(sampleFile);

            expect(element.loading).toBe('lazy');
        });

        it('should have error handler', () => {
            const element = createImageElement(sampleFile);

            expect(element._ragotHandlers?.error).toBeTruthy();
            expect(typeof element._ragotHandlers?.error).toBe('function');
        });

        it('should replace with placeholder on error', () => {
            const element = createImageElement(sampleFile);
            const parent = document.createElement('div');
            parent.appendChild(element);

            // Trigger error
            element.dispatchEvent(new Event('error'));

            // Should be replaced with placeholder
            expect(parent.querySelector('img')).toBeNull();
            expect(parent.querySelector('.unknown-file-placeholder')).not.toBeNull();
        });
    });

    describe('createPlaceholderElement', () => {
        it('should create div with placeholder class', () => {
            const element = createPlaceholderElement(sampleFile, 'video');

            expect(element.tagName).toBe('DIV');
            expect(element.classList.contains('unknown-file-placeholder')).toBe(true);
        });

        it('should display filename', () => {
            const element = createPlaceholderElement(sampleFile, 'video');

            expect(element.textContent).toContain('test-video.mp4');
        });

        it('should show video icon and message for video type', () => {
            const element = createPlaceholderElement(sampleFile, 'video');

            expect(element.innerHTML).toContain('video-icon');
            expect(element.textContent).toContain('Video failed to load');
        });

        it('should show image icon and message for image type', () => {
            const element = createPlaceholderElement(sampleFile, 'image');

            expect(element.innerHTML).toContain('image-icon');
            expect(element.textContent).toContain('Image failed to load');
        });

        it('should show file icon for unknown type', () => {
            const element = createPlaceholderElement(sampleFile);

            expect(element.innerHTML).toContain('file-icon');
            expect(element.textContent).toContain('Unsupported file type');
        });

        it('should have appropriate flex styling', () => {
            const element = createPlaceholderElement(sampleFile, 'video');
            expect(element.querySelector('.unknown-file-placeholder__content')).not.toBeNull();
            expect(element.querySelector('.unknown-file-placeholder__icon')).not.toBeNull();
            expect(element.querySelector('.unknown-file-placeholder__meta')).not.toBeNull();
        });
    });

    describe('updateMediaInfoOverlay', () => {
        let overlay, filename, metadata, dimensionsSpan, sizeSpan, dateSpan;

        beforeEach(() => {
            // Create media info overlay structure
            overlay = document.createElement('div');
            overlay.className = 'media-info-overlay';

            filename = document.createElement('div');
            filename.className = 'filename';

            metadata = document.createElement('div');
            metadata.className = 'metadata';

            dimensionsSpan = document.createElement('span');
            dimensionsSpan.className = 'dimensions';

            sizeSpan = document.createElement('span');
            sizeSpan.className = 'size';

            dateSpan = document.createElement('span');
            dateSpan.className = 'date';

            metadata.appendChild(dimensionsSpan);
            metadata.appendChild(sizeSpan);
            metadata.appendChild(dateSpan);

            overlay.appendChild(filename);
            overlay.appendChild(metadata);

            document.body.appendChild(overlay);
        });

        it('should update filename', () => {
            updateMediaInfoOverlay(sampleFile);

            expect(filename.textContent).toBe('test-video.mp4');
        });

        it('should display Unknown file when name missing', () => {
            updateMediaInfoOverlay({ ...sampleFile, name: null });

            expect(filename.textContent).toBe('Unknown file');
        });

        it('should format size in MB for large files', () => {
            updateMediaInfoOverlay(sampleFile);

            expect(sizeSpan.textContent).toBe('10 MB');
        });

        it('should format size in KB for small files', () => {
            const smallFile = { ...sampleFile, size: 512000 }; // ~488 KB
            updateMediaInfoOverlay(smallFile);

            expect(sizeSpan.textContent).toBe('48.8 KB');
        });

        it('should display dimensions', () => {
            updateMediaInfoOverlay(sampleFile);

            expect(dimensionsSpan.textContent).toBe('1920 × 1080');
        });

        it('should format date correctly', () => {
            updateMediaInfoOverlay(sampleFile);

            // Date formatting can vary by locale, just check it's not empty
            expect(dateSpan.textContent).not.toBe('');
            expect(dateSpan.textContent).not.toBe('Unknown date');
        });

        it('should show Unknown size when size missing', () => {
            updateMediaInfoOverlay({ ...sampleFile, size: null });

            expect(sizeSpan.textContent).toBe('Unknown size');
        });

        it('should show Unknown dimensions when dimensions missing', () => {
            updateMediaInfoOverlay({ ...sampleFile, width: null, height: null });

            expect(dimensionsSpan.textContent).toBe('Unknown dimensions');
        });

        it('should handle missing file gracefully', () => {
            expect(() => updateMediaInfoOverlay(null)).not.toThrow();
        });

        it('should handle missing overlay gracefully', () => {
            document.body.innerHTML = '';
            expect(() => updateMediaInfoOverlay(sampleFile)).not.toThrow();
        });
    });
});
