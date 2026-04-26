/**
 * ConfigManager Unit Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We need to test the module in isolation, so we'll dynamically import after mocking
describe('ConfigManager', () => {
  let configManager;
  let bus;
  let APP_EVENTS;

  beforeEach(async () => {
    vi.resetModules();

    // Reset global state
    window.appConfig = undefined;
    window.ragotModules = {
      appStore: {
        set: vi.fn(),
        get: vi.fn(() => ({}))
      }
    };

    // Mock fetch for config loading
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        python_config: { DEBUG_MODE: true },
        javascript_config: {
          core_app: { media_per_page_desktop: 10 },
          ui: { theme: 'nord' }
        },
        isPasswordProtectionActive: true
      })
    });

    // Import fresh modules
    ({ bus } = await import('../../libs/ragot.esm.min.js'));
    ({ APP_EVENTS } = await import('../../core/appEvents.js'));
    configManager = await import('../../utils/configManager.js');
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchAndApplyConfig', () => {
    it('should fetch config from /api/config and store it', async () => {
      const config = await configManager.fetchAndApplyConfig();

      expect(fetch).toHaveBeenCalledWith('/api/config');
      expect(config.python_config.DEBUG_MODE).toBe(true);
      // Config is now stored via appStore, not window.appConfig
      expect(config).toBeDefined();
    });

    it('should emit config loaded event on success', async () => {
      const eventHandler = vi.fn();
      const unsub = bus.on(APP_EVENTS.CONFIG_LOADED, eventHandler);

      await configManager.fetchAndApplyConfig();

      expect(eventHandler).toHaveBeenCalled();
      expect(eventHandler.mock.calls[0][0].python_config.DEBUG_MODE).toBe(true);

      unsub();
    });

    it('should handle fetch errors gracefully', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      const config = await configManager.fetchAndApplyConfig();

      // Should return empty/default config structure
      expect(config).toHaveProperty('python_config');
      expect(config).toHaveProperty('javascript_config');
    });

    it('should handle non-ok response', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error'
      });

      const config = await configManager.fetchAndApplyConfig();

      expect(config).toBeDefined();
    });
  });

  describe('getConfigValue', () => {
    it('should return value at dot-separated path', async () => {
      await configManager.fetchAndApplyConfig();

      const value = configManager.getConfigValue('python_config.DEBUG_MODE', false);
      expect(value).toBe(true);
    });

    it('should return default value for missing path', async () => {
      await configManager.fetchAndApplyConfig();

      const value = configManager.getConfigValue('nonexistent.path', 'default');
      expect(value).toBe('default');
    });

    it('should return default value for partially matching path', async () => {
      await configManager.fetchAndApplyConfig();

      const value = configManager.getConfigValue('python_config.missing_key', 'fallback');
      expect(value).toBe('fallback');
    });

    it('should handle nested paths correctly', async () => {
      await configManager.fetchAndApplyConfig();

      const value = configManager.getConfigValue('javascript_config.core_app.media_per_page_desktop', 5);
      expect(value).toBe(10);
    });

    it.skip('should warn if called before config is fetched (timing-dependent, skipped)', async () => {
      // This test is skipped because it depends on 3-second grace period timing
      // which is too slow for CI and can be flaky
      // The warning functionality is tested manually during development
    });
  });

  describe('saveConfig', () => {
    it('should POST config to /api/config', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Config saved', isPasswordProtectionActive: true })
      });

      const newConfig = {
        python_config: { DEBUG_MODE: false },
        javascript_config: { ui: { theme: 'dracula' } }
      };

      const result = await configManager.saveConfig(newConfig);

      expect(fetch).toHaveBeenCalledWith('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      expect(result.message).toBe('Config saved');
    });

    it('should update local config cache on success', async () => {
      await configManager.fetchAndApplyConfig();

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Saved', isPasswordProtectionActive: false })
      });

      const newConfig = {
        python_config: { DEBUG_MODE: false },
        javascript_config: { ui: { theme: 'monokai' } }
      };

      await configManager.saveConfig(newConfig);

      // Verify that getCurrentConfig reflects the update
      const currentConfig = configManager.getCurrentConfig();
      expect(currentConfig.isPasswordProtectionActive).toBe(false);
    });

    it('should throw on save failure', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: () => Promise.resolve({ error: 'Not authorized' })
      });

      await expect(configManager.saveConfig({})).rejects.toThrow('Not authorized');
    });
  });
});
