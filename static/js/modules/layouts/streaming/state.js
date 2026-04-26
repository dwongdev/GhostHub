/**
 * Streaming Layout - State Management
 *
 * StreamingStateModule extends Module so other modules/components can subscribe
 * to state changes. All legacy getter/setter exports are thin wrappers kept for
 * backward compatibility with data.js, rows.js, cards.js, navigation.js, etc.
 */
import { Module, $ } from '../../../libs/ragot.esm.min.js';

export const MEDIA_PER_PAGE = 20;
export const SCROLL_LOAD_THRESHOLD = 200;
export const MAX_CONTINUE_WATCHING = 15;

// ── StreamingStateModule ────────────────────────────────────────────────────

export class StreamingStateModule extends Module {
    constructor() {
        super({
            // Container reference
            streamingContainer: null,
            isStreamingLayout: false,

            // Media data
            categoriesData: [],
            categoryMediaCache: {},
            continueWatchingData: [],
            whatsNewData: [],
            videoProgressMap: {},
            continueWatchingLoading: false,
            whatsNewLoading: false,

            // UI/loading state
            isLoading: false,

            // Filter state
            mediaFilter: 'all',
            categoryIdFilter: null,
            categoryNameFilter: null,
            subfolderFilter: null,
            parentNameFilter: null,
            categoryIdsFilter: null,

            // Grid mode
            gridMode: false,
            gridTotalItems: 0,

            // Pagination
            currentPage: 1,
            limit: 20,
            total: 0,
            totalPages: 1,
            hasMore: false,
        });

        // Lazy loading observer — not reactive, no subscribers need it
        this._lazyLoadObserver = null;
    }
}

// Singleton — started immediately so subscribers can attach before layout init
export const streamingState = new StreamingStateModule();
streamingState.start();

// Lazy-loaded image tracker — WeakSet, never reactive
export const lazyLoadedImages = new WeakSet();

// ── Getters ─────────────────────────────────────────────────────────────────

export function getContainer() {
    return $('#streaming-content-container') || $('#streaming-container') || streamingState.state.streamingContainer;
}
export function isActive() { return document.documentElement.getAttribute('data-layout') === 'streaming'; }
export function getIsLoading() { return streamingState.state.isLoading; }
export function getCategoriesData() { return streamingState.state.categoriesData; }
export function getContinueWatchingData() { return streamingState.state.continueWatchingData; }
export function getWhatsNewData() { return streamingState.state.whatsNewData; }
export function getVideoProgressMap() { return streamingState.state.videoProgressMap; }
export function getContinueWatchingLoading() { return streamingState.state.continueWatchingLoading; }
export function getWhatsNewLoading() { return streamingState.state.whatsNewLoading; }
export function getLazyLoadObserver() { return streamingState._lazyLoadObserver; }
export function getLazyLoadedImages() { return lazyLoadedImages; }
export function getMediaFilter() { return streamingState.state.mediaFilter; }
export function getCategoryIdFilter() { return streamingState.state.categoryIdFilter; }
export function getCategoryNameFilter() { return streamingState.state.categoryNameFilter; }
export function getSubfolderFilter() { return streamingState.state.subfolderFilter; }
export function getParentNameFilter() { return streamingState.state.parentNameFilter; }
export function getCategoryIdsFilter() { return streamingState.state.categoryIdsFilter; }
export function getCurrentPage() { return streamingState.state.currentPage; }
export function getLimit() { return streamingState.state.limit; }
export function getTotal() { return streamingState.state.total; }
export function getTotalPages() { return streamingState.state.totalPages; }
export function getHasMore() { return streamingState.state.hasMore; }
export function getGridMode() { return streamingState.state.gridMode; }
export function getGridTotalItems() { return streamingState.state.gridTotalItems; }

// ── Setters ─────────────────────────────────────────────────────────────────

export function setContainer(container) { streamingState.setState({ streamingContainer: container }); }
export function setIsStreamingLayout(value) { streamingState.setState({ isStreamingLayout: value }); }
export function setIsLoading(value) { streamingState.setState({ isLoading: value }); }
export function setCategoriesData(data) { streamingState.setState({ categoriesData: data }); }
export function setCategoryMediaCache(cache) { streamingState.setState({ categoryMediaCache: cache }); }
export function setContinueWatchingData(data) { streamingState.setState({ continueWatchingData: data }); }
export function setWhatsNewData(data) { streamingState.setState({ whatsNewData: data }); }
export function setVideoProgressMap(map) { streamingState.setState({ videoProgressMap: map }); }
export function setContinueWatchingLoading(value) { streamingState.setState({ continueWatchingLoading: value }); }
export function setWhatsNewLoading(value) { streamingState.setState({ whatsNewLoading: value }); }
export function setLazyLoadObserver(observer) { streamingState._lazyLoadObserver = observer; }
export function setMediaFilter(filter) { streamingState.setState({ mediaFilter: filter }); }
export function setCategoryIdFilter(id) { streamingState.setState({ categoryIdFilter: id }); }
export function setCategoryNameFilter(name) { streamingState.setState({ categoryNameFilter: name }); }
export function setSubfolderFilter(subfolder) { streamingState.setState({ subfolderFilter: subfolder }); }
export function setParentNameFilter(name) { streamingState.setState({ parentNameFilter: name }); }
export function setCategoryIdsFilter(ids) { streamingState.setState({ categoryIdsFilter: ids }); }
export function setCurrentPage(page) { streamingState.setState({ currentPage: page }); }
export function setLimit(value) { streamingState.setState({ limit: value }); }
export function setTotal(value) { streamingState.setState({ total: value }); }
export function setTotalPages(value) { streamingState.setState({ totalPages: value }); }
export function setHasMore(value) { streamingState.setState({ hasMore: value }); }
export function setGridMode(value) { streamingState.setState({ gridMode: value }); }
export function setGridTotalItems(value) { streamingState.setState({ gridTotalItems: value }); }

// ── Cache operations ─────────────────────────────────────────────────────────
// Replace the whole reference on each mutation so Module subscribers see the change.

export function getCategoryCache(categoryId, subfolder = null, mf = 'all') {
    const key = `${categoryId}|sf:${subfolder || ''}|mf:${mf || 'all'}`;
    return streamingState.state.categoryMediaCache[key];
}

export function setCategoryCache(categoryId, data, subfolder = null, mf = 'all') {
    const key = `${categoryId}|sf:${subfolder || ''}|mf:${mf || 'all'}`;
    const cache = { ...streamingState.state.categoryMediaCache };
    cache[key] = data;
    streamingState.setState({ categoryMediaCache: cache });
}

export function clearCategoryMediaCache() {
    streamingState.setState({ categoryMediaCache: {} });
}

export function pruneCategoryMediaCache(validCategoryIds) {
    if (!Array.isArray(validCategoryIds) || validCategoryIds.length === 0) {
        streamingState.setState({ categoryMediaCache: {} });
        return;
    }

    const validIds = new Set(validCategoryIds.map((categoryId) => String(categoryId)));
    const nextCache = Object.fromEntries(
        Object.entries(streamingState.state.categoryMediaCache).filter(([key]) => {
            const [categoryId] = key.split('|sf:');
            return validIds.has(categoryId);
        }),
    );
    streamingState.setState({ categoryMediaCache: nextCache });
}

export function updateCategoryCache(categoryId, updates, subfolder = null, mf = 'all') {
    const key = `${categoryId}|sf:${subfolder || ''}|mf:${mf || 'all'}`;
    const existing = streamingState.state.categoryMediaCache[key];
    if (!existing) return;
    const cache = { ...streamingState.state.categoryMediaCache };
    cache[key] = { ...existing, ...updates };
    streamingState.setState({ categoryMediaCache: cache });
}

// ── Video progress operations ────────────────────────────────────────────────

export function getVideoProgress(videoUrl) {
    if (!videoUrl) return null;
    const direct = streamingState.state.videoProgressMap[videoUrl];
    if (direct) return direct;
    for (const [key, value] of Object.entries(streamingState.state.videoProgressMap)) {
        if (urlMatches(key, videoUrl)) {
            return value;
        }
    }
    return null;
}

export function setVideoProgress(videoUrl, progress) {
    const map = { ...streamingState.state.videoProgressMap };
    map[videoUrl] = progress;
    streamingState.setState({ videoProgressMap: map });
}

export function deleteVideoProgress(videoUrl) {
    if (!videoUrl) return;
    const map = { ...streamingState.state.videoProgressMap };
    let changed = false;
    Object.keys(map).forEach((key) => {
        if (urlMatches(key, videoUrl)) {
            delete map[key];
            changed = true;
        }
    });
    if (changed) streamingState.setState({ videoProgressMap: map });
}

export function clearVideoProgressMap() {
    streamingState.setState({ videoProgressMap: {} });
}

export function clearContinueWatchingData() {
    streamingState.setState({ continueWatchingData: [] });
}

export function clearWhatsNewData() {
    streamingState.setState({ whatsNewData: [] });
}

// ── URL rename helpers ───────────────────────────────────────────────────────

function buildThumbnailUrlFromVideoUrl(videoUrl) {
    if (!videoUrl || !videoUrl.startsWith('/media/')) return null;
    const parts = videoUrl.split('/');
    if (parts.length < 4) return null;
    const categoryId = parts[2];
    const filename = decodeURIComponent(parts.slice(3).join('/'));
    if (!categoryId || !filename) return null;
    const baseName = filename
        .replace(/[/\\]/g, '_')
        .replace(/\.[^.]+$/, '')
        .replace(/[?&%#'!$"()[\]{}+=, ;]/g, '_');
    return `/thumbnails/${categoryId}/${encodeURIComponent(baseName)}.jpeg`;
}

function urlMatches(a, b) {
    if (!a || !b) return false;
    if (a === b) return true;
    try { if (a === encodeURI(b)) return true; } catch (e) { /* ignore */ }
    try { if (a === decodeURIComponent(b)) return true; } catch (e) { /* ignore */ }
    try { if (decodeURIComponent(a) === decodeURIComponent(b)) return true; } catch (e) { /* ignore */ }
    return false;
}

function getFilenameFromUrl(url) {
    if (!url) return null;
    const raw = String(url).split('?')[0].split('#')[0];
    const last = raw.split('/').pop();
    if (!last) return null;
    try { return decodeURIComponent(last); } catch (e) { return last; }
}

export function updateContinueWatchingVideoUrl(oldUrl, newUrl) {
    if (!oldUrl || !newUrl) return;
    const oldThumb = buildThumbnailUrlFromVideoUrl(oldUrl);
    const newThumb = buildThumbnailUrlFromVideoUrl(newUrl);
    let updated = 0;
    const data = streamingState.state.continueWatchingData.map(item => {
        if (item.videoUrl !== oldUrl) return item;
        const copy = { ...item, videoUrl: newUrl };
        if (copy.thumbnailUrl === oldUrl) copy.thumbnailUrl = newUrl;
        else if (oldThumb && newThumb && copy.thumbnailUrl === oldThumb) copy.thumbnailUrl = newThumb;
        updated++;
        return copy;
    });
    if (updated > 0) streamingState.setState({ continueWatchingData: data });
}

export function updateVideoProgressMapUrl(oldUrl, newUrl) {
    if (!oldUrl || !newUrl) return;
    const entry = streamingState.state.videoProgressMap[oldUrl];
    if (!entry) return;
    const map = { ...streamingState.state.videoProgressMap };
    map[newUrl] = entry;
    delete map[oldUrl];
    streamingState.setState({ videoProgressMap: map });
}

export function updateCategoryMediaCacheForRename(oldUrl, newUrl) {
    if (!oldUrl || !newUrl) return;
    const oldThumb = buildThumbnailUrlFromVideoUrl(oldUrl);
    const newThumb = buildThumbnailUrlFromVideoUrl(newUrl);
    const newFilename = getFilenameFromUrl(newUrl);

    function applyRename(item) {
        if (!urlMatches(item.url, oldUrl)) return item;
        const clone = { ...item, url: newUrl };
        if (newFilename) { clone.name = newFilename; clone.displayName = newFilename; clone.filename = newFilename; }
        if (clone.thumbnailUrl === oldUrl) clone.thumbnailUrl = newUrl;
        else if (oldThumb && newThumb && clone.thumbnailUrl === oldThumb) clone.thumbnailUrl = newThumb;
        return clone;
    }

    const cache = { ...streamingState.state.categoryMediaCache };
    Object.keys(cache).forEach(key => {
        const entry = cache[key];
        if (!entry || !Array.isArray(entry.media)) return;
        cache[key] = { ...entry, media: entry.media.map(applyRename) };
    });

    const whatsNewData = Array.isArray(streamingState.state.whatsNewData)
        ? streamingState.state.whatsNewData.map(applyRename)
        : streamingState.state.whatsNewData;

    streamingState.setState({ categoryMediaCache: cache, whatsNewData });
}
