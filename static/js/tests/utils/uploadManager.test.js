/**
 * UploadManager Unit Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as uploadManager from '../../utils/uploadManager.js';

describe('UploadManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uploadManager.resetUploadState();
    
    // Mock XMLHttpRequest
    const mockXHR = {
      open: vi.fn(),
      send: vi.fn(),
      setRequestHeader: vi.fn(),
      upload: {
        addEventListener: vi.fn()
      },
      addEventListener: vi.fn((event, handler) => {
        if (event === 'load') {
          // Simulate successful upload
          setTimeout(() => handler(), 0);
        }
      }),
      readyState: 4,
      status: 200,
      responseText: '{}'
    };
    global.XMLHttpRequest = vi.fn(() => mockXHR);
  });

  afterEach(() => {
    uploadManager.cancelAllUploads();
  });

  describe('formatBytes', () => {
    it('should format 0 bytes', () => {
      expect(uploadManager.formatBytes(0)).toBe('0 B');
    });

    it('should format bytes', () => {
      expect(uploadManager.formatBytes(500)).toBe('500 B');
    });

    it('should format kilobytes', () => {
      expect(uploadManager.formatBytes(1024)).toBe('1 KB');
      expect(uploadManager.formatBytes(1536)).toBe('1.5 KB');
    });

    it('should format megabytes', () => {
      expect(uploadManager.formatBytes(1048576)).toBe('1 MB');
      expect(uploadManager.formatBytes(5242880)).toBe('5 MB');
    });

    it('should format gigabytes', () => {
      expect(uploadManager.formatBytes(1073741824)).toBe('1 GB');
    });

    it('should format terabytes', () => {
      expect(uploadManager.formatBytes(1099511627776)).toBe('1 TB');
    });
  });

  describe('isUploadCancelled', () => {
    it('should return false initially', () => {
      expect(uploadManager.isUploadCancelled()).toBe(false);
    });

    it('should return true after cancelAllUploads', () => {
      uploadManager.cancelAllUploads();
      expect(uploadManager.isUploadCancelled()).toBe(true);
    });
  });

  describe('Dynamic Settings', () => {
    it('should return default concurrency initially', () => {
      // Default is 2 on desktop (non-mobile mock in beforeEach)
      expect(uploadManager.getMaxConcurrentChunks()).toBe(2);
    });

    it('should return null hardware tier initially', () => {
      expect(uploadManager.getHardwareTier()).toBeNull();
    });

    it('should return negotiated settings after negotiation', async () => {
      const mockSettings = {
        chunk_size: 4194304,
        max_concurrent_chunks: 6,
        hardware_tier: 'PRO',
        tier: 'fast'
      };
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockSettings)
      });

      // Start an upload to trigger negotiation
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' });
      await uploadManager.uploadFiles([{ file: mockFile, relativePath: '' }], '/drive');

      expect(uploadManager.getMaxConcurrentChunks()).toBe(6);
      expect(uploadManager.getHardwareTier()).toBe('PRO');
    });
  });

  describe('resetUploadState', () => {
    it('should reset cancelled state', () => {
      uploadManager.cancelAllUploads();
      expect(uploadManager.isUploadCancelled()).toBe(true);
      
      uploadManager.resetUploadState();
      expect(uploadManager.isUploadCancelled()).toBe(false);
    });
  });

  describe('Background Session', () => {
    it('should track current upload session', async () => {
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' });
      const files = [{ file: mockFile, relativePath: '' }];
      
      // Start upload (it's async, we don't await yet to check session)
      const uploadPromise = uploadManager.uploadFiles(files, '/drive', '');
      
      const session = uploadManager.getCurrentUploadSession();
      expect(session).not.toBeNull();
      expect(session.files).toHaveLength(1);
      expect(session.isRunning).toBe(true);
      
      await uploadPromise;
      expect(session.isRunning).toBe(false);
    });

    it('should allow updating session callbacks', async () => {
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' });
      const files = [{ file: mockFile, relativePath: '' }];
      
      const uploadPromise = uploadManager.uploadFiles(files, '/drive', '');
      
      const progressFn = vi.fn();
      const completeFn = vi.fn();
      
      uploadManager.updateSessionCallbacks(progressFn, completeFn);
      
      await uploadPromise;
      
      expect(progressFn).toHaveBeenCalled();
      expect(completeFn).toHaveBeenCalled();
    });

    it('should store detailed log of results', async () => {
      const mockFile1 = new File(['test1'], 'test1.txt', { type: 'text/plain' });
      const mockFile2 = new File(['test2'], 'test2.txt', { type: 'text/plain' });
      const files = [
        { file: mockFile1, relativePath: '' },
        { file: mockFile2, relativePath: '' }
      ];
      
      await uploadManager.uploadFiles(files, '/drive', '');
      
      const session = uploadManager.getCurrentUploadSession();
      expect(session.results.log).toHaveLength(2);
      expect(session.results.log[0].filename).toBe('test1.txt');
      expect(session.results.log[0].success).toBe(true);
    });
  });

  describe('cancelAllUploads', () => {
    it('should set cancelled flag', () => {
      uploadManager.cancelAllUploads();
      expect(uploadManager.isUploadCancelled()).toBe(true);
    });

    it('should attempt to cancel active uploads', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ upload_id: 'test-123' })
      });
      
      uploadManager.cancelAllUploads();
      
      expect(uploadManager.isUploadCancelled()).toBe(true);
    });
  });

  describe('uploadFiles', () => {
    it('should handle empty file list', async () => {
      const result = await uploadManager.uploadFiles([], '/test/path', 'subfolder');
      
      expect(result.success).toBe(0);
      expect(result.failed).toBe(0);
      expect(result.errors).toHaveLength(0);
    });

    it('should track progress', async () => {
      const progressFn = vi.fn();
      const mockFile = new File(['test content'], 'test.txt', { type: 'text/plain' });
      
      const mockXHR = {
        open: vi.fn(),
        send: vi.fn(),
        upload: {
          addEventListener: vi.fn((event, handler) => {
            if (event === 'progress') {
              handler({ lengthComputable: true, loaded: 50, total: 100 });
            }
          })
        },
        addEventListener: vi.fn((event, handler) => {
          if (event === 'load') {
            setTimeout(() => handler(), 10);
          }
        }),
        status: 200,
        responseText: '{}'
      };
      global.XMLHttpRequest = vi.fn(() => mockXHR);
      
      const files = [{ file: mockFile, relativePath: '' }];
      
      await uploadManager.uploadFiles(files, '/drive', '', progressFn);
      
      // Progress should be called (at minimum at end)
      expect(progressFn).toHaveBeenCalled();
    });

    it('should call onFileComplete callback', async () => {
      const onFileComplete = vi.fn();
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' });
      
      const mockXHR = {
        open: vi.fn(),
        send: vi.fn(),
        upload: { addEventListener: vi.fn() },
        addEventListener: vi.fn((event, handler) => {
          if (event === 'load') setTimeout(() => handler(), 0);
        }),
        status: 200,
        responseText: '{}'
      };
      global.XMLHttpRequest = vi.fn(() => mockXHR);
      
      const files = [{ file: mockFile, relativePath: '' }];
      await uploadManager.uploadFiles(files, '/drive', '', null, onFileComplete);
      
      expect(onFileComplete).toHaveBeenCalledWith('test.txt', true);
    });

    it('should respect cancelled state', async () => {
      // Cancel uploads first
      uploadManager.cancelAllUploads();
      
      // Verify cancelled state
      expect(uploadManager.isUploadCancelled()).toBe(true);
      
      // Reset for next test
      uploadManager.resetUploadState();
      expect(uploadManager.isUploadCancelled()).toBe(false);
    });
  });
});
