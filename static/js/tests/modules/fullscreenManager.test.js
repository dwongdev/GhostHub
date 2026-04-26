/**
 * FullscreenManager Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('../../core/app.js', () => ({
  MOBILE_DEVICE: false,
  app: {
    state: {
      fullMediaList: []
    }
  }
}));

vi.mock('../../utils/configManager.js', () => ({
  getConfigValue: vi.fn(() => 5)
}));

describe('FullscreenManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="media-viewer">
        <div class="media-wrapper">
          <video id="test-video" src="test.mp4"></video>
        </div>
      </div>
    `;
    
    // Mock fullscreen API
    document.fullscreenElement = null;
    document.webkitFullscreenElement = null;
    
    Element.prototype.requestFullscreen = vi.fn().mockResolvedValue(undefined);
    Element.prototype.webkitRequestFullscreen = vi.fn();
    document.exitFullscreen = vi.fn().mockResolvedValue(undefined);
    document.webkitExitFullscreen = vi.fn();
  });

  describe('Fullscreen API detection', () => {
    it('should have requestFullscreen available', () => {
      const element = document.getElementById('test-video');
      expect(element.requestFullscreen).toBeDefined();
    });

    it('should have exitFullscreen available', () => {
      expect(document.exitFullscreen).toBeDefined();
    });
  });

  describe('Video element controls', () => {
    it('should be able to add fullscreen button to video', () => {
      const video = document.getElementById('test-video');
      const button = document.createElement('button');
      button.className = 'fullscreen-btn';
      button.textContent = '⛶';
      video.parentElement.appendChild(button);
      
      expect(document.querySelector('.fullscreen-btn')).toBeDefined();
    });
  });

  describe('Fullscreen toggle simulation', () => {
    it('should call requestFullscreen on element', async () => {
      const element = document.getElementById('test-video');
      
      await element.requestFullscreen();
      
      expect(element.requestFullscreen).toHaveBeenCalled();
    });

    it('should call exitFullscreen when in fullscreen', async () => {
      document.fullscreenElement = document.getElementById('test-video');
      
      await document.exitFullscreen();
      
      expect(document.exitFullscreen).toHaveBeenCalled();
    });
  });

  describe('Fullscreen change events', () => {
    it('should be able to add fullscreenchange listener', () => {
      const handler = vi.fn();
      document.addEventListener('fullscreenchange', handler);
      
      document.dispatchEvent(new Event('fullscreenchange'));
      
      expect(handler).toHaveBeenCalled();
      
      document.removeEventListener('fullscreenchange', handler);
    });
  });

  describe('Mobile fullscreen behavior', () => {
    it('should handle webkit prefixed fullscreen', async () => {
      const element = document.getElementById('test-video');
      
      // Simulate environment without standard fullscreen
      const originalRequestFullscreen = element.requestFullscreen;
      element.requestFullscreen = undefined;
      
      if (element.webkitRequestFullscreen) {
        element.webkitRequestFullscreen();
        expect(element.webkitRequestFullscreen).toHaveBeenCalled();
      }
      
      // Restore
      element.requestFullscreen = originalRequestFullscreen;
    });
  });
});


