/**
 * Vitest Test Setup
 * Sets up browser environment mocks for testing
 */

import { vi } from 'vitest';

// Mock DOM elements that the app expects
function setupDOM() {
  document.body.innerHTML = `
    <div id="categories-section"></div>
    <div id="media-viewer" class="hidden">
      <div class="spinner-container"></div>
    </div>
    <div id="grid-container"></div>
    <button id="sync-toggle-btn"></button>
    <meta name="theme-color" content="#2d3250">
  `;
}

// Mock window properties
function setupWindow() {
  // Mock window.appConfig
  window.appConfig = {
    python_config: {
      DEBUG_MODE: false,
      MAX_CACHE_SIZE: 50
    },
    javascript_config: {
      core_app: {
        media_per_page_desktop: 5,
        media_per_page_mobile: 3,
        load_more_threshold_desktop: 3,
        load_more_threshold_mobile: 2,
        render_window_size: 0,
        mobile_cleanup_interval: 60000,
        mobile_fetch_timeout: 15000,
        fullscreen_check_interval: 2000
      },
      ui: {
        theme: 'dark',
        layout: 'streaming',
        features: {
          chat: true,
          syncButton: true,
          headerBranding: true
        }
      }
    },
    isPasswordProtectionActive: false
  };

  // Mock window.serverConfig
  window.serverConfig = {
    MEMORY_CLEANUP_INTERVAL: 60000
  };

  // Mock window.ragotModules with an appStore that mirrors appConfig
  window.__RAGOT_ALLOW_DIRECT_MUTATION__ = true;
  const _storeData = {};
  window.ragotModules = {
    appStore: {
      get: (key, defaultValue) => (key in _storeData ? _storeData[key] : defaultValue),
      set: (key, value) => { _storeData[key] = value; }
    }
  };
  // Seed the store with the same config that window.appConfig holds
  window.ragotModules.appStore.set('config', window.appConfig);

  // Mock navigator.deviceMemory
  Object.defineProperty(navigator, 'deviceMemory', {
    value: 4,
    writable: true,
    configurable: true
  });

  // Mock navigator.userAgent
  Object.defineProperty(navigator, 'userAgent', {
    value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    writable: true,
    configurable: true
  });

  // Mock requestIdleCallback
  window.requestIdleCallback = vi.fn((callback) => {
    setTimeout(() => callback({ timeRemaining: () => 50 }), 0);
    return 1;
  });

  // Mock IntersectionObserver
  window.IntersectionObserver = vi.fn().mockImplementation((callback) => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
    takeRecords: vi.fn(() => [])
  }));

  // Mock URL.createObjectURL and revokeObjectURL
  URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  URL.revokeObjectURL = vi.fn();

  // Mock sessionStorage
  const sessionStorageData = {};
  Object.defineProperty(window, 'sessionStorage', {
    value: {
      getItem: vi.fn((key) => sessionStorageData[key] || null),
      setItem: vi.fn((key, value) => { sessionStorageData[key] = value; }),
      removeItem: vi.fn((key) => { delete sessionStorageData[key]; }),
      clear: vi.fn(() => { Object.keys(sessionStorageData).forEach(k => delete sessionStorageData[k]); })
    },
    writable: true
  });

  // Mock localStorage
  const localStorageData = {};
  Object.defineProperty(window, 'localStorage', {
    value: {
      getItem: vi.fn((key) => localStorageData[key] || null),
      setItem: vi.fn((key, value) => { localStorageData[key] = value; }),
      removeItem: vi.fn((key) => { delete localStorageData[key]; }),
      clear: vi.fn(() => { Object.keys(localStorageData).forEach(k => delete localStorageData[k]); })
    },
    writable: true
  });
}

// Mock fetch API
function setupFetch() {
  global.fetch = vi.fn((url, options) => {
    // Default mock responses based on URL
    if (url === '/api/config') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(window.appConfig)
      });
    }

    if (url === '/api/validate_session_password') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ valid: true })
      });
    }

    if (url.startsWith('/api/progress/videos')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ videos: [] })
      });
    }

    // Default response
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({})
    });
  });
}

// Mock console methods to track calls
function setupConsole() {
  const originalConsole = { ...console };

  // Keep original implementations but spy on them
  vi.spyOn(console, 'log').mockImplementation(() => { });
  vi.spyOn(console, 'warn').mockImplementation(() => { });
  vi.spyOn(console, 'error').mockImplementation(() => { });
  vi.spyOn(console, 'debug').mockImplementation(() => { });
  vi.spyOn(console, 'info').mockImplementation(() => { });

  return originalConsole;
}

// Mock XMLHttpRequest
function setupXHR() {
  const mockXHR = {
    open: vi.fn(),
    send: vi.fn(),
    setRequestHeader: vi.fn(),
    upload: {
      addEventListener: vi.fn()
    },
    addEventListener: vi.fn(),
    readyState: 4,
    status: 200,
    responseText: '{}'
  };

  global.XMLHttpRequest = vi.fn(() => mockXHR);
  global.XMLHttpRequest.mockInstance = mockXHR;
}

// Setup before all tests
setupDOM();
setupWindow();
setupFetch();
setupConsole();
setupXHR();

// Reset mocks between tests
beforeEach(() => {
  vi.clearAllMocks();
  setupDOM();

  // Reset appConfig to default state
  window.appConfig = {
    python_config: {
      DEBUG_MODE: false,
      MAX_CACHE_SIZE: 50
    },
    javascript_config: {
      core_app: {
        media_per_page_desktop: 5,
        media_per_page_mobile: 3
      },
      ui: {
        theme: 'dark',
        layout: 'streaming',
        features: {
          chat: true,
          syncButton: true,
          headerBranding: true
        }
      }
    },
    isPasswordProtectionActive: false
  };

  // Re-seed the ragotModules store so it reflects the reset appConfig
  if (window.ragotModules?.appStore?.set) {
    window.ragotModules.appStore.set('config', window.appConfig);
  }
});

// Export utilities for tests
export const testUtils = {
  setupDOM,
  setupWindow,
  setupFetch,

  // Mock a specific fetch response
  mockFetchResponse(url, response) {
    const originalFetch = global.fetch;
    global.fetch = vi.fn((requestUrl, options) => {
      if (requestUrl === url || requestUrl.startsWith(url)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(response)
        });
      }
      return originalFetch(requestUrl, options);
    });
  },

  // Mock a fetch error
  mockFetchError(url, error = 'Network error') {
    const originalFetch = global.fetch;
    global.fetch = vi.fn((requestUrl, options) => {
      if (requestUrl === url || requestUrl.startsWith(url)) {
        return Promise.reject(new Error(error));
      }
      return originalFetch(requestUrl, options);
    });
  },

  // Create a mock media element
  createMockMediaElement(type = 'video') {
    const element = document.createElement(type);
    element.play = vi.fn(() => Promise.resolve());
    element.pause = vi.fn();
    element.load = vi.fn();
    return element;
  },

  // Simulate window resize
  setWindowWidth(width) {
    Object.defineProperty(window, 'innerWidth', {
      value: width,
      writable: true
    });
  }
};
