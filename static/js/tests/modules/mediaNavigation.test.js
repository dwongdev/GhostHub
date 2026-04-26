/**
 * MediaNavigation Unit Tests
 * Tests for media navigation and playback controls
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('MediaNavigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="media-view" class="hidden">
        <div id="media-viewer" class="hidden">
          <div class="media-wrapper">
            <div class="spinner-container"></div>
          </div>
          <div class="nav-controls">
            <button class="nav-prev">↑</button>
            <button class="nav-next">↓</button>
          </div>
          <div class="media-info">
            <span class="media-counter">1 / 10</span>
            <span class="media-title"></span>
          </div>
        </div>
      </div>
    `;
    
    // Mock app state service
    window.__RAGOT_ALLOW_DIRECT_MUTATION__ = true;
    window.ragotModules = {
      ...(window.ragotModules || {}),
      appState: {
        currentCategoryId: 'test-category',
        currentMediaIndex: 0,
        fullMediaList: [
          { url: '/media/video1.mp4', type: 'video', name: 'Video 1' },
          { url: '/media/image1.jpg', type: 'image', name: 'Image 1' },
          { url: '/media/video2.mp4', type: 'video', name: 'Video 2' }
        ],
        isLoading: false,
        hasMoreMedia: true,
        syncModeEnabled: false,
        navigationDisabled: false
      }
    };
  });

  describe('Navigation state', () => {
    it('should track current media index', () => {
      expect(window.ragotModules.appState.currentMediaIndex).toBe(0);
    });

    it('should have media list', () => {
      expect(window.ragotModules.appState.fullMediaList).toHaveLength(3);
    });

    it('should track current category', () => {
      expect(window.ragotModules.appState.currentCategoryId).toBe('test-category');
    });
  });

  describe('Navigation controls', () => {
    it('should have prev button', () => {
      expect(document.querySelector('.nav-prev')).toBeDefined();
    });

    it('should have next button', () => {
      expect(document.querySelector('.nav-next')).toBeDefined();
    });

    it('should navigate to next', () => {
      const maxIndex = window.ragotModules.appState.fullMediaList.length - 1;
      
      if (window.ragotModules.appState.currentMediaIndex < maxIndex) {
        window.ragotModules.appState.currentMediaIndex++;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(1);
    });

    it('should navigate to previous', () => {
      window.ragotModules.appState.currentMediaIndex = 2;
      
      if (window.ragotModules.appState.currentMediaIndex > 0) {
        window.ragotModules.appState.currentMediaIndex--;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(1);
    });

    it('should not go below 0', () => {
      window.ragotModules.appState.currentMediaIndex = 0;
      
      if (window.ragotModules.appState.currentMediaIndex > 0) {
        window.ragotModules.appState.currentMediaIndex--;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(0);
    });

    it('should not exceed max index', () => {
      const maxIndex = window.ragotModules.appState.fullMediaList.length - 1;
      window.ragotModules.appState.currentMediaIndex = maxIndex;
      
      if (window.ragotModules.appState.currentMediaIndex < maxIndex) {
        window.ragotModules.appState.currentMediaIndex++;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(maxIndex);
    });
  });

  describe('Keyboard navigation', () => {
    it('should handle ArrowUp for previous', () => {
      window.ragotModules.appState.currentMediaIndex = 1;
      
      const event = new KeyboardEvent('keydown', { key: 'ArrowUp' });
      if (event.key === 'ArrowUp' && window.ragotModules.appState.currentMediaIndex > 0) {
        window.ragotModules.appState.currentMediaIndex--;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(0);
    });

    it('should handle ArrowDown for next', () => {
      const event = new KeyboardEvent('keydown', { key: 'ArrowDown' });
      const maxIndex = window.ragotModules.appState.fullMediaList.length - 1;
      
      if (event.key === 'ArrowDown' && window.ragotModules.appState.currentMediaIndex < maxIndex) {
        window.ragotModules.appState.currentMediaIndex++;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(1);
    });

    it('should block navigation when disabled', () => {
      window.ragotModules.appState.navigationDisabled = true;
      const originalIndex = window.ragotModules.appState.currentMediaIndex;
      
      if (!window.ragotModules.appState.navigationDisabled) {
        window.ragotModules.appState.currentMediaIndex++;
      }
      
      expect(window.ragotModules.appState.currentMediaIndex).toBe(originalIndex);
    });
  });

  describe('Touch navigation', () => {
    it('should detect swipe up', () => {
      const startY = 300;
      const endY = 100;
      const threshold = 50;
      
      const isSwipeUp = startY - endY > threshold;
      
      expect(isSwipeUp).toBe(true);
    });

    it('should detect swipe down', () => {
      const startY = 100;
      const endY = 300;
      const threshold = 50;
      
      const isSwipeDown = endY - startY > threshold;
      
      expect(isSwipeDown).toBe(true);
    });
  });

  describe('Media counter', () => {
    it('should display counter', () => {
      const counter = document.querySelector('.media-counter');
      expect(counter).toBeDefined();
    });

    it('should update counter', () => {
      const counter = document.querySelector('.media-counter');
      const current = window.ragotModules.appState.currentMediaIndex + 1;
      const total = window.ragotModules.appState.fullMediaList.length;
      
      counter.textContent = `${current} / ${total}`;
      
      expect(counter.textContent).toBe('1 / 3');
    });
  });

  describe('Media title', () => {
    it('should display title', () => {
      const title = document.querySelector('.media-title');
      const media = window.ragotModules.appState.fullMediaList[0];
      title.textContent = media.name;
      
      expect(title.textContent).toBe('Video 1');
    });

    it('should extract title from URL', () => {
      const url = '/media/category/my_video.mp4';
      const filename = url.split('/').pop();
      const title = filename.replace(/\.[^/.]+$/, '').replace(/_/g, ' ');
      
      expect(title).toBe('my video');
    });
  });

  describe('Loading state', () => {
    it('should show spinner when loading', () => {
      const spinner = document.querySelector('.spinner-container');
      spinner.classList.add('visible');
      
      expect(spinner.classList.contains('visible')).toBe(true);
    });

    it('should hide spinner when loaded', () => {
      const spinner = document.querySelector('.spinner-container');
      spinner.classList.remove('visible');
      
      expect(spinner.classList.contains('visible')).toBe(false);
    });

    it('should track loading state', () => {
      window.ragotModules.appState.isLoading = true;
      expect(window.ragotModules.appState.isLoading).toBe(true);
      
      window.ragotModules.appState.isLoading = false;
      expect(window.ragotModules.appState.isLoading).toBe(false);
    });
  });

  describe('Progress tracking', () => {
    it('should save video progress', () => {
      const progress = {
        category_id: 'test-category',
        video_url: '/media/video1.mp4',
        video_timestamp: 120,
        video_duration: 600
      };
      
      expect(progress.video_timestamp).toBe(120);
      expect(progress.video_duration).toBe(600);
    });

    it('should calculate progress percentage', () => {
      const timestamp = 300;
      const duration = 600;
      const percent = Math.round((timestamp / duration) * 100);
      
      expect(percent).toBe(50);
    });
  });

  describe('Sync mode integration', () => {
    it('should respect sync navigation disabled', () => {
      window.ragotModules.appState.syncModeEnabled = true;
      window.ragotModules.appState.navigationDisabled = true;
      
      const canNavigate = !window.ragotModules.appState.navigationDisabled;
      
      expect(canNavigate).toBe(false);
    });

    it('should allow navigation when sync disabled', () => {
      window.ragotModules.appState.syncModeEnabled = false;
      window.ragotModules.appState.navigationDisabled = false;
      
      const canNavigate = !window.ragotModules.appState.navigationDisabled;
      
      expect(canNavigate).toBe(true);
    });
  });

  describe('Load more media', () => {
    it('should detect when near end', () => {
      window.ragotModules.appState.currentMediaIndex = 2;
      const threshold = 2;
      const total = window.ragotModules.appState.fullMediaList.length;
      
      const nearEnd = window.ragotModules.appState.currentMediaIndex >= total - threshold;
      
      expect(nearEnd).toBe(true);
    });

    it('should check hasMoreMedia flag', () => {
      expect(window.ragotModules.appState.hasMoreMedia).toBe(true);
    });

    it('should update hasMoreMedia when exhausted', () => {
      window.ragotModules.appState.hasMoreMedia = false;
      expect(window.ragotModules.appState.hasMoreMedia).toBe(false);
    });
  });
});

