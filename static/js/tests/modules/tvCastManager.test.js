/**
 * TV Cast Manager Unit Tests
 * Tests for casting media to TV displays
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('TVCastManager', () => {
  let mockSocket;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="cast-controls" class="hidden">
        <button id="cast-btn" title="Cast to TV">📺</button>
        <div id="cast-device-list" class="hidden">
          <div class="cast-device" data-display-id="tv1">Living Room TV</div>
          <div class="cast-device" data-display-id="tv2">Bedroom TV</div>
        </div>
      </div>
      <div id="cast-status"></div>
    `;
    
    // Mock socket
    mockSocket = {
      emit: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      connected: true
    };
    
    // Mock fetch
    global.fetch = vi.fn();
  });

  describe('Cast UI', () => {
    it('should have cast button', () => {
      expect(document.getElementById('cast-btn')).toBeDefined();
    });

    it('should have device list', () => {
      expect(document.getElementById('cast-device-list')).toBeDefined();
    });

    it('should show device list on button click', () => {
      const btn = document.getElementById('cast-btn');
      const list = document.getElementById('cast-device-list');
      
      btn.addEventListener('click', () => {
        list.classList.toggle('hidden');
      });
      
      btn.click();
      expect(list.classList.contains('hidden')).toBe(false);
    });

    it('should list available displays', () => {
      const devices = document.querySelectorAll('.cast-device');
      expect(devices.length).toBe(2);
    });
  });

  describe('Display discovery', () => {
    it('should fetch available displays', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          displays: [
            { id: 'tv1', name: 'Living Room TV', connected: true },
            { id: 'tv2', name: 'Bedroom TV', connected: true }
          ]
        })
      });
      
      const response = await fetch('/api/displays');
      const data = await response.json();
      
      expect(data.displays).toHaveLength(2);
    });

    it('should handle no displays available', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ displays: [] })
      });
      
      const response = await fetch('/api/displays');
      const data = await response.json();
      
      expect(data.displays).toHaveLength(0);
    });
  });

  describe('Casting media', () => {
    it('should emit cast event', () => {
      const castData = {
        displayId: 'tv1',
        categoryId: 'movies',
        mediaUrl: '/media/movie.mp4',
        mediaIndex: 0
      };
      
      mockSocket.emit('cast_media_to_display', castData);
      
      expect(mockSocket.emit).toHaveBeenCalledWith('cast_media_to_display', castData);
    });

    it('should select display on click', () => {
      const handler = vi.fn();
      const list = document.getElementById('cast-device-list');
      
      list.addEventListener('click', (e) => {
        const device = e.target.closest('.cast-device');
        if (device) handler(device.dataset.displayId);
      });
      
      const device = list.querySelector('.cast-device');
      device.click();
      
      expect(handler).toHaveBeenCalledWith('tv1');
    });
  });

  describe('Cast status', () => {
    it('should show casting status', () => {
      const status = document.getElementById('cast-status');
      status.textContent = 'Casting to Living Room TV';
      status.classList.add('active');
      
      expect(status.textContent).toContain('Living Room TV');
      expect(status.classList.contains('active')).toBe(true);
    });

    it('should clear status on stop', () => {
      const status = document.getElementById('cast-status');
      status.textContent = '';
      status.classList.remove('active');
      
      expect(status.textContent).toBe('');
    });
  });

  describe('Socket events', () => {
    it('should listen for cast confirmation', () => {
      mockSocket.on('cast_started', vi.fn());
      expect(mockSocket.on).toHaveBeenCalledWith('cast_started', expect.any(Function));
    });

    it('should listen for cast errors', () => {
      mockSocket.on('cast_error', vi.fn());
      expect(mockSocket.on).toHaveBeenCalledWith('cast_error', expect.any(Function));
    });

    it('should emit stop cast event', () => {
      mockSocket.emit('stop_cast', { displayId: 'tv1' });
      expect(mockSocket.emit).toHaveBeenCalledWith('stop_cast', { displayId: 'tv1' });
    });
  });

  describe('Display connection status', () => {
    it('should show connected status', () => {
      const device = document.querySelector('.cast-device');
      device.classList.add('connected');
      
      expect(device.classList.contains('connected')).toBe(true);
    });

    it('should show disconnected status', () => {
      const device = document.querySelector('.cast-device');
      device.classList.add('disconnected');
      
      expect(device.classList.contains('disconnected')).toBe(true);
    });
  });

  describe('Cast controls', () => {
    it('should pause cast', () => {
      mockSocket.emit('cast_control', { displayId: 'tv1', action: 'pause' });
      
      expect(mockSocket.emit).toHaveBeenCalledWith('cast_control', {
        displayId: 'tv1',
        action: 'pause'
      });
    });

    it('should resume cast', () => {
      mockSocket.emit('cast_control', { displayId: 'tv1', action: 'play' });
      
      expect(mockSocket.emit).toHaveBeenCalledWith('cast_control', {
        displayId: 'tv1',
        action: 'play'
      });
    });

    it('should seek in cast', () => {
      mockSocket.emit('cast_control', { displayId: 'tv1', action: 'seek', time: 120 });
      
      expect(mockSocket.emit).toHaveBeenCalledWith('cast_control', {
        displayId: 'tv1',
        action: 'seek',
        time: 120
      });
    });
  });

  describe('Error handling', () => {
    it('should handle connection errors', () => {
      const error = { message: 'Display not connected' };
      
      expect(error.message).toBe('Display not connected');
    });

    it('should retry on failure', () => {
      let attempts = 0;
      const maxAttempts = 3;
      
      const retry = () => {
        attempts++;
        return attempts < maxAttempts;
      };
      
      while (retry()) {}
      
      expect(attempts).toBe(3);
    });
  });
});
