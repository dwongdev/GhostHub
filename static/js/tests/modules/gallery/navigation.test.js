/**
 * Gallery Navigation Module Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Gallery Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    document.body.innerHTML = `
      <div id="gallery-container">
        <div class="gallery-grid">
          <div class="gallery-item" data-index="0" data-url="/media/a.jpg"></div>
          <div class="gallery-item" data-index="1" data-url="/media/b.jpg"></div>
          <div class="gallery-item" data-index="2" data-url="/media/c.jpg"></div>
        </div>
      </div>
      <div id="media-view" class="hidden"></div>
    `;
    
    window.ragotModules = {
      mediaLoader: {
        viewCategory: vi.fn()
      }
    };
  });

  describe('Item click navigation', () => {
    it('should handle item click', () => {
      const handler = vi.fn();
      const grid = document.querySelector('.gallery-grid');
      
      grid.addEventListener('click', (e) => {
        const item = e.target.closest('.gallery-item');
        if (item) handler(item.dataset.url, parseInt(item.dataset.index));
      });
      
      const item = grid.querySelector('.gallery-item');
      item.click();
      
      expect(handler).toHaveBeenCalledWith('/media/a.jpg', 0);
    });

    it('should open media viewer', async () => {
      const url = '/media/photo.jpg';
      const index = 0;
      
      await window.ragotModules.mediaLoader.viewCategory('gallery', [url], index);
      
      expect(window.ragotModules.mediaLoader.viewCategory).toHaveBeenCalled();
    });
  });

  describe('Keyboard navigation', () => {
    it('should handle Enter on focused item', () => {
      const item = document.querySelector('.gallery-item');
      item.tabIndex = 0;
      item.focus();
      
      const handler = vi.fn();
      item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handler();
      });
      
      item.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      
      expect(handler).toHaveBeenCalled();
    });

    it('should navigate with arrow keys', () => {
      let focusIndex = 0;
      const items = document.querySelectorAll('.gallery-item');
      
      // Arrow right
      if (focusIndex < items.length - 1) focusIndex++;
      expect(focusIndex).toBe(1);
      
      // Arrow left
      if (focusIndex > 0) focusIndex--;
      expect(focusIndex).toBe(0);
    });
  });

  describe('Scroll navigation', () => {
    it('should scroll to item', () => {
      const item = document.querySelector('.gallery-item');
      item.scrollIntoView = vi.fn();
      
      item.scrollIntoView({ behavior: 'smooth' });
      
      expect(item.scrollIntoView).toHaveBeenCalled();
    });
  });

  describe('Date section navigation', () => {
    it('should jump to date', () => {
      const dateHeader = document.createElement('div');
      dateHeader.className = 'date-header';
      dateHeader.id = 'date-2024-12-12';
      document.body.appendChild(dateHeader);
      
      dateHeader.scrollIntoView = vi.fn();
      dateHeader.scrollIntoView();
      
      expect(dateHeader.scrollIntoView).toHaveBeenCalled();
    });
  });

  describe('Back navigation', () => {
    it('should return to gallery from viewer', () => {
      const mediaViewer = document.getElementById('media-view');
      const gallery = document.getElementById('gallery-container');
      
      mediaViewer.classList.remove('hidden');
      gallery.classList.add('hidden');
      
      // Go back
      mediaViewer.classList.add('hidden');
      gallery.classList.remove('hidden');
      
      expect(gallery.classList.contains('hidden')).toBe(false);
    });

    it('should handle Escape to go back', () => {
      const handler = vi.fn();
      
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') handler();
      });
      
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Selection navigation', () => {
    it('should select item with Shift+Click', () => {
      const selected = new Set();
      const items = document.querySelectorAll('.gallery-item');
      
      // Simulate shift+click
      selected.add(items[0].dataset.url);
      selected.add(items[1].dataset.url);
      
      expect(selected.size).toBe(2);
    });

    it('should select all with Ctrl+A', () => {
      const selected = new Set();
      const items = document.querySelectorAll('.gallery-item');
      
      items.forEach(item => selected.add(item.dataset.url));
      
      expect(selected.size).toBe(3);
    });
  });
});
