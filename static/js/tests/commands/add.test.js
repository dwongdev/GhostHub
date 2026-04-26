/**
 * Add Command Unit Tests
 * Tests for /add command - adds media to shared playlist
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/liveVisibility.js', () => ({
  refreshAllLayouts: vi.fn(() => Promise.resolve())
}));

import { add } from '../../commands/add.js';
import { refreshAllLayouts } from '../../utils/liveVisibility.js';

describe('Add Command', () => {
  let mockSocket;
  let mockDisplayMessage;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = { emit: vi.fn() };
    mockDisplayMessage = vi.fn();
    global.fetch = vi.fn();

    window.ragotModules = {
      appState: {
        currentCategoryId: 'movies',
        currentMediaIndex: 0,
        fullMediaList: [
          { url: '/media/movie1.mp4', name: 'Movie 1', type: 'video' },
          { url: '/media/movie2.mp4', name: 'Movie 2', type: 'video' }
        ]
      }
    };
  });

  describe('exports', () => {
    it('should export add command object', () => {
      expect(add).toBeDefined();
    });

    it('should have execute function', () => {
      expect(add.execute).toBeInstanceOf(Function);
    });

    it('should have getHelpText function', () => {
      expect(add.getHelpText).toBeInstanceOf(Function);
    });

    it('should have description', () => {
      expect(add.description).toBeDefined();
      expect(typeof add.description).toBe('string');
    });
  });

  describe('getHelpText', () => {
    it('should return help text', () => {
      const helpText = add.getHelpText();
      expect(helpText).toContain('/add');
    });
  });

  describe('execute', () => {
    it('should show error if no category is loaded', async () => {
      window.ragotModules.appState.currentCategoryId = null;

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('No media item open.'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should show error if no media index', async () => {
      window.ragotModules.appState.currentMediaIndex = null;

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('No media item open.'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should show error if index out of range', async () => {
      window.ragotModules.appState.currentMediaIndex = 100;

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('No media item open.'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should call API to add to playlist', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      });

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(fetch).toHaveBeenCalledWith(
        '/api/session/playlist/add',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
      );
    });

    it('should show success message on success', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      });

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Added "Movie 1" to playlist.'),
        expect.objectContaining({ icon: 'checkCircle' })
      );
    });

    it('should refresh layouts after adding', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true })
      });

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(refreshAllLayouts).toHaveBeenCalled();
    });

    it('should show error message on failure', async () => {
      global.fetch.mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ success: false, message: 'Failed to add' })
      });

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should handle fetch errors', async () => {
      global.fetch.mockRejectedValue(new Error('Network error'));

      await add.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Failed to add.'),
        expect.objectContaining({ icon: 'x' })
      );
    });
  });
});
