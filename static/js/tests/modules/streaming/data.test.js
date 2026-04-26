import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  buildContinueWatchingData,
  fetchCategories,
  fetchAllCategoryMedia,
  fetchCategoryMedia,
  fetchNewestMedia,
  primeCategoryLoadingShells,
  getCategoryProgress
} from '../../../modules/layouts/streaming/data.js';

import { streamingState } from '../../../modules/layouts/streaming/state.js';
import * as layoutUtils from '../../../utils/layoutUtils.js';
import * as progressDB from '../../../utils/progressDB.js';
import * as profileUtils from '../../../utils/profileUtils.js';
import * as requestCache from '../../../utils/requestCache.js';
import * as progressPersistence from '../../../modules/media/progressPersistence.js';

// Mock dependencies
vi.mock('../../../utils/layoutUtils.js', () => ({
  fetchVideoProgressData: vi.fn(),
  ensureProgressDBReady: vi.fn()
}));

vi.mock('../../../utils/progressDB.js', () => ({
  getLocalProgress: vi.fn()
}));

vi.mock('../../../utils/profileUtils.js', () => ({
  hasActiveProfile: vi.fn(() => false)
}));

vi.mock('../../../utils/showHiddenManager.js', () => ({
  getShowHiddenHeaders: vi.fn(() => ({})),
  appendShowHiddenParam: vi.fn(url => url)
}));

vi.mock('../../../utils/requestCache.js', () => ({
  cachedFetch: vi.fn()
}));

vi.mock('../../../modules/media/progressPersistence.js', () => ({
  isPendingDeletion: vi.fn()
}));

describe('Streaming Layout Data Fetching & Processing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset singleton state
    streamingState.setState({
      categoriesData: [],
      continueWatchingData: [],
      whatsNewData: [],
      videoProgressMap: {},
      continueWatchingLoading: false,
      whatsNewLoading: false,
      mediaFilter: 'all',
      categoryIdFilter: null,
      subfolderFilter: null
    });
  });

  describe('buildContinueWatchingData', () => {
    it('should correctly parse and sort continue watching data, avoiding duplicates', async () => {
      // Setup base categories
      streamingState.setState({
        categoriesData: [{ id: 'cat1', name: 'Movies' }, { id: 'cat2', name: 'TV Shows' }]
      });

      // Mock fetched DB videos
      layoutUtils.fetchVideoProgressData.mockResolvedValue([
        { video_url: 'movieA.mp4', category_id: 'cat1', video_timestamp: 100, last_watched: 50 },
        { video_url: 'movieA.mp4', category_id: 'cat1', video_timestamp: 200, last_watched: 100 }, // Duplicate URL, newer last_watched
        { video_url: 'tvshowB.mp4', category_id: 'cat2', video_timestamp: 300, last_watched: 75 }
      ]);

      progressPersistence.isPendingDeletion.mockReturnValue(false);

      await buildContinueWatchingData(false);

      const cwData = streamingState.state.continueWatchingData;

      // Should have 2 items (movieA merged, tvshowB)
      expect(cwData.length).toBe(2);

      // Should be sorted descending by last_watched
      expect(cwData[0].videoUrl).toBe('movieA.mp4'); // last_watched: 100
      expect(cwData[0].videoTimestamp).toBe(200); // the newer one was adopted
      expect(cwData[0].categoryName).toBe('Movies');

      expect(cwData[1].videoUrl).toBe('tvshowB.mp4'); // last_watched: 75
      expect(cwData[1].categoryName).toBe('TV Shows');

      // videoProgressMap should be populated
      const progressMap = streamingState.state.videoProgressMap;
      expect(progressMap['movieA.mp4'].video_timestamp).toBe(200);
      expect(progressMap['tvshowB.mp4'].video_timestamp).toBe(300);
    });

    it('should skip videos marked for pending deletion', async () => {
      layoutUtils.fetchVideoProgressData.mockResolvedValue([
        { video_url: 'movieC.mp4', category_id: 'cat1', video_timestamp: 100, last_watched: 50 }
      ]);

      // This mock makes it so the video is considered "completed/deleting"
      progressPersistence.isPendingDeletion.mockReturnValue(true);

      await buildContinueWatchingData(false);

      // CW list should be empty because it skipped movieC
      expect(streamingState.state.continueWatchingData.length).toBe(0);
    });

    it('keeps the previous CW snapshot visible while an async refresh is still running', async () => {
      let resolveFetch;
      const existingItem = {
        videoUrl: 'existing.mp4',
        categoryId: 'cat1',
        categoryName: 'Movies',
        thumbnailUrl: 'existing.jpg',
        videoTimestamp: 25,
        videoDuration: 100,
        lastWatched: 10
      };

      streamingState.setState({
        categoriesData: [{ id: 'cat1', name: 'Movies' }],
        continueWatchingData: [existingItem],
        videoProgressMap: {
          'existing.mp4': { video_timestamp: 25, video_duration: 100 }
        }
      });

      layoutUtils.fetchVideoProgressData.mockReturnValue(new Promise((resolve) => {
        resolveFetch = resolve;
      }));
      progressPersistence.isPendingDeletion.mockReturnValue(false);

      const refreshPromise = buildContinueWatchingData(true);

      expect(streamingState.state.continueWatchingLoading).toBe(true);
      expect(streamingState.state.continueWatchingData).toEqual([existingItem]);
      expect(streamingState.state.videoProgressMap).toEqual({
        'existing.mp4': { video_timestamp: 25, video_duration: 100 }
      });

      resolveFetch([
        { video_url: 'fresh.mp4', category_id: 'cat1', video_timestamp: 40, video_duration: 120, last_watched: 20 }
      ]);
      await refreshPromise;

      expect(streamingState.state.continueWatchingLoading).toBe(false);
      expect(streamingState.state.continueWatchingData[0].videoUrl).toBe('fresh.mp4');
      expect(streamingState.state.videoProgressMap).toEqual({
        'fresh.mp4': { video_timestamp: 40, video_duration: 120 }
      });
    });
  });

  describe('getCategoryProgress', () => {
    it('should return server data when an active profile exists', () => {
      profileUtils.hasActiveProfile.mockReturnValue(true);

      const categoryItem = {
        id: 'item1',
        saved_index: 5,
        video_timestamp: 120,
        video_duration: 600,
        thumbnailUrl: 'thumb.jpg'
      };

      const result = getCategoryProgress(categoryItem);
      expect(result.savedIndex).toBe(5);
      expect(result.videoTimestamp).toBe(120);
    });

    it('should override with local progress when no active profile exists', () => {
      profileUtils.hasActiveProfile.mockReturnValue(false);
      progressDB.getLocalProgress.mockReturnValue({
        index: 8,
        video_timestamp: 300,
        video_duration: 600,
        thumbnail_url: 'local_thumb.jpg'
      });

      const categoryItem = {
        id: 'item2',
        saved_index: 2,
        video_timestamp: 50,
        video_duration: 600
      };

      const result = getCategoryProgress(categoryItem);

      // Should take the values from localProgress instead of categoryItem
      expect(result.savedIndex).toBe(8);
      expect(result.videoTimestamp).toBe(300);
      expect(result.thumbnailUrl).toBe('local_thumb.jpg');
    });
  });

  describe('fetchCategoryMedia', () => {
    it('should properly format URL parameters for subfolders and pagination', async () => {
      const mockResponse = {
        ok: true,
        json: async () => ({
          files: [{ id: 'f1' }, { id: 'f2' }],
          subfolders: ['folder1'],
          pagination: { hasMore: true, total: 100 }
        })
      };
      requestCache.cachedFetch.mockResolvedValue(mockResponse);

      const result = await fetchCategoryMedia('cat-123', 2, false, 'Movies/Action', { includeTotal: true });

      expect(result.media.length).toBe(2);
      expect(result.hasMore).toBe(true);
      expect(result.subfolders).toContain('folder1');
      expect(result.total).toBe(100);

      // Verify URL structure
      const fetchCallUrl = requestCache.cachedFetch.mock.calls[0][0];
      expect(fetchCallUrl).toContain('/api/categories/cat-123/media');
      expect(fetchCallUrl).toContain('page=2');
      expect(fetchCallUrl).toContain('subfolder=Movies%2FAction');
    });

    it('should fall back gracefully if the API fails', async () => {
      requestCache.cachedFetch.mockResolvedValue({ ok: false }); // simulate failure

      const result = await fetchCategoryMedia('cat-404', 1);

      expect(result.media).toEqual([]);
      expect(result.hasMore).toBe(false);
      expect(result.total).toBeNull();
    });

    it('bypasses client request dedupe on visibility refresh without adding force_refresh', async () => {
      const mockResponse = {
        ok: true,
        json: async () => ({
          files: [{ id: 'f1' }],
          subfolders: [],
          pagination: { hasMore: false, total: 1 }
        })
      };

      global.fetch = vi.fn().mockResolvedValue(mockResponse);

      const result = await fetchCategoryMedia('cat-123', 1, false, null, { bypassClientCache: true });

      expect(result.media).toHaveLength(1);
      expect(global.fetch).toHaveBeenCalledTimes(1);
      expect(requestCache.cachedFetch).not.toHaveBeenCalled();
      expect(global.fetch.mock.calls[0][0]).not.toContain('force_refresh=true');
    });
  });

  describe('fetchCategories', () => {
    it('prunes stale category caches during category-list refreshes', async () => {
      streamingState.setState({
        categoryMediaCache: {
          'cat-live|sf:|mf:all': { media: [{ id: 'a' }], page: 1, hasMore: false, loading: false, subfolders: [] },
          'cat-stale|sf:|mf:all': { media: [{ id: 'b' }], page: 1, hasMore: false, loading: false, subfolders: [] }
        }
      });

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          categories: [{ id: 'cat-live', name: 'Live USB' }],
          pagination: { total: 1, totalPages: 1, hasMore: false }
        })
      });

      const categories = await fetchCategories(true, {
        bypassClientCache: true,
        pruneMissingCategories: true
      });

      expect(categories).toEqual([{ id: 'cat-live', name: 'Live USB' }]);
      expect(streamingState.state.categoryMediaCache['cat-live|sf:|mf:all']).toBeDefined();
      expect(streamingState.state.categoryMediaCache['cat-stale|sf:|mf:all']).toBeUndefined();
    });
  });

  describe('fetchAllCategoryMedia', () => {
    it('should cache failed single-category subfolder loads under the subfolder key', async () => {
      streamingState.setState({
        categoriesData: [{ id: 'cat-123', name: 'Movies' }],
        categoryIdFilter: 'cat-123',
        subfolderFilter: 'Movies/Action',
        mediaFilter: 'all'
      });

      requestCache.cachedFetch.mockRejectedValue(new Error('boom'));

      await fetchAllCategoryMedia(false);

      expect(streamingState.state.categoryMediaCache['cat-123|sf:Movies/Action|mf:all']).toEqual({
        media: [],
        page: 1,
        hasMore: false,
        loading: false,
        subfolders: [],
        asyncIndexing: false,
        indexingProgress: 0
      });
    });
  });

  describe('primeCategoryLoadingShells', () => {
    it('creates loading cache entries for categories that do not have a row cache yet', () => {
      streamingState.setState({
        categoriesData: [{ id: 'cat-1', name: 'Movies' }, { id: 'cat-2', name: 'Shows' }],
        mediaFilter: 'all'
      });

      primeCategoryLoadingShells();

      expect(streamingState.state.categoryMediaCache['cat-1|sf:|mf:all']).toEqual({
        media: [],
        page: 1,
        hasMore: false,
        loading: true,
        subfolders: [],
        asyncIndexing: false,
        indexingProgress: 0
      });
      expect(streamingState.state.categoryMediaCache['cat-2|sf:|mf:all']).toEqual({
        media: [],
        page: 1,
        hasMore: false,
        loading: true,
        subfolders: [],
        asyncIndexing: false,
        indexingProgress: 0
      });
    });
  });

  describe('fetchNewestMedia', () => {
    it('preserves the previous row snapshot while the latest media refresh is pending', async () => {
      let resolveFetch;
      const previousMedia = [{ id: 'old-1', name: 'Old upload' }];
      streamingState.setState({ whatsNewData: previousMedia });

      global.fetch = vi.fn().mockReturnValue(new Promise((resolve) => {
        resolveFetch = resolve;
      }));

      const refreshPromise = fetchNewestMedia(10, true);

      expect(streamingState.state.whatsNewLoading).toBe(true);
      expect(streamingState.state.whatsNewData).toEqual(previousMedia);

      resolveFetch({
        ok: true,
        json: async () => ({
          media: [{ id: 'new-1', name: 'New upload' }]
        })
      });

      await refreshPromise;

      expect(streamingState.state.whatsNewLoading).toBe(false);
      expect(streamingState.state.whatsNewData).toEqual([{ id: 'new-1', name: 'New upload' }]);
    });
  });
});
