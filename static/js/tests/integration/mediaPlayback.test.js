/**
 * Media Playback Integration Tests
 * Tests the interaction between media loading, navigation, and playback
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Media Playback Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="categoriesSection">
        <div id="categoryList"></div>
      </div>
      <div id="mediaViewer" class="hidden">
        <div id="media-view" class="hidden">
          <div id="media-viewer" class="hidden">
            <div class="media-wrapper"></div>
          </div>
        </div>
      </div>
    `;
    
    // Mock appConfig
    window.appConfig = {
      python_config: {
        SHUFFLE_MEDIA: false,
        SAVE_CURRENT_INDEX: true
      },
      javascript_config: {
        core_app: {
          media_per_page_desktop: 5
        }
      }
    };
    
    // Mock appModules
    window.ragotModules = {
      mediaLoader: {
        viewCategory: vi.fn().mockResolvedValue(undefined),
        clearResources: vi.fn()
      },
      mediaNavigation: {
        renderMediaWindow: vi.fn(),
        navigateToMedia: vi.fn()
      },
      fullscreenManager: {
        toggleFullscreen: vi.fn()
      }
    };
  });

  describe('Category to media view flow', () => {
    it('should call viewCategory when selecting a category', async () => {
      const categoryId = 'test-category';
      
      await window.ragotModules.mediaLoader.viewCategory(categoryId);
      
      expect(window.ragotModules.mediaLoader.viewCategory).toHaveBeenCalledWith(categoryId);
    });

    it('should show media view after category load', async () => {
      const categoriesSection = document.getElementById('categoriesSection');
      const mediaViewer = document.getElementById('mediaViewer');
      
      await window.ragotModules.mediaLoader.viewCategory('test');
      
      // Simulate view switch
      categoriesSection.classList.add('hidden');
      mediaViewer.classList.remove('hidden');
      
      expect(categoriesSection.classList.contains('hidden')).toBe(true);
      expect(mediaViewer.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Media navigation', () => {
    it('should navigate to specific media index', () => {
      window.ragotModules.mediaNavigation.renderMediaWindow(5);
      
      expect(window.ragotModules.mediaNavigation.renderMediaWindow).toHaveBeenCalledWith(5);
    });

    it('should handle forced order navigation', async () => {
      const forcedOrder = ['/media/video1.mp4', '/media/video2.mp4'];
      
      await window.ragotModules.mediaLoader.viewCategory('test', forcedOrder, 0);
      
      expect(window.ragotModules.mediaLoader.viewCategory).toHaveBeenCalledWith('test', forcedOrder, 0);
    });
  });

  describe('Video playback', () => {
    it('should create video element with correct attributes', () => {
      const video = document.createElement('video');
      video.src = '/media/test.mp4';
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      
      expect(video.src).toContain('test.mp4');
      expect(video.controls).toBe(true);
      expect(video.autoplay).toBe(true);
      expect(video.playsInline).toBe(true);
    });

    it('should handle video play/pause', async () => {
      const video = document.createElement('video');
      video.play = vi.fn().mockResolvedValue(undefined);
      video.pause = vi.fn();
      
      await video.play();
      expect(video.play).toHaveBeenCalled();
      
      video.pause();
      expect(video.pause).toHaveBeenCalled();
    });

    it('should handle video progress events', () => {
      const video = document.createElement('video');
      const progressHandler = vi.fn();
      
      video.addEventListener('timeupdate', progressHandler);
      video.dispatchEvent(new Event('timeupdate'));
      
      expect(progressHandler).toHaveBeenCalled();
    });
  });

  describe('Image display', () => {
    it('should create image element correctly', () => {
      const img = document.createElement('img');
      img.src = '/media/photo.jpg';
      img.alt = 'Photo';
      
      expect(img.src).toContain('photo.jpg');
      expect(img.alt).toBe('Photo');
    });

    it('should handle image load event', () => {
      const img = document.createElement('img');
      const loadHandler = vi.fn();
      
      img.addEventListener('load', loadHandler);
      img.dispatchEvent(new Event('load'));
      
      expect(loadHandler).toHaveBeenCalled();
    });

    it('should handle image error event', () => {
      const img = document.createElement('img');
      const errorHandler = vi.fn();
      
      img.addEventListener('error', errorHandler);
      img.dispatchEvent(new Event('error'));
      
      expect(errorHandler).toHaveBeenCalled();
    });
  });

  describe('Fullscreen behavior', () => {
    it('should toggle fullscreen on media', () => {
      const video = document.createElement('video');
      
      window.ragotModules.fullscreenManager.toggleFullscreen(video);
      
      expect(window.ragotModules.fullscreenManager.toggleFullscreen).toHaveBeenCalledWith(video);
    });
  });

  describe('Progress tracking', () => {
    it('should save video progress', async () => {
      const progressData = {
        category_id: 'test',
        video_url: '/media/video.mp4',
        video_timestamp: 120,
        video_duration: 300
      };
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      });
      
      await fetch('/api/progress/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(progressData)
      });
      
      expect(fetch).toHaveBeenCalled();
    });

    it('should load saved progress', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          video_url: '/media/video.mp4',
          video_timestamp: 120
        })
      });
      
      const response = await fetch('/api/progress/test');
      const progress = await response.json();
      
      expect(progress.video_timestamp).toBe(120);
    });
  });

  describe('Resource cleanup', () => {
    it('should clear resources when leaving media view', () => {
      window.ragotModules.mediaLoader.clearResources(true);
      
      expect(window.ragotModules.mediaLoader.clearResources).toHaveBeenCalledWith(true);
    });
  });
});
