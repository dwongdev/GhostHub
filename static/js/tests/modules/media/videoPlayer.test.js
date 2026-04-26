/**
 * Tests for Video Player Module
 * Tests video element creation, codec detection, and error handling.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createActualVideoElement } from '../../../modules/media/videoPlayer.js';

// Mock dependencies
vi.mock('../../../core/app.js', () => ({
    MOBILE_DEVICE: false
}));

vi.mock('../../../modules/playback/autoPlay.js', () => ({
    isAutoPlayActive: vi.fn(() => false)
}));

vi.mock('../../../modules/media/elementFactory.js', () => ({
    requiresTranscoding: vi.fn(() => false),
    createCannotPlayElement: vi.fn((file, msg) => {
        const div = document.createElement('div');
        div.className = 'cannot-play';
        div.textContent = msg;
        return div;
    }),
    createPlaceholderElement: vi.fn((file, type) => {
        const div = document.createElement('div');
        div.className = 'placeholder';
        const text = document.createElement('div');
        text.className = 'placeholder-text';
        text.textContent = 'Loading...';
        div.appendChild(text);
        return div;
    })
}));

vi.mock('../../../modules/media/transcodingPlayer.js', () => ({
    createTranscodingVideoElement: vi.fn((file, isActive, decision) => {
        const video = document.createElement('video');
        video.className = 'transcoding-video';
        video.setAttribute('data-transcoding', 'true');
        return video;
    })
}));

describe('Video Player Module', () => {
    let file;
    let mockGhoststreamManager;

    beforeEach(() => {
        file = {
            name: 'test-video.mp4',
            url: '/media/test-video.mp4',
            thumbnailUrl: '/thumbnails/test-video.jpg'
        };

        // Reset window.ragotModules
        window.ragotModules = {
            ghoststreamManager: null,
            fullscreenManager: null,
            syncManager: null
        };

        // Clear all mocks
        vi.clearAllMocks();
    });

    describe('createActualVideoElement - Basic Creation', () => {
        it('should create a video element with correct attributes', () => {
            const video = createActualVideoElement(file, false);

            expect(video.tagName).toBe('VIDEO');
            expect(video.src).toContain('/media/test-video.mp4');
            expect(video.preload).toBe('auto');
            expect(video.muted).toBe(true);
        });

        it('should set poster from thumbnailUrl', () => {
            const video = createActualVideoElement(file, false);

            expect(video.poster).toContain('/thumbnails/test-video.jpg');
        });

        it('should use default SVG poster when no thumbnailUrl', () => {
            file.thumbnailUrl = null;
            const video = createActualVideoElement(file, false);

            expect(video.poster).toContain('data:image/svg+xml');
        });

        it('should set controlsList attribute', () => {
            const video = createActualVideoElement(file, false);

            // Note: controls will be set based on MOBILE_DEVICE value
            // This test verifies controlsList is always set
            expect(video.hasAttribute('controlsList')).toBe(true);
            expect(video.getAttribute('controlsList')).toBe('nodownload');
        });

        it('should set playsinline attributes', () => {
            const video = createActualVideoElement(file, false);

            expect(video.playsInline).toBe(true);
            expect(video.getAttribute('playsinline')).toBe('true');
            expect(video.getAttribute('webkit-playsinline')).toBe('true');
        });

        it('should disable remote playback and enable PiP', () => {
            const video = createActualVideoElement(file, false);

            expect(video.getAttribute('disableRemotePlayback')).toBe('true');
            expect(video.disablePictureInPicture).toBe(false);
            expect(video.autoPictureInPicture).toBe(true);
        });
    });

    describe('createActualVideoElement - Active Video', () => {
        it('should set fetchpriority=high for active videos', () => {
            const video = createActualVideoElement(file, true);

            expect(video.getAttribute('fetchpriority')).toBe('high');
        });

        it('should not set fetchpriority for inactive videos', () => {
            const video = createActualVideoElement(file, false);

            expect(video.hasAttribute('fetchpriority')).toBe(false);
        });

        it('should attach video controls after loadeddata for active videos', async () => {
            const mockAttachControls = vi.fn();
            window.ragotModules.videoControls = {
                attachControls: mockAttachControls
            };

            const video = createActualVideoElement(file, true);

            // Trigger loadeddata event
            video.dispatchEvent(new Event('loadeddata'));

            // Wait for setTimeout
            await new Promise(resolve => setTimeout(resolve, 150));

            expect(mockAttachControls).toHaveBeenCalledWith(video, file);
        });

        it('should not attach video controls for inactive videos', async () => {
            const mockAttachControls = vi.fn();
            window.ragotModules.videoControls = {
                attachControls: mockAttachControls
            };

            const video = createActualVideoElement(file, false);
            video.dispatchEvent(new Event('loadeddata'));

            await new Promise(resolve => setTimeout(resolve, 150));

            expect(mockAttachControls).not.toHaveBeenCalled();
        });

        it('suppresses sync events while scrub preview is active', () => {
            const sendPlaybackSync = vi.fn();
            window.ragotModules.syncManager = {
                isPlaybackSyncInProgress: vi.fn(() => false),
                sendPlaybackSync
            };

            const video = createActualVideoElement(file, false);
            video.setAttribute('data-scrub-preview-active', 'true');

            video.dispatchEvent(new Event('play'));
            video.dispatchEvent(new Event('pause'));
            video.dispatchEvent(new Event('seeked'));

            expect(sendPlaybackSync).not.toHaveBeenCalled();
        });
    });

    describe('createActualVideoElement - Auto-Play Integration', () => {
        it('should enable loop when auto-play is inactive', async () => {
            const { isAutoPlayActive } = await import('../../../modules/playback/autoPlay.js');
            vi.mocked(isAutoPlayActive).mockReturnValue(false);

            const video = createActualVideoElement(file, false);

            expect(video.loop).toBe(true);
            expect(video.hasAttribute('loop')).toBe(true);
        });

        it('should disable loop when auto-play is active', async () => {
            const { isAutoPlayActive } = await import('../../../modules/playback/autoPlay.js');
            vi.mocked(isAutoPlayActive).mockReturnValue(true);

            const video = createActualVideoElement(file, false);

            expect(video.loop).toBe(false);
            expect(video.hasAttribute('loop')).toBe(false);
        });
    });

    describe('createActualVideoElement - Transcoding Detection', () => {
        it('should block incompatible formats when GhostStream unavailable', async () => {
            const { requiresTranscoding, createCannotPlayElement } =
                await import('../../../modules/media/elementFactory.js');

            vi.mocked(requiresTranscoding).mockReturnValue(true);
            window.ragotModules.ghoststreamManager = null;

            const element = createActualVideoElement(file, false);

            expect(element.className).toBe('cannot-play');
            expect(createCannotPlayElement).toHaveBeenCalledWith(
                file,
                'No transcoding server connected.'
            );
        });

        it('should create transcoding video when proactive analysis suggests it', async () => {
            const { requiresTranscoding } = await import('../../../modules/media/elementFactory.js');
            const { createTranscodingVideoElement } =
                await import('../../../modules/media/transcodingPlayer.js');

            vi.mocked(requiresTranscoding).mockReturnValue(false);

            const mockAnalyzePlayback = vi.fn(() => ({
                mode: 'transcode',
                canDirectPlay: false,
                reason: 'Codec not supported'
            }));

            window.ragotModules.ghoststreamManager = {
                isAvailable: () => true,
                analyzePlayback: mockAnalyzePlayback
            };

            const element = createActualVideoElement(file, true);

            expect(mockAnalyzePlayback).toHaveBeenCalledWith(file.name);
            expect(createTranscodingVideoElement).toHaveBeenCalled();
            expect(element.getAttribute('data-transcoding')).toBe('true');
        });

        it('should create normal video when direct play is possible', async () => {
            const mockAnalyzePlayback = vi.fn(() => ({
                mode: 'directplay',
                canDirectPlay: true,
                reason: 'Native support'
            }));

            window.ragotModules.ghoststreamManager = {
                isAvailable: () => true,
                analyzePlayback: mockAnalyzePlayback
            };

            const element = createActualVideoElement(file, false);

            expect(element.tagName).toBe('VIDEO');
            expect(element.hasAttribute('data-transcoding')).toBe(false);
        });
    });

    describe('createActualVideoElement - Error Handling', () => {
        it('should retry loading on error up to maxRetries', () => {
            const video = createActualVideoElement(file, false);
            const originalSrc = video.src;

            // Simulate error
            Object.defineProperty(video, 'error', {
                value: { code: 2, message: 'Network error' },
                writable: true
            });

            video.dispatchEvent(new Event('error'));

            expect(video.getAttribute('data-retries')).toBe('1');
            expect(video.src).not.toBe(originalSrc);
            expect(video.src).toContain('retry=1');
        });

        it('should replace with placeholder after max retries', () => {
            const video = createActualVideoElement(file, false);
            const container = document.createElement('div');
            container.appendChild(video);

            // Set retries to max - 1
            video.setAttribute('data-retries', '2');

            // Simulate error
            Object.defineProperty(video, 'error', {
                value: { code: 2, message: 'Network error' },
                writable: true
            });

            video.dispatchEvent(new Event('error'));

            // Should be replaced with placeholder
            expect(container.querySelector('video')).toBeNull();
            expect(container.querySelector('.placeholder')).not.toBeNull();
        });

        it('should detect codec errors and attempt auto-transcode with GhostStream', async () => {
            const { createTranscodingVideoElement } =
                await import('../../../modules/media/transcodingPlayer.js');

            window.ragotModules.ghoststreamManager = {
                isAvailable: () => true
            };

            const video = createActualVideoElement(file, false);
            const container = document.createElement('div');
            container.className = 'viewer-media-item';
            container.appendChild(video);

            // Simulate codec error (error code 3 = MEDIA_ERR_DECODE)
            Object.defineProperty(video, 'error', {
                value: { code: 3, message: 'DECODE error' },
                writable: true
            });

            video.dispatchEvent(new Event('error'));

            expect(createTranscodingVideoElement).toHaveBeenCalled();
            expect(container.querySelector('.transcoding-video')).not.toBeNull();
        });

        it('should show error message for codec errors without GhostStream', () => {
            window.ragotModules.ghoststreamManager = null;

            const video = createActualVideoElement(file, false);
            const container = document.createElement('div');
            container.appendChild(video);

            // Simulate codec error
            Object.defineProperty(video, 'error', {
                value: { code: 3, message: 'DECODE error' },
                writable: true
            });

            video.dispatchEvent(new Event('error'));

            const placeholder = container.querySelector('.placeholder');
            expect(placeholder).not.toBeNull();
            expect(placeholder.textContent).toContain('Cannot play this video');
        });
    });

    describe('createActualVideoElement - Sync Integration', () => {
        it('should send play sync event', () => {
            const mockSendPlaybackSync = vi.fn();
            window.ragotModules.syncManager = {
                sendPlaybackSync: mockSendPlaybackSync
            };

            const video = createActualVideoElement(file, false);
            video.currentTime = 10.5;

            video.dispatchEvent(new Event('play'));

            expect(mockSendPlaybackSync).toHaveBeenCalledWith('play', 10.5);
        });

        it('should send pause sync event', () => {
            const mockSendPlaybackSync = vi.fn();
            window.ragotModules.syncManager = {
                sendPlaybackSync: mockSendPlaybackSync
            };

            const video = createActualVideoElement(file, false);
            video.currentTime = 20.3;

            video.dispatchEvent(new Event('pause'));

            expect(mockSendPlaybackSync).toHaveBeenCalledWith('pause', 20.3);
        });

        it('should send seek sync event', () => {
            const mockSendPlaybackSync = vi.fn();
            window.ragotModules.syncManager = {
                sendPlaybackSync: mockSendPlaybackSync
            };

            const video = createActualVideoElement(file, false);
            video.currentTime = 45.7;

            video.dispatchEvent(new Event('seeked'));

            expect(mockSendPlaybackSync).toHaveBeenCalledWith('seek', 45.7);
        });

        it('should handle missing syncManager gracefully', () => {
            window.ragotModules.syncManager = null;

            const video = createActualVideoElement(file, false);

            // Should not throw errors
            expect(() => {
                video.dispatchEvent(new Event('play'));
                video.dispatchEvent(new Event('pause'));
                video.dispatchEvent(new Event('seeked'));
            }).not.toThrow();
        });
    });

    describe('createActualVideoElement - Edge Cases', () => {
        it('should handle file without thumbnailUrl', () => {
            const fileNoThumb = { ...file, thumbnailUrl: null };
            const video = createActualVideoElement(fileNoThumb, false);

            expect(video.poster).toContain('data:image/svg+xml');
        });

        it('should handle file with query parameters in URL', () => {
            file.url = '/media/test.mp4?category=movies';
            const video = createActualVideoElement(file, false);

            expect(video.src).toContain('/media/test.mp4?category=movies');
        });

        it('should not autoplay videos', () => {
            const video = createActualVideoElement(file, false);

            expect(video.hasAttribute('autoplay')).toBe(false);
        });

        it('should always start videos muted', () => {
            const video = createActualVideoElement(file, false);

            expect(video.muted).toBe(true);
        });

        it('should set controlsList to nodownload', () => {
            const video = createActualVideoElement(file, false);

            expect(video.getAttribute('controlsList')).toBe('nodownload');
        });
    });
});

