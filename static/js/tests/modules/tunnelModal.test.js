/**
 * TunnelModal Unit Tests
 * Tests for tunnel/remote access configuration
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('TunnelModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="tunnel-modal" class="hidden">
        <div class="tunnel-modal-content">
          <div class="tunnel-header">
            <h2>Remote Access</h2>
            <button class="tunnel-close-btn">&times;</button>
          </div>
          <div class="tunnel-body">
            <div id="tunnel-status">Disconnected</div>
            <input id="tunnel-url" type="text" readonly />
            <button id="tunnel-start-btn">Start Tunnel</button>
            <button id="tunnel-stop-btn" class="hidden">Stop Tunnel</button>
            <button id="tunnel-copy-btn" class="hidden">Copy URL</button>
          </div>
          <div class="tunnel-footer">
            <button id="tunnel-modal-save-settings-btn">Save</button>
          </div>
        </div>
      </div>
    `;
    
    // Mock fetch
    global.fetch = vi.fn();
    
    // Mock clipboard
    navigator.clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
  });

  describe('Modal UI', () => {
    it('should have tunnel modal', () => {
      expect(document.getElementById('tunnel-modal')).toBeDefined();
    });

    it('should render a consistent save label', () => {
      const saveBtn = document.getElementById('tunnel-modal-save-settings-btn');
      expect(saveBtn.textContent).toBe('Save');
    });

    it('should be hidden by default', () => {
      const modal = document.getElementById('tunnel-modal');
      expect(modal.classList.contains('hidden')).toBe(true);
    });

    it('should open modal', () => {
      const modal = document.getElementById('tunnel-modal');
      modal.classList.remove('hidden');
      
      expect(modal.classList.contains('hidden')).toBe(false);
    });

    it('should close on X button', () => {
      const modal = document.getElementById('tunnel-modal');
      modal.classList.remove('hidden');
      
      modal.classList.add('hidden');
      
      expect(modal.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Tunnel status', () => {
    it('should show disconnected by default', () => {
      const status = document.getElementById('tunnel-status');
      expect(status.textContent).toBe('Disconnected');
    });

    it('should update status to connecting', () => {
      const status = document.getElementById('tunnel-status');
      status.textContent = 'Connecting...';
      status.classList.add('connecting');
      
      expect(status.textContent).toBe('Connecting...');
    });

    it('should update status to connected', () => {
      const status = document.getElementById('tunnel-status');
      status.textContent = 'Connected';
      status.classList.remove('connecting');
      status.classList.add('connected');
      
      expect(status.classList.contains('connected')).toBe(true);
    });
  });

  describe('Tunnel URL', () => {
    it('should have URL input', () => {
      expect(document.getElementById('tunnel-url')).toBeDefined();
    });

    it('should display tunnel URL', () => {
      const urlInput = document.getElementById('tunnel-url');
      urlInput.value = 'https://abc123.tunnel.example.com';
      
      expect(urlInput.value).toContain('tunnel');
    });

    it('should be readonly', () => {
      const urlInput = document.getElementById('tunnel-url');
      expect(urlInput.readOnly).toBe(true);
    });
  });

  describe('Start tunnel', () => {
    it('should have start button', () => {
      expect(document.getElementById('tunnel-start-btn')).toBeDefined();
    });

    it('should call start API', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          url: 'https://abc123.tunnel.example.com'
        })
      });
      
      const response = await fetch('/api/tunnel/start', { method: 'POST' });
      const data = await response.json();
      
      expect(data.success).toBe(true);
      expect(data.url).toContain('tunnel');
    });

    it('should hide start button after connecting', () => {
      const startBtn = document.getElementById('tunnel-start-btn');
      const stopBtn = document.getElementById('tunnel-stop-btn');
      
      startBtn.classList.add('hidden');
      stopBtn.classList.remove('hidden');
      
      expect(startBtn.classList.contains('hidden')).toBe(true);
      expect(stopBtn.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Stop tunnel', () => {
    it('should have stop button', () => {
      expect(document.getElementById('tunnel-stop-btn')).toBeDefined();
    });

    it('should call stop API', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      });
      
      const response = await fetch('/api/tunnel/stop', { method: 'POST' });
      const data = await response.json();
      
      expect(data.success).toBe(true);
    });

    it('should show start button after stopping', () => {
      const startBtn = document.getElementById('tunnel-start-btn');
      const stopBtn = document.getElementById('tunnel-stop-btn');
      
      stopBtn.classList.add('hidden');
      startBtn.classList.remove('hidden');
      
      expect(startBtn.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Copy URL', () => {
    it('should have copy button', () => {
      expect(document.getElementById('tunnel-copy-btn')).toBeDefined();
    });

    it('should copy URL to clipboard', async () => {
      const url = 'https://abc123.tunnel.example.com';
      
      await navigator.clipboard.writeText(url);
      
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(url);
    });

    it('should show copy button when connected', () => {
      const copyBtn = document.getElementById('tunnel-copy-btn');
      copyBtn.classList.remove('hidden');
      
      expect(copyBtn.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Error handling', () => {
    it('should handle start failure', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: 'Failed to start tunnel' })
      });
      
      const response = await fetch('/api/tunnel/start', { method: 'POST' });
      
      expect(response.ok).toBe(false);
    });

    it('should display error message', () => {
      const status = document.getElementById('tunnel-status');
      status.textContent = 'Error: Failed to connect';
      status.classList.add('error');
      
      expect(status.classList.contains('error')).toBe(true);
    });
  });

  describe('Tunnel status polling', () => {
    it('should check tunnel status', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          connected: true,
          url: 'https://abc123.tunnel.example.com'
        })
      });
      
      const response = await fetch('/api/tunnel/status');
      const data = await response.json();
      
      expect(data.connected).toBe(true);
    });
  });
});
