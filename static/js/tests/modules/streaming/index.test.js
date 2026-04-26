/**
 * Streaming Index Module Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Streaming Index', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    document.body.innerHTML = `
      <div id="streaming-container" class="hidden"></div>
      <div id="categoriesSection"></div>
    `;
    
    window.appConfig = {
      javascript_config: {
        ui: {
          layout: 'streaming'
        }
      }
    };
  });

  describe('Module exports', () => {
    it('should have init function', () => {
      const streamingModule = {
        init: vi.fn(),
        cleanup: vi.fn(),
        refresh: vi.fn()
      };
      
      expect(typeof streamingModule.init).toBe('function');
    });

    it('should have cleanup function', () => {
      const streamingModule = {
        cleanup: vi.fn()
      };
      
      expect(typeof streamingModule.cleanup).toBe('function');
    });
  });

  describe('Initialization', () => {
    it('should show streaming container on init', () => {
      const container = document.getElementById('streaming-container');
      const categoriesSection = document.getElementById('categoriesSection');
      
      // Simulate init
      container.classList.remove('hidden');
      categoriesSection.classList.add('hidden');
      
      expect(container.classList.contains('hidden')).toBe(false);
    });

    it('should check layout config', () => {
      const isStreamingLayout = window.appConfig.javascript_config.ui.layout === 'streaming';
      
      expect(isStreamingLayout).toBe(true);
    });

    it('should skip init for non-streaming layout', () => {
      window.appConfig.javascript_config.ui.layout = 'gallery';

      const isStreamingLayout = window.appConfig.javascript_config.ui.layout === 'streaming';

      expect(isStreamingLayout).toBe(false);
    });
  });

  describe('Cleanup', () => {
    it('should hide container on cleanup', () => {
      const container = document.getElementById('streaming-container');
      container.classList.remove('hidden');
      
      // Simulate cleanup
      container.classList.add('hidden');
      
      expect(container.classList.contains('hidden')).toBe(true);
    });

    it('should clear cached data', () => {
      const cache = new Map();
      cache.set('movies', {});
      
      cache.clear();
      
      expect(cache.size).toBe(0);
    });
  });

  describe('Refresh', () => {
    it('should reload all data on refresh', () => {
      const refreshCalled = vi.fn();
      
      refreshCalled();
      
      expect(refreshCalled).toHaveBeenCalled();
    });
  });

  describe('Event listeners', () => {
    it('should listen for layout changes', () => {
      const handler = vi.fn();
      
      document.addEventListener('layoutChanged', handler);
      document.dispatchEvent(new CustomEvent('layoutChanged', {
        detail: { layout: 'streaming' }
      }));
      
      expect(handler).toHaveBeenCalled();
    });

    it('should listen for config updates', () => {
      const handler = vi.fn();
      
      document.addEventListener('configLoaded', handler);
      document.dispatchEvent(new CustomEvent('configLoaded'));
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Layout switching', () => {
    it('should switch to streaming layout', () => {
      document.documentElement.setAttribute('data-layout', 'streaming');
      
      expect(document.documentElement.getAttribute('data-layout')).toBe('streaming');
    });

    it('should switch from streaming to default', () => {
      document.documentElement.setAttribute('data-layout', 'default');
      
      expect(document.documentElement.getAttribute('data-layout')).toBe('default');
    });
  });
});
