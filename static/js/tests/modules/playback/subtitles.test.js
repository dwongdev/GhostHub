/**
 * Tests for Subtitle Manager Module
 * Tests subtitle loading and display for video elements.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock configManager
vi.mock('../../../utils/configManager.js', () => ({
    getConfigValue: vi.fn((key, defaultValue) => {
        if (key === 'python_config.ENABLE_SUBTITLES') {
            return true; // Default to enabled for most tests
        }
        return defaultValue;
    })
}));

import {
    isSubtitlesEnabled,
    fetchSubtitles,
    removeSubtitles,
    addSubtitleTracks,
    loadSubtitlesForVideo,
    clearSubtitleCache,
    getCacheSize
} from '../../../modules/playback/subtitles.js';

import { getConfigValue } from '../../../utils/configManager.js';

describe('Subtitle Manager Module', () => {
    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = '';

        // Clear subtitle cache before each test
        clearSubtitleCache();

        // Reset mocks
        vi.clearAllMocks();

        // Reset fetch mock
        global.fetch = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    describe('isSubtitlesEnabled', () => {
        it('should return true when subtitles are enabled', () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);

            expect(isSubtitlesEnabled()).toBe(true);
        });

        it('should return false when subtitles are disabled', () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(false);

            expect(isSubtitlesEnabled()).toBe(false);
        });

        it('should default to false when config value is not boolean', () => {
            vi.mocked(getConfigValue).mockReturnValueOnce('yes');

            expect(isSubtitlesEnabled()).toBe(false);
        });

        it('should call getConfigValue with correct key', () => {
            isSubtitlesEnabled();

            expect(getConfigValue).toHaveBeenCalledWith('python_config.ENABLE_SUBTITLES', false);
        });
    });

    describe('fetchSubtitles', () => {
        it('should return empty array when subtitles are disabled', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(false);

            const subtitles = await fetchSubtitles('/media/movies/test.mp4');

            expect(subtitles).toEqual([]);
            expect(global.fetch).not.toHaveBeenCalled();
        });

        it('should fetch subtitles from API', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([
                    { label: 'English', url: '/api/subtitles/cache?file=test_en.vtt', language: 'en' },
                    { label: 'Spanish', url: '/api/subtitles/cache?file=test_es.vtt', language: 'es' }
                ])
            }));

            const subtitles = await fetchSubtitles('/media/movies/test.mp4');

            expect(global.fetch).toHaveBeenCalledWith(
                '/api/subtitles/video?video_url=%2Fmedia%2Fmovies%2Ftest.mp4'
            );
            expect(subtitles).toHaveLength(2);
            expect(subtitles[0].label).toBe('English');
        });

        it('should cache subtitle results', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([
                    { label: 'English', url: '/api/subtitles/cache?file=test_en.vtt' }
                ])
            }));

            // First call
            const subtitles1 = await fetchSubtitles('/media/movies/test.mp4');
            expect(global.fetch).toHaveBeenCalledTimes(1);

            // Second call should use cache
            const subtitles2 = await fetchSubtitles('/media/movies/test.mp4');
            expect(global.fetch).toHaveBeenCalledTimes(1); // Still only 1 call

            expect(subtitles1).toEqual(subtitles2);
        });

        it('should cache empty arrays', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([])
            }));

            await fetchSubtitles('/media/movies/test.mp4');
            await fetchSubtitles('/media/movies/test.mp4');

            expect(global.fetch).toHaveBeenCalledTimes(1);
        });

        it('should return empty array on API error', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: false,
                status: 404
            }));

            const subtitles = await fetchSubtitles('/media/movies/test.mp4');

            expect(subtitles).toEqual([]);
        });

        it('should handle network errors gracefully', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);
            global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));

            const subtitles = await fetchSubtitles('/media/movies/test.mp4');

            expect(subtitles).toEqual([]);
        });

        it('should URL-encode video paths', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([])
            }));

            await fetchSubtitles('/media/movies/test video.mp4');

            expect(global.fetch).toHaveBeenCalledWith(
                '/api/subtitles/video?video_url=%2Fmedia%2Fmovies%2Ftest%20video.mp4'
            );
        });
    });

    describe('removeSubtitles', () => {
        it('should remove track elements from video', () => {
            const video = document.createElement('video');
            const track1 = document.createElement('track');
            const track2 = document.createElement('track');
            video.appendChild(track1);
            video.appendChild(track2);

            removeSubtitles(video);

            expect(video.querySelectorAll('track').length).toBe(0);
        });

        it('should handle non-video elements gracefully', () => {
            const div = document.createElement('div');

            expect(() => removeSubtitles(div)).not.toThrow();
        });

        it('should handle null/undefined gracefully', () => {
            expect(() => removeSubtitles(null)).not.toThrow();
            expect(() => removeSubtitles(undefined)).not.toThrow();
        });

        it('should handle video with no tracks', () => {
            const video = document.createElement('video');

            expect(() => removeSubtitles(video)).not.toThrow();
        });
    });

    describe('addSubtitleTracks', () => {
        it('should add track elements to video', () => {
            const video = document.createElement('video');
            const subtitles = [
                { label: 'English', url: '/subs/en.vtt', language: 'en' },
                { label: 'Spanish', url: '/subs/es.vtt', language: 'es' }
            ];

            addSubtitleTracks(video, subtitles);

            const tracks = video.querySelectorAll('track');
            expect(tracks.length).toBe(2);
            expect(tracks[0].label).toBe('English');
            expect(tracks[0].src).toContain('/subs/en.vtt');
            expect(tracks[0].srclang).toBe('en');
        });

        it('should set default track for first subtitle', () => {
            const video = document.createElement('video');
            const subtitles = [
                { label: 'English', url: '/subs/en.vtt', language: 'en', default: true }
            ];

            addSubtitleTracks(video, subtitles);

            const track = video.querySelector('track');
            expect(track.default).toBe(true);
        });

        it('should not set default for non-first subtitles', () => {
            const video = document.createElement('video');
            const subtitles = [
                { label: 'English', url: '/subs/en.vtt', language: 'en' },
                { label: 'Spanish', url: '/subs/es.vtt', language: 'es', default: true }
            ];

            addSubtitleTracks(video, subtitles);

            const tracks = video.querySelectorAll('track');
            expect(tracks[1].default).toBe(false);
        });

        it('should remove existing tracks before adding new ones', () => {
            const video = document.createElement('video');
            const oldTrack = document.createElement('track');
            video.appendChild(oldTrack);

            const subtitles = [
                { label: 'English', url: '/subs/en.vtt', language: 'en' }
            ];

            addSubtitleTracks(video, subtitles);

            const tracks = video.querySelectorAll('track');
            expect(tracks.length).toBe(1);
            expect(tracks[0].label).toBe('English');
        });

        it('should set default language to "en" when not provided', () => {
            const video = document.createElement('video');
            const subtitles = [
                { label: 'English', url: '/subs/en.vtt' } // No language specified
            ];

            addSubtitleTracks(video, subtitles);

            const track = video.querySelector('track');
            expect(track.srclang).toBe('en');
        });

        it('should generate label when not provided', () => {
            const video = document.createElement('video');
            const subtitles = [
                { url: '/subs/track1.vtt' },
                { url: '/subs/track2.vtt' }
            ];

            addSubtitleTracks(video, subtitles);

            const tracks = video.querySelectorAll('track');
            expect(tracks[0].label).toBe('Track 1');
            expect(tracks[1].label).toBe('Track 2');
        });

        it('should handle empty subtitles array', () => {
            const video = document.createElement('video');

            addSubtitleTracks(video, []);

            expect(video.querySelectorAll('track').length).toBe(0);
        });

        it('should handle null/undefined subtitles', () => {
            const video = document.createElement('video');

            expect(() => addSubtitleTracks(video, null)).not.toThrow();
            expect(() => addSubtitleTracks(video, undefined)).not.toThrow();
        });

        it('should handle non-video elements gracefully', () => {
            const div = document.createElement('div');
            const subtitles = [
                { label: 'English', url: '/subs/en.vtt' }
            ];

            expect(() => addSubtitleTracks(div, subtitles)).not.toThrow();
        });

        it('should set track kind to "subtitles"', () => {
            const video = document.createElement('video');
            const subtitles = [
                { label: 'English', url: '/subs/en.vtt' }
            ];

            addSubtitleTracks(video, subtitles);

            const track = video.querySelector('track');
            expect(track.kind).toBe('subtitles');
        });
    });

    describe('loadSubtitlesForVideo', () => {
        it('should fetch and add subtitles to video', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([
                    { label: 'English', url: '/subs/en.vtt', language: 'en' }
                ])
            }));

            const video = document.createElement('video');
            const result = await loadSubtitlesForVideo(video, '/media/movies/test.mp4');

            expect(result).toBe(true);
            expect(video.querySelectorAll('track').length).toBe(1);
        });

        it('should return false when subtitles disabled', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(false);
            const video = document.createElement('video');

            const result = await loadSubtitlesForVideo(video, '/media/movies/test.mp4');

            expect(result).toBe(false);
        });

        it('should return false when no subtitles available', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([])
            }));

            const video = document.createElement('video');
            const result = await loadSubtitlesForVideo(video, '/media/movies/test.mp4');

            expect(result).toBe(false);
        });

        it('should return false for invalid video element', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);

            const result1 = await loadSubtitlesForVideo(null, '/media/movies/test.mp4');
            const result2 = await loadSubtitlesForVideo(document.createElement('div'), '/media/movies/test.mp4');

            expect(result1).toBe(false);
            expect(result2).toBe(false);
        });

        it('should return false when videoUrl is missing', async () => {
            vi.mocked(getConfigValue).mockReturnValueOnce(true);
            const video = document.createElement('video');

            const result = await loadSubtitlesForVideo(video, null);

            expect(result).toBe(false);
        });

        it('should handle errors gracefully', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));

            const video = document.createElement('video');
            const result = await loadSubtitlesForVideo(video, '/media/movies/test.mp4');

            expect(result).toBe(false);
        });
    });

    describe('clearSubtitleCache', () => {
        it('should clear all cached subtitles', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([
                    { label: 'English', url: '/subs/en.vtt' }
                ])
            }));

            // Cache some subtitles
            await fetchSubtitles('/media/movies/test1.mp4');
            await fetchSubtitles('/media/movies/test2.mp4');

            expect(getCacheSize()).toBe(2);

            clearSubtitleCache();

            expect(getCacheSize()).toBe(0);
        });

        it('should not throw when cache is already empty', () => {
            expect(() => clearSubtitleCache()).not.toThrow();
            expect(getCacheSize()).toBe(0);
        });
    });

    describe('getCacheSize', () => {
        it('should return 0 for empty cache', () => {
            expect(getCacheSize()).toBe(0);
        });

        it('should return correct count after caching', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([
                    { label: 'English', url: '/subs/en.vtt' }
                ])
            }));

            await fetchSubtitles('/media/movies/test1.mp4');
            expect(getCacheSize()).toBe(1);

            await fetchSubtitles('/media/movies/test2.mp4');
            expect(getCacheSize()).toBe(2);

            await fetchSubtitles('/media/movies/test3.mp4');
            expect(getCacheSize()).toBe(3);
        });

        it('should not count duplicate entries', async () => {
            vi.mocked(getConfigValue).mockReturnValue(true);
            global.fetch = vi.fn(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve([
                    { label: 'English', url: '/subs/en.vtt' }
                ])
            }));

            await fetchSubtitles('/media/movies/test.mp4');
            await fetchSubtitles('/media/movies/test.mp4');
            await fetchSubtitles('/media/movies/test.mp4');

            expect(getCacheSize()).toBe(1);
        });
    });
});
