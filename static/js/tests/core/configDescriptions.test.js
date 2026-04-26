/**
 * Config Descriptions Unit Tests
 */

import { describe, it, expect } from 'vitest';
import { CONFIG_DESCRIPTIONS } from '../../core/configDescriptions.js';

describe('ConfigDescriptions', () => {
  describe('CONFIG_DESCRIPTIONS export', () => {
    it('should export CONFIG_DESCRIPTIONS object', () => {
      expect(CONFIG_DESCRIPTIONS).toBeDefined();
      expect(typeof CONFIG_DESCRIPTIONS).toBe('object');
    });

    it('should have multiple entries', () => {
      expect(Object.keys(CONFIG_DESCRIPTIONS).length).toBeGreaterThan(0);
    });
  });

  describe('python_config descriptions', () => {
    it('should have SHUFFLE_MEDIA description', () => {
      expect(CONFIG_DESCRIPTIONS['python_config.SHUFFLE_MEDIA']).toBeDefined();
      const desc = CONFIG_DESCRIPTIONS['python_config.SHUFFLE_MEDIA'];
      expect(typeof desc).toBe('object');
      expect(desc.description).toBeDefined();
      expect(typeof desc.description).toBe('string');
      expect(desc.level).toBeDefined();
    });

    it('should have MAX_CACHE_SIZE description', () => {
      expect(CONFIG_DESCRIPTIONS['python_config.MAX_CACHE_SIZE']).toBeDefined();
    });

    it('should have SAVE_VIDEO_PROGRESS description', () => {
      expect(CONFIG_DESCRIPTIONS['python_config.SAVE_VIDEO_PROGRESS']).toBeDefined();
    });

    it('should have SESSION_PASSWORD description', () => {
      expect(CONFIG_DESCRIPTIONS['python_config.SESSION_PASSWORD']).toBeDefined();
    });

    it('should have ENABLE_SUBTITLES description', () => {
      expect(CONFIG_DESCRIPTIONS['python_config.ENABLE_SUBTITLES']).toBeDefined();
    });
  });

  describe('javascript_config descriptions', () => {
    it('should have core_app media_per_page_desktop description', () => {
      expect(CONFIG_DESCRIPTIONS['javascript_config.core_app.media_per_page_desktop']).toBeDefined();
    });

    it('should have sync_manager socket settings', () => {
      expect(CONFIG_DESCRIPTIONS['javascript_config.sync_manager.socket_reconnectionAttempts']).toBeDefined();
    });

    it('should have ui theme description', () => {
      expect(CONFIG_DESCRIPTIONS['javascript_config.ui.theme']).toBeDefined();
    });

    it('should have ui layout description', () => {
      expect(CONFIG_DESCRIPTIONS['javascript_config.ui.layout']).toBeDefined();
    });

    it('should have feature toggle descriptions', () => {
      expect(CONFIG_DESCRIPTIONS['javascript_config.ui.features.chat']).toBeDefined();
      expect(CONFIG_DESCRIPTIONS['javascript_config.ui.features.headerBranding']).toBeDefined();
      expect(CONFIG_DESCRIPTIONS['javascript_config.ui.features.search']).toBeDefined();
    });
  });

  describe('description content', () => {
    it('all descriptions should be non-empty strings or objects with description', () => {
      Object.entries(CONFIG_DESCRIPTIONS).forEach(([key, desc]) => {
        if (typeof desc === 'object') {
          expect(desc.description).toBeDefined();
          expect(typeof desc.description).toBe('string');
          expect(desc.description.length, `Description for ${key} should not be empty`).toBeGreaterThan(0);
          expect(desc.level).toBeDefined();
          expect(['basic', 'advanced']).toContain(desc.level);
        } else {
          expect(typeof desc).toBe('string');
          expect(desc.length, `Description for ${key} should not be empty`).toBeGreaterThan(0);
        }
      });
    });

    it('descriptions should contain helpful information', () => {
      // Descriptions should typically contain context about the setting
      const shuffleDesc = CONFIG_DESCRIPTIONS['python_config.SHUFFLE_MEDIA'];
      const descText = typeof shuffleDesc === 'object' ? shuffleDesc.description : shuffleDesc;
      expect(descText).toContain('Random Play');
    });
  });
});
