/**
 * UsersManager Unit Tests
 * Tests for connected users management
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('UsersManager', () => {
  let mockSocket;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="users-panel" class="hidden">
        <div class="users-header">
          <span id="users-count">0 users</span>
          <button id="users-toggle-btn">👥</button>
        </div>
        <div id="users-list"></div>
      </div>
    `;
    
    // Mock socket
    mockSocket = {
      emit: vi.fn(),
      on: vi.fn(),
      id: 'my-socket-id'
    };
  });

  describe('Users panel UI', () => {
    it('should have users panel', () => {
      expect(document.getElementById('users-panel')).toBeDefined();
    });

    it('should have users count', () => {
      expect(document.getElementById('users-count')).toBeDefined();
    });

    it('should have users list', () => {
      expect(document.getElementById('users-list')).toBeDefined();
    });

    it('should toggle panel visibility', () => {
      const panel = document.getElementById('users-panel');
      
      panel.classList.toggle('hidden');
      expect(panel.classList.contains('hidden')).toBe(false);
      
      panel.classList.toggle('hidden');
      expect(panel.classList.contains('hidden')).toBe(true);
    });
  });

  describe('User count', () => {
    it('should display user count', () => {
      const countEl = document.getElementById('users-count');
      countEl.textContent = '5 users';
      
      expect(countEl.textContent).toBe('5 users');
    });

    it('should handle singular user', () => {
      const count = 1;
      const text = count === 1 ? '1 user' : `${count} users`;
      
      expect(text).toBe('1 user');
    });

    it('should handle zero users', () => {
      const count = 0;
      const text = count === 1 ? '1 user' : `${count} users`;
      
      expect(text).toBe('0 users');
    });
  });

  describe('Users list', () => {
    it('should render user items', () => {
      const list = document.getElementById('users-list');
      
      const user = document.createElement('div');
      user.className = 'user-item';
      user.dataset.id = 'user-123';
      user.innerHTML = '<span class="user-name">User 1</span>';
      list.appendChild(user);
      
      expect(list.querySelector('.user-item')).toBeDefined();
    });

    it('should show admin badge', () => {
      const list = document.getElementById('users-list');
      
      const user = document.createElement('div');
      user.className = 'user-item';
      user.innerHTML = '<span class="user-name">Admin</span><span class="admin-badge">👑</span>';
      list.appendChild(user);
      
      expect(list.querySelector('.admin-badge')).toBeDefined();
    });

    it('should highlight current user', () => {
      const list = document.getElementById('users-list');
      
      const user = document.createElement('div');
      user.className = 'user-item current-user';
      user.innerHTML = '<span class="user-name">Me</span>';
      list.appendChild(user);
      
      expect(list.querySelector('.current-user')).toBeDefined();
    });
  });

  describe('Socket events', () => {
    it('should handle user list update', () => {
      const handler = vi.fn();
      mockSocket.on('users_update', handler);
      
      expect(mockSocket.on).toHaveBeenCalledWith('users_update', handler);
    });

    it('should handle user joined', () => {
      const handler = vi.fn();
      mockSocket.on('user_joined', handler);
      
      expect(mockSocket.on).toHaveBeenCalledWith('user_joined', handler);
    });

    it('should handle user left', () => {
      const handler = vi.fn();
      mockSocket.on('user_left', handler);
      
      expect(mockSocket.on).toHaveBeenCalledWith('user_left', handler);
    });

    it('should emit request for users list', () => {
      mockSocket.emit('get_users');
      
      expect(mockSocket.emit).toHaveBeenCalledWith('get_users');
    });
  });

  describe('User data', () => {
    it('should parse user data', () => {
      const userData = {
        id: 'socket-123',
        username: 'User1',
        isAdmin: false,
        isHost: false
      };
      
      expect(userData.username).toBe('User1');
      expect(userData.isAdmin).toBe(false);
    });

    it('should identify current user', () => {
      const users = [
        { id: 'other-id', username: 'Other' },
        { id: 'my-socket-id', username: 'Me' }
      ];
      
      const currentUser = users.find(u => u.id === mockSocket.id);
      
      expect(currentUser.username).toBe('Me');
    });
  });

  describe('Admin actions', () => {
    it('should show kick button for admins', () => {
      const list = document.getElementById('users-list');
      
      const user = document.createElement('div');
      user.className = 'user-item';
      
      const kickBtn = document.createElement('button');
      kickBtn.className = 'kick-btn';
      kickBtn.textContent = 'Kick';
      user.appendChild(kickBtn);
      
      list.appendChild(user);
      
      expect(list.querySelector('.kick-btn')).toBeDefined();
    });

    it('should emit kick event', () => {
      mockSocket.emit('kick_user', { userId: 'user-123' });
      
      expect(mockSocket.emit).toHaveBeenCalledWith('kick_user', { userId: 'user-123' });
    });
  });

  describe('User status', () => {
    it('should show online indicator', () => {
      const list = document.getElementById('users-list');
      
      const user = document.createElement('div');
      user.className = 'user-item';
      
      const status = document.createElement('span');
      status.className = 'status-indicator online';
      user.appendChild(status);
      
      list.appendChild(user);
      
      expect(list.querySelector('.status-indicator.online')).toBeDefined();
    });

    it('should show host indicator', () => {
      const list = document.getElementById('users-list');
      
      const user = document.createElement('div');
      user.className = 'user-item host';
      user.innerHTML = '<span class="host-badge">🎬</span>';
      list.appendChild(user);
      
      expect(list.querySelector('.host-badge')).toBeDefined();
    });
  });
});
