/**
 * CacheManager Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the core/app module before importing cacheManager
vi.mock('../../core/app.js', () => ({
  MAX_CACHE_SIZE: 5,
  MOBILE_DEVICE: false,
  MOBILE_CLEANUP_INTERVAL: 60000,
  app: {
    mediaCache: new Map(),
    state: {
      lastCleanupTime: 0
    }
  }
}));

import * as cacheManager from '../../utils/cacheManager.js';
import { app, MAX_CACHE_SIZE, MOBILE_DEVICE, MOBILE_CLEANUP_INTERVAL } from '../../core/app.js';

describe('CacheManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    app.mediaCache.clear();
    app.state.lastCleanupTime = 0;
    window.ragotModules = {
      appCache: app.mediaCache,
      appState: app.state,
      appRuntime: {
        MAX_CACHE_SIZE,
        MOBILE_DEVICE,
        MOBILE_CLEANUP_INTERVAL
      }
    };
  });

  describe('addToCache', () => {
    it('should add element to cache', () => {
      const element = document.createElement('img');
      element.src = 'test.jpg';
      
      cacheManager.addToCache('test-key', element);
      
      expect(app.mediaCache.has('test-key')).toBe(true);
    });

    it('should store the same element reference', () => {
      const element = document.createElement('img');
      element.src = 'test.jpg';
      element.id = 'original';
      
      cacheManager.addToCache('test-key', element);
      
      const cached = app.mediaCache.get('test-key');
      expect(cached).toBe(element);
      expect(cached.src).toContain('test.jpg');
    });

    it('should not add null/undefined elements', () => {
      cacheManager.addToCache('null-key', null);
      cacheManager.addToCache('undefined-key', undefined);
      
      expect(app.mediaCache.has('null-key')).toBe(false);
      expect(app.mediaCache.has('undefined-key')).toBe(false);
    });

    it('should not add with null/undefined key', () => {
      const element = document.createElement('div');
      
      cacheManager.addToCache(null, element);
      cacheManager.addToCache(undefined, element);
      
      expect(app.mediaCache.size).toBe(0);
    });

    it('should prune cache when exceeding max size', () => {
      for (let i = 0; i < MAX_CACHE_SIZE + 3; i++) {
        const element = document.createElement('div');
        cacheManager.addToCache(`key-${i}`, element);
      }
      
      expect(app.mediaCache.size).toBeLessThanOrEqual(MAX_CACHE_SIZE);
    });
  });

  describe('getFromCache', () => {
    it('should return cached element from cache', () => {
      const element = document.createElement('video');
      element.id = 'test-video';
      cacheManager.addToCache('video-key', element);
      
      const retrieved = cacheManager.getFromCache('video-key');
      
      expect(retrieved).toBe(element);
      expect(retrieved.tagName).toBe('VIDEO');
    });

    it('should return null for missing key', () => {
      expect(cacheManager.getFromCache('nonexistent')).toBeNull();
    });

    it('should return null for null/undefined key', () => {
      expect(cacheManager.getFromCache(null)).toBeNull();
      expect(cacheManager.getFromCache(undefined)).toBeNull();
    });
  });

  describe('hasInCache', () => {
    it('should return true for existing key', () => {
      const element = document.createElement('div');
      cacheManager.addToCache('exists', element);
      
      expect(cacheManager.hasInCache('exists')).toBe(true);
    });

    it('should return false for missing key', () => {
      expect(cacheManager.hasInCache('missing')).toBe(false);
    });

    it('should return falsy for null/undefined', () => {
      expect(cacheManager.hasInCache(null)).toBeFalsy();
      expect(cacheManager.hasInCache(undefined)).toBeFalsy();
    });
  });

  describe('pruneCache', () => {
    it('should remove oldest entries when over limit', () => {
      // Add more than MAX_CACHE_SIZE items
      for (let i = 0; i < 10; i++) {
        app.mediaCache.set(`key-${i}`, document.createElement('div'));
      }
      
      cacheManager.pruneCache();
      
      expect(app.mediaCache.size).toBe(MAX_CACHE_SIZE);
    });

    it('should keep most recent entries', () => {
      for (let i = 0; i < 10; i++) {
        app.mediaCache.set(`key-${i}`, document.createElement('div'));
      }
      
      cacheManager.pruneCache();
      
      // Most recent entries should remain
      expect(app.mediaCache.has(`key-${10 - MAX_CACHE_SIZE}`)).toBe(true);
    });
  });

  describe('clearCache', () => {
    it('should empty the entire cache', () => {
      for (let i = 0; i < 5; i++) {
        app.mediaCache.set(`key-${i}`, document.createElement('div'));
      }
      
      cacheManager.clearCache();
      
      expect(app.mediaCache.size).toBe(0);
    });
  });

  describe('performCacheCleanup', () => {
    it('should clear cache when forced', () => {
      app.mediaCache.set('test', document.createElement('div'));
      
      cacheManager.performCacheCleanup(true);
      
      expect(app.mediaCache.size).toBe(0);
    });

    it('should update lastCleanupTime', () => {
      const before = app.state.lastCleanupTime;
      
      cacheManager.performCacheCleanup(true);
      
      expect(app.state.lastCleanupTime).toBeGreaterThan(before);
    });

    it('should not clean up if interval not reached', () => {
      app.state.lastCleanupTime = Date.now();
      app.mediaCache.set('test', document.createElement('div'));
      
      cacheManager.performCacheCleanup(false);
      
      // Should not clear since interval not reached
      expect(app.mediaCache.has('test')).toBe(true);
    });

    it('should handle detached video elements', () => {
      const video = document.createElement('video');
      video.pause = vi.fn();
      document.body.appendChild(video);
      
      cacheManager.performCacheCleanup(true);
      
      // Should not throw
      expect(true).toBe(true);
      
      document.body.removeChild(video);
    });
  });
});


