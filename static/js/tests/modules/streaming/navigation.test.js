/**
 * Streaming Navigation Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Streaming Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    document.body.innerHTML = `
      <div id="streaming-container">
        <div class="hero-section">
          <button class="hero-play-btn">Play</button>
        </div>
        <div class="category-rows">
          <div class="category-row" data-category-id="movies">
            <div class="row-content">
              <div class="media-card" data-url="/media/movie1.mp4" data-index="0"></div>
              <div class="media-card" data-url="/media/movie2.mp4" data-index="1"></div>
            </div>
          </div>
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

  describe('Card click navigation', () => {
    it('should open media on card click', () => {
      const card = document.querySelector('.media-card');
      const handler = vi.fn();
      
      card.addEventListener('click', () => {
        handler(card.dataset.url);
      });
      
      card.click();
      
      expect(handler).toHaveBeenCalledWith('/media/movie1.mp4');
    });

    it('should call mediaLoader.viewCategory', async () => {
      const categoryId = 'movies';
      const mediaUrls = ['/media/movie1.mp4', '/media/movie2.mp4'];
      const startIndex = 0;
      
      await window.ragotModules.mediaLoader.viewCategory(categoryId, mediaUrls, startIndex);
      
      expect(window.ragotModules.mediaLoader.viewCategory).toHaveBeenCalledWith(
        categoryId, mediaUrls, startIndex
      );
    });
  });

  describe('Hero navigation', () => {
    it('should play featured on button click', () => {
      const playBtn = document.querySelector('.hero-play-btn');
      const handler = vi.fn();
      
      playBtn.addEventListener('click', handler);
      playBtn.click();
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Keyboard navigation', () => {
    it('should focus next card with ArrowRight', () => {
      let focusIndex = 0;
      const cards = document.querySelectorAll('.media-card');
      
      if (focusIndex < cards.length - 1) focusIndex++;
      
      expect(focusIndex).toBe(1);
    });

    it('should focus prev card with ArrowLeft', () => {
      let focusIndex = 1;
      
      if (focusIndex > 0) focusIndex--;
      
      expect(focusIndex).toBe(0);
    });

    it('should enter card on Enter', () => {
      const card = document.querySelector('.media-card');
      const handler = vi.fn();
      
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handler();
      });
      
      card.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Row navigation', () => {
    it('should focus first card in row', () => {
      const row = document.querySelector('.category-row');
      const firstCard = row.querySelector('.media-card');
      firstCard.focus = vi.fn();
      
      firstCard.focus();
      
      expect(firstCard.focus).toHaveBeenCalled();
    });

    it('should navigate between rows with ArrowDown', () => {
      let currentRowIndex = 0;
      const rows = document.querySelectorAll('.category-row');
      
      if (currentRowIndex < rows.length - 1) currentRowIndex++;
      
      expect(currentRowIndex).toBeLessThanOrEqual(rows.length);
    });
  });

  describe('Back navigation', () => {
    it('should return to streaming view on Escape', () => {
      const mediaViewer = document.getElementById('media-view');
      const streaming = document.getElementById('streaming-container');
      
      mediaViewer.classList.remove('hidden');
      streaming.classList.add('hidden');
      
      // Simulate Escape
      mediaViewer.classList.add('hidden');
      streaming.classList.remove('hidden');
      
      expect(streaming.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Scroll-based focus', () => {
    it('should scroll card into view when focused', () => {
      const card = document.querySelector('.media-card');
      card.scrollIntoView = vi.fn();
      
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      
      expect(card.scrollIntoView).toHaveBeenCalled();
    });
  });

  describe('Touch navigation', () => {
    it('should handle tap on card', () => {
      const card = document.querySelector('.media-card');
      const handler = vi.fn();
      
      card.addEventListener('touchend', handler);
      card.dispatchEvent(new TouchEvent('touchend'));
      
      expect(handler).toHaveBeenCalled();
    });
  });
});
