/**
 * ProgressDB Unit Tests
 * Tests for IndexedDB-based progress storage for non-admin users
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { APP_EVENTS } from '../../core/appEvents.js';

vi.mock('../../utils/profileUtils.js', () => ({
  hasActiveProfile: vi.fn(() => false)
}));

import { hasActiveProfile } from '../../utils/profileUtils.js';

// Mock IndexedDB
const mockIndexedDB = {
  open: vi.fn(),
  deleteDatabase: vi.fn()
};

// Mock IDBDatabase
const mockDB = {
  objectStoreNames: {
    contains: vi.fn().mockReturnValue(true)
  },
  transaction: vi.fn().mockReturnValue({
    objectStore: vi.fn().mockReturnValue({
      put: vi.fn(),
      get: vi.fn(),
      getAll: vi.fn().mockReturnValue({
        onsuccess: null,
        onerror: null,
        result: []
      })
    })
  }),
  createObjectStore: vi.fn().mockReturnValue({
    createIndex: vi.fn()
  })
};

// Helper: set admin status in the store
function setAdmin(isAdmin) {
  window.ragotModules.appStore.set('isAdmin', isAdmin);
}

describe('ProgressDB', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock IndexedDB
    window.indexedDB = mockIndexedDB;

    // Set up ragotModules with appStore AND tvCastManager
    // (setup.js creates appStore but we need to add tvCastManager)
    window.ragotModules.tvCastManager = {
      isCastingToCategory: vi.fn().mockReturnValue(false)
    };

    // Default: not admin, no active profile
    setAdmin(false);
    hasActiveProfile.mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('isUserAdmin', () => {
    it('should return false when user is not admin', async () => {
      setAdmin(false);

      const { isUserAdmin } = await import('../../utils/progressDB.js');
      expect(isUserAdmin()).toBe(false);
    });

    it('should return true when user is admin', async () => {
      setAdmin(true);

      const { isUserAdmin } = await import('../../utils/progressDB.js');
      expect(isUserAdmin()).toBe(true);
    });
  });

  describe('isSessionProgressEnabled', () => {
    it('should always return true for legacy compatibility', async () => {
      const { isSessionProgressEnabled } = await import('../../utils/progressDB.js');
      expect(isSessionProgressEnabled()).toBe(true);
    });
  });

  describe('isTvAuthorityForCategory', () => {
    it('should return false when not casting', async () => {
      vi.resetModules();
      window.ragotModules.tvCastManager.isCastingToCategory.mockReturnValue(false);

      const { isTvAuthorityForCategory } = await import('../../utils/progressDB.js');
      expect(isTvAuthorityForCategory('test-category')).toBe(false);
    });

    it('should return true when casting to the category', async () => {
      vi.resetModules();
      hasActiveProfile.mockReturnValue(true);
      window.ragotModules.tvCastManager.isCastingToCategory.mockReturnValue(true);

      const { isTvAuthorityForCategory } = await import('../../utils/progressDB.js');
      expect(isTvAuthorityForCategory('test-category')).toBe(true);
    });

    it('should return false when tvCastManager is not available', async () => {
      vi.resetModules();
      delete window.ragotModules.tvCastManager;

      const { isTvAuthorityForCategory } = await import('../../utils/progressDB.js');
      expect(isTvAuthorityForCategory('test-category')).toBe(false);
    });
  });

  describe('saveLocalProgress', () => {
    it('should not save progress when an active profile exists', async () => {
      hasActiveProfile.mockReturnValue(true);

      const { bus } = await import('../../libs/ragot.esm.min.js');
      const emitSpy = vi.spyOn(bus, 'emit');
      const { saveLocalProgress } = await import('../../utils/progressDB.js');

      saveLocalProgress('cat1', 5, 10, 30, 120, '/thumb.jpg');

      // Profile-backed progress should not broadcast local IndexedDB updates
      expect(emitSpy).not.toHaveBeenCalled();
    });

    it('should emit local progress update when no active profile exists', async () => {
      hasActiveProfile.mockReturnValue(false);

      const { bus } = await import('../../libs/ragot.esm.min.js');
      const emitSpy = vi.spyOn(bus, 'emit');
      const { saveLocalProgress } = await import('../../utils/progressDB.js');

      saveLocalProgress('cat1', 5, 10, 30, 120, '/thumb.jpg');

      expect(emitSpy).toHaveBeenCalledWith(
        APP_EVENTS.LOCAL_PROGRESS_UPDATE,
        expect.objectContaining({
          category_id: 'cat1',
          index: 5,
          total_count: 10
        })
      );
    });
  });

  describe('getLocalProgress', () => {
    it('should return null when an active profile exists', async () => {
      hasActiveProfile.mockReturnValue(true);

      const { getLocalProgress } = await import('../../utils/progressDB.js');
      expect(getLocalProgress('cat1')).toBeNull();
    });

    it('should return saved local progress when no active profile exists', async () => {
      hasActiveProfile.mockReturnValue(false);

      const { saveLocalProgress, getLocalProgress } = await import('../../utils/progressDB.js');
      saveLocalProgress('cat1', 3, 12, 45, 120, '/thumb1.jpg');

      const progress = getLocalProgress('cat1');
      expect(progress).toEqual(expect.objectContaining({
        index: 3,
        total_count: 12,
        video_timestamp: 45,
        video_duration: 120,
        thumbnail_url: '/thumb1.jpg'
      }));
    });
  });

  describe('saveVideoLocalProgress', () => {
    it('should not save when an active profile exists', async () => {
      hasActiveProfile.mockReturnValue(true);

      const { bus } = await import('../../libs/ragot.esm.min.js');
      const emitSpy = vi.spyOn(bus, 'emit');
      const { saveVideoLocalProgress } = await import('../../utils/progressDB.js');

      saveVideoLocalProgress('/video.mp4', 'cat1', 30, 120, '/thumb.jpg');

      expect(emitSpy).not.toHaveBeenCalled();
    });

    it('should not save when timestamp is 0 or negative', async () => {
      hasActiveProfile.mockReturnValue(false);

      const { bus } = await import('../../libs/ragot.esm.min.js');
      const emitSpy = vi.spyOn(bus, 'emit');
      const { saveVideoLocalProgress } = await import('../../utils/progressDB.js');

      saveVideoLocalProgress('/video.mp4', 'cat1', 0, 120, '/thumb.jpg');

      expect(emitSpy).not.toHaveBeenCalled();
    });

    it('should allow near-end progress to remain saved until completion is explicit', async () => {
      hasActiveProfile.mockReturnValue(false);

      const { bus } = await import('../../libs/ragot.esm.min.js');
      const emitSpy = vi.spyOn(bus, 'emit');
      const {
        saveVideoLocalProgress,
        getVideoLocalProgress
      } = await import('../../utils/progressDB.js');

      saveVideoLocalProgress('/video.mp4', 'cat1', 119, 120, '/thumb.jpg');

      expect(getVideoLocalProgress('/video.mp4')).toEqual(expect.objectContaining({
        video_timestamp: 119,
        video_duration: 120
      }));
      expect(emitSpy).toHaveBeenCalledWith(
        APP_EVENTS.LOCAL_PROGRESS_UPDATE,
        expect.objectContaining({
          video_url: '/video.mp4',
          video_timestamp: 119,
          video_duration: 120
        })
      );
    });
  });

  describe('getVideoLocalProgress', () => {
    it('should return null when an active profile exists', async () => {
      hasActiveProfile.mockReturnValue(true);

      const { getVideoLocalProgress } = await import('../../utils/progressDB.js');
      expect(getVideoLocalProgress('/video.mp4')).toBeNull();
    });
  });

  describe('getCategoryVideoLocalProgress', () => {
    it('should return empty object when an active profile exists', async () => {
      hasActiveProfile.mockReturnValue(true);

      const { getCategoryVideoLocalProgress } = await import('../../utils/progressDB.js');
      expect(getCategoryVideoLocalProgress('cat1')).toEqual({});
    });
  });

  describe('getAllVideoLocalProgress', () => {
    it('should return empty array when an active profile exists', async () => {
      hasActiveProfile.mockReturnValue(true);

      const { getAllVideoLocalProgress } = await import('../../utils/progressDB.js');
      expect(getAllVideoLocalProgress()).toEqual([]);
    });
  });
});
