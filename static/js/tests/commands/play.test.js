/**
 * Play Command Unit Tests
 * Tests for /play command - auto-play media
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('../../utils/authManager.js', () => ({
  ensureFeatureAccess: vi.fn(() => Promise.resolve(true))
}));

import { play } from '../../commands/play.js';
import { ensureFeatureAccess } from '../../utils/authManager.js';

describe('Play Command', () => {
  let mockSocket;
  let mockDisplayMessage;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = { emit: vi.fn() };
    mockDisplayMessage = vi.fn();
    
    // Mock window.ragotModules
    window.ragotModules = {
      mediaNavigation: {
        toggleAutoPlay: vi.fn()
      }
    };
  });

  describe('exports', () => {
    it('should export play command object', () => {
      expect(play).toBeDefined();
    });

    it('should have execute function', () => {
      expect(play.execute).toBeInstanceOf(Function);
    });

    it('should have getHelpText function', () => {
      expect(play.getHelpText).toBeInstanceOf(Function);
    });

    it('should have description', () => {
      expect(play.description).toBeDefined();
    });
  });

  describe('getHelpText', () => {
    it('should return help text', () => {
      const helpText = play.getHelpText();
      expect(helpText).toContain('/play');
      expect(helpText).toContain('stop');
    });
  });

  describe('execute', () => {
    it('should check password protection', async () => {
      await play.execute(mockSocket, mockDisplayMessage, '');
      
      expect(ensureFeatureAccess).toHaveBeenCalled();
    });

    it('should deny access if password not validated', async () => {
      ensureFeatureAccess.mockResolvedValueOnce(false);
      
      await play.execute(mockSocket, mockDisplayMessage, '');
      
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Password required.'),
        expect.objectContaining({ icon: 'stop' })
      );
    });

    it('should show error if mediaNavigation not available', async () => {
      window.ragotModules = {};
      
      await play.execute(mockSocket, mockDisplayMessage, '');
      
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Media navigation not available.'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should start auto-play with default interval', async () => {
      await play.execute(mockSocket, mockDisplayMessage, '');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith(10);
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Auto-play started'),
        expect.objectContaining({ icon: 'play' })
      );
    });

    it('should start auto-play with custom interval', async () => {
      await play.execute(mockSocket, mockDisplayMessage, '5');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith(5);
    });

    it('should parse interval from args', async () => {
      await play.execute(mockSocket, mockDisplayMessage, '30');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith(30);
    });

    it('should stop auto-play with stop arg', async () => {
      await play.execute(mockSocket, mockDisplayMessage, 'stop');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith('stop');
      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('stopped'),
        expect.objectContaining({ icon: 'stop' })
      );
    });

    it('should stop auto-play with off arg', async () => {
      await play.execute(mockSocket, mockDisplayMessage, 'off');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith('stop');
    });

    it('should handle case-insensitive stop', async () => {
      await play.execute(mockSocket, mockDisplayMessage, 'STOP');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith('stop');
    });

    it('should ignore invalid interval and use default', async () => {
      await play.execute(mockSocket, mockDisplayMessage, 'invalid');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith(10);
    });

    it('should ignore negative interval and use default', async () => {
      await play.execute(mockSocket, mockDisplayMessage, '-5');
      
      expect(window.ragotModules.mediaNavigation.toggleAutoPlay).toHaveBeenCalledWith(10);
    });
  });
});
