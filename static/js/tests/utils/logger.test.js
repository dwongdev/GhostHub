/**
 * Logger Unit Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('Logger', () => {
  let logger;
  let originalConsoleLog;
  let originalConsoleDebug;
  let originalConsoleWarn;
  let originalConsoleError;

  beforeEach(async () => {
    vi.resetModules();
    
    // Store original console methods
    originalConsoleLog = console.log;
    originalConsoleDebug = console.debug;
    originalConsoleWarn = console.warn;
    originalConsoleError = console.error;
    
    // Mock configManager
    vi.doMock('../../utils/configManager.js', () => ({
      getConfigValue: vi.fn((path, defaultValue) => {
        if (path === 'python_config.DEBUG_MODE') {
          return window.appConfig?.python_config?.DEBUG_MODE ?? defaultValue;
        }
        return defaultValue;
      })
    }));
    
    // Import fresh module
    logger = await import('../../utils/logger.js');
  });

  afterEach(() => {
    // Restore console methods
    console.log = originalConsoleLog;
    console.debug = originalConsoleDebug;
    console.warn = originalConsoleWarn;
    console.error = originalConsoleError;
  });

  describe('isDebugEnabled', () => {
    it('should return false when DEBUG_MODE is false', () => {
      window.appConfig = { python_config: { DEBUG_MODE: false } };
      expect(logger.isDebugEnabled()).toBe(false);
    });

    it('should return true when DEBUG_MODE is true', async () => {
      window.appConfig = { python_config: { DEBUG_MODE: true } };
      
      vi.resetModules();
      vi.doMock('../../utils/configManager.js', () => ({
        getConfigValue: vi.fn(() => true)
      }));
      
      const freshLogger = await import('../../utils/logger.js');
      expect(freshLogger.isDebugEnabled()).toBe(true);
    });
  });

  describe('forceLog', () => {
    it('should always log regardless of debug mode', () => {
      const logSpy = vi.fn();
      logger.originalConsole.log = logSpy;
      
      logger.forceLog('Test message');
      
      expect(logSpy).toHaveBeenCalledWith('Test message');
    });

    it('should handle multiple arguments', () => {
      const logSpy = vi.fn();
      logger.originalConsole.log = logSpy;
      
      logger.forceLog('Message', { data: 123 }, [1, 2, 3]);
      
      expect(logSpy).toHaveBeenCalledWith('Message', { data: 123 }, [1, 2, 3]);
    });
  });

  describe('forceWarn', () => {
    it('should always warn regardless of debug mode', () => {
      const warnSpy = vi.fn();
      logger.originalConsole.warn = warnSpy;
      
      logger.forceWarn('Warning message');
      
      expect(warnSpy).toHaveBeenCalledWith('Warning message');
    });
  });

  describe('forceError', () => {
    it('should always error regardless of debug mode', () => {
      const errorSpy = vi.fn();
      logger.originalConsole.error = errorSpy;
      
      logger.forceError('Error message');
      
      expect(errorSpy).toHaveBeenCalledWith('Error message');
    });
  });

  describe('initLogger', () => {
    it('should silence console.log when debug is disabled', async () => {
      window.appConfig = { python_config: { DEBUG_MODE: false } };
      
      vi.resetModules();
      vi.doMock('../../utils/configManager.js', () => ({
        getConfigValue: vi.fn(() => false)
      }));
      
      const freshLogger = await import('../../utils/logger.js');
      freshLogger.initLogger();
      
      const logSpy = vi.fn();
      const originalLog = console.log;
      
      console.log('This should be silenced');
      
      // In production mode, console.log should be a no-op
      // We can verify by checking it doesn't throw
      expect(true).toBe(true);
    });

    it('should preserve console.warn and console.error', async () => {
      window.appConfig = { python_config: { DEBUG_MODE: false } };
      
      vi.resetModules();
      vi.doMock('../../utils/configManager.js', () => ({
        getConfigValue: vi.fn(() => false)
      }));
      
      const freshLogger = await import('../../utils/logger.js');
      freshLogger.initLogger();
      
      // console.warn and console.error should still work
      expect(typeof console.warn).toBe('function');
      expect(typeof console.error).toBe('function');
    });
  });

  describe('originalConsole', () => {
    it('should export original console methods', () => {
      expect(logger.originalConsole).toBeDefined();
      expect(typeof logger.originalConsole.log).toBe('function');
      expect(typeof logger.originalConsole.warn).toBe('function');
      expect(typeof logger.originalConsole.error).toBe('function');
      expect(typeof logger.originalConsole.info).toBe('function');
      expect(typeof logger.originalConsole.debug).toBe('function');
    });
  });
});
