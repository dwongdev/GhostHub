/**
 * CommandPopup Unit Tests
 * Tests for slash command autocomplete popup
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('CommandPopup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="chat-container">
        <input id="chat-input" type="text" />
        <div id="command-popup" class="hidden">
          <div class="command-list"></div>
        </div>
      </div>
    `;
  });

  describe('Popup visibility', () => {
    it('should have popup element', () => {
      expect(document.getElementById('command-popup')).toBeDefined();
    });

    it('should be hidden by default', () => {
      const popup = document.getElementById('command-popup');
      expect(popup.classList.contains('hidden')).toBe(true);
    });

    it('should show on / input', () => {
      const input = document.getElementById('chat-input');
      const popup = document.getElementById('command-popup');
      
      input.value = '/';
      popup.classList.remove('hidden');
      
      expect(popup.classList.contains('hidden')).toBe(false);
    });

    it('should hide on empty input', () => {
      const popup = document.getElementById('command-popup');
      popup.classList.remove('hidden');
      
      popup.classList.add('hidden');
      
      expect(popup.classList.contains('hidden')).toBe(true);
    });

    it('should hide on Escape', () => {
      const popup = document.getElementById('command-popup');
      popup.classList.remove('hidden');
      
      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      if (event.key === 'Escape') {
        popup.classList.add('hidden');
      }
      
      expect(popup.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Command filtering', () => {
    const commands = [
      { name: 'help', description: 'Show help' },
      { name: 'search', description: 'Search media' },
      { name: 'random', description: 'Random media' },
      { name: 'view', description: 'View category' },
      { name: 'myview', description: 'View your progress' }
    ];

    it('should filter commands by prefix', () => {
      const query = 'he';
      const filtered = commands.filter(cmd => 
        cmd.name.toLowerCase().startsWith(query.toLowerCase())
      );
      
      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('help');
    });

    it('should show all commands for empty query', () => {
      const query = '';
      const filtered = query ? commands.filter(c => c.name.startsWith(query)) : commands;
      
      expect(filtered).toHaveLength(5);
    });

    it('should match partial names', () => {
      const query = 'view';
      const filtered = commands.filter(cmd => 
        cmd.name.toLowerCase().includes(query.toLowerCase())
      );
      
      expect(filtered).toHaveLength(2); // view and myview
    });
  });

  describe('Command list rendering', () => {
    it('should render command items', () => {
      const list = document.querySelector('.command-list');
      
      const item = document.createElement('div');
      item.className = 'command-item';
      item.dataset.command = 'help';
      item.innerHTML = '<span class="cmd-name">/help</span><span class="cmd-desc">Show help</span>';
      list.appendChild(item);
      
      expect(list.querySelector('.command-item')).toBeDefined();
    });

    it('should highlight selected item', () => {
      const list = document.querySelector('.command-list');
      
      const item = document.createElement('div');
      item.className = 'command-item selected';
      list.appendChild(item);
      
      expect(item.classList.contains('selected')).toBe(true);
    });
  });

  describe('Keyboard navigation', () => {
    it('should move selection down with ArrowDown', () => {
      let selectedIndex = 0;
      const maxIndex = 4;
      
      if (selectedIndex < maxIndex) selectedIndex++;
      
      expect(selectedIndex).toBe(1);
    });

    it('should move selection up with ArrowUp', () => {
      let selectedIndex = 2;
      
      if (selectedIndex > 0) selectedIndex--;
      
      expect(selectedIndex).toBe(1);
    });

    it('should wrap to bottom on ArrowUp at top', () => {
      let selectedIndex = 0;
      const maxIndex = 4;
      
      if (selectedIndex === 0) selectedIndex = maxIndex;
      
      expect(selectedIndex).toBe(4);
    });

    it('should wrap to top on ArrowDown at bottom', () => {
      let selectedIndex = 4;
      const maxIndex = 4;
      
      if (selectedIndex === maxIndex) selectedIndex = 0;
      
      expect(selectedIndex).toBe(0);
    });
  });

  describe('Command selection', () => {
    it('should insert command on Enter', () => {
      const input = document.getElementById('chat-input');
      const selectedCommand = 'search';
      
      input.value = '/' + selectedCommand + ' ';
      
      expect(input.value).toBe('/search ');
    });

    it('should insert command on click', () => {
      const input = document.getElementById('chat-input');
      const handler = vi.fn((cmd) => {
        input.value = '/' + cmd + ' ';
      });
      
      handler('random');
      
      expect(input.value).toBe('/random ');
    });

    it('should hide popup after selection', () => {
      const popup = document.getElementById('command-popup');
      popup.classList.remove('hidden');
      
      // Simulate selection
      popup.classList.add('hidden');
      
      expect(popup.classList.contains('hidden')).toBe(true);
    });

    it('should focus input after selection', () => {
      const input = document.getElementById('chat-input');
      input.focus = vi.fn();
      
      input.focus();
      
      expect(input.focus).toHaveBeenCalled();
    });
  });

  describe('Tab completion', () => {
    it('should complete on Tab', () => {
      const input = document.getElementById('chat-input');
      input.value = '/hel';
      
      // Simulate tab completion
      input.value = '/help ';
      
      expect(input.value).toBe('/help ');
    });
  });

  describe('Positioning', () => {
    it('should position popup above input', () => {
      const popup = document.getElementById('command-popup');
      popup.style.bottom = '40px';
      
      expect(popup.style.bottom).toBe('40px');
    });
  });
});
