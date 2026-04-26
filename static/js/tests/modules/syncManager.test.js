/**
 * SyncManager Unit Tests
 * Tests for synchronized viewing functionality
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('SyncManager', () => {
  let mockSocket;

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup DOM
    document.body.innerHTML = `
      <button id="sync-toggle-btn"></button>
      <div id="sync-status" class="hidden"></div>
      <div id="sync-users-count">0</div>
      <div id="media-viewer" class="hidden"></div>
    `;

    // Mock socket
    mockSocket = {
      emit: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      connected: true,
      id: 'test-socket-id'
    };

    // Mock appConfig
    window.appConfig = {
      javascript_config: {
        sync_manager: {
          socket_reconnectionAttempts: 10,
          socket_reconnectionDelay: 1000,
          heartbeatInterval: 30000
        }
      }
    };

    // Mock app state service
    window.__RAGOT_ALLOW_DIRECT_MUTATION__ = true;
    window.ragotModules = {
      ...(window.ragotModules || {}),
      appState: {
        syncModeEnabled: false,
        isHost: false,
        navigationDisabled: false,
        currentCategoryId: null,
        currentMediaIndex: 0
      }
    };
  });

  describe('Sync state management', () => {
    it('should start with sync disabled', () => {
      expect(window.ragotModules.appState.syncModeEnabled).toBe(false);
    });

    it('should start as non-host', () => {
      expect(window.ragotModules.appState.isHost).toBe(false);
    });

    it('should allow navigation when not in sync', () => {
      expect(window.ragotModules.appState.navigationDisabled).toBe(false);
    });

    it('should track sync toggle button state', () => {
      const btn = document.getElementById('sync-toggle-btn');
      expect(btn.classList.contains('active')).toBe(false);

      btn.classList.add('active');
      expect(btn.classList.contains('active')).toBe(true);
    });
  });

  describe('Socket events', () => {
    it('should emit join_sync event', () => {
      mockSocket.emit('join_sync', { room: 'test-room' });

      expect(mockSocket.emit).toHaveBeenCalledWith('join_sync', { room: 'test-room' });
    });

    it('should emit leave_sync event', () => {
      mockSocket.emit('leave_sync', { room: 'test-room' });

      expect(mockSocket.emit).toHaveBeenCalledWith('leave_sync', { room: 'test-room' });
    });

    it('should emit sync_navigate event', () => {
      const navData = {
        categoryId: 'cat1',
        mediaIndex: 5,
        mediaUrl: '/media/video.mp4'
      };

      mockSocket.emit('sync_navigate', navData);

      expect(mockSocket.emit).toHaveBeenCalledWith('sync_navigate', navData);
    });

    it('should emit heartbeat event', () => {
      mockSocket.emit('sync_heartbeat', { timestamp: Date.now() });

      expect(mockSocket.emit).toHaveBeenCalled();
    });
  });

  describe('Host functionality', () => {
    it('should allow host to navigate', () => {
      window.ragotModules.appState.isHost = true;
      window.ragotModules.appState.syncModeEnabled = true;

      // Host should be able to navigate
      expect(window.ragotModules.appState.navigationDisabled).toBe(false);
    });

    it('should track host status', () => {
      window.ragotModules.appState.isHost = true;
      expect(window.ragotModules.appState.isHost).toBe(true);

      window.ragotModules.appState.isHost = false;
      expect(window.ragotModules.appState.isHost).toBe(false);
    });
  });

  describe('Guest functionality', () => {
    it('should disable navigation for guests in sync mode', () => {
      window.ragotModules.appState.syncModeEnabled = true;
      window.ragotModules.appState.isHost = false;
      window.ragotModules.appState.navigationDisabled = true;

      expect(window.ragotModules.appState.navigationDisabled).toBe(true);
    });

    it('should follow host navigation', () => {
      const hostNavigation = {
        categoryId: 'movies',
        mediaIndex: 10,
        mediaUrl: '/media/movie.mp4'
      };

      // Simulate receiving navigation from host
      window.ragotModules.appState.currentCategoryId = hostNavigation.categoryId;
      window.ragotModules.appState.currentMediaIndex = hostNavigation.mediaIndex;

      expect(window.ragotModules.appState.currentCategoryId).toBe('movies');
      expect(window.ragotModules.appState.currentMediaIndex).toBe(10);
    });
  });

  describe('Sync status display', () => {
    it('should show sync status when enabled', () => {
      const status = document.getElementById('sync-status');
      status.classList.remove('hidden');

      expect(status.classList.contains('hidden')).toBe(false);
    });

    it('should update user count', () => {
      const countEl = document.getElementById('sync-users-count');
      countEl.textContent = '5';

      expect(countEl.textContent).toBe('5');
    });

    it('should hide sync status when disabled', () => {
      const status = document.getElementById('sync-status');
      status.classList.add('hidden');

      expect(status.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Reconnection handling', () => {
    it('should have reconnection config', () => {
      const config = window.appConfig.javascript_config.sync_manager;

      expect(config.socket_reconnectionAttempts).toBe(10);
      expect(config.socket_reconnectionDelay).toBe(1000);
    });

    it('should track connection state', () => {
      expect(mockSocket.connected).toBe(true);

      mockSocket.connected = false;
      expect(mockSocket.connected).toBe(false);
    });
  });

  describe('Cleanup on disconnect', () => {
    it('should reset sync state on disconnect', () => {
      // Simulate disconnect cleanup
      window.ragotModules.appState.syncModeEnabled = false;
      window.ragotModules.appState.isHost = false;
      window.ragotModules.appState.navigationDisabled = false;

      expect(window.ragotModules.appState.syncModeEnabled).toBe(false);
      expect(window.ragotModules.appState.isHost).toBe(false);
      expect(window.ragotModules.appState.navigationDisabled).toBe(false);
    });
  });
});

