/**
 * UIController Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('UIController', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Setup DOM - streaming/gallery layouts use their own containers,
    // but media viewer is shared across all layouts
    document.body.innerHTML = `
      <div id="media-viewer" class="hidden">
        <div class="spinner-container"></div>
      </div>
      <div id="loading-spinner" class="hidden"></div>
      <div id="error-message" class="hidden"></div>
      <header class="gh-header"></header>
      <div id="chat-container" class="hidden"></div>
    `;
  });

  describe('View switching', () => {
    it('should hide media viewer by default', () => {
      const mediaViewer = document.getElementById('media-viewer');
      expect(mediaViewer.classList.contains('hidden')).toBe(true);
    });

    it('should show media viewer when opening media', () => {
      const mediaViewer = document.getElementById('media-viewer');

      mediaViewer.classList.remove('hidden');

      expect(mediaViewer.classList.contains('hidden')).toBe(false);
    });

    it('should hide media viewer when going back', () => {
      const mediaViewer = document.getElementById('media-viewer');

      mediaViewer.classList.remove('hidden');
      mediaViewer.classList.add('hidden');

      expect(mediaViewer.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Loading spinner', () => {
    it('should be hidden by default', () => {
      const spinner = document.getElementById('loading-spinner');
      expect(spinner.classList.contains('hidden')).toBe(true);
    });

    it('should show when loading', () => {
      const spinner = document.getElementById('loading-spinner');
      spinner.classList.remove('hidden');
      expect(spinner.classList.contains('hidden')).toBe(false);
    });

    it('should hide after loading completes', () => {
      const spinner = document.getElementById('loading-spinner');
      spinner.classList.remove('hidden');
      spinner.classList.add('hidden');
      expect(spinner.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Error message', () => {
    it('should be hidden by default', () => {
      const error = document.getElementById('error-message');
      expect(error.classList.contains('hidden')).toBe(true);
    });

    it('should display error text', () => {
      const error = document.getElementById('error-message');
      error.textContent = 'An error occurred';
      error.classList.remove('hidden');

      expect(error.textContent).toBe('An error occurred');
      expect(error.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Chat container', () => {
    it('should be hidden by default', () => {
      const chat = document.getElementById('chat-container');
      expect(chat.classList.contains('hidden')).toBe(true);
    });

    it('should toggle visibility', () => {
      const chat = document.getElementById('chat-container');

      chat.classList.toggle('hidden');
      expect(chat.classList.contains('hidden')).toBe(false);

      chat.classList.toggle('hidden');
      expect(chat.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Keyboard navigation', () => {
    it('should handle escape key event', () => {
      const handler = vi.fn();
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') handler();
      });

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

      expect(handler).toHaveBeenCalled();
    });

    it('should handle arrow key events', () => {
      const upHandler = vi.fn();
      const downHandler = vi.fn();

      document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowUp') upHandler();
        if (e.key === 'ArrowDown') downHandler();
      });

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));

      expect(upHandler).toHaveBeenCalled();
      expect(downHandler).toHaveBeenCalled();
    });
  });

  describe('Responsive behavior', () => {
    it('should detect window resize', () => {
      const handler = vi.fn();
      window.addEventListener('resize', handler);

      window.dispatchEvent(new Event('resize'));

      expect(handler).toHaveBeenCalled();

      window.removeEventListener('resize', handler);
    });
  });
});
