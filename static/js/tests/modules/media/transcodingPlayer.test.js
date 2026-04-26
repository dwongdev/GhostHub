/**
 * Tests for Transcoding Player Module
 * Tests GhostStream transcoding for incompatible video formats (MKV, AVI, etc.).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock dependencies before imports
vi.mock('../../../core/app.js', () => ({
    app: {
        state: {
            currentMediaIndex: 0,
            fullMediaList: [
                { type: 'video', name: 'test.mkv', url: '/media/movies/test.mkv' }
            ]
        }
    },
    MOBILE_DEVICE: false
}));

vi.mock('../../../utils/progressDB.js', () => ({
    isUserAdmin: vi.fn(() => false),
    isSessionProgressEnabled: vi.fn(() => true),
    isTvAuthorityForCategory: vi.fn(() => false),
    saveVideoLocalProgress: vi.fn(),
    getVideoLocalProgress: vi.fn(() => null)
}));

vi.mock('./elementFactory.js', () => ({
    requiresTranscoding: vi.fn((filename) => filename.endsWith('.mkv') || filename.endsWith('.avi')),
    createCannotPlayElement: vi.fn(() => {
        const div = document.createElement('div');
        div.className = 'cannot-play-container';
        return div;
    })
}));

import {
    initTranscodingPlayer,
    createTranscodingVideoElement,
    playWithTranscoding
} from '../../../modules/media/transcodingPlayer.js';
import { app } from '../../../core/app.js';

describe('Transcoding Player Module', () => {
    let mockGhoststreamManager;
    let mockSocket;
    let sampleFile;

    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = '';

        // Sample MKV file
        sampleFile = {
            name: 'test-video.mkv',
            url: '/media/movies/test-video.mkv',
            thumbnailUrl: '/thumbnails/test-video.jpg',
            type: 'video',
            size: 10485760,
            width: 1920,
            height: 1080
        };

        // Mock socket
        mockSocket = {
            connected: true,
            emit: vi.fn()
        };

        // Mock GhostStream manager
        mockGhoststreamManager = {
            isAvailable: vi.fn(() => true),
            checkStatus: vi.fn(() => Promise.resolve()),
            getPreferences: vi.fn(() => ({
                preferredQuality: 'original',
                enableABR: false
            })),
            checkCache: vi.fn(() => Promise.resolve(null)),
            transcode: vi.fn(() => Promise.resolve({
                job_id: 'test-job-123',
                stream_url: 'http://localhost:8080/hls/test.m3u8',
                start_time: 0,
                duration: 120,
                media_info: { duration: 120 }
            })),
            getJobStatus: vi.fn(() => Promise.resolve({
                status: 'streaming',
                stream_url: 'http://localhost:8080/hls/test.m3u8'
            })),
            createHLSPlayer: vi.fn((video, streamUrl) => ({
                load: vi.fn(() => Promise.resolve()),
                destroy: vi.fn(),
                hls: {
                    loadSource: vi.fn()
                }
            })),
            cancelJob: vi.fn(),
            transcodeMedia: vi.fn(() => Promise.resolve({
                job_id: 'test-job-456',
                stream_url: 'http://localhost:8080/hls/test.m3u8'
            }))
        };

        window.ragotModules = {
            appState: app.state,
            ghoststreamManager: mockGhoststreamManager,
            fullscreenManager: null,
            syncManager: null
        };

        window.socket = mockSocket;

        // Mock video.play() to avoid jsdom NotImplementedError
        HTMLVideoElement.prototype.play = vi.fn(() => Promise.resolve());

        // Reset mocks
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    describe('initTranscodingPlayer', () => {
        it('should initialize with socket instance', () => {
            expect(() => initTranscodingPlayer(mockSocket)).not.toThrow();
        });

        it('should accept null socket', () => {
            expect(() => initTranscodingPlayer(null)).not.toThrow();
        });
    });

    describe('createTranscodingVideoElement', () => {
        it('should create container with correct classes', () => {
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);

            expect(element.className).toContain('viewer-media');
            expect(element.className).toContain('ghoststream-transcode-container');
        });

        it('should set data attributes', () => {
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);

            expect(element.dataset.transcoding).toBe('true');
            expect(element.dataset.url).toBe('/media/movies/test-video.mkv');
            expect(element.dataset.index).toBe('0');
        });

        it('should create poster image when thumbnailUrl provided', () => {
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);

            const poster = element.querySelector('.ghoststream-poster');
            expect(poster).not.toBeNull();
            expect(poster.src).toContain('/thumbnails/test-video.jpg');
            expect(poster.alt).toBe('test-video.mkv');
        });

        it('should not create poster when thumbnailUrl missing', () => {
            const fileWithoutThumbnail = { ...sampleFile, thumbnailUrl: null };
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(fileWithoutThumbnail, true, decision);

            const poster = element.querySelector('.ghoststream-poster');
            expect(poster).toBeNull();
        });

        it('should create badge with reason', () => {
            const decision = { reason: 'MKV format requires transcoding' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);

            const badge = element.querySelector('.ghoststream-badge');
            expect(badge).not.toBeNull();
            expect(badge.innerHTML).toContain('MKV format requires transcoding');
        });

        it('should create loading indicator', () => {
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);

            const indicator = element.querySelector('.ghoststream-indicator');
            expect(indicator).not.toBeNull();
            expect(indicator.innerHTML).toContain('Preparing stream...');
        });

        it('should call checkStatus on creation', async () => {
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);
            document.body.appendChild(element);

            // Wait for async operation
            await new Promise(r => setTimeout(r, 100));

            expect(mockGhoststreamManager.checkStatus).toHaveBeenCalled();
        });

        it('should call checkCache with correct parameters', async () => {
            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(sampleFile, true, decision);
            document.body.appendChild(element);

            // Wait for async operation
            await new Promise(r => setTimeout(r, 100));

            expect(mockGhoststreamManager.checkCache).toHaveBeenCalledWith(
                'movies',
                'test-video.mkv',
                'original',
                'h264'
            );
        });
    });

    describe('playWithTranscoding (Fallback Method)', () => {
        it('should throw error when GhostStream unavailable', async () => {
            mockGhoststreamManager.isAvailable.mockReturnValueOnce(false);

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';

            await expect(
                playWithTranscoding(sampleFile, container, placeholder)
            ).rejects.toThrow('GhostStream not available');
        });

        it('should call transcodeMedia with correct parameters', async () => {
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('#EXTM3U\n#EXT-X-VERSION:3')
            }));

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';
            container.appendChild(placeholder);

            await playWithTranscoding(sampleFile, container, placeholder);

            expect(mockGhoststreamManager.transcodeMedia).toHaveBeenCalledWith(
                'movies',
                'test-video.mkv',
                expect.objectContaining({
                    mode: 'stream',
                    format: 'hls',
                    video_codec: 'h264'
                })
            );
        });

        it('should verify manifest before playing', async () => {
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('#EXTM3U\n#EXT-X-VERSION:3')
            }));

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';
            container.appendChild(placeholder);

            await playWithTranscoding(sampleFile, container, placeholder);

            expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/hls/test.m3u8');
        });

        it('should create video element and replace placeholder', async () => {
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('#EXTM3U\n#EXT-X-VERSION:3')
            }));

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';
            container.appendChild(placeholder);

            const video = await playWithTranscoding(sampleFile, container, placeholder);

            expect(video).not.toBeNull();
            expect(video.tagName).toBe('VIDEO');
            expect(video.className).toContain('ghoststream-video');
            expect(container.contains(video)).toBe(true);
            expect(container.contains(placeholder)).toBe(false);
        });

        it('should set up HLS player', async () => {
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('#EXTM3U\n#EXT-X-VERSION:3')
            }));

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';
            container.appendChild(placeholder);

            await playWithTranscoding(sampleFile, container, placeholder);

            expect(mockGhoststreamManager.createHLSPlayer).toHaveBeenCalled();
        });

        it('should attach cleanup function to video', async () => {
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('#EXTM3U\n#EXT-X-VERSION:3')
            }));

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';
            container.appendChild(placeholder);

            const video = await playWithTranscoding(sampleFile, container, placeholder);

            expect(video._ghoststreamCleanup).toBeDefined();
            expect(typeof video._ghoststreamCleanup).toBe('function');

            // Call cleanup
            video._ghoststreamCleanup();

            expect(mockGhoststreamManager.cancelJob).toHaveBeenCalledWith('test-job-456');
        });

        it('should throw error when transcode job fails', async () => {
            mockGhoststreamManager.transcodeMedia.mockResolvedValueOnce(null);

            const container = document.createElement('div');
            const placeholder = document.createElement('div');
            placeholder.innerHTML = '<div class="placeholder-text"></div>';
            container.appendChild(placeholder);

            await expect(
                playWithTranscoding(sampleFile, container, placeholder)
            ).rejects.toThrow('Failed to start transcode job');
        });
    });

    describe('URL Parsing', () => {
        it('should correctly parse category from URL', async () => {
            const file = {
                name: 'test.mkv',
                url: '/media/tv-shows/season1/test.mkv',
                thumbnailUrl: '/thumbnails/test.jpg'
            };

            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(file, true, decision);
            document.body.appendChild(element);

            await new Promise(r => setTimeout(r, 100));

            expect(mockGhoststreamManager.checkCache).toHaveBeenCalledWith(
                'tv-shows',
                expect.any(String),
                expect.any(String),
                expect.any(String)
            );
        });

        it('should decode URL-encoded filenames', async () => {
            const file = {
                name: 'test video.mkv',
                url: '/media/movies/test%20video.mkv',
                thumbnailUrl: '/thumbnails/test.jpg'
            };

            const decision = { reason: 'Format not supported' };
            const element = createTranscodingVideoElement(file, true, decision);
            document.body.appendChild(element);

            await new Promise(r => setTimeout(r, 100));

            expect(mockGhoststreamManager.checkCache).toHaveBeenCalledWith(
                'movies',
                'test video.mkv',
                expect.any(String),
                expect.any(String)
            );
        });
    });
});


