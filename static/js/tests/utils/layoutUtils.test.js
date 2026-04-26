/**
 * LayoutUtils Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the progressDB module before importing layoutUtils
vi.mock('../../utils/progressDB.js', () => ({
  isUserAdmin: vi.fn(() => false),
  getAllVideoLocalProgress: vi.fn(() => []),
  isProgressDBReady: vi.fn(() => true),
  initProgressDB: vi.fn(() => Promise.resolve())
}));

// Import after mocking
import * as layoutUtils from '../../utils/layoutUtils.js';
import * as progressDB from '../../utils/progressDB.js';

describe('LayoutUtils', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.removeAttribute('data-layout');
    window.ragotModules.appStore.set('activeProfileId', null);
  });

  describe('escapeHtml', () => {
    it('should escape HTML special characters', () => {
      expect(layoutUtils.escapeHtml('<script>alert("xss")</script>')).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
    });

    it('should handle ampersands', () => {
      expect(layoutUtils.escapeHtml('A & B')).toBe('A &amp; B');
    });

    it('should return empty string for null/undefined', () => {
      expect(layoutUtils.escapeHtml(null)).toBe('');
      expect(layoutUtils.escapeHtml(undefined)).toBe('');
    });

    it('should handle normal strings', () => {
      expect(layoutUtils.escapeHtml('Hello World')).toBe('Hello World');
    });
  });

  describe('formatTime', () => {
    it('should format seconds to mm:ss', () => {
      expect(layoutUtils.formatTime(125)).toBe('2:05');
      expect(layoutUtils.formatTime(65)).toBe('1:05');
      expect(layoutUtils.formatTime(30)).toBe('0:30');
    });

    it('should format hours correctly', () => {
      expect(layoutUtils.formatTime(3661)).toBe('1:01:01');
      expect(layoutUtils.formatTime(7200)).toBe('2:00:00');
    });

    it('should handle zero and negative', () => {
      expect(layoutUtils.formatTime(0)).toBe('');
      expect(layoutUtils.formatTime(-10)).toBe('');
    });

    it('should handle null/undefined', () => {
      expect(layoutUtils.formatTime(null)).toBe('');
      expect(layoutUtils.formatTime(undefined)).toBe('');
    });
  });

  describe('getDateKey', () => {
    it('should convert Unix timestamp to date key', () => {
      const timestamp = 1702310400; // Dec 11, 2023 UTC
      const result = layoutUtils.getDateKey(timestamp);
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('should return Unknown for null/undefined', () => {
      expect(layoutUtils.getDateKey(null)).toBe('Unknown');
      expect(layoutUtils.getDateKey(undefined)).toBe('Unknown');
    });

    it('should handle invalid timestamps', () => {
      expect(layoutUtils.getDateKey('invalid')).toBe('Unknown');
    });
  });

  describe('formatDateDisplay', () => {
    it('should show "Today" for today\'s date', () => {
      // Use local date format to avoid timezone issues
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      const dateKey = `${year}-${month}-${day}`;
      expect(layoutUtils.formatDateDisplay(dateKey)).toBe('Today');
    });

    it('should show "Yesterday" for yesterday\'s date', () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      // Use local date format to avoid timezone issues
      const year = yesterday.getFullYear();
      const month = String(yesterday.getMonth() + 1).padStart(2, '0');
      const day = String(yesterday.getDate()).padStart(2, '0');
      const dateKey = `${year}-${month}-${day}`;
      expect(layoutUtils.formatDateDisplay(dateKey)).toBe('Yesterday');
    });

    it('should format Unknown date key', () => {
      expect(layoutUtils.formatDateDisplay('Unknown')).toBe('Unknown Date');
    });
  });

  describe('extractTitle', () => {
    it('should extract title from URL', () => {
      expect(layoutUtils.extractTitle('/media/category/my_video.mp4')).toBe('my video');
    });

    it('should remove file extension', () => {
      expect(layoutUtils.extractTitle('document.pdf')).toBe('document');
    });

    it('should replace underscores with spaces', () => {
      expect(layoutUtils.extractTitle('my_cool_file.txt')).toBe('my cool file');
    });

    it('should handle null/undefined', () => {
      expect(layoutUtils.extractTitle(null)).toBe('Untitled');
      expect(layoutUtils.extractTitle(undefined)).toBe('Untitled');
    });

    it('should decode URL-encoded characters', () => {
      expect(layoutUtils.extractTitle('/path/hello%20world.mp4')).toBe('hello world');
    });
  });

  describe('calculateProgress', () => {
    it('should calculate percentage correctly', () => {
      expect(layoutUtils.calculateProgress(50, 100)).toBe(50);
      expect(layoutUtils.calculateProgress(25, 100)).toBe(25);
    });

    it('should cap at 100%', () => {
      expect(layoutUtils.calculateProgress(150, 100)).toBe(100);
    });

    it('should return 0 for zero/invalid total', () => {
      expect(layoutUtils.calculateProgress(50, 0)).toBe(0);
      expect(layoutUtils.calculateProgress(50, null)).toBe(0);
      expect(layoutUtils.calculateProgress(50, -10)).toBe(0);
    });
  });

  describe('isVideo', () => {
    it('should detect video MIME types', () => {
      expect(layoutUtils.isVideo('video/mp4', '')).toBe(true);
      expect(layoutUtils.isVideo('video/webm', '')).toBe(true);
    });

    it('should detect video by type string', () => {
      expect(layoutUtils.isVideo('video', '')).toBe(true);
    });

    it('should detect video by file extension', () => {
      expect(layoutUtils.isVideo(null, 'movie.mp4')).toBe(true);
      expect(layoutUtils.isVideo(null, 'clip.webm')).toBe(true);
      expect(layoutUtils.isVideo(null, 'video.mkv')).toBe(true);
    });

    it('should return false for non-videos', () => {
      expect(layoutUtils.isVideo('image/png', 'photo.png')).toBe(false);
      expect(layoutUtils.isVideo(null, 'document.pdf')).toBe(false);
    });
  });

  describe('isImage', () => {
    it('should detect image MIME types', () => {
      expect(layoutUtils.isImage('image/png', '')).toBe(true);
      expect(layoutUtils.isImage('image/jpeg', '')).toBe(true);
    });

    it('should detect image by type string', () => {
      expect(layoutUtils.isImage('image', '')).toBe(true);
    });

    it('should detect image by file extension', () => {
      expect(layoutUtils.isImage(null, 'photo.jpg')).toBe(true);
      expect(layoutUtils.isImage(null, 'picture.png')).toBe(true);
      expect(layoutUtils.isImage(null, 'graphic.webp')).toBe(true);
    });

    it('should return false for non-images', () => {
      expect(layoutUtils.isImage('video/mp4', 'movie.mp4')).toBe(false);
    });
  });

  describe('buildProgressMap', () => {
    it('should build map from video progress array', () => {
      const videos = [
        { video_url: '/video1.mp4', video_timestamp: 100, video_duration: 300 },
        { video_path: '/video2.mp4', video_timestamp: 200, video_duration: 600 }
      ];

      const map = layoutUtils.buildProgressMap(videos);

      expect(map['/video1.mp4']).toEqual({ video_timestamp: 100, video_duration: 300 });
      expect(map['/video2.mp4']).toEqual({ video_timestamp: 200, video_duration: 600 });
    });

    it('should skip entries with no timestamp', () => {
      const videos = [
        { video_url: '/video1.mp4', video_timestamp: 0, video_duration: 300 },
        { video_url: '/video2.mp4', video_timestamp: null, video_duration: 300 }
      ];

      const map = layoutUtils.buildProgressMap(videos);

      expect(Object.keys(map).length).toBe(0);
    });
  });

  describe('getCurrentLayout', () => {
    it('should return streaming when no attribute set', () => {
      expect(layoutUtils.getCurrentLayout()).toBe('streaming');
    });

    it('should return layout from data attribute', () => {
      document.documentElement.setAttribute('data-layout', 'streaming');
      expect(layoutUtils.getCurrentLayout()).toBe('streaming');
    });
  });

  describe('registerLayoutHandler', () => {
    it('should register handlers for valid layouts', () => {
      const handler = { viewMedia: vi.fn() };

      // Should not throw
      layoutUtils.registerLayoutHandler('streaming', handler);
      layoutUtils.registerLayoutHandler('gallery', handler);
    });
  });

  describe('fetchVideoProgressData', () => {
    it('should fetch from server when an active profile exists', async () => {
      window.ragotModules.appStore.set('activeProfileId', 'profile-1');

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ videos: [{ video_url: '/test.mp4', video_timestamp: 100 }] })
      });

      const videos = await layoutUtils.fetchVideoProgressData();

      expect(fetch).toHaveBeenCalledWith('/api/progress/videos?limit=500', { headers: expect.any(Object) });
      expect(videos).toHaveLength(1);
    });

    it('should use IndexedDB when no active profile exists', async () => {
      window.ragotModules.appStore.set('activeProfileId', null);
      vi.mocked(progressDB.getAllVideoLocalProgress).mockReturnValue([
        { video_url: '/local.mp4', video_timestamp: 50 }
      ]);

      const videos = await layoutUtils.fetchVideoProgressData();

      expect(progressDB.getAllVideoLocalProgress).toHaveBeenCalled();
      expect(videos).toHaveLength(1);
    });
  });
});
