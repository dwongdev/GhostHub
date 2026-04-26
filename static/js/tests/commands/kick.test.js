/**
 * Kick Command Unit Tests
 * Tests for /kick command - admin only
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

import { kick } from '../../commands/kick.js';

describe('Kick Command', () => {
  let mockSocket;
  let mockDisplayMessage;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = { emit: vi.fn() };
    mockDisplayMessage = vi.fn();
    global.fetch = vi.fn();
  });

  describe('exports', () => {
    it('should export kick command object', () => {
      expect(kick).toBeDefined();
    });

    it('should have execute function', () => {
      expect(kick.execute).toBeInstanceOf(Function);
    });

    it('should have getHelpText function', () => {
      expect(kick.getHelpText).toBeInstanceOf(Function);
    });
  });

  describe('getHelpText', () => {
    it('should return help text', () => {
      const helpText = kick.getHelpText();
      expect(helpText).toContain('/kick');
      expect(helpText).toContain('Admin');
    });
  });

  describe('execute', () => {
    it('should show usage if no args provided', async () => {
      await kick.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Specify a profile name or user ID.'),
        expect.objectContaining({ icon: 'lightbulb' })
      );
    });

    it('should show usage if args is whitespace only', async () => {
      await kick.execute(mockSocket, mockDisplayMessage, '   ');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Specify a profile name or user ID.'),
        expect.objectContaining({ icon: 'lightbulb' })
      );
    });

    it('should surface a generic failure when admin verification errors', async () => {
      global.fetch.mockRejectedValue(new Error('Network error'));

      await kick.execute(mockSocket, mockDisplayMessage, 'abc');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Kick failed.'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should check admin status', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ isAdmin: true })
      });

      await kick.execute(mockSocket, mockDisplayMessage, 'abcd1234');

      expect(fetch).toHaveBeenCalledWith('/api/admin/status');
    });

    it('should reject non-admin users', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ isAdmin: false })
      });

      await kick.execute(mockSocket, mockDisplayMessage, 'abcd1234');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Admin only.'),
        expect.objectContaining({ icon: 'stop' })
      );
      expect(mockSocket.emit).not.toHaveBeenCalled();
    });

    it('should emit kick event for admin users', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ isAdmin: true })
      });

      await kick.execute(mockSocket, mockDisplayMessage, 'abcd1234');

      expect(mockSocket.emit).toHaveBeenCalledWith(
        'admin_kick_user',
        { target_user_id: 'abcd1234' }
      );
    });

    it('should show attempting message for admin', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ isAdmin: true })
      });

      await kick.execute(mockSocket, mockDisplayMessage, 'abcd1234');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Kicked abcd1234.'),
        expect.objectContaining({ icon: 'checkCircle' })
      );
    });

    it('should handle admin status check failure', async () => {
      global.fetch.mockResolvedValue({ ok: false, status: 500 });

      await kick.execute(mockSocket, mockDisplayMessage, 'abcd1234');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Could not verify admin status'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should handle network errors', async () => {
      global.fetch.mockRejectedValue(new Error('Network error'));

      await kick.execute(mockSocket, mockDisplayMessage, 'abcd1234');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Kick failed.'),
        expect.objectContaining({ icon: 'x' })
      );
    });
  });
});
