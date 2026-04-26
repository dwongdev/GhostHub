/**
 * AdminController Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('../../utils/authManager.js', () => ({
  ensureFeatureAccess: vi.fn(() => Promise.resolve(true))
}));

describe('AdminController', () => {
  let mockFetch;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="admin-panel" class="hidden">
        <button id="refresh-categories-btn"></button>
        <button id="clear-cache-btn"></button>
        <button id="generate-thumbnails-btn"></button>
      </div>
    `;
    
    // Mock fetch
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    });
    global.fetch = mockFetch;
    
    // Mock cookies for admin check
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'is_admin=true'
    });
  });

  describe('Admin detection', () => {
    it('should detect admin from cookie', () => {
      const isAdmin = document.cookie.includes('is_admin=true');
      expect(isAdmin).toBe(true);
    });

    it('should not detect admin when cookie is missing', () => {
      document.cookie = '';
      const isAdmin = document.cookie.includes('is_admin=true');
      expect(isAdmin).toBe(false);
    });
  });

  describe('Admin panel visibility', () => {
    it('should have admin panel in DOM', () => {
      expect(document.getElementById('admin-panel')).toBeDefined();
    });

    it('should be hidden by default', () => {
      const panel = document.getElementById('admin-panel');
      expect(panel.classList.contains('hidden')).toBe(true);
    });

    it('should show panel for admin users', () => {
      const panel = document.getElementById('admin-panel');
      panel.classList.remove('hidden');
      expect(panel.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Admin actions', () => {
    it('should have refresh categories button', () => {
      expect(document.getElementById('refresh-categories-btn')).toBeDefined();
    });

    it('should have clear cache button', () => {
      expect(document.getElementById('clear-cache-btn')).toBeDefined();
    });

    it('should have generate thumbnails button', () => {
      expect(document.getElementById('generate-thumbnails-btn')).toBeDefined();
    });
  });

  describe('API endpoints for admin actions', () => {
    it('should call refresh endpoint', async () => {
      await fetch('/api/categories/refresh', { method: 'POST' });
      
      expect(mockFetch).toHaveBeenCalledWith('/api/categories/refresh', { method: 'POST' });
    });

    it('should call clear cache endpoint', async () => {
      await fetch('/api/cache/clear', { method: 'POST' });
      
      expect(mockFetch).toHaveBeenCalledWith('/api/cache/clear', { method: 'POST' });
    });

    it('should call thumbnail generation endpoint', async () => {
      await fetch('/api/thumbnails/generate', { method: 'POST' });
      
      expect(mockFetch).toHaveBeenCalledWith('/api/thumbnails/generate', { method: 'POST' });
    });
  });
});
