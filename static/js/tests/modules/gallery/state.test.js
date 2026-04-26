/**
 * Gallery State Module Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Gallery State', () => {
  let state;

  beforeEach(() => {
    state = {
      allMedia: [],
      filteredMedia: [],
      selectedItems: new Set(),
      currentFilter: 'all',
      currentView: 'timeline',
      isLoading: false,
      hasMore: true,
      page: 1,
      dateGroups: {}
    };
  });

  describe('Media state', () => {
    it('should store all media', () => {
      state.allMedia = [{ url: 'a.jpg' }, { url: 'b.jpg' }];
      expect(state.allMedia).toHaveLength(2);
    });

    it('should track filtered media separately', () => {
      state.allMedia = [{ type: 'image' }, { type: 'video' }];
      state.filteredMedia = state.allMedia.filter(m => m.type === 'image');
      
      expect(state.filteredMedia).toHaveLength(1);
      expect(state.allMedia).toHaveLength(2);
    });
  });

  describe('Filter state', () => {
    it('should default to all filter', () => {
      expect(state.currentFilter).toBe('all');
    });

    it('should update filter', () => {
      state.currentFilter = 'photos';
      expect(state.currentFilter).toBe('photos');
    });

    it('should accept valid filters', () => {
      const validFilters = ['all', 'photos', 'videos'];
      expect(validFilters).toContain('photos');
    });
  });

  describe('View state', () => {
    it('should default to timeline view', () => {
      expect(state.currentView).toBe('timeline');
    });

    it('should switch to grid view', () => {
      state.currentView = 'grid';
      expect(state.currentView).toBe('grid');
    });
  });

  describe('Selection state', () => {
    it('should start with empty selection', () => {
      expect(state.selectedItems.size).toBe(0);
    });

    it('should add to selection', () => {
      state.selectedItems.add('/media/photo1.jpg');
      state.selectedItems.add('/media/photo2.jpg');
      
      expect(state.selectedItems.size).toBe(2);
    });

    it('should remove from selection', () => {
      state.selectedItems.add('/media/photo1.jpg');
      state.selectedItems.delete('/media/photo1.jpg');
      
      expect(state.selectedItems.size).toBe(0);
    });

    it('should check if selected', () => {
      state.selectedItems.add('/media/photo1.jpg');
      
      expect(state.selectedItems.has('/media/photo1.jpg')).toBe(true);
      expect(state.selectedItems.has('/media/other.jpg')).toBe(false);
    });

    it('should clear selection', () => {
      state.selectedItems.add('/media/a.jpg');
      state.selectedItems.add('/media/b.jpg');
      state.selectedItems.clear();
      
      expect(state.selectedItems.size).toBe(0);
    });

    it('should toggle selection', () => {
      const url = '/media/photo.jpg';
      
      if (state.selectedItems.has(url)) {
        state.selectedItems.delete(url);
      } else {
        state.selectedItems.add(url);
      }
      
      expect(state.selectedItems.has(url)).toBe(true);
    });
  });

  describe('Pagination state', () => {
    it('should start at page 1', () => {
      expect(state.page).toBe(1);
    });

    it('should increment page', () => {
      state.page++;
      expect(state.page).toBe(2);
    });

    it('should track hasMore', () => {
      expect(state.hasMore).toBe(true);
      
      state.hasMore = false;
      expect(state.hasMore).toBe(false);
    });
  });

  describe('Loading state', () => {
    it('should start not loading', () => {
      expect(state.isLoading).toBe(false);
    });

    it('should set loading', () => {
      state.isLoading = true;
      expect(state.isLoading).toBe(true);
    });
  });

  describe('Date groups', () => {
    it('should store date groups', () => {
      state.dateGroups = {
        '2024-12-12': [{ url: 'a.jpg' }],
        '2024-12-11': [{ url: 'b.jpg' }, { url: 'c.jpg' }]
      };
      
      expect(Object.keys(state.dateGroups)).toHaveLength(2);
      expect(state.dateGroups['2024-12-11']).toHaveLength(2);
    });
  });

  describe('State reset', () => {
    it('should reset all state', () => {
      state.allMedia = [{ url: 'a.jpg' }];
      state.selectedItems.add('a.jpg');
      state.page = 5;
      
      // Reset
      state.allMedia = [];
      state.filteredMedia = [];
      state.selectedItems.clear();
      state.page = 1;
      state.hasMore = true;
      
      expect(state.allMedia).toHaveLength(0);
      expect(state.selectedItems.size).toBe(0);
      expect(state.page).toBe(1);
    });
  });
});
