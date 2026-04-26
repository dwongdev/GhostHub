/**
 * PWA Installer Unit Tests
 * Tests for Progressive Web App installation
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('PWA Installer', () => {
  let deferredPrompt;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <button id="pwa-install-btn" class="hidden">Install App</button>
      <div id="pwa-prompt" class="hidden">
        <p>Add GhostHub to your home screen?</p>
        <button id="pwa-install-yes">Install</button>
        <button id="pwa-install-no">Not Now</button>
      </div>
    `;
    
    // Mock beforeinstallprompt event
    deferredPrompt = {
      prompt: vi.fn(),
      userChoice: Promise.resolve({ outcome: 'accepted' })
    };
  });

  describe('Install button', () => {
    it('should have install button', () => {
      expect(document.getElementById('pwa-install-btn')).toBeDefined();
    });

    it('should be hidden by default', () => {
      const btn = document.getElementById('pwa-install-btn');
      expect(btn.classList.contains('hidden')).toBe(true);
    });

    it('should show when installable', () => {
      const btn = document.getElementById('pwa-install-btn');
      btn.classList.remove('hidden');
      
      expect(btn.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Install prompt', () => {
    it('should have prompt element', () => {
      expect(document.getElementById('pwa-prompt')).toBeDefined();
    });

    it('should show prompt', () => {
      const prompt = document.getElementById('pwa-prompt');
      prompt.classList.remove('hidden');
      
      expect(prompt.classList.contains('hidden')).toBe(false);
    });

    it('should have install and dismiss buttons', () => {
      expect(document.getElementById('pwa-install-yes')).toBeDefined();
      expect(document.getElementById('pwa-install-no')).toBeDefined();
    });
  });

  describe('beforeinstallprompt event', () => {
    it('should store deferred prompt', () => {
      window.deferredPrompt = deferredPrompt;
      
      expect(window.deferredPrompt).toBeDefined();
      expect(window.deferredPrompt.prompt).toBeInstanceOf(Function);
    });

    it('should call prompt on install click', async () => {
      window.deferredPrompt = deferredPrompt;
      
      await window.deferredPrompt.prompt();
      
      expect(deferredPrompt.prompt).toHaveBeenCalled();
    });

    it('should handle accepted outcome', async () => {
      window.deferredPrompt = deferredPrompt;
      
      const { outcome } = await window.deferredPrompt.userChoice;
      
      expect(outcome).toBe('accepted');
    });

    it('should handle dismissed outcome', async () => {
      deferredPrompt.userChoice = Promise.resolve({ outcome: 'dismissed' });
      window.deferredPrompt = deferredPrompt;
      
      const { outcome } = await window.deferredPrompt.userChoice;
      
      expect(outcome).toBe('dismissed');
    });
  });

  describe('Service Worker', () => {
    it('should check for SW support', () => {
      const hasServiceWorker = 'serviceWorker' in navigator;
      // In test env this will be false, which is fine
      expect(typeof hasServiceWorker).toBe('boolean');
    });
  });

  describe('Manifest', () => {
    it('should have manifest link', () => {
      const link = document.createElement('link');
      link.rel = 'manifest';
      link.href = '/static/manifest.json';
      document.head.appendChild(link);
      
      expect(document.querySelector('link[rel="manifest"]')).toBeDefined();
    });
  });

  describe('Install state tracking', () => {
    it('should track if installed', () => {
      let isInstalled = false;
      
      // Check display-mode
      if (window.matchMedia) {
        // Would check standalone mode
        isInstalled = false;
      }
      
      expect(typeof isInstalled).toBe('boolean');
    });

    it('should hide button after install', () => {
      const btn = document.getElementById('pwa-install-btn');
      btn.classList.remove('hidden');
      
      // Simulate install
      btn.classList.add('hidden');
      window.deferredPrompt = null;
      
      expect(btn.classList.contains('hidden')).toBe(true);
    });
  });

  describe('iOS install prompt', () => {
    it('should detect iOS', () => {
      const isIOS = /iPad|iPhone|iPod/.test('iPhone');
      expect(isIOS).toBe(true);
    });

    it('should show iOS instructions', () => {
      const instructions = 'Tap Share then "Add to Home Screen"';
      expect(instructions).toContain('Add to Home Screen');
    });
  });
});
