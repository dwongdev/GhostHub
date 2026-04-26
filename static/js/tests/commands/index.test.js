/**
 * Commands Index Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock all command modules
vi.mock('../../modules/chat/manager.js', () => ({
  displayLocalSystemMessage: vi.fn()
}));

vi.mock('../../core/app.js', () => ({
  app: {
    state: {
      currentCategoryId: null,
      fullMediaList: []
    }
  }
}));

vi.mock('../../utils/authManager.js', () => ({
  ensureFeatureAccess: vi.fn(() => Promise.resolve(true))
}));

// Import after mocking
import { commands, getAllHelpText } from '../../commands/index.js';

describe('Commands Index', () => {
  describe('commands object', () => {
    it('should export all available commands', () => {
      expect(commands).toBeDefined();
      expect(typeof commands).toBe('object');
    });

    it('should include help command', () => {
      expect(commands.help).toBeDefined();
      expect(commands.help.execute).toBeInstanceOf(Function);
      expect(commands.help.getHelpText).toBeInstanceOf(Function);
    });

    it('should include myview command', () => {
      expect(commands.myview).toBeDefined();
    });

    it('should include view command', () => {
      expect(commands.view).toBeDefined();
    });

    it('should include random command', () => {
      expect(commands.random).toBeDefined();
    });

    it('should include kick command', () => {
      expect(commands.kick).toBeDefined();
    });

    it('should include search command', () => {
      expect(commands.search).toBeDefined();
    });

    it('should include find as alias for search', () => {
      expect(commands.find).toBeDefined();
    });

    it('should include add command', () => {
      expect(commands.add).toBeDefined();
    });

    it('should include play command', () => {
      expect(commands.play).toBeDefined();
    });

    it('should include remove command', () => {
      expect(commands.remove).toBeDefined();
    });
  });

  describe('getAllHelpText', () => {
    it('should return a string with all help texts', () => {
      const helpText = getAllHelpText();
      
      expect(typeof helpText).toBe('string');
      expect(helpText.length).toBeGreaterThan(0);
    });

    it('should include help from all commands', () => {
      const helpText = getAllHelpText();
      
      // Check that various commands are mentioned
      expect(helpText).toContain('/help');
    });

    it('should join help texts with newlines', () => {
      const helpText = getAllHelpText();
      
      // Should have newlines separating entries
      expect(helpText).toContain('\n');
    });
  });

  describe('command structure', () => {
    it('all commands should have getHelpText function', () => {
      Object.entries(commands).forEach(([name, cmd]) => {
        expect(cmd.getHelpText, `${name} should have getHelpText`).toBeInstanceOf(Function);
      });
    });

    it('all commands should have execute function or be an object with execute', () => {
      Object.entries(commands).forEach(([name, cmd]) => {
        const hasExecute = typeof cmd.execute === 'function' || 
                          (typeof cmd === 'object' && typeof cmd.execute === 'function');
        expect(hasExecute, `${name} should have execute function`).toBe(true);
      });
    });
  });
});


