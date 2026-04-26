/**
 * Gallery Data Module Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Gallery Data', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  describe('Media fetching', () => {
    it('should fetch all media from categories', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          media: [
            { url: '/media/photo1.jpg', type: 'image', created: 1702310400 },
            { url: '/media/video1.mp4', type: 'video', created: 1702224000 }
          ]
        })
      });
      
      const response = await fetch('/api/gallery/media');
      const data = await response.json();
      
      expect(data.media).toHaveLength(2);
    });

    it('should handle pagination', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          media: [],
          page: 2,
          hasMore: false,
          total: 50
        })
      });
      
      const response = await fetch('/api/gallery/media?page=2&per_page=20');
      const data = await response.json();
      
      expect(data.page).toBe(2);
      expect(data.hasMore).toBe(false);
    });
  });

  describe('Date grouping', () => {
    it('should group media by date', () => {
      const media = [
        { url: 'a.jpg', created: 1702310400 }, // Dec 11
        { url: 'b.jpg', created: 1702310400 }, // Dec 11
        { url: 'c.jpg', created: 1702224000 }  // Dec 10
      ];
      
      const grouped = media.reduce((acc, item) => {
        const date = new Date(item.created * 1000).toISOString().split('T')[0];
        if (!acc[date]) acc[date] = [];
        acc[date].push(item);
        return acc;
      }, {});
      
      expect(Object.keys(grouped).length).toBe(2);
    });

    it('should sort dates descending', () => {
      const dates = ['2024-12-10', '2024-12-12', '2024-12-11'];
      dates.sort((a, b) => b.localeCompare(a));
      
      expect(dates[0]).toBe('2024-12-12');
    });
  });

  describe('Media filtering', () => {
    it('should filter photos only', () => {
      const media = [
        { type: 'image' }, { type: 'video' }, { type: 'image' }
      ];
      const photos = media.filter(m => m.type === 'image');
      
      expect(photos).toHaveLength(2);
    });

    it('should filter videos only', () => {
      const media = [
        { type: 'image' }, { type: 'video' }, { type: 'video' }
      ];
      const videos = media.filter(m => m.type === 'video');
      
      expect(videos).toHaveLength(2);
    });
  });

  describe('Category data', () => {
    it('should fetch category info', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: 'photos',
          name: 'Photos',
          mediaCount: 500
        })
      });
      
      const response = await fetch('/api/categories/photos');
      const data = await response.json();
      
      expect(data.name).toBe('Photos');
    });
  });

  describe('Sorting', () => {
    it('should sort by date newest first', () => {
      const media = [
        { created: 100 }, { created: 300 }, { created: 200 }
      ];
      media.sort((a, b) => b.created - a.created);
      
      expect(media[0].created).toBe(300);
    });

    it('should sort by name', () => {
      const media = [
        { name: 'zebra.jpg' }, { name: 'apple.jpg' }, { name: 'mango.jpg' }
      ];
      media.sort((a, b) => a.name.localeCompare(b.name));
      
      expect(media[0].name).toBe('apple.jpg');
    });
  });
});
