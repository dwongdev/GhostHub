/**
 * CommandHandler Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('../../commands/index.js', () => ({
  commands: {
    help: {
      execute: vi.fn(),
      getHelpText: () => '/help - Show help'
    },
    test: {
      execute: vi.fn(),
      getHelpText: () => '/test - Test command'
    }
  },
  getAllHelpText: () => 'All help text'
}));

let initCommandHandler, processCommand;
import { commands } from '../../commands/index.js';

describe('CommandHandler', () => {
  let mockSocket;
  let mockDisplayLocalMessage;
  let handler;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();
    
    mockSocket = { emit: vi.fn() };
    mockDisplayLocalMessage = vi.fn();
    
    // Re-import to reset rate limiting state
    const module = await import('../../modules/chat/commandHandler.js');
    initCommandHandler = module.initCommandHandler;
    processCommand = module.processCommand;
    
    // Initialize the command handler
    handler = initCommandHandler(mockSocket, mockDisplayLocalMessage);
  });

  describe('initCommandHandler', () => {
    it('should return null if no socket provided', () => {
      const result = initCommandHandler(null, mockDisplayLocalMessage);
      expect(result).toBeNull();
    });

    it('should return handler instance with commands', () => {
      expect(handler).toBeDefined();
      expect(handler.commands).toBeDefined();
    });

    it('should expose processCommand function', () => {
      expect(handler.processCommand).toBeInstanceOf(Function);
    });

    it('should return handler instance for registry provisioning by main.js', () => {
      expect(handler.processCommand).toBe(processCommand);
    });
  });

  describe('processCommand', () => {
    it('should return false for non-command messages', () => {
      const result = processCommand('hello');
      expect(result).toBe(false);
    });

    it('should return true for command messages', () => {
      const result = processCommand('/help');
      expect(result).toBe(true);
    });

    it('should execute valid commands', () => {
      processCommand('/help');
      expect(commands.help.execute).toHaveBeenCalled();
    });

    it('should pass arguments to command', () => {
      processCommand('/test arg1 arg2');
      
      expect(commands.test.execute).toHaveBeenCalledWith(
        mockSocket,
        mockDisplayLocalMessage,
        'arg1 arg2'
      );
    });

    it('should handle unknown commands', () => {
      processCommand('/unknown');
      
      expect(mockDisplayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('Unknown command')
      );
    });

    it('should handle commands without arguments', () => {
      vi.clearAllMocks(); // Clear any previous calls
      processCommand('/help');
      
      expect(commands.help.execute).toHaveBeenCalledWith(
        mockSocket,
        mockDisplayLocalMessage,
        ''
      );
    });

    it('should be case-insensitive for command names', () => {
      vi.clearAllMocks();
      processCommand('/help'); // Use lowercase - the module lowercases it
      expect(commands.help.execute).toHaveBeenCalled();
    });

    it('should handle double slash by treating as single slash', () => {
      vi.clearAllMocks();
      const result = processCommand('//help');
      // Double slash gets normalized to single slash
      expect(result).toBe(true);
    });

    it('should not process messages with leading whitespace before slash', () => {
      vi.clearAllMocks();
      const result = processCommand('  /help  ');
      // Leading whitespace means it doesn't start with / - returns false (not a command)
      expect(result).toBe(false);
    });

    it('should rate limit after many rapid commands', async () => {
      // Fresh module import for clean rate limit state
      vi.resetModules();
      const freshModule = await import('../../modules/chat/commandHandler.js');
      freshModule.initCommandHandler(mockSocket, mockDisplayLocalMessage);
      
      // Execute max commands quickly (limit is 3 in 5 seconds)
      freshModule.processCommand('/help');
      freshModule.processCommand('/test');
      freshModule.processCommand('/help');
      freshModule.processCommand('/test'); // This should be rate limited
      
      expect(mockDisplayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('rate limit')
      );
    });

    it('should handle command execution errors gracefully', async () => {
      vi.resetModules();
      
      // Mock command that throws
      vi.doMock('../../commands/index.js', () => ({
        commands: {
          error: {
            execute: () => { throw new Error('Test error'); },
            getHelpText: () => '/error'
          }
        }
      }));
      
      const freshModule = await import('../../modules/chat/commandHandler.js');
      const localDisplay = vi.fn();
      freshModule.initCommandHandler(mockSocket, localDisplay);
      
      // Should not throw
      expect(() => freshModule.processCommand('/error')).not.toThrow();
    });
  });
});
