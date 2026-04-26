/**
 * Search Command Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock authManager
vi.mock('../../utils/authManager.js', () => ({
  ensureFeatureAccess: vi.fn(() => Promise.resolve(true))
}));

import { search, find } from '../../commands/search.js';
import { ensureFeatureAccess } from '../../utils/authManager.js';

describe('Search Command', () => {
  let mockSocket;
  let displayLocalMessage;

  beforeEach(() => {
    vi.clearAllMocks();
    
    mockSocket = {};
    displayLocalMessage = vi.fn();
    
    // Setup DOM
    document.body.innerHTML = '<div id="chat-messages"></div>';
    
    // Mock appModules
    window.ragotModules = {
      mediaLoader: {
        viewCategory: vi.fn().mockResolvedValue(undefined)
      }
    };
  });

  describe('search object', () => {
    it('should have required properties', () => {
      expect(search.description).toBeDefined();
      expect(search.getHelpText).toBeInstanceOf(Function);
      expect(search.execute).toBeInstanceOf(Function);
    });

    it('should return help text', () => {
      const helpText = search.getHelpText();
      expect(helpText).toContain('/search');
      expect(helpText).toContain('query');
    });
  });

  describe('execute', () => {
    it('should check password protection', async () => {
      await search.execute(mockSocket, displayLocalMessage, 'test query');
      
      expect(ensureFeatureAccess).toHaveBeenCalled();
    });

    it('should reject access when password validation fails', async () => {
      vi.mocked(ensureFeatureAccess).mockResolvedValueOnce(false);
      
      await search.execute(mockSocket, displayLocalMessage, 'test');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('Password required.'),
        expect.objectContaining({ icon: 'stop' })
      );
    });

    it('should require minimum 2 character query', async () => {
      await search.execute(mockSocket, displayLocalMessage, 'a');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('minimum 2 characters')
      );
    });

    it('should show usage for empty query', async () => {
      await search.execute(mockSocket, displayLocalMessage, '');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('Usage:')
      );
    });

    it('should trim query whitespace', async () => {
      await search.execute(mockSocket, displayLocalMessage, '   ');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('minimum 2 characters')
      );
    });

    it('should display searching message for valid query', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ results: [], total_categories: 0 })
      });
      
      await search.execute(mockSocket, displayLocalMessage, 'test');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('Searching for "test"')
      );
    });

    it('should call search API with encoded query', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ results: [], total_categories: 0 })
      });
      
      await search.execute(mockSocket, displayLocalMessage, 'test query');
      
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/search?q=test%20query')
      );
    });

    it('should handle API errors gracefully', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: 'Server error' })
      });
      
      await search.execute(mockSocket, displayLocalMessage, 'test');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('Search failed')
      );
    });

    it('should handle network errors', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
      
      await search.execute(mockSocket, displayLocalMessage, 'test');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('Search error'),
        expect.objectContaining({ icon: 'x' })
      );
    });

    it('should display no results message', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ results: [], total_categories: 0 })
      });
      
      await search.execute(mockSocket, displayLocalMessage, 'nonexistent');
      
      expect(displayLocalMessage).toHaveBeenCalledWith(
        expect.stringContaining('No results found'),
        expect.objectContaining({ icon: 'search' })
      );
    });

    it('should display results in chat when found', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          results: [
            {
              category_id: 'cat1',
              category_name: 'Test Category',
              matches: [
                { filename: 'test.mp4', type: 'video', url: '/media/test.mp4' }
              ],
              total_matches: 1
            }
          ],
          total_categories: 1
        })
      });
      
      await search.execute(mockSocket, displayLocalMessage, 'test');

      const htmlCall = displayLocalMessage.mock.calls.find(
        ([message, options]) => message instanceof HTMLElement && options?.isHtml === true
      );
      expect(htmlCall).toBeTruthy();
      expect(htmlCall[1]).toEqual(expect.objectContaining({ isHtml: true, icon: 'search' }));
      expect(htmlCall[0].textContent).toContain('Test Category');
    });
  });

  describe('find alias', () => {
    it('should have same execute function as search', () => {
      expect(find.execute).toBe(search.execute);
    });

    it('should have its own description', () => {
      expect(find.description).toContain('Alias');
    });

    it('should have its own help text', () => {
      expect(find.getHelpText()).toContain('/find');
    });
  });
});
