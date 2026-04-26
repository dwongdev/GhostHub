/**
 * Tests for subfolderUtils module
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
    isSubfolderFile,
    getSubfolderName,
    extractSubfolders,
    getSubfoldersFromResponse,
    filterDirectFiles,
    processMediaWithSubfolders,
    formatSubfolderName
} from '../../utils/subfolderUtils.js';

describe('subfolderUtils', () => {
    describe('isSubfolderFile', () => {
        it('returns true for file in subfolder', () => {
            const file = { name: 'folder/video.mp4' };
            expect(isSubfolderFile(file)).toBe(true);
        });

        it('returns false for direct file', () => {
            const file = { name: 'video.mp4' };
            expect(isSubfolderFile(file)).toBe(false);
        });

        it('returns false for null input', () => {
            expect(isSubfolderFile(null)).toBe(false);
        });

        it('returns false for undefined input', () => {
            expect(isSubfolderFile(undefined)).toBe(false);
        });

        it('prefers displayName over name', () => {
            const file = { name: 'root/file.mp4', displayName: 'subfolder/video.mp4' };
            expect(isSubfolderFile(file)).toBe(true);
        });
    });

    describe('getSubfolderName', () => {
        it('extracts immediate subfolder name', () => {
            const file = { name: 'monster/deep/file.mp4' };
            expect(getSubfolderName(file)).toBe('monster');
        });

        it('prefers displayName when available', () => {
            const file = { name: 'root/file.mp4', displayName: 'nested/clip.mp4' };
            expect(getSubfolderName(file)).toBe('nested');
        });

        it('returns null for direct file', () => {
            const file = { name: 'video.mp4' };
            expect(getSubfolderName(file)).toBe(null);
        });

        it('handles null file', () => {
            expect(getSubfolderName(null)).toBe(null);
        });

        it('handles missing name property', () => {
            expect(getSubfolderName({})).toBe(null);
        });
    });

    describe('extractSubfolders', () => {
        it('extracts unique subfolders with counts', () => {
            const mediaItems = [
                { name: 'folder1/video1.mp4', type: 'video', url: '/media/1/f1/v1.mp4', thumbnailUrl: '/thumb/1' },
                { name: 'folder1/video2.mp4', type: 'video', url: '/media/1/f1/v2.mp4' },
                { name: 'folder2/image1.jpg', type: 'image', url: '/media/1/f2/i1.jpg' },
                { name: 'video.mp4', type: 'video', url: '/media/1/v.mp4' },
            ];
            const result = extractSubfolders(mediaItems, '1');

            expect(result).toHaveLength(2);

            const folder1 = result.find(f => f.name === 'folder1');
            expect(folder1.count).toBe(2);
            expect(folder1.containsVideo).toBe(true);

            const folder2 = result.find(f => f.name === 'folder2');
            expect(folder2.count).toBe(1);
            expect(folder2.containsVideo).toBe(false);
        });

        it('uses video thumbnail for folder with only videos', () => {
            const mediaItems = [
                { name: 'folder/video.mp4', type: 'video', url: '/media/1/v.mp4', thumbnailUrl: '/thumb/v' },
            ];
            const result = extractSubfolders(mediaItems, '1');

            expect(result[0].thumbnailUrl).toBe('/thumb/v');
        });

        it('falls back to image URL for thumbnail', () => {
            const mediaItems = [
                { name: 'folder/image.jpg', type: 'image', url: '/media/1/i.jpg' },
            ];
            const result = extractSubfolders(mediaItems, '1');

            expect(result[0].thumbnailUrl).toBe('/media/1/i.jpg');
        });

        it('handles empty array', () => {
            expect(extractSubfolders([], '1')).toEqual([]);
        });

        it('handles null input', () => {
            expect(extractSubfolders(null, '1')).toEqual([]);
        });

        it('includes categoryId in results', () => {
            const mediaItems = [
                { name: 'folder/video.mp4', type: 'video', url: '/media/5/v.mp4' },
            ];
            const result = extractSubfolders(mediaItems, '5');

            expect(result[0].categoryId).toBe('5');
        });
    });

    describe('getSubfoldersFromResponse', () => {
        it('prefers server-provided subfolders', () => {
            const apiResponse = {
                subfolders: [
                    { name: 'serverFolder', count: 5, contains_video: true, thumbnail_url: '/thumb' }
                ],
                files: []
            };
            const result = getSubfoldersFromResponse(apiResponse, '1');

            expect(result).toHaveLength(1);
            expect(result[0].name).toBe('serverFolder');
            expect(result[0].containsVideo).toBe(true);
        });

        it('falls back to extracting from files', () => {
            const apiResponse = {
                files: [
                    { name: 'folder/video.mp4', type: 'video', url: '/media/1/v.mp4' }
                ]
            };
            const result = getSubfoldersFromResponse(apiResponse, '1');

            expect(result).toHaveLength(1);
            expect(result[0].name).toBe('folder');
        });

        it('returns empty array for empty response', () => {
            expect(getSubfoldersFromResponse({}, '1')).toEqual([]);
        });

        it('returns empty array for null response', () => {
            expect(getSubfoldersFromResponse(null, '1')).toEqual([]);
        });
    });

    describe('filterDirectFiles', () => {
        it('filters out subfolder files', () => {
            const mediaItems = [
                { name: 'folder/video.mp4', type: 'video' },
                { name: 'video.mp4', type: 'video' },
                { name: 'another/video.mp4', type: 'video' },
            ];
            const result = filterDirectFiles(mediaItems);

            expect(result).toHaveLength(1);
            expect(result[0].name).toBe('video.mp4');
        });

        it('handles empty array', () => {
            expect(filterDirectFiles([])).toEqual([]);
        });

        it('handles null input', () => {
            expect(filterDirectFiles(null)).toEqual([]);
        });
    });

    describe('processMediaWithSubfolders', () => {
        it('replaces subfolder files with marker entries', () => {
            const mediaItems = [
                { name: 'folder/video.mp4', type: 'video', url: '/media/1/v.mp4' },
                { name: 'folder/image.jpg', type: 'image', url: '/media/1/i.jpg' },
                { name: 'direct.mp4', type: 'video', url: '/media/1/d.mp4' },
            ];
            const result = processMediaWithSubfolders(mediaItems, '1');

            expect(result.items).toHaveLength(2);
            expect(result.items[0].name).toBe('folder');
            expect(result.items[0].type).toBe('subfolder');
            expect(result.items[1].name).toBe('direct.mp4');
        });

        it('creates subfolder markers with correct metadata', () => {
            const mediaItems = [
                { name: 'folder/video.mp4', type: 'video', url: '/media/1/v.mp4', thumbnailUrl: '/thumb' },
            ];
            const result = processMediaWithSubfolders(mediaItems, '1');

            expect(result.subfolders[0].containsVideo).toBe(true);
            expect(result.subfolders[0].count).toBe(1);
        });

        it('handles empty media items with subfolders', () => {
            const subfolders = [
                { name: 'folder', count: 5, containsVideo: true, thumbnailUrl: '/thumb' }
            ];
            const result = processMediaWithSubfolders([], '1', subfolders);

            expect(result.items).toHaveLength(1);
            expect(result.items[0].type).toBe('subfolder');
        });

        it('returns original items when no subfolders', () => {
            const mediaItems = [
                { name: 'video.mp4', type: 'video', url: '/media/1/v.mp4' },
            ];
            const result = processMediaWithSubfolders(mediaItems, '1', []);

            expect(result.items).toBe(mediaItems);
        });
    });

    describe('formatSubfolderName', () => {
        it('capitalizes first letter', () => {
            expect(formatSubfolderName('folder')).toBe('Folder');
        });

        it('replaces hyphens with spaces', () => {
            expect(formatSubfolderName('my-folder')).toBe('My Folder');
        });

        it('replaces underscores with spaces', () => {
            expect(formatSubfolderName('my_folder')).toBe('My Folder');
        });

        it('handles null input', () => {
            expect(formatSubfolderName(null)).toBe('');
        });

        it('handles empty string', () => {
            expect(formatSubfolderName('')).toBe('');
        });

        it('handles complex names', () => {
            expect(formatSubfolderName('my-folder_name')).toBe('My Folder Name');
        });
    });
});
