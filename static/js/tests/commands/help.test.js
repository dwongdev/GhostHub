/**
 * Help Command Unit Tests
 * Tests for /help command
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../commands/helpUtils.js', () => ({
  getAllHelpText: vi.fn(() => '• /help - Show help\n• /search - Search media')
}));

import { help } from '../../commands/help.js';
import { getAllHelpText } from '../../commands/helpUtils.js';

describe('Help Command', () => {
  let mockSocket;
  let mockDisplayMessage;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = { emit: vi.fn() };
    mockDisplayMessage = vi.fn();

    // Mock window.ragotModules.commandHandler.commands
    global.window = {
      ragotModules: {
        commandHandler: {
          commands: {
            help: help,
            search: { getHelpText: () => '• /search - Search' }
          }
        }
      }
    };
  });

  describe('exports', () => {
    it('should export help command object', () => {
      expect(help).toBeDefined();
    });

    it('should have execute function', () => {
      expect(help.execute).toBeInstanceOf(Function);
    });

    it('should have getHelpText function', () => {
      expect(help.getHelpText).toBeInstanceOf(Function);
    });

    it('should have description', () => {
      expect(help.description).toBeDefined();
      expect(typeof help.description).toBe('string');
    });
  });

  describe('getHelpText', () => {
    it('should return help text for help command', () => {
      const helpText = help.getHelpText();
      expect(helpText).toContain('/help');
    });
  });

  describe('execute', () => {
    it('should call getAllHelpText', () => {
      help.execute(mockSocket, mockDisplayMessage, '');

      expect(getAllHelpText).toHaveBeenCalled();
    });

    it('should display help message', () => {
      help.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('Available commands'),
        expect.objectContaining({ icon: 'lightbulb' })
      );
    });

    it('should include all command help texts', () => {
      help.execute(mockSocket, mockDisplayMessage, '');

      expect(mockDisplayMessage).toHaveBeenCalledWith(
        expect.stringContaining('/help'),
        expect.objectContaining({ icon: 'lightbulb' })
      );
    });
  });
});
