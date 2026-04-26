/**
 * Streaming Layout - Data Fetching
 * All API calls and data management for the streaming layout.
 */

import {
    getLocalProgress
} from '../../../utils/progressDB.js';
import { hasActiveProfile } from '../../../utils/profileUtils.js';

import { getShowHiddenHeaders, appendShowHiddenParam } from '../../../utils/showHiddenManager.js';
import { cachedFetch } from '../../../utils/requestCache.js';

import {
    fetchVideoProgressData,
    ensureProgressDBReady as ensureDBReady
} from '../../../utils/layoutUtils.js';
import { isPendingDeletion } from '../../media/progressPersistence.js';

import {
    MEDIA_PER_PAGE,
    getCategoriesData,
    setCategoriesData,
    getCategoryCache,
    setCategoryCache,
    clearCategoryMediaCache,
    pruneCategoryMediaCache,
    setContinueWatchingData,
    setWhatsNewData,
    updateCategoryCache,
    getMediaFilter,
    getCategoryIdFilter,
    getSubfolderFilter,
    getParentNameFilter,
    getCategoryIdsFilter,
    getCurrentPage,
    getLimit,
    setTotal,
    setTotalPages,
    setHasMore,
    setGridTotalItems,
    setVideoProgressMap,
    setContinueWatchingLoading,
    setWhatsNewLoading
} from './state.js';

// ── Thumbnail prewarm ────────────────────────────────────────────────────────

const prewarmedThumbnails = new Set();

function queueThumbnailPrewarm(mediaItems, limit = 8) {
    if (!Array.isArray(mediaItems) || mediaItems.length === 0) return;
    const candidates = mediaItems
        .filter(item => item && (item.thumbnailUrl || item.url))
        .slice(0, limit)
        .map(item => item.thumbnailUrl || item.url)
        .filter(url => typeof url === 'string' && url.includes('/thumbnails/'))
        .filter(Boolean);
    if (candidates.length === 0) return;
    const run = () => {
        candidates.forEach(url => {
            const finalUrl = appendShowHiddenParam(url);
            if (!finalUrl || prewarmedThumbnails.has(finalUrl)) return;
            prewarmedThumbnails.add(finalUrl);
            const img = new Image();
            img.decoding = 'async';
            img.fetchPriority = 'low';
            img.src = finalUrl;
        });
    };
    if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(run, { timeout: 2000 });
    } else {
        setTimeout(run, 0);
    }
}

// ── API calls ────────────────────────────────────────────────────────────────

/**
 * Fetch categories from API.
 */
export async function fetchCategories(
    forceRefresh = false,
    { bypassClientCache = false, pruneMissingCategories = false, signal = null } = {}
) {
    const params = new URLSearchParams();
    const categoryIdFilter = getCategoryIdFilter();
    const parentNameFilter = getParentNameFilter();
    const categoryIdsFilter = getCategoryIdsFilter();
    const mediaFilter = getMediaFilter();
    const currentPage = getCurrentPage();
    const limit = getLimit();

    params.append('page', currentPage);
    params.append('limit', limit);

    if (mediaFilter && mediaFilter !== 'all') params.append('filter', mediaFilter);
    if (forceRefresh) params.append('force_refresh', 'true');
    if (categoryIdFilter) params.append('category_id', categoryIdFilter);
    if (categoryIdsFilter && categoryIdsFilter.length > 0) {
        params.append('category_ids', categoryIdsFilter.join(','));
    } else if (parentNameFilter) {
        params.append('parent_name', parentNameFilter);
    }

    const url = `/api/categories?${params.toString()}`;
    const skipClientCache = forceRefresh || bypassClientCache;
    const response = skipClientCache
        ? await fetch(url, { headers: getShowHiddenHeaders(), cache: 'no-store', signal })
        : await cachedFetch(url, { headers: getShowHiddenHeaders(), signal });

    if (!response.ok) throw new Error('Failed to fetch categories');

    const data = await response.json();
    if (signal?.aborted) return [];
    const categories = data.categories || [];

    if (data.pagination) {
        setTotal(data.pagination.total || 0);
        setTotalPages(data.pagination.totalPages || 1);
        setHasMore(data.pagination.hasMore || false);
    }

    setCategoriesData(categories);
    if (pruneMissingCategories) {
        pruneCategoryMediaCache(categories.map((category) => category?.id).filter(Boolean));
    }
    return categories;
}

/**
 * Fetch media items for a single category.
 */
export async function fetchCategoryMedia(
    categoryId,
    page = 1,
    forceRefresh = false,
    subfolder = null,
    { includeTotal = false, limit: customLimit, signal = null, bypassClientCache = false } = {}
) {
    try {
        const effectiveLimit = customLimit || MEDIA_PER_PAGE;
        const params = new URLSearchParams({
            page: page.toString(),
            limit: effectiveLimit.toString()
        });
        if (!includeTotal) params.append('include_total', 'false');
        if (forceRefresh) params.append('force_refresh', 'true');
        if (subfolder) params.append('subfolder', subfolder);

        const url = `/api/categories/${encodeURIComponent(categoryId)}/media?${params}`;
        const response = forceRefresh || bypassClientCache
            ? await fetch(url, { headers: getShowHiddenHeaders(), cache: 'no-store', signal })
            : await cachedFetch(url, { headers: getShowHiddenHeaders(), signal });

        if (!response.ok) return { media: [], hasMore: false, total: null, subfolders: [], asyncIndexing: false, indexingProgress: 0 };

        const data = await response.json();
        if (signal?.aborted) return { media: [], hasMore: false, total: null, subfolders: [], asyncIndexing: false, indexingProgress: 0 };

        if (data.async_indexing) {
            const media = data.files || [];
            const subfolders = data.subfolders || [];
            const total = data.pagination?.total ?? null;

            queueThumbnailPrewarm(media, 8);
            return {
                media,
                hasMore: false,
                subfolders,
                total,
                asyncIndexing: true,
                indexingProgress: data.indexing_progress || 0
            };
        }

        const media = data.files || [];
        const hasMore = data.pagination ? data.pagination.hasMore : (media.length >= effectiveLimit);
        const total = data.pagination?.total ?? null;
        const subfolders = data.subfolders || [];

        queueThumbnailPrewarm(media, 8);
        return { media, hasMore, subfolders, total, asyncIndexing: false, indexingProgress: 100 };
    } catch (e) {
        console.error(`[StreamingLayout] Error fetching media for ${categoryId}:`, e);
        return { media: [], hasMore: false, subfolders: [], total: null, asyncIndexing: false, indexingProgress: 0 };
    }
}

/**
 * Fetch all category media for the current page (eager first 3, rest JIT).
 */
export async function fetchAllCategoryMedia(forceRefresh = false, onCategoryLoaded = null, { signal = null, bypassClientCache = false } = {}) {
    if (forceRefresh) clearCategoryMediaCache();
    if (signal?.aborted) return;

    const categories = getCategoriesData();
    if (!categories || categories.length === 0) return;

    const isSingleCategoryView = getCategoryIdFilter() !== null || getSubfolderFilter() !== null;
    const categoriesToLoad = categories;
    const gridChunkSize = 30;

    let loadedCount = 0;
    let nextIndex = 0;
    const totalToLoad = categoriesToLoad.length;
    const maxConcurrency = Math.min(6, totalToLoad);

    const fetchOne = async (category) => {
        if (signal?.aborted) return;
        const subfolderFilter = getSubfolderFilter();
        const categoryFilter = getCategoryIdFilter();
        const activeSubfolder = (subfolderFilter && categoryFilter === category.id) ? subfolderFilter : null;
        try {
            const fetchOptions = (isSingleCategoryView && categories.length === 1)
                ? { includeTotal: true, limit: gridChunkSize }
                : {};
            const result = await fetchCategoryMedia(category.id, 1, forceRefresh, activeSubfolder, {
                ...fetchOptions,
                signal,
                bypassClientCache
            });
            if (signal?.aborted) return;
            if (isSingleCategoryView && result.total !== null && result.total !== undefined) {
                setGridTotalItems(result.total);
            }
            setCategoryCache(category.id, {
                media: result.media,
                page: 1,
                hasMore: result.hasMore,
                loading: false,
                subfolders: result.subfolders || [],
                asyncIndexing: result.asyncIndexing === true,
                indexingProgress: result.indexingProgress || 0
            }, activeSubfolder, getMediaFilter());
        } catch (e) {
            console.warn(`[StreamingLayout] Failed to fetch media for ${category.id}:`, e);
            setCategoryCache(category.id, {
                media: [],
                page: 1,
                hasMore: false,
                loading: false,
                subfolders: [],
                asyncIndexing: false,
                indexingProgress: 0
            }, activeSubfolder, getMediaFilter());
        } finally {
            loadedCount++;
            if (typeof onCategoryLoaded === 'function') {
                try { onCategoryLoaded(category, loadedCount, categories.length); } catch (_) { /* ignore */ }
            }
        }
    };

    const workers = Array.from({ length: maxConcurrency }, async () => {
        while (true) {
            if (signal?.aborted) break;
            const current = nextIndex++;
            if (current >= totalToLoad) break;
            await fetchOne(categoriesToLoad[current]);
        }
    });

    await Promise.all(workers);
}

export function primeCategoryLoadingShells({ replaceExisting = false } = {}) {
    const categories = getCategoriesData() || [];
    if (categories.length === 0) return;

    const categoryFilter = getCategoryIdFilter();
    const subfolderFilter = getSubfolderFilter();
    const mediaFilter = getMediaFilter();

    categories.forEach((category) => {
        if (!category?.id) return;
        const activeSubfolder = (subfolderFilter && categoryFilter === category.id) ? subfolderFilter : null;
        const existingCache = getCategoryCache(category.id, activeSubfolder, mediaFilter)
            || (mediaFilter && mediaFilter !== 'all' ? getCategoryCache(category.id, activeSubfolder, 'all') : null);

        if (!replaceExisting && existingCache) return;

        setCategoryCache(category.id, {
            media: [],
            page: 1,
            hasMore: false,
            loading: true,
            subfolders: [],
            asyncIndexing: false,
            indexingProgress: 0
        }, activeSubfolder, mediaFilter);
    });
}

/**
 * Load more media for a category (pagination / horizontal VS).
 */
export async function loadMoreMedia(categoryId) {
    const subfolderFilter = getSubfolderFilter();
    const categoryFilter = getCategoryIdFilter();
    const activeSubfolder = (subfolderFilter && categoryFilter === categoryId) ? subfolderFilter : null;
    const mediaFilter = getMediaFilter();
    const cache = getCategoryCache(categoryId, activeSubfolder, mediaFilter)
        || (mediaFilter && mediaFilter !== 'all' ? getCategoryCache(categoryId, activeSubfolder, 'all') : null);
    if (!cache || cache.loading || !cache.hasMore) return [];

    updateCategoryCache(categoryId, { loading: true }, activeSubfolder, mediaFilter);
    try {
        const nextPage = cache.page + 1;
        const result = await fetchCategoryMedia(categoryId, nextPage, false, activeSubfolder);
        if (result.media.length > 0) {
            updateCategoryCache(categoryId, {
                media: cache.media.concat(result.media),
                page: nextPage,
                hasMore: result.hasMore,
                loading: false,
                asyncIndexing: result.asyncIndexing === true,
                indexingProgress: result.indexingProgress || 0
            }, activeSubfolder, mediaFilter);
            return result.media;
        } else {
            updateCategoryCache(categoryId, {
                hasMore: false,
                loading: false,
                asyncIndexing: result.asyncIndexing === true,
                indexingProgress: result.indexingProgress || 0
            }, activeSubfolder, mediaFilter);
            return [];
        }
    } catch (e) {
        console.error(`[StreamingLayout] Error loading more media for ${categoryId}:`, e);
        updateCategoryCache(categoryId, { loading: false }, activeSubfolder, mediaFilter);
        return [];
    }
}

/**
 * Build continue watching data from video progress.
 */
export async function buildContinueWatchingData(forceRefresh = false) {
    setContinueWatchingLoading(true);

    try {
        const videos = await fetchVideoProgressData(50, forceRefresh);
        const categories = getCategoriesData();
        const categoryNameById = new Map(categories.map(c => [c.id, c.name]));
        const continueWatchingMap = new Map();
        const nextVideoProgressMap = {};

        const normalizeVideoUrl = (url) => {
            if (!url) return '';
            try {
                url = decodeURIComponent(url);
            } catch (_) { /* ignore */ }
            return String(url).split('#')[0].split('?')[0];
        };

        for (const v of videos) {
            const videoUrl = v.video_url || v.video_path;
            const timestamp = v.video_timestamp;
            if (!videoUrl || !timestamp || timestamp <= 0) continue;
            // Skip videos that were just marked completed (race-condition guard)
            if (isPendingDeletion(videoUrl)) continue;
            const lastWatched = v.last_watched || v.last_updated || 0;
            const entry = {
                videoUrl,
                categoryId: v.category_id,
                categoryName: categoryNameById.get(v.category_id) || 'Unknown',
                thumbnailUrl: v.thumbnail_url,
                videoTimestamp: timestamp,
                videoDuration: v.video_duration || 0,
                lastWatched
            };
            const normalizedUrl = normalizeVideoUrl(videoUrl) || videoUrl;
            const existing = continueWatchingMap.get(normalizedUrl);
            if (!existing || Number(existing.lastWatched || 0) <= Number(lastWatched || 0)) {
                continueWatchingMap.set(normalizedUrl, entry);
            }
            nextVideoProgressMap[normalizedUrl] = {
                video_timestamp: timestamp,
                video_duration: v.video_duration || 0
            };
        }

        const continueWatching = [...continueWatchingMap.values()];
        continueWatching.sort((a, b) => (b.lastWatched || 0) - (a.lastWatched || 0));
        setVideoProgressMap(nextVideoProgressMap);
        setContinueWatchingData(continueWatching);
        return continueWatching;
    } catch (error) {
        console.error('[StreamingLayout] Error building Continue Watching data:', error);
        return [];
    } finally {
        setContinueWatchingLoading(false);
    }
}

/**
 * Get progress for a category from the correct source.
 */
export function getCategoryProgress(category) {
    let savedIndex = category.saved_index;
    let videoTimestamp = category.video_timestamp || 0;
    let videoDuration = category.video_duration || 0;
    let thumbnailUrl = category.thumbnailUrl;

    if (!hasActiveProfile()) {
        const localProgress = getLocalProgress(category.id);
        if (localProgress) {
            savedIndex = localProgress.index;
            videoTimestamp = localProgress.video_timestamp || 0;
            videoDuration = localProgress.video_duration || 0;
            if (localProgress.thumbnail_url) thumbnailUrl = localProgress.thumbnail_url;
        } else {
            savedIndex = null;
            videoTimestamp = 0;
            videoDuration = 0;
        }
    }

    return { savedIndex, videoTimestamp, videoDuration, thumbnailUrl };
}

export async function ensureProgressDBReady() {
    await ensureDBReady();
}

/**
 * Fetch newest media across all categories.
 */
export async function fetchNewestMedia(limit = 10, forceRefresh = false) {
    setWhatsNewLoading(true);
    try {
        const url = `/api/media/newest?limit=${limit}${forceRefresh ? '&force_refresh=true' : ''}`;
        const response = await fetch(url, { headers: getShowHiddenHeaders(), cache: 'no-store' });
        if (!response.ok) return [];
        const data = await response.json();
        const media = data.media || [];
        setWhatsNewData(media);
        return media;
    } catch (e) {
        console.error('[StreamingLayout] Error fetching newest media:', e);
        return [];
    } finally {
        setWhatsNewLoading(false);
    }
}

export function getLoadedCategoryCount() {
    return getCategoriesData().length;
}
