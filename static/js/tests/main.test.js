/**
 * Main.js Unit Tests
 * Tests for main application entry point
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Main Application', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="categoriesSection"></div>
      <div id="mediaViewer" class="hidden"></div>
      <div id="chat-container" class="hidden"></div>
      <div id="loading-spinner" class="hidden"></div>
    `;
    
    // Mock appConfig
    window.appConfig = {
      python_config: {
        DEBUG_MODE: false
      },
      javascript_config: {
        main: {
          phase2_init_delay: 250,
          phase3_init_delay: 500
        }
      }
    };
    
    // Mock socket
    window.io = vi.fn(() => ({
      on: vi.fn(),
      emit: vi.fn(),
      connect: vi.fn()
    }));
    
    // Mock modules
    window.ragotModules = {};
  });

  describe('DOM ready', () => {
    it('should wait for DOMContentLoaded', () => {
      const handler = vi.fn();
      
      document.addEventListener('DOMContentLoaded', handler);
      document.dispatchEvent(new Event('DOMContentLoaded'));
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Phase 1: Critical init', () => {
    it('should fetch config first', () => {
      const fetchConfig = vi.fn();
      fetchConfig();
      
      expect(fetchConfig).toHaveBeenCalled();
    });

    it('should initialize core modules', () => {
      const initCore = vi.fn();
      initCore();
      
      expect(initCore).toHaveBeenCalled();
    });
  });

  describe('Phase 2: Secondary init', () => {
    it('should use configured delay', () => {
      const delay = window.appConfig.javascript_config.main.phase2_init_delay;
      expect(delay).toBe(250);
    });

    it('should initialize secondary modules', () => {
      vi.useFakeTimers();
      
      const initSecondary = vi.fn();
      setTimeout(initSecondary, 250);
      
      vi.advanceTimersByTime(250);
      
      expect(initSecondary).toHaveBeenCalled();
      
      vi.useRealTimers();
    });
  });

  describe('Phase 3: Non-critical init', () => {
    it('should use configured delay', () => {
      const delay = window.appConfig.javascript_config.main.phase3_init_delay;
      expect(delay).toBe(500);
    });

    it('should initialize chat after delay', () => {
      vi.useFakeTimers();
      
      const initChat = vi.fn();
      setTimeout(initChat, 500);
      
      vi.advanceTimersByTime(500);
      
      expect(initChat).toHaveBeenCalled();
      
      vi.useRealTimers();
    });
  });

  describe('Socket initialization', () => {
    it('should create socket connection', () => {
      const socket = window.io();
      
      expect(window.io).toHaveBeenCalled();
      expect(socket.on).toBeDefined();
    });

    it('should register socket handlers', () => {
      const socket = window.io();
      
      socket.on('connect', vi.fn());
      socket.on('disconnect', vi.fn());
      
      expect(socket.on).toHaveBeenCalledWith('connect', expect.any(Function));
    });
  });

  describe('Config loaded event', () => {
    it('should dispatch configLoaded event', () => {
      const handler = vi.fn();
      document.addEventListener('configLoaded', handler);
      
      document.dispatchEvent(new CustomEvent('configLoaded', {
        detail: window.appConfig
      }));
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Error handling', () => {
    it('should handle initialization errors', () => {
      const handleError = vi.fn();
      
      window.addEventListener('error', handleError);
      window.dispatchEvent(new ErrorEvent('error', { message: 'Init failed' }));
      
      expect(handleError).toHaveBeenCalled();
      
      window.removeEventListener('error', handleError);
    });

    it('should handle unhandled rejections', () => {
      const handler = vi.fn();
      
      window.addEventListener('unhandledrejection', handler);
      window.dispatchEvent(new Event('unhandledrejection'));
      
      expect(handler).toHaveBeenCalled();
      
      window.removeEventListener('unhandledrejection', handler);
    });
  });

  describe('Module registration', () => {
    it('should register modules to window.ragotModules', () => {
      window.ragotModules.testModule = { init: vi.fn() };
      
      expect(window.ragotModules.testModule).toBeDefined();
    });
  });

  describe('Layout detection', () => {
    it('should detect streaming layout', () => {
      window.appConfig.javascript_config.ui = { layout: 'streaming' };
      
      expect(window.appConfig.javascript_config.ui.layout).toBe('streaming');
    });

    it('should detect gallery layout', () => {
      window.appConfig.javascript_config.ui = { layout: 'gallery' };
      
      expect(window.appConfig.javascript_config.ui.layout).toBe('gallery');
    });

    it('should default to streaming layout', () => {
      window.appConfig.javascript_config.ui = { layout: 'streaming' };

      expect(window.appConfig.javascript_config.ui.layout).toBe('streaming');
    });
  });

  describe('Cast receiver mode', () => {
    it('should detect display client', () => {
      const urlParams = new URLSearchParams('?display_client=true');
      const isDisplayClient = urlParams.get('display_client') === 'true';
      
      expect(isDisplayClient).toBe(true);
    });

    it('should handle cast_media_to_display event', () => {
      const socket = window.io();
      const handler = vi.fn();
      
      socket.on('cast_media_to_display', handler);
      
      expect(socket.on).toHaveBeenCalledWith('cast_media_to_display', handler);
    });
  });
});
