/**
 * View Command Unit Tests
 * Tests for /view command - jump to another user's view
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('../../core/app.js', () => ({
  app: {
    state: {}
  }
}));

vi.mock('../../utils/authManager.js', () => ({
  ensureFeatureAccess: vi.fn(() => Promise.resolve(true))
}));

import { view } from '../../commands/view.js';
import { ensureFeatureAccess } from '../../utils/authManager.js';

describe('View Command', () => {
  let mockSocket;
  let mockDisplayMessage;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = { emit: vi.fn() };
    mockDisplayMessage = vi.fn();
  });

  describe('exports', () => {
    it('should export view command object', () => {
      expect(view).toBeDefined();
    });

    it('should have execute function', () => {
      expect(view.execute).toBeInstanceOf(Function);
    });

    it('should have getHelpText function', () => {
      expect(view.getHelpText).toBeInstanceOf(Function);
    });

    it('should have description', () => {
      expect(view.description).toBeDefined();
    });
  });

  describe('getHelpText', () => {
    it('should return help text', () => {
      const helpText = view.getHelpText();
      expect(helpText).toContain('/view');
      expect(helpText).toContain('name or id');
    });
  });

  describe('execute', () => {
    it('should check password protection', async () => {
      await view.execute(mockSocket, mockDisplayMessage, 'abc123');
      
      expect(ensureFeatureAccess).toHaveBeenCalled();
    });

    it('should deny access if password not validated', async () => {
      ensureFeatureAccess.mockResolvedValueOnce(false);
      
      await view.execute(mockSocket, mockDisplayMessage, 'abc123');
      
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Password required.'),
        expect.objectContaining({ icon: 'stop' })
      );
      expect(mockSocket.emit).not.toHaveBeenCalled();
    });

    it('should show usage if no target provided', async () => {
      await view.execute(mockSocket, mockDisplayMessage, '');
      
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Specify a profile name or session ID.'),
        expect.objectContaining({ icon: 'lightbulb' })
      );
    });

    it('should show usage if only whitespace provided', async () => {
      await view.execute(mockSocket, mockDisplayMessage, '   ');
      
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Specify a profile name or session ID.'),
        expect.objectContaining({ icon: 'lightbulb' })
      );
    });

    it('should emit request_view_info event', async () => {
      await view.execute(mockSocket, mockDisplayMessage, 'target123');
      
      expect(mockSocket.emit).toHaveBeenCalledWith('request_view_info', {
        target_session_id: 'target123'
      });
    });

    it('should trim session_id', async () => {
      await view.execute(mockSocket, mockDisplayMessage, '  target123  ');
      
      expect(mockSocket.emit).toHaveBeenCalledWith('request_view_info', {
        target_session_id: 'target123'
      });
    });

    it('should display requesting message', async () => {
      await view.execute(mockSocket, mockDisplayMessage, 'target123');
      
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Viewing target123.'),
        expect.objectContaining({ icon: 'eye' })
      );
    });
  });
});
