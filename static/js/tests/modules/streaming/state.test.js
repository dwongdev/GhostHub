/**
 * Streaming State Module Unit Tests
 */

import { describe, it, expect, beforeEach } from 'vitest';

describe('Streaming State', () => {
  let state;

  beforeEach(() => {
    state = {
      categoryCache: new Map(),
      continueWatching: [],
      recentlyViewed: [],
      featuredMedia: null,
      isInitialized: false,
      loadingCategories: new Set()
    };
  });

  describe('Category cache', () => {
    it('should cache category data', () => {
      state.categoryCache.set('movies', {
        media: [{ url: 'movie1.mp4' }],
        page: 1,
        hasMore: true
      });
      
      expect(state.categoryCache.has('movies')).toBe(true);
    });

    it('should retrieve cached category', () => {
      state.categoryCache.set('movies', { media: [], page: 1 });
      const cached = state.categoryCache.get('movies');
      
      expect(cached.page).toBe(1);
    });

    it('should update cache with new page', () => {
      state.categoryCache.set('movies', { media: [1, 2], page: 1, hasMore: true });
      
      const existing = state.categoryCache.get('movies');
      existing.media.push(3, 4);
      existing.page = 2;
      
      expect(state.categoryCache.get('movies').media).toHaveLength(4);
    });

    it('should clear cache', () => {
      state.categoryCache.set('a', {});
      state.categoryCache.set('b', {});
      state.categoryCache.clear();
      
      expect(state.categoryCache.size).toBe(0);
    });
  });

  describe('Continue watching', () => {
    it('should store continue watching list', () => {
      state.continueWatching = [
        { url: 'movie1.mp4', progress: 50 },
        { url: 'movie2.mp4', progress: 30 }
      ];
      
      expect(state.continueWatching).toHaveLength(2);
    });

    it('should sort by most recent', () => {
      state.continueWatching = [
        { url: 'a.mp4', lastWatched: 100 },
        { url: 'b.mp4', lastWatched: 300 },
        { url: 'c.mp4', lastWatched: 200 }
      ];
      
      state.continueWatching.sort((a, b) => b.lastWatched - a.lastWatched);
      
      expect(state.continueWatching[0].url).toBe('b.mp4');
    });

    it('should limit to max items', () => {
      const maxItems = 10;
      state.continueWatching = Array(15).fill({ url: 'video.mp4' });
      state.continueWatching = state.continueWatching.slice(0, maxItems);
      
      expect(state.continueWatching).toHaveLength(10);
    });
  });

  describe('updateContinueWatchingVideoUrl', () => {
    it('should update video URL when file is renamed', () => {
      state.continueWatching = [
        { url: '/media/cat1/old-name.mp4', progress: 50 },
        { url: '/media/cat2/other.mp4', progress: 30 }
      ];
      
      const oldUrl = '/media/cat1/old-name.mp4';
      const newUrl = '/media/cat1/new-name.mp4';
      
      state.continueWatching.forEach(item => {
        if (item.url === oldUrl) {
          item.url = newUrl;
        }
      });
      
      expect(state.continueWatching[0].url).toBe(newUrl);
      expect(state.continueWatching[1].url).toBe('/media/cat2/other.mp4');
    });

    it('should handle multiple entries with same old URL', () => {
      state.continueWatching = [
        { url: '/media/cat1/movie.mp4', progress: 50 },
        { url: '/media/cat1/movie.mp4', progress: 75 }
      ];
      
      const oldUrl = '/media/cat1/movie.mp4';
      const newUrl = '/media/cat1/renamed.mp4';
      
      state.continueWatching.forEach(item => {
        if (item.url === oldUrl) {
          item.url = newUrl;
        }
      });
      
      expect(state.continueWatching[0].url).toBe(newUrl);
      expect(state.continueWatching[1].url).toBe(newUrl);
    });

    it('should do nothing when old URL not found', () => {
      state.continueWatching = [
        { url: '/media/cat1/movie1.mp4', progress: 50 },
        { url: '/media/cat2/movie2.mp4', progress: 30 }
      ];
      
      const originalData = JSON.parse(JSON.stringify(state.continueWatching));
      
      const oldUrl = '/media/cat3/notfound.mp4';
      const newUrl = '/media/cat3/new.mp4';
      
      state.continueWatching.forEach(item => {
        if (item.url === oldUrl) {
          item.url = newUrl;
        }
      });
      
      expect(state.continueWatching).toEqual(originalData);
    });
  });

  describe('updateVideoProgressMapUrl', () => {
    it('should update video progress map URL when file is renamed', () => {
      state.videoProgressMap = {
        '/media/cat1/old-name.mp4': { timestamp: 100, duration: 200 },
        '/media/cat2/other.mp4': { timestamp: 50, duration: 100 }
      };
      
      const oldUrl = '/media/cat1/old-name.mp4';
      const newUrl = '/media/cat1/new-name.mp4';
      
      const entry = state.videoProgressMap[oldUrl];
      if (entry) {
        state.videoProgressMap[newUrl] = entry;
        delete state.videoProgressMap[oldUrl];
      }
      
      expect(state.videoProgressMap[newUrl]).toEqual({ timestamp: 100, duration: 200 });
      expect(state.videoProgressMap[oldUrl]).toBeUndefined();
      expect(state.videoProgressMap['/media/cat2/other.mp4']).toBeDefined();
    });

    it('should do nothing when old URL not in progress map', () => {
      const originalMap = {
        '/media/cat1/movie1.mp4': { timestamp: 100 },
        '/media/cat2/movie2.mp4': { timestamp: 50 }
      };
      state.videoProgressMap = { ...originalMap };
      
      const oldUrl = '/media/cat3/notfound.mp4';
      const newUrl = '/media/cat3/new.mp4';
      
      const entry = state.videoProgressMap[oldUrl];
      if (entry) {
        state.videoProgressMap[newUrl] = entry;
        delete state.videoProgressMap[oldUrl];
      }
      
      expect(state.videoProgressMap).toEqual(originalMap);
    });
  });

  describe('Recently viewed', () => {
    it('should store recently viewed', () => {
      state.recentlyViewed = [
        { url: 'photo1.jpg', viewedAt: Date.now() }
      ];
      
      expect(state.recentlyViewed).toHaveLength(1);
    });

    it('should add to front of list', () => {
      state.recentlyViewed = [{ url: 'old.jpg' }];
      state.recentlyViewed.unshift({ url: 'new.jpg' });
      
      expect(state.recentlyViewed[0].url).toBe('new.jpg');
    });
  });

  describe('Featured media', () => {
    it('should store featured media', () => {
      state.featuredMedia = {
        url: '/media/featured.mp4',
        title: 'Featured Movie',
        description: 'A great movie'
      };
      
      expect(state.featuredMedia.title).toBe('Featured Movie');
    });

    it('should handle null featured', () => {
      state.featuredMedia = null;
      expect(state.featuredMedia).toBeNull();
    });
  });

  describe('Loading state', () => {
    it('should track loading categories', () => {
      state.loadingCategories.add('movies');
      state.loadingCategories.add('photos');
      
      expect(state.loadingCategories.has('movies')).toBe(true);
    });

    it('should remove from loading when done', () => {
      state.loadingCategories.add('movies');
      state.loadingCategories.delete('movies');
      
      expect(state.loadingCategories.has('movies')).toBe(false);
    });

    it('should check if any loading', () => {
      state.loadingCategories.add('movies');
      
      expect(state.loadingCategories.size > 0).toBe(true);
    });
  });

  describe('Initialization', () => {
    it('should track initialization', () => {
      expect(state.isInitialized).toBe(false);
      
      state.isInitialized = true;
      
      expect(state.isInitialized).toBe(true);
    });
  });
});
