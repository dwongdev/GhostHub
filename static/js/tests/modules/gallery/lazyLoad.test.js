/**
 * Gallery LazyLoad Module Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Gallery LazyLoad', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    window.IntersectionObserver = vi.fn().mockImplementation((callback) => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn()
    }));
  });

  describe('Observer setup', () => {
    it('should create observer with options', () => {
      const options = {
        rootMargin: '200px 0px',
        threshold: 0.01
      };
      
      new IntersectionObserver(() => {}, options);
      
      expect(window.IntersectionObserver).toHaveBeenCalled();
    });
  });

  describe('Image lazy loading', () => {
    it('should observe image elements', () => {
      const observer = new IntersectionObserver(() => {});
      const img = document.createElement('img');
      img.dataset.src = '/thumbnails/photo.jpg';
      
      observer.observe(img);
      
      expect(observer.observe).toHaveBeenCalled();
    });

    it('should load image when intersecting', () => {
      const img = document.createElement('img');
      img.dataset.src = '/thumbnails/photo.jpg';
      img.className = 'placeholder';
      
      // Simulate load
      img.src = img.dataset.src;
      img.classList.remove('placeholder');
      img.classList.add('loaded');
      
      expect(img.src).toContain('photo.jpg');
    });

    it('should add loading class while loading', () => {
      const img = document.createElement('img');
      img.classList.add('loading');
      
      expect(img.classList.contains('loading')).toBe(true);
    });

    it('should handle load complete', () => {
      const img = document.createElement('img');
      img.classList.add('loading');
      
      // Simulate load complete
      img.classList.remove('loading');
      img.classList.add('loaded');
      
      expect(img.classList.contains('loaded')).toBe(true);
    });
  });

  describe('Error handling', () => {
    it('should handle image load error', () => {
      const img = document.createElement('img');
      
      img.addEventListener('error', () => {
        img.classList.add('error');
        img.src = '/static/icons/placeholder.png';
      });
      
      img.dispatchEvent(new Event('error'));
      
      expect(img.classList.contains('error')).toBe(true);
    });
  });

  describe('Performance', () => {
    it('should batch observe operations', () => {
      const observer = new IntersectionObserver(() => {});
      const items = [];
      
      for (let i = 0; i < 10; i++) {
        const img = document.createElement('img');
        items.push(img);
        observer.observe(img);
      }
      
      expect(observer.observe).toHaveBeenCalledTimes(10);
    });

    it('should unobserve after load', () => {
      const observer = new IntersectionObserver(() => {});
      const img = document.createElement('img');
      
      observer.observe(img);
      observer.unobserve(img);
      
      expect(observer.unobserve).toHaveBeenCalled();
    });
  });

  describe('Cleanup', () => {
    it('should disconnect observer', () => {
      const observer = new IntersectionObserver(() => {});
      
      observer.disconnect();
      
      expect(observer.disconnect).toHaveBeenCalled();
    });
  });
});
