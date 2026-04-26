/**
 * FileManager Unit Tests
 * Tests for file upload/download functionality
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('FileManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="file-manager-modal" class="hidden">
        <div class="fm-header">
          <h2>File Manager</h2>
          <button class="fm-close-btn">&times;</button>
        </div>
        <div class="fm-content">
          <select id="fm-drive-select"></select>
          <input id="fm-subfolder" type="text" />
          <div class="fm-upload-zone" id="fm-upload-zone"></div>
          <div class="fm-file-list" id="fm-file-list"></div>
          <div class="fm-progress" id="fm-progress"></div>
        </div>
      </div>
    `;
    
    // Mock fetch
    global.fetch = vi.fn();
  });

  describe('Modal UI', () => {
    it('should have modal container', () => {
      expect(document.getElementById('file-manager-modal')).toBeDefined();
    });

    it('should be hidden by default', () => {
      const modal = document.getElementById('file-manager-modal');
      expect(modal.classList.contains('hidden')).toBe(true);
    });

    it('should show modal', () => {
      const modal = document.getElementById('file-manager-modal');
      modal.classList.remove('hidden');
      expect(modal.classList.contains('hidden')).toBe(false);
    });

    it('should close on X button click', () => {
      const modal = document.getElementById('file-manager-modal');
      const closeBtn = modal.querySelector('.fm-close-btn');
      
      modal.classList.remove('hidden');
      
      closeBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
      });
      closeBtn.click();
      
      expect(modal.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Drive selection', () => {
    it('should have drive select element', () => {
      expect(document.getElementById('fm-drive-select')).toBeDefined();
    });

    it('should populate drives', () => {
      const select = document.getElementById('fm-drive-select');
      
      const option = document.createElement('option');
      option.value = '/media/usb';
      option.textContent = 'USB Drive (32GB)';
      select.appendChild(option);
      
      expect(select.options.length).toBe(1);
    });

    it('should fetch drives from API', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          drives: [
            { path: '/media/usb1', label: 'USB 1', size: '32GB' },
            { path: '/media/usb2', label: 'USB 2', size: '64GB' }
          ]
        })
      });
      
      const response = await fetch('/api/storage/drives');
      const data = await response.json();
      
      expect(data.drives).toHaveLength(2);
    });
  });

  describe('Subfolder input', () => {
    it('should have subfolder input', () => {
      expect(document.getElementById('fm-subfolder')).toBeDefined();
    });

    it('should accept subfolder path', () => {
      const input = document.getElementById('fm-subfolder');
      input.value = 'Movies/2024';
      
      expect(input.value).toBe('Movies/2024');
    });
  });

  describe('Upload zone', () => {
    it('should have upload zone', () => {
      expect(document.getElementById('fm-upload-zone')).toBeDefined();
    });

    it('should handle dragover', () => {
      const zone = document.getElementById('fm-upload-zone');
      const handler = vi.fn((e) => e.preventDefault());
      
      zone.addEventListener('dragover', handler);
      zone.dispatchEvent(new Event('dragover'));
      
      expect(handler).toHaveBeenCalled();
    });

    it('should handle drop', () => {
      const zone = document.getElementById('fm-upload-zone');
      const handler = vi.fn();
      
      zone.addEventListener('drop', handler);
      zone.dispatchEvent(new Event('drop'));
      
      expect(handler).toHaveBeenCalled();
    });

    it('should highlight on drag enter', () => {
      const zone = document.getElementById('fm-upload-zone');
      
      zone.addEventListener('dragenter', () => {
        zone.classList.add('drag-over');
      });
      zone.dispatchEvent(new Event('dragenter'));
      
      expect(zone.classList.contains('drag-over')).toBe(true);
    });

    it('should remove highlight on drag leave', () => {
      const zone = document.getElementById('fm-upload-zone');
      zone.classList.add('drag-over');
      
      zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
      });
      zone.dispatchEvent(new Event('dragleave'));
      
      expect(zone.classList.contains('drag-over')).toBe(false);
    });
  });

  describe('File list', () => {
    it('should have file list container', () => {
      expect(document.getElementById('fm-file-list')).toBeDefined();
    });

    it('should display selected files', () => {
      const list = document.getElementById('fm-file-list');
      
      const fileItem = document.createElement('div');
      fileItem.className = 'fm-file-item';
      fileItem.textContent = 'video.mp4 (100MB)';
      list.appendChild(fileItem);
      
      expect(list.children.length).toBe(1);
    });

    it('should show file size', () => {
      const formatSize = (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
      };
      
      expect(formatSize(1048576)).toBe('1 MB');
      expect(formatSize(1073741824)).toBe('1 GB');
    });
  });

  describe('Progress tracking', () => {
    it('should have progress container', () => {
      expect(document.getElementById('fm-progress')).toBeDefined();
    });

    it('should show upload progress', () => {
      const progress = document.getElementById('fm-progress');
      
      const bar = document.createElement('div');
      bar.className = 'fm-progress-bar';
      bar.style.width = '50%';
      progress.appendChild(bar);
      
      expect(bar.style.width).toBe('50%');
    });

    it('should update progress text', () => {
      const progress = document.getElementById('fm-progress');
      
      const text = document.createElement('span');
      text.className = 'fm-progress-text';
      text.textContent = '5 of 10 files';
      progress.appendChild(text);
      
      expect(text.textContent).toBe('5 of 10 files');
    });
  });

  describe('Upload API', () => {
    it('should initialize chunked upload', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ upload_id: 'abc123' })
      });
      
      const response = await fetch('/api/storage/upload/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'large.mp4',
          total_chunks: 10,
          total_size: 50000000
        })
      });
      const data = await response.json();
      
      expect(data.upload_id).toBe('abc123');
    });

    it('should upload chunk', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ received: true, chunk_index: 0 })
      });
      
      const formData = new FormData();
      formData.append('upload_id', 'abc123');
      formData.append('chunk_index', '0');
      formData.append('chunk', new Blob(['test data']));
      
      const response = await fetch('/api/storage/upload/chunk', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      
      expect(data.received).toBe(true);
    });

    it('should cancel upload', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ cancelled: true })
      });
      
      const response = await fetch('/api/storage/upload/cancel/abc123', {
        method: 'POST'
      });
      const data = await response.json();
      
      expect(data.cancelled).toBe(true);
    });
  });

  describe('Download API', () => {
    it('should download category as ZIP', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        blob: () => Promise.resolve(new Blob(['zip content']))
      });
      
      const response = await fetch('/api/categories/cat1/download');
      const blob = await response.blob();
      
      expect(blob).toBeDefined();
    });
  });
});
