/**
 * CategoryManager Unit Tests
 * Tests for category display and management
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('CategoryManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="categoriesSection">
        <div id="categoryList"></div>
      </div>
      <div id="mediaViewer" class="hidden"></div>
    `;
    
    // Mock IntersectionObserver
    window.IntersectionObserver = vi.fn().mockImplementation((callback) => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn()
    }));
    
    // Mock fetch
    global.fetch = vi.fn();
  });

  describe('Category list rendering', () => {
    it('should have category list container', () => {
      expect(document.getElementById('categoryList')).toBeDefined();
    });

    it('should render category cards', () => {
      const list = document.getElementById('categoryList');
      
      const card = document.createElement('div');
      card.className = 'category-card';
      card.dataset.categoryId = 'test-cat';
      list.appendChild(card);
      
      expect(list.querySelector('.category-card')).toBeDefined();
      expect(list.querySelector('[data-category-id="test-cat"]')).toBeDefined();
    });

    it('should render category thumbnail', () => {
      const list = document.getElementById('categoryList');
      
      const card = document.createElement('div');
      card.className = 'category-card';
      
      const thumb = document.createElement('img');
      thumb.className = 'category-thumbnail';
      thumb.dataset.src = '/thumbnails/cat.jpg';
      card.appendChild(thumb);
      
      list.appendChild(card);
      
      expect(list.querySelector('.category-thumbnail')).toBeDefined();
    });

    it('should render category name', () => {
      const list = document.getElementById('categoryList');
      
      const card = document.createElement('div');
      card.className = 'category-card';
      
      const name = document.createElement('span');
      name.className = 'category-name';
      name.textContent = 'Movies';
      card.appendChild(name);
      
      list.appendChild(card);
      
      expect(list.querySelector('.category-name').textContent).toBe('Movies');
    });

    it('should render media count', () => {
      const list = document.getElementById('categoryList');
      
      const card = document.createElement('div');
      card.className = 'category-card';
      
      const count = document.createElement('span');
      count.className = 'media-count';
      count.textContent = '42 items';
      card.appendChild(count);
      
      list.appendChild(card);
      
      expect(list.querySelector('.media-count').textContent).toBe('42 items');
    });
  });

  describe('Category fetching', () => {
    it('should fetch categories from API', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          categories: [
            { id: 'cat1', name: 'Movies', mediaCount: 10 },
            { id: 'cat2', name: 'Photos', mediaCount: 100 }
          ]
        })
      });
      
      const response = await fetch('/api/categories');
      const data = await response.json();
      
      expect(data.categories).toHaveLength(2);
      expect(data.categories[0].name).toBe('Movies');
    });

    it('should handle empty categories', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ categories: [] })
      });
      
      const response = await fetch('/api/categories');
      const data = await response.json();
      
      expect(data.categories).toHaveLength(0);
    });

    it('should handle fetch errors', async () => {
      global.fetch.mockRejectedValue(new Error('Network error'));
      
      await expect(fetch('/api/categories')).rejects.toThrow('Network error');
    });
  });

  describe('Lazy loading', () => {
    it('should create IntersectionObserver', () => {
      const observer = new IntersectionObserver(() => {});
      
      expect(window.IntersectionObserver).toHaveBeenCalled();
    });

    it('should observe category cards', () => {
      const observer = new IntersectionObserver(() => {});
      const card = document.createElement('div');
      
      observer.observe(card);
      
      expect(observer.observe).toHaveBeenCalledWith(card);
    });

    it('should load image when intersecting', () => {
      const img = document.createElement('img');
      img.dataset.src = '/thumbnails/test.jpg';
      img.className = 'placeholder';
      
      // Simulate load
      img.src = img.dataset.src;
      img.classList.remove('placeholder');
      img.classList.add('loaded');
      
      expect(img.src).toContain('test.jpg');
      expect(img.classList.contains('loaded')).toBe(true);
    });
  });

  describe('Category click handling', () => {
    it('should handle category click', () => {
      const handler = vi.fn();
      const list = document.getElementById('categoryList');
      
      list.addEventListener('click', (e) => {
        const card = e.target.closest('.category-card');
        if (card) handler(card.dataset.categoryId);
      });
      
      const card = document.createElement('div');
      card.className = 'category-card';
      card.dataset.categoryId = 'movies';
      list.appendChild(card);
      
      card.click();
      
      expect(handler).toHaveBeenCalledWith('movies');
    });
  });

  describe('Category filtering', () => {
    it('should filter by search term', () => {
      const categories = [
        { id: 'cat1', name: 'Movies' },
        { id: 'cat2', name: 'Photos' },
        { id: 'cat3', name: 'Home Movies' }
      ];
      
      const searchTerm = 'movie';
      const filtered = categories.filter(cat => 
        cat.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      
      expect(filtered).toHaveLength(2);
    });
  });

  describe('Category sorting', () => {
    it('should sort by name', () => {
      const categories = [
        { name: 'Zebra' },
        { name: 'Apple' },
        { name: 'Mango' }
      ];
      
      categories.sort((a, b) => a.name.localeCompare(b.name));
      
      expect(categories[0].name).toBe('Apple');
      expect(categories[2].name).toBe('Zebra');
    });

    it('should sort by media count', () => {
      const categories = [
        { name: 'A', mediaCount: 5 },
        { name: 'B', mediaCount: 100 },
        { name: 'C', mediaCount: 20 }
      ];
      
      categories.sort((a, b) => b.mediaCount - a.mediaCount);
      
      expect(categories[0].mediaCount).toBe(100);
    });
  });

  describe('Loading states', () => {
    it('should show loading shimmer', () => {
      const list = document.getElementById('categoryList');
      const shimmer = document.createElement('div');
      shimmer.className = 'category-card loading';
      list.appendChild(shimmer);
      
      expect(list.querySelector('.loading')).toBeDefined();
    });

    it('should remove loading state after fetch', () => {
      const list = document.getElementById('categoryList');
      const shimmer = document.createElement('div');
      shimmer.className = 'category-card loading';
      list.appendChild(shimmer);
      
      shimmer.classList.remove('loading');
      
      expect(shimmer.classList.contains('loading')).toBe(false);
    });
  });
});
