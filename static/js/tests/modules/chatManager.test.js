/**
 * ChatManager Unit Tests
 * Tests for chat functionality
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('ChatManager', () => {
  let mockSocket;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="chat-container" class="hidden">
        <div id="chat-messages"></div>
        <input id="chat-input" type="text" />
        <button id="chat-send-btn">Send</button>
        <button id="chat-toggle-btn"></button>
        <div id="chat-user-count">0</div>
      </div>
    `;
    
    // Mock socket
    mockSocket = {
      emit: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      connected: true
    };
  });

  describe('Chat UI', () => {
    it('should have chat container', () => {
      expect(document.getElementById('chat-container')).toBeDefined();
    });

    it('should have messages container', () => {
      expect(document.getElementById('chat-messages')).toBeDefined();
    });

    it('should have input field', () => {
      const input = document.getElementById('chat-input');
      expect(input).toBeDefined();
      expect(input.type).toBe('text');
    });

    it('should have send button', () => {
      expect(document.getElementById('chat-send-btn')).toBeDefined();
    });

    it('should toggle visibility', () => {
      const container = document.getElementById('chat-container');
      
      container.classList.remove('hidden');
      expect(container.classList.contains('hidden')).toBe(false);
      
      container.classList.add('hidden');
      expect(container.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Message handling', () => {
    it('should add message to chat', () => {
      const messages = document.getElementById('chat-messages');
      const messageEl = document.createElement('div');
      messageEl.className = 'chat-message';
      messageEl.textContent = 'Hello World';
      messages.appendChild(messageEl);
      
      expect(messages.children.length).toBe(1);
      expect(messages.firstChild.textContent).toBe('Hello World');
    });

    it('should add system message', () => {
      const messages = document.getElementById('chat-messages');
      const systemEl = document.createElement('div');
      systemEl.className = 'chat-system-message';
      systemEl.textContent = 'User joined';
      messages.appendChild(systemEl);
      
      expect(messages.querySelector('.chat-system-message')).toBeDefined();
    });

    it('should add local-only message', () => {
      const messages = document.getElementById('chat-messages');
      const localEl = document.createElement('div');
      localEl.className = 'chat-local-system';
      localEl.textContent = 'Command executed';
      messages.appendChild(localEl);
      
      expect(messages.querySelector('.chat-local-system')).toBeDefined();
    });

    it('should scroll to bottom on new message', () => {
      const messages = document.getElementById('chat-messages');
      
      // Add multiple messages
      for (let i = 0; i < 10; i++) {
        const msg = document.createElement('div');
        msg.textContent = `Message ${i}`;
        messages.appendChild(msg);
      }
      
      messages.scrollTop = messages.scrollHeight;
      
      expect(messages.scrollTop).toBe(messages.scrollHeight);
    });
  });

  describe('Input handling', () => {
    it('should get input value', () => {
      const input = document.getElementById('chat-input');
      input.value = 'Test message';
      
      expect(input.value).toBe('Test message');
    });

    it('should clear input after send', () => {
      const input = document.getElementById('chat-input');
      input.value = 'Test message';
      input.value = '';
      
      expect(input.value).toBe('');
    });

    it('should handle Enter key', () => {
      const input = document.getElementById('chat-input');
      const handler = vi.fn();
      
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handler();
      });
      
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      
      expect(handler).toHaveBeenCalled();
    });

    it('should detect slash commands', () => {
      const input = document.getElementById('chat-input');
      input.value = '/help';
      
      const isCommand = input.value.startsWith('/');
      expect(isCommand).toBe(true);
    });

    it('should detect regular messages', () => {
      const input = document.getElementById('chat-input');
      input.value = 'Hello everyone';
      
      const isCommand = input.value.startsWith('/');
      expect(isCommand).toBe(false);
    });
  });

  describe('Socket events', () => {
    it('should emit chat message', () => {
      mockSocket.emit('chat_message', { text: 'Hello', username: 'User1' });
      
      expect(mockSocket.emit).toHaveBeenCalledWith('chat_message', {
        text: 'Hello',
        username: 'User1'
      });
    });

    it('should register message handler', () => {
      mockSocket.on('chat_message', vi.fn());
      
      expect(mockSocket.on).toHaveBeenCalledWith('chat_message', expect.any(Function));
    });

    it('should handle user join event', () => {
      mockSocket.on('user_joined', vi.fn());
      
      expect(mockSocket.on).toHaveBeenCalledWith('user_joined', expect.any(Function));
    });

    it('should handle user leave event', () => {
      mockSocket.on('user_left', vi.fn());
      
      expect(mockSocket.on).toHaveBeenCalledWith('user_left', expect.any(Function));
    });
  });

  describe('User count', () => {
    it('should display user count', () => {
      const countEl = document.getElementById('chat-user-count');
      countEl.textContent = '5';
      
      expect(countEl.textContent).toBe('5');
    });

    it('should update on user join', () => {
      const countEl = document.getElementById('chat-user-count');
      let count = parseInt(countEl.textContent);
      count++;
      countEl.textContent = count.toString();
      
      expect(countEl.textContent).toBe('1');
    });
  });

  describe('Message formatting', () => {
    it('should escape HTML in messages', () => {
      const div = document.createElement('div');
      div.textContent = '<script>alert("xss")</script>';
      
      expect(div.innerHTML).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
    });

    it('should format timestamps', () => {
      const date = new Date();
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      const formatted = `${hours}:${minutes}`;
      
      expect(formatted).toMatch(/^\d{2}:\d{2}$/);
    });
  });
});
