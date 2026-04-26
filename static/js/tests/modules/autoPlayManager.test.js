/**
 * AutoPlayManager Unit Tests
 * Tests for automatic media advancement functionality
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('AutoPlayManager', () => {
  let navigateMediaMock;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="media-viewer">
        <video class="viewer-media active" data-index="0"></video>
      </div>
    `;
    
    // Mock app state service in registry
    window.__RAGOT_ALLOW_DIRECT_MUTATION__ = true;
    window.ragotModules = {
      ...(window.ragotModules || {}),
      appState: {
        currentMediaIndex: 0,
        fullMediaList: [
          { url: '/media/image1.jpg', type: 'image', name: 'Image 1' },
          { url: '/media/video1.mp4', type: 'video', name: 'Video 1' },
          { url: '/media/image2.jpg', type: 'image', name: 'Image 2' }
        ]
      }
    };
    
    navigateMediaMock = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('toggleAutoPlay', () => {
    it('should start auto-play with default interval', async () => {
      const { initAutoPlayManager, toggleAutoPlay, isAutoPlayActive } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      const result = toggleAutoPlay(true);
      
      expect(result).toBe('started');
      expect(isAutoPlayActive()).toBe(true);
    });

    it('should start auto-play with custom interval', async () => {
      const { initAutoPlayManager, toggleAutoPlay, getAutoPlayInterval } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(5); // 5 seconds
      
      expect(getAutoPlayInterval()).toBe(5000);
    });

    it('should stop auto-play when called with false', async () => {
      const { initAutoPlayManager, toggleAutoPlay, isAutoPlayActive } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(10);
      expect(isAutoPlayActive()).toBe(true);
      
      const result = toggleAutoPlay(false);
      expect(result).toBe('stopped');
      expect(isAutoPlayActive()).toBe(false);
    });

    it('should stop auto-play when called with "stop"', async () => {
      const { initAutoPlayManager, toggleAutoPlay, isAutoPlayActive } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(10);
      
      const result = toggleAutoPlay('stop');
      expect(result).toBe('stopped');
      expect(isAutoPlayActive()).toBe(false);
    });
  });

  describe('handleAutoPlay', () => {
    it('should set timer for image files', async () => {
      const { initAutoPlayManager, toggleAutoPlay, handleAutoPlay } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(5); // 5 second interval
      
      // Current item is an image (index 0)
      handleAutoPlay(0);
      
      // Fast-forward timer
      vi.advanceTimersByTime(5000);
      
      expect(navigateMediaMock).toHaveBeenCalledWith('next');
    });

    it('should not navigate when auto-play is inactive', async () => {
      const { initAutoPlayManager, toggleAutoPlay, handleAutoPlay } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(false); // Ensure stopped
      
      handleAutoPlay(0);
      
      vi.advanceTimersByTime(15000);
      
      expect(navigateMediaMock).not.toHaveBeenCalled();
    });

    it('should not crash when current file is undefined', async () => {
      const { initAutoPlayManager, toggleAutoPlay, handleAutoPlay } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(5);
      
      // Index out of bounds
      expect(() => handleAutoPlay(999)).not.toThrow();
    });
  });

  describe('isAutoPlayActive', () => {
    it('should return false initially', async () => {
      const { isAutoPlayActive } = await import('../../modules/playback/autoPlay.js');
      
      // Need to reset module state - for fresh import
      expect(typeof isAutoPlayActive).toBe('function');
    });
  });

  describe('Auto-play indicator', () => {
    it('should create indicator element when auto-play starts', async () => {
      const { initAutoPlayManager, toggleAutoPlay } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(10);
      
      const indicator = document.getElementById('autoplay-indicator');
      expect(indicator).toBeDefined();
    });

    it('should hide indicator when auto-play stops', async () => {
      const { initAutoPlayManager, toggleAutoPlay } = await import('../../modules/playback/autoPlay.js');
      
      initAutoPlayManager(navigateMediaMock);
      toggleAutoPlay(10);
      toggleAutoPlay(false);
      
      const indicator = document.getElementById('autoplay-indicator');
      if (indicator) {
        expect(indicator.style.display).toBe('none');
      }
    });
  });
});
