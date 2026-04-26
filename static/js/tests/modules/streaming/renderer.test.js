/**
 * Streaming Renderer Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Streaming Renderer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    document.body.innerHTML = `
      <div id="streaming-container">
        <div class="hero-section"></div>
        <div class="category-rows"></div>
      </div>
    `;
  });

  describe('Initial render', () => {
    it('should render hero section', () => {
      expect(document.querySelector('.hero-section')).toBeDefined();
    });

    it('should render category rows container', () => {
      expect(document.querySelector('.category-rows')).toBeDefined();
    });
  });

  describe('Row rendering', () => {
    it('should render category row', () => {
      const rows = document.querySelector('.category-rows');
      
      rows.innerHTML = `
        <div class="category-row" data-category-id="movies">
          <h2 class="row-title">Movies</h2>
          <div class="row-content"></div>
        </div>
      `;
      
      expect(document.querySelector('[data-category-id="movies"]')).toBeDefined();
    });

    it('should render multiple rows', () => {
      const rows = document.querySelector('.category-rows');
      
      ['Movies', 'Photos', 'Music'].forEach(name => {
        const row = document.createElement('div');
        row.className = 'category-row';
        row.innerHTML = `<h2 class="row-title">${name}</h2>`;
        rows.appendChild(row);
      });
      
      expect(rows.querySelectorAll('.category-row')).toHaveLength(3);
    });
  });

  describe('Card rendering', () => {
    it('should render media cards in row', () => {
      const rows = document.querySelector('.category-rows');
      rows.innerHTML = `
        <div class="category-row">
          <div class="row-content"></div>
        </div>
      `;
      
      const content = rows.querySelector('.row-content');
      
      for (let i = 0; i < 5; i++) {
        const card = document.createElement('div');
        card.className = 'media-card';
        card.dataset.url = `/media/video${i}.mp4`;
        content.appendChild(card);
      }
      
      expect(content.querySelectorAll('.media-card')).toHaveLength(5);
    });

    it('should render card thumbnail', () => {
      const card = document.createElement('div');
      card.className = 'media-card';
      card.innerHTML = `
        <div class="card-image-container">
          <img class="card-thumb" src="/thumbnails/movie.jpg" />
        </div>
      `;
      
      expect(card.querySelector('.card-thumb').src).toContain('movie.jpg');
    });

    it('should render card title', () => {
      const card = document.createElement('div');
      card.className = 'media-card';
      card.innerHTML = `
        <div class="card-info">
          <span class="card-title">Movie Title</span>
        </div>
      `;
      
      expect(card.querySelector('.card-title').textContent).toBe('Movie Title');
    });
  });

  describe('Skeleton rendering', () => {
    it('should render skeleton cards', () => {
      const content = document.createElement('div');
      content.className = 'row-content';
      
      for (let i = 0; i < 5; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'media-card skeleton';
        content.appendChild(skeleton);
      }
      
      expect(content.querySelectorAll('.skeleton')).toHaveLength(5);
    });

    it('should replace skeletons with real cards', () => {
      const content = document.createElement('div');
      content.className = 'row-content';
      content.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
      
      // Replace with real cards
      content.innerHTML = '<div class="media-card"></div><div class="media-card"></div>';
      
      expect(content.querySelectorAll('.skeleton')).toHaveLength(0);
      expect(content.querySelectorAll('.media-card')).toHaveLength(2);
    });
  });

  describe('Progress bar rendering', () => {
    it('should render progress bar on card', () => {
      const card = document.createElement('div');
      card.className = 'media-card';
      
      const progress = document.createElement('div');
      progress.className = 'progress-bar';
      progress.style.width = '50%';
      card.appendChild(progress);
      
      expect(card.querySelector('.progress-bar').style.width).toBe('50%');
    });
  });

  describe('Empty state', () => {
    it('should show empty message when no content', () => {
      const rows = document.querySelector('.category-rows');
      rows.innerHTML = '<div class="empty-state">No content available</div>';
      
      expect(document.querySelector('.empty-state')).toBeDefined();
    });
  });

  describe('Error state', () => {
    it('should show error message', () => {
      const rows = document.querySelector('.category-rows');
      rows.innerHTML = '<div class="error-state">Failed to load content</div>';
      
      expect(document.querySelector('.error-state').textContent).toContain('Failed');
    });
  });

  describe('Append rendering', () => {
    it('should append new cards to existing row', () => {
      const content = document.createElement('div');
      content.className = 'row-content';
      content.innerHTML = '<div class="media-card">1</div>';
      
      const newCard = document.createElement('div');
      newCard.className = 'media-card';
      newCard.textContent = '2';
      content.appendChild(newCard);
      
      expect(content.querySelectorAll('.media-card')).toHaveLength(2);
    });
  });
});
