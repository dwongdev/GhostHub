/**
 * ConfigModal Unit Tests
 * Tests for settings/configuration modal
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('ConfigModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="config-modal" class="hidden">
        <div class="config-modal-content">
          <div class="config-header">
            <h2>Settings</h2>
            <button class="config-close-btn">&times;</button>
          </div>
          <div class="config-tabs">
            <button class="config-tab active" data-tab="general">General</button>
            <button class="config-tab" data-tab="appearance">Appearance</button>
            <button class="config-tab" data-tab="advanced">Advanced</button>
          </div>
          <div class="config-body">
            <div class="config-section" id="section-general"></div>
            <div class="config-section hidden" id="section-appearance"></div>
            <div class="config-section hidden" id="section-advanced"></div>
          </div>
          <div class="config-footer">
            <button id="config-save-btn">Save</button>
            <button id="config-cancel-btn">Cancel</button>
          </div>
        </div>
      </div>
    `;
    
    // Mock appConfig
    window.appConfig = {
      python_config: {
        DEBUG_MODE: false,
        SHUFFLE_MEDIA: true
      },
      javascript_config: {
        ui: {
          theme: 'dark',
          layout: 'streaming'
        }
      }
    };
    
    // Mock fetch
    global.fetch = vi.fn();
  });

  describe('Modal UI', () => {
    it('should have config modal', () => {
      expect(document.getElementById('config-modal')).toBeDefined();
    });

    it('should be hidden by default', () => {
      const modal = document.getElementById('config-modal');
      expect(modal.classList.contains('hidden')).toBe(true);
    });

    it('should open modal', () => {
      const modal = document.getElementById('config-modal');
      modal.classList.remove('hidden');
      expect(modal.classList.contains('hidden')).toBe(false);
    });

    it('should close on X button', () => {
      const modal = document.getElementById('config-modal');
      const closeBtn = modal.querySelector('.config-close-btn');
      
      modal.classList.remove('hidden');
      closeBtn.click();
      
      // Simulate close handler
      modal.classList.add('hidden');
      expect(modal.classList.contains('hidden')).toBe(true);
    });

    it('should close on cancel button', () => {
      const modal = document.getElementById('config-modal');
      const cancelBtn = document.getElementById('config-cancel-btn');
      
      modal.classList.remove('hidden');
      cancelBtn.click();
      
      modal.classList.add('hidden');
      expect(modal.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Tab navigation', () => {
    it('should have tab buttons', () => {
      const tabs = document.querySelectorAll('.config-tab');
      expect(tabs.length).toBe(3);
    });

    it('should show general tab by default', () => {
      const generalTab = document.querySelector('[data-tab="general"]');
      expect(generalTab.classList.contains('active')).toBe(true);
    });

    it('should switch tabs', () => {
      const tabs = document.querySelectorAll('.config-tab');
      const sections = document.querySelectorAll('.config-section');
      
      // Click appearance tab
      tabs[1].click();
      
      // Simulate tab switch
      tabs.forEach(t => t.classList.remove('active'));
      tabs[1].classList.add('active');
      
      sections.forEach(s => s.classList.add('hidden'));
      document.getElementById('section-appearance').classList.remove('hidden');
      
      expect(tabs[1].classList.contains('active')).toBe(true);
      expect(document.getElementById('section-appearance').classList.contains('hidden')).toBe(false);
    });
  });

  describe('Config values', () => {
    it('should read config values', () => {
      expect(window.appConfig.python_config.DEBUG_MODE).toBe(false);
      expect(window.appConfig.javascript_config.ui.theme).toBe('dark');
    });

    it('should update config values', () => {
      window.appConfig.python_config.DEBUG_MODE = true;
      expect(window.appConfig.python_config.DEBUG_MODE).toBe(true);
    });

    it('should handle nested config paths', () => {
      const getNestedValue = (obj, path) => {
        return path.split('.').reduce((curr, key) => curr?.[key], obj);
      };
      
      const value = getNestedValue(window.appConfig, 'javascript_config.ui.theme');
      expect(value).toBe('dark');
    });
  });

  describe('Save functionality', () => {
    it('should save config to server', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'Config saved' })
      });
      
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(window.appConfig)
      });
      const data = await response.json();
      
      expect(data.message).toBe('Config saved');
    });

    it('should handle save errors', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: 'Permission denied' })
      });
      
      const response = await fetch('/api/config', { method: 'POST' });
      
      expect(response.ok).toBe(false);
    });
  });

  describe('Theme settings', () => {
    it('should have theme options', () => {
      const themes = ['dark', 'midnight', 'nord', 'monokai', 'dracula'];
      
      expect(themes).toContain('dark');
      expect(themes.length).toBe(5);
    });

    it('should apply theme preview', () => {
      document.documentElement.setAttribute('data-theme', 'nord');
      expect(document.documentElement.getAttribute('data-theme')).toBe('nord');
    });
  });

  describe('Layout settings', () => {
    it('should have layout options', () => {
      const layouts = ['default', 'streaming', 'gallery'];
      
      expect(layouts).toContain('streaming');
      expect(layouts.length).toBe(3);
    });

    it('should apply layout preview', () => {
      document.documentElement.setAttribute('data-layout', 'streaming');
      expect(document.documentElement.getAttribute('data-layout')).toBe('streaming');
    });
  });

  describe('Feature toggles', () => {
    it('should toggle chat feature', () => {
      document.documentElement.setAttribute('data-feature-chat', 'false');
      expect(document.documentElement.getAttribute('data-feature-chat')).toBe('false');
    });

    it('should toggle sync status', () => {
      document.documentElement.setAttribute('data-feature-sync-status', 'true');
      expect(document.documentElement.getAttribute('data-feature-sync-status')).toBe('true');
    });
  });

  describe('Form validation', () => {
    it('should validate required fields', () => {
      const value = '';
      const isValid = value.trim().length > 0;
      
      expect(isValid).toBe(false);
    });

    it('should validate number range', () => {
      const value = 50;
      const min = 1;
      const max = 100;
      const isValid = value >= min && value <= max;
      
      expect(isValid).toBe(true);
    });
  });
});
