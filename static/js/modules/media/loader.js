/**
 * Media Loader Module
 * Manages media loading, caching, and resource cleanup
 */


import { getShowHiddenHeaders } from '../../utils/showHiddenManager.js';

import {
    addToCache,
    getFromCache,
    hasInCache,
    performCacheCleanup
} from '../../utils/cacheManager.js';

import { renderMediaWindow } from './navigation.js';
import { toggleAutoPlay } from '../playback/autoPlay.js';
import {
    getLocalProgress,
    getAllVideoLocalProgress,
    getCategoryVideoLocalProgress,
    initProgressDB,
    isProgressDBReady,
} from '../../utils/progressDB.js';
import { hasActiveProfile } from '../../utils/profileUtils.js';
import { fileIcon } from '../../utils/icons.js';
import { createElement, css, attr, $, $$ } from '../../libs/ragot.esm.min.js';
import {
    setupControls,
    toggleSpinner
} from '../ui/controller.js';
import { showIndexingStatus, hideIndexingStatus } from '../../utils/indexingStatusLane.js';

// Local state for the current subfolder being viewed
let activeSubfolder = null;

function normalizeVideoProgressMap(progressMap) {
    if (!progressMap || typeof progressMap !== 'object') return {};
    const normalized = {};
    Object.entries(progressMap).forEach(([url, value]) => {
        if (!value || typeof value !== 'object') return;
        const videoTimestamp = Number(value.video_timestamp ?? value.timestamp ?? 0) || 0;
        const videoDuration = Number(value.video_duration ?? value.duration ?? 0) || 0;
        if (videoTimestamp > 0) {
            normalized[url] = {
                ...value,
                video_timestamp: videoTimestamp,
                video_duration: videoDuration
            };
        }
    });
    return normalized;
}

function resolveVideoProgressForUrl(progressMap, url) {
    if (!progressMap || !url) return null;
    if (progressMap[url]) return progressMap[url];
    try {
        const encoded = encodeURI(url);
        if (progressMap[encoded]) return progressMap[encoded];
    } catch (e) { /* ignore */ }
    try {
        const decoded = decodeURIComponent(url);
        if (progressMap[decoded]) return progressMap[decoded];
    } catch (e) { /* ignore */ }
    return null;
}


function findMediaIndexByUrl(mediaList, targetUrl) {
    if (!Array.isArray(mediaList) || !targetUrl) return -1;
    return mediaList.findIndex((item) => urlsMatch(item?.url, targetUrl) || urlsMatch(targetUrl, item?.url));
}

async function fetchServerCategoryProgress(categoryId, limit = 500) {
    try {
        const response = await fetch(`/api/progress/videos?limit=${limit}`, {
            headers: getShowHiddenHeaders(),
            cache: 'no-store'
        });
        if (!response.ok) {
            return { progressMap: {}, latest: null };
        }
        const payload = await response.json();
        const videos = Array.isArray(payload?.videos) ? payload.videos : [];
        const categoryVideos = videos.filter((entry) => entry?.category_id === categoryId);
        const progressMap = {};

        categoryVideos.forEach((entry) => {
            const videoUrl = entry.video_path || entry.video_url;
            const videoTimestamp = Number(entry.video_timestamp || 0);
            if (!videoUrl || videoTimestamp <= 0) return;
            progressMap[videoUrl] = {
                video_timestamp: videoTimestamp,
                video_duration: Number(entry.video_duration || 0),
                thumbnail_url: entry.thumbnail_url || null,
                last_watched: entry.last_watched || 0
            };
        });

        const latestEntry = categoryVideos.find((entry) => Number(entry?.video_timestamp || 0) > 0) || null;
        const latest = latestEntry ? {
            video_url: latestEntry.video_path || latestEntry.video_url,
            video_timestamp: Number(latestEntry.video_timestamp || 0),
            video_duration: Number(latestEntry.video_duration || 0)
        } : null;

        return { progressMap, latest };
    } catch (e) {
        console.warn('[ContinueWatching] Failed to fetch server category progress:', e);
        return { progressMap: {}, latest: null };
    }
}

/**
 * Processes a raw file object from the API to ensure it has necessary properties for the app.
 * @param {Object} file - The raw file object.
 * @returns {Object} The processed file object with 'type' and 'originalPath'.
 */
function processApiFile(file) {
    let type = file.type;
    if (!type) {
        if (file.url && /\.(jpe?g|png|gif|webp)$/i.test(file.url)) {
            type = 'image';
        } else if (file.url && /\.(mp4|webm|mov|mkv|avi)$/i.test(file.url)) {
            type = 'video';
        } else {
            type = 'unknown';
        }
    }
    return {
        ...file, // Spread existing file properties
        type: type,
        originalPath: file.path || file.url // Prefer 'path' if available, fallback to 'url'
    };
}
import { setupLayoutNavigation, onLayoutMediaRendered, onLayoutViewerClosed, urlsMatch } from '../../utils/layoutUtils.js';
import { processMediaWithSubfolders, getSubfoldersFromResponse } from '../../utils/subfolderUtils.js';
import { setAppState, batchAppState } from '../../utils/appStateUtils.js';
import { toast } from '../../utils/notificationManager.js';

/**
 * Load and display a media category
 * @param {string}         categoryId    – Category ID to view
 * @param {string[]|null}  [forced_order] – Optional array of media URLs to force a specific order
 * @param {number}         [startIndex=0] – Optional index to start rendering from
 * @param {string|null}    [subfolder=null] – Optional subfolder to filter by
 * @returns {Promise} Resolves when loaded
 */
async function viewCategory(categoryId, forced_order = null, startIndex = null, subfolder = null, sort_by = null, sort_order = null) {
    console.log(`[viewCategory] Entering: category=${categoryId}, startIndex=${startIndex}`);

    // --- INSTANT TRANSITION ---
    // Show spinner in viewer immediately
    toggleSpinner(true);

    // Show viewer immediately — layout container (streaming/gallery) stays in DOM
    // but is covered by the media viewer's higher z-index
    if (window.ragotModules.appDom.mediaViewer) window.ragotModules.appDom.mediaViewer.classList.remove('hidden');

    // Show mobile back button overlay
    const mobileBackOverlay = $('#mobile-back-overlay');
    if (mobileBackOverlay) {
        mobileBackOverlay.style.display = 'block';
    }
    // ---------------------------

    // Stop auto-play when switching categories
    toggleAutoPlay('stop');

    // Capture old map in case you want to preserve extra metadata
    const oldMap = new Map((window.ragotModules.appState.fullMediaList || []).map(item => [item.url, item]));

    // Removed early return checks to ensure proper handling of saved indices

    // IMPORTANT: Preserve video progress state set by streaming layout BEFORE reset
    // This allows Continue Watching to resume at the correct timestamp
    const preservedVideoProgressMap = forced_order ? window.ragotModules.appState.videoProgressMap : null;
    const preservedSavedVideoTimestamp = forced_order ? window.ragotModules.appState.savedVideoTimestamp : null;
    const preservedSavedVideoIndex = forced_order ? window.ragotModules.appState.savedVideoIndex : null;
    const preservedSavedVideoCategoryId = forced_order ? window.ragotModules.appState.savedVideoCategoryId : null;

    // Check if we need to refresh (force refresh only when requested)
    const needsRefresh = window.ragotModules.appState.needsMediaRefresh || false;
    const forceRefresh = window.ragotModules.appState.forceMediaRefresh || false;
    if (needsRefresh) {
        console.log(`[viewCategory] Refresh requested (force=${forceRefresh})`);
        setAppState('needsMediaRefresh', false); // Reset flag
        setAppState('forceMediaRefresh', false);
    }

    // Reset state
    setAppState('currentCategoryId', categoryId);
    // Clear activeSubfolder if not explicitly provided to avoid stale subfolder filters
    activeSubfolder = subfolder || null; // Preserve subfolder for pagination/swiping locally, or clear if not provided
    setAppState('currentPage', 1);
    setAppState('hasMoreMedia', true);
    setAppState('isLoading', false);
    setAppState('fullMediaList', []);
    setAppState('mediaUrlSet', new Set()); // Clear URL tracking Set
    setAppState('knownSubfolders', new Set()); // Track subfolders found on page 1
    setAppState('preloadQueue', []);
    setAppState('isPreloading', false);
    // Initialize currentMediaIndex with startIndex, it might be overridden by last_known_index
    setAppState('currentMediaIndex', startIndex || 0);

    // Clear cache + abort
    window.ragotModules.appCache.clear();
    if (window.ragotModules.appState.currentFetchController) window.ragotModules.appState.currentFetchController.abort();
    setAppState('currentFetchController', new AbortController());
    setAppState('sortBy', sort_by || 'name');
    setAppState('sortOrder', sort_order || 'ASC');

    // Aggressive cleanup of DOM/resources
    clearResources(true);
    if (window.ragotModules.appDom.mediaViewer) {
        $$('.viewer-media', window.ragotModules.appDom.mediaViewer).forEach(el => el.remove());
    }


    setupLayoutNavigation();
    // Render initial window (might be empty, but sets up UI)
    renderMediaWindow(startIndex);
    // ---------------------------

    // Decide page size - Always use appRuntime.getMediaPerPage()
    const pageSize = window.ragotModules.appRuntime.getMediaPerPage();
    const signal = window.ragotModules.appState.currentFetchController.signal;

    try {
        // For shared links (forced_order): Build media objects with proper thumbnail URLs
        // This enables instant loading without page-by-page search (scales to 50k+ items)
        if (forced_order) {
            console.log(`Forced order present (${forced_order.length} URLs) — building media objects with computed thumbnails.`);

            // Show spinner immediately
            toggleSpinner(true);

            setAppState('fullMediaList', forced_order.map(item => {
                // If item is already a processed object (passed from streaming/gallery layout), use it directly
                if (item && typeof item === 'object' && !Array.isArray(item)) {
                    return item;
                }

                // Otherwise, it's a raw URL string (likely from a shared link)
                const url = item;
                const name = decodeURIComponent(url.split('/').pop() || 'unknown');
                const isImage = /\.(jpe?g|png|gif|webp)$/i.test(url);
                const isVideo = /\.(mp4|webm|mov|mkv|avi)$/i.test(url);

                let thumbnailUrl;
                if (isImage) {
                    thumbnailUrl = url;
                } else if (isVideo) {
                    const urlParts = url.split('/');
                    const categoryId = urlParts[2];
                    const baseName = name
                        .replace(/[/\\]/g, '_')
                        .replace(/\.[^.]+$/, '')
                        .replace(/[?&%#'!$"()\[\]{}+=, ;]/g, '_');
                    thumbnailUrl = `/thumbnails/${categoryId}/${encodeURIComponent(baseName)}.jpeg`;
                } else {
                    thumbnailUrl = '/static/icons/Ghosthub192.png';
                }

                return {
                    url,
                    name,
                    displayName: name, // Shared links use filename as display name
                    type: isImage ? 'image' : isVideo ? 'video' : 'unknown',
                    thumbnailUrl
                };
            }));

            // forced_order contains all items - no more to load
            setAppState('hasMoreMedia', false);
            console.log(`Built ${window.ragotModules.appState.fullMediaList.length} media objects from forced_order. hasMoreMedia=false`);

            // Restore preserved video progress state for streaming layout Continue Watching
            if (preservedVideoProgressMap) {
                setAppState('videoProgressMap', normalizeVideoProgressMap(preservedVideoProgressMap));
                console.log('[ContinueWatching] Restored videoProgressMap from streaming layout');
            }
            if (forced_order) {
                setAppState('videoProgressMap', normalizeVideoProgressMap(preservedVideoProgressMap));
                setAppState('savedVideoTimestamp', preservedSavedVideoTimestamp);
                setAppState('savedVideoIndex', preservedSavedVideoIndex);
                setAppState('savedVideoCategoryId', preservedSavedVideoCategoryId);
            }
        } else {
            // Normal first-page load
            const initialData = await loadMoreMedia(pageSize, signal, forceRefresh || false);
            let savedIndexToApply = null;

            // Resolve resume state from the active progress owner.
            let progressSource = 'none';
            let progressIndex = null;
            let progressVideoTimestamp = null;
            let progressVideoDuration = null;
            let progressVideoUrl = null;

            const activeProfile = hasActiveProfile();
            const saveVideoProgressEnabled = window.ragotModules?.appStore?.get?.('config', {})?.python_config?.SAVE_VIDEO_PROGRESS !== false;
            const shouldUseServerProgress = activeProfile;
            let serverCategoryProgress = null;
            let categoryVideoProgressMap = {};

            if (!activeProfile && !isProgressDBReady()) {
                await initProgressDB();
            }

            // Resolve progress data
            if (saveVideoProgressEnabled) {
                if (shouldUseServerProgress) {
                    serverCategoryProgress = await fetchServerCategoryProgress(categoryId);
                }
                const isSyncGuest = window.ragotModules.appState.syncModeEnabled && !window.ragotModules.appState.isHost;
                const hasSyncTimestamp = typeof window.ragotModules.appState.savedVideoTimestamp === 'number';

                if (isSyncGuest && hasSyncTimestamp) {
                    // SYNC GUEST: Skip local/server progress resolution, use the timestamp provided by host
                    progressSource = 'sync';
                    progressIndex = startIndex !== null ? parseInt(startIndex) : (window.ragotModules.appState.savedVideoIndex !== null ? window.ragotModules.appState.savedVideoIndex : 0);
                    progressVideoTimestamp = window.ragotModules.appState.savedVideoTimestamp;
                    console.log(`[Sync] Using host-provided progress for guest: index=${progressIndex}, timestamp=${progressVideoTimestamp}`);
                } else if (!activeProfile && sessionEnabled) {
                    const localProgress = getLocalProgress(categoryId);
                    if (localProgress && localProgress.index !== undefined) {
                        progressSource = 'localStorage';
                        progressIndex = parseInt(localProgress.index);
                        progressVideoTimestamp = localProgress.video_timestamp;
                        progressVideoDuration = localProgress.video_duration;
                    }
                    categoryVideoProgressMap = normalizeVideoProgressMap(getCategoryVideoLocalProgress(categoryId));
                    if (progressVideoTimestamp === null || progressVideoTimestamp <= 0) {
                        const latestCategoryVideo = getAllVideoLocalProgress()
                            .filter((entry) => entry?.category_id === categoryId && Number(entry?.video_timestamp || 0) > 0)
                            .sort((a, b) => Number(b?.last_updated || 0) - Number(a?.last_updated || 0))[0];
                        if (latestCategoryVideo) {
                            progressSource = 'indexeddb-video';
                            progressVideoTimestamp = Number(latestCategoryVideo.video_timestamp || 0);
                            progressVideoDuration = Number(latestCategoryVideo.video_duration || 0);
                            progressVideoUrl = latestCategoryVideo.video_url || null;
                        }
                    }
                } else if (activeProfile) {
                    if (serverCategoryProgress?.latest?.video_timestamp > 0) {
                        progressSource = 'server';
                        progressVideoTimestamp = serverCategoryProgress.latest.video_timestamp;
                        progressVideoDuration = serverCategoryProgress.latest.video_duration;
                        progressVideoUrl = serverCategoryProgress.latest.video_url;
                    }
                }
            }

            if (progressIndex === null && progressVideoUrl) {
                const matchedIndex = findMediaIndexByUrl(window.ragotModules.appState.fullMediaList, progressVideoUrl);
                if (matchedIndex >= 0) {
                    progressIndex = matchedIndex;
                }
            }

            // Explicitly provided index (from card click) should override server/DB progress
            // unless it's null/undefined
            if (startIndex !== null && startIndex !== undefined) {
                const parsed = parseInt(startIndex);
                if (!isNaN(parsed) && parsed >= 0) {
                    savedIndexToApply = parsed;
                    console.log(`[ContinueWatching] Using explicitly passed startIndex: ${savedIndexToApply}`);
                } else {
                    console.warn(`[ContinueWatching] Invalid startIndex (${startIndex}), falling back to progress`);
                    savedIndexToApply = (progressIndex !== null && !isNaN(progressIndex)) ? progressIndex : 0;
                }
            } else if (progressIndex !== null && !isNaN(progressIndex)) {
                savedIndexToApply = progressIndex;
                console.log(`[ContinueWatching] Using resolved progressIndex: ${progressIndex} from ${progressSource}`);
            } else {
                savedIndexToApply = 0;
            }

            console.log('[ContinueWatching] Progress resolved:', { progressSource, progressIndex, progressVideoTimestamp });

            // Store tracking mode
            const trackingMode = initialData?.tracking_mode || 'category';
            setAppState('trackingMode', trackingMode);

            // For video tracking mode, store video progress map
            if (trackingMode === 'video') {
                if (activeProfile) {
                    setAppState('videoProgressMap', normalizeVideoProgressMap(serverCategoryProgress?.progressMap || {}));
                } else if (sessionEnabled) {
                    setAppState('videoProgressMap', normalizeVideoProgressMap(categoryVideoProgressMap));
                } else {
                    setAppState('videoProgressMap', null);
                }
            } else {
                setAppState('videoProgressMap', null);
            }

            // --- RESOLVE RESUME POSITION ---
            // Store video timestamp for resume playback
            let resumeTimestamp = null;
            let resumeDuration = null;

            // Priority 1: Timestamp matched with the resolved index (from server/DB/local)
            // This applies in 'category' tracking mode or when the index is fresh
            if (savedIndexToApply === progressIndex && typeof progressVideoTimestamp === 'number' && progressVideoTimestamp > 0) {
                resumeTimestamp = progressVideoTimestamp;
                resumeDuration = progressVideoDuration || 0;
                console.log(`[ContinueWatching] Using index-matched timestamp: ${resumeTimestamp}`);
            }

            // Priority 2: If Priority 1 failed, check the videoProgressMap for the specific file at this index
            // This is crucial for 'video' tracking mode where progress is mapped by URL
            if (resumeTimestamp === null && window.ragotModules.appState.videoProgressMap) {
                const targetFile = window.ragotModules.appState.fullMediaList?.[savedIndexToApply];
                if (targetFile?.url) {
                    const videoProg = resolveVideoProgressForUrl(window.ragotModules.appState.videoProgressMap, targetFile.url);
                    if (videoProg) {
                        resumeTimestamp = videoProg.video_timestamp;
                        resumeDuration = videoProg.video_duration;
                        console.log(`[ContinueWatching] Using videoProgressMap timestamp: ${resumeTimestamp}`);
                    }
                }
            }

            setAppState('savedVideoTimestamp', resumeTimestamp);
            setAppState('savedVideoDuration', resumeDuration || 0);
            setAppState('savedVideoIndex', savedIndexToApply);
            setAppState('savedVideoCategoryId', categoryId);

            console.log('[ContinueWatching] Progress state initialized:', {
                index: savedIndexToApply,
                timestamp: resumeTimestamp,
                source: progressSource
            });

            // Load pages until we reach the target index
            if (savedIndexToApply > 0) {
                const itemsPerPage = pageSize;
                let currentPage = 2; // Start at page 2 because page 1 is already loaded above
                const maxAttempts = 20; // Safety break to prevent infinite loops

                while (window.ragotModules.appState.fullMediaList.length <= savedIndexToApply && window.ragotModules.appState.hasMoreMedia && currentPage <= maxAttempts) {
                    console.log(`Loading more data to reach saved index ${savedIndexToApply} (current items: ${window.ragotModules.appState.fullMediaList.length}, page: ${currentPage})...`);
                    const pageResult = await loadMoreMedia(itemsPerPage, signal, false, currentPage);

                    if (!pageResult?.files?.length && window.ragotModules.appState.hasMoreMedia) {
                        console.warn(`Failed to load data on attempt ${currentPage}. Retrying...`);
                        await new Promise(resolve => setTimeout(resolve, 500)); // Wait a bit before retrying
                    } else if (!pageResult?.files?.length && !window.ragotModules.appState.hasMoreMedia) {
                        console.warn(`No more media to load after ${currentPage} attempts, and target index ${savedIndexToApply} not reached.`);
                        break;
                    }
                    currentPage++;
                }

                // Update app state with how many pages we actually loaded
                setAppState('currentPage', currentPage);

                // Apply the saved index if we have enough data, otherwise fall back to 0
                setAppState(
                    'currentMediaIndex',
                    savedIndexToApply < window.ragotModules.appState.fullMediaList.length ? savedIndexToApply : 0
                );

                if (window.ragotModules.appState.currentMediaIndex !== savedIndexToApply) {
                    console.warn(`Could not load saved index ${savedIndexToApply}, using index ${window.ragotModules.appState.currentMediaIndex}`);
                }
            }
        }

        // Don't do no-op check here - we haven't rendered the elements yet
        // Even if we've loaded the data for saved index, the elements aren't in the DOM yet

        // Ensure viewer is updated with loaded data
        renderMediaWindow(window.ragotModules.appState.currentMediaIndex);

        // Add a more robust check to ensure the media element for the saved index is actually rendered
        // This is crucial for saved indices on different pages
        setTimeout(() => {
            const targetIndex = window.ragotModules.appState.currentMediaIndex;
            const mediaElement = $(`.viewer-media[data-index="${targetIndex}"]`, window.ragotModules.appDom.mediaViewer);

            // --- SYNC: After confirming the correct index is loaded and rendered, broadcast to guests ---
            if (window.ragotModules.appState.syncModeEnabled && window.ragotModules.appState.isHost) {
                const currentFile = window.ragotModules.appState.fullMediaList[targetIndex];
                window.ragotModules.syncManager.sendSyncUpdate({
                    category_id: window.ragotModules.appState.currentCategoryId,
                    file_url: currentFile?.url || null,
                    index: targetIndex
                }).then(ok => { if (!ok) console.warn('Sync update failed'); });
            }

            if (!mediaElement) {
                console.warn(`Media element for index ${targetIndex} not found in DOM after initial render. Forcing re-render...`);

                // Check if we need to load more data first
                if (targetIndex >= window.ragotModules.appState.fullMediaList.length && window.ragotModules.appState.hasMoreMedia) {
                    console.warn(`Target index ${targetIndex} is beyond current data (${window.ragotModules.appState.fullMediaList.length} items). Loading more data...`);

                    // Load more data and then try rendering again
                    loadMoreMedia(pageSize, signal, false).then(() => {
                        // Double-check if we now have enough data
                        if (targetIndex < window.ragotModules.appState.fullMediaList.length) {
                            console.log(`Successfully loaded data for index ${targetIndex}. Re-rendering...`);
                            renderMediaWindow(targetIndex);
                        } else {
                            console.error(`Failed to load data for index ${targetIndex} after additional attempt. Falling back to index 0.`);
                            // Only fall back to index 0 if we really can't load the target index
                            renderMediaWindow(0);
                        }
                    });
                } else {
                    // We should have the data, so just force a re-render
                    console.log(`Data for index ${targetIndex} should be available. Forcing re-render...`);
                    renderMediaWindow(targetIndex);
                }
            } else {
                console.log(`Media element for index ${targetIndex} successfully rendered.`);

                // Verify the element is properly active
                if (!mediaElement.classList.contains('active')) {
                    console.warn(`Media element for index ${targetIndex} found but not active. Fixing...`);
                    $$('.viewer-media.active', window.ragotModules.appDom.mediaViewer).forEach(el => el.classList.remove('active'));
                    mediaElement.classList.add('active');
                }
            }
        }, 200); // Slightly longer delay to ensure DOM is fully updated

    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error('viewCategory error:', err);
            toast.error('Error loading media');
            // Hide spinner on error so UI isn't stuck
            toggleSpinner(false);
        }
        if (window.ragotModules.appDom.mediaViewer) window.ragotModules.appDom.mediaViewer.classList.add('hidden');

    } finally {
        // Spinner hiding is now handled by renderMediaWindow waiting for load
        // if (window.ragotModules.appDom.spinnerContainer) window.ragotModules.appDom.spinnerContainer.style.display = 'none';
    }
}




/**
 * Load additional media items
 * @param {number|null} customLimit - Items per page
 * @param {AbortSignal|null} signal - For cancellation
 * @param {boolean} forceRefresh - Force server refresh
 * @param {number|null} targetPage - Specific page to load
 */
async function loadMoreMedia(customLimit = null, signal = null, forceRefresh = false, targetPage = null) {
    const effectiveSignal = signal || (window.ragotModules.appState.currentFetchController ? window.ragotModules.appState.currentFetchController.signal : null);
    const pageToLoad = targetPage || window.ragotModules.appState.currentPage; // Use targetPage if provided

    console.log(`loadMoreMedia called: pageToLoad=${pageToLoad}, hasMoreMedia=${window.ragotModules.appState.hasMoreMedia}, isLoading=${window.ragotModules.appState.isLoading}, currentMediaIndex=${window.ragotModules.appState.currentMediaIndex}, fullMediaList.length=${window.ragotModules.appState.fullMediaList.length}`);

    // Check if the signal has been aborted
    if (effectiveSignal && effectiveSignal.aborted) {
        console.log("loadMoreMedia skipped: signal was aborted.");
        return null;
    }

    if (!window.ragotModules.appState.hasMoreMedia || window.ragotModules.appState.isLoading) {
        console.log(`Load more skipped: hasMoreMedia=${window.ragotModules.appState.hasMoreMedia}, isLoading=${window.ragotModules.appState.isLoading}`);
        return null; // Don't load if no more items or already loading
    }

    setAppState('isLoading', true);
    const limit = customLimit || window.ragotModules.appRuntime.getMediaPerPage();
    console.log(`Loading page ${pageToLoad} with limit ${limit}...`); // Use pageToLoad

    // Show loading indicator
    toggleSpinner(true);

    try {
        // Add cache-busting parameter, force_refresh parameter, and the effective AbortSignal
        const cacheBuster = Date.now();
        // Only use forceRefresh parameter as provided, don't default to true for first page
        const forceRefreshParam = forceRefresh ? '&force_refresh=true' : '';
        const fetchOptions = {
            signal: effectiveSignal, // Use the determined signal
            cache: forceRefresh ? 'no-store' : 'default' // Bypass browser HTTP cache when force refreshing
        };
        console.log(`Fetching media with forceRefresh: ${forceRefresh}, syncModeEnabled: ${window.ragotModules.appState.syncModeEnabled}`);
        // Always set shuffle=false in sync mode to ensure consistent ordering
        const shuffleParam = window.ragotModules.appState.syncModeEnabled ? '&shuffle=false' : '';
        // Add a sync parameter to ensure the server knows this is a sync request
        const syncParam = window.ragotModules.appState.syncModeEnabled ? '&sync=true' : '';
        const subfolderParam = activeSubfolder ? `&subfolder=${encodeURIComponent(activeSubfolder)}` : '';
        const sortParam = window.ragotModules.appState.sortBy ? `&sort_by=${window.ragotModules.appState.sortBy}` : '';
        const orderParam = window.ragotModules.appState.sortOrder ? `&sort_order=${window.ragotModules.appState.sortOrder}` : '';
        const response = await fetch(`/api/categories/${window.ragotModules.appState.currentCategoryId}/media?page=${pageToLoad}&limit=${limit}${forceRefreshParam}${shuffleParam}${syncParam}${subfolderParam}${sortParam}${orderParam}&_=${cacheBuster}`, {
            ...fetchOptions,
            headers: {
                ...fetchOptions.headers,
                ...getShowHiddenHeaders()
            }
        }); // Use pageToLoad

        if (!response.ok) {
            // Don't throw error if fetch was aborted, just return
            if (effectiveSignal && effectiveSignal.aborted) {
                console.log("Fetch aborted during loadMoreMedia response check.");
                setAppState('isLoading', false); // Reset loading flag
                return null;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        if (data.error) {
            console.error("Server error fetching more media:", data.error);
            toast.error(`Error loading more media: ${data.error}`);
            setAppState('hasMoreMedia', false); // Stop trying if server reports error
        } else if (data.async_indexing) {
            // Handle async indexing response
            console.log(`Received async indexing response with progress: ${data.indexing_progress}%`);
            setAppState('asyncIndexingActive', true);

            // Process any available files
            if (data.files && data.files.length > 0) {
                console.log(`Received ${data.files.length} media items during indexing.`);
                // Add only new files to avoid duplicates - use persistent Set for O(1) lookup
                const newFilesRaw = data.files.filter(f => !window.ragotModules.appState.mediaUrlSet.has(f.url));
                const newFiles = newFilesRaw.map(processApiFile);

                if (newFiles.length > 0) {
                    batchAppState((state) => {
                        newFiles.forEach(f => state.mediaUrlSet.add(f.url));
                        state.fullMediaList.push(...newFiles);
                    }, { source: 'mediaLoader.loadMoreMedia.appendAsyncFiles' });
                    console.log(`Added ${newFiles.length} new media items.`);

                    // Update swipe indicators if the view is active
                    if (window.ragotModules.appDom.mediaViewer && !window.ragotModules.appDom.mediaViewer.classList.contains('hidden')) {
                        onLayoutMediaRendered(window.ragotModules.appState.currentMediaIndex, window.ragotModules.appState.fullMediaList.length);
                    }
                }
            }

            // Set hasMore based on indexing progress
            setAppState('hasMoreMedia', data.pagination.hasMore || data.indexing_progress < 100);
            const loadedCount = window.ragotModules.appState.fullMediaList.length;
            const primaryText = loadedCount > 0
                ? 'Indexing media. More pages are loading...'
                : 'Preparing media library. First items are loading...';
            const secondaryText = loadedCount > 0
                ? `${data.indexing_progress}% complete - ${loadedCount} items ready`
                : `${data.indexing_progress}% complete`;
            showIndexingStatus(data.indexing_progress, {
                title: primaryText,
                meta: secondaryText
            });

            // If indexing is still in progress, poll for updates
            if (data.indexing_progress < 100) {
                // Schedule another request after a delay
                setTimeout(() => {
                    if (window.ragotModules.appState.currentCategoryId) { // Only if still viewing this category
                        console.log("Polling for indexing progress updates...");
                        loadMoreMedia(limit, effectiveSignal, false, pageToLoad);
                    }
                }, 2000); // Poll every 2 seconds
            } else {
                // Indexing complete, remove progress indicator
                setAppState('asyncIndexingActive', false);
                hideIndexingStatus();

                // Reload from server now that indexing is complete to avoid partial preview lists
                setAppState('fullMediaList', []);
                setAppState('mediaUrlSet', new Set());
                setAppState('knownSubfolders', new Set());
                setAppState('currentPage', 1);
                setAppState('hasMoreMedia', true);

                setTimeout(() => {
                    if (window.ragotModules.appState.currentCategoryId) {
                        loadMoreMedia(limit, effectiveSignal, true, 1);
                    }
                }, 0);
            }
        } else if (data.files && data.files.length > 0) {
            console.log(`Received ${data.files.length} new media items.`);

            // Process subfolder grouping on first page load
            let filesToProcess = data.files;
            if (pageToLoad === 1 && data.subfolders && data.subfolders.length > 0) {
                const subfolders = data.subfolders.map(sf => ({
                    name: sf.name,
                    count: sf.count,
                    containsVideo: sf.contains_video,
                    thumbnailUrl: sf.thumbnail_url || null,
                    categoryId: window.ragotModules.appState.currentCategoryId
                }));
                const processed = processMediaWithSubfolders(data.files, window.ragotModules.appState.currentCategoryId, subfolders);
                filesToProcess = processed.items;
                // Store known subfolder names so we can filter them out on subsequent pages
                setAppState('knownSubfolders', new Set(subfolders.map(sf => sf.name)));
                console.log(`[Subfolders] Found ${subfolders.length} subfolders, processed ${filesToProcess.length} items`);
            } else if (pageToLoad > 1 && window.ragotModules.appState.knownSubfolders && window.ragotModules.appState.knownSubfolders.size > 0) {
                // On subsequent pages, filter out files that belong to known subfolders
                // (they were already represented by subfolder marker cards on page 1)
                filesToProcess = data.files.filter(f => {
                    if (!f.name || !f.name.includes('/')) return true; // Direct file, keep it
                    const subName = f.name.split('/')[0];
                    return !window.ragotModules.appState.knownSubfolders.has(subName);
                });
                if (filesToProcess.length < data.files.length) {
                    console.log(`[Subfolders] Filtered ${data.files.length - filesToProcess.length} subfolder files on page ${pageToLoad}`);
                }
            }

            // Add only new files to avoid duplicates - use persistent Set for O(1) lookup
            const newFilesRaw = filesToProcess.filter(f => !window.ragotModules.appState.mediaUrlSet.has(f.url));
            const newFiles = newFilesRaw.map(f => f.isSubfolder ? f : processApiFile(f));

            if (newFiles.length > 0) {
                // If a specific page was loaded, we might need to insert/replace.
                // For now, append and rely on server order + rendering logic.
                batchAppState((state) => {
                    newFiles.forEach(f => state.mediaUrlSet.add(f.url));
                    state.fullMediaList.push(...newFiles);
                }, { source: 'mediaLoader.loadMoreMedia.appendFiles' });
                console.log(`Added ${newFiles.length} new media items.`);
            } else {
                console.log("Received files, but they were already present in the list.");
            }

            setAppState('hasMoreMedia', data.pagination.hasMore);
            // Only increment currentPage if we loaded the *next* sequential page
            if (!targetPage) {
                setAppState('currentPage', window.ragotModules.appState.currentPage + 1);
            }
            console.log(`Total media now: ${window.ragotModules.appState.fullMediaList.length}, hasMore: ${window.ragotModules.appState.hasMoreMedia}, nextPageToLoad=${window.ragotModules.appState.currentPage}`);

            // If all files on this page were filtered (subfolder files already shown as cards),
            // automatically fetch the next page to avoid empty loads
            if (newFiles.length === 0 && data.files.length > 0 && window.ragotModules.appState.hasMoreMedia && !targetPage) {
                console.log(`[Subfolders] Page ${pageToLoad} had only subfolder files, loading next page...`);
                setTimeout(() => loadMoreMedia(limit, effectiveSignal, false), 0);
            }

            // Update swipe indicators if the view is active
            if (window.ragotModules.appDom.mediaViewer && !window.ragotModules.appDom.mediaViewer.classList.contains('hidden')) {
                onLayoutMediaRendered(window.ragotModules.appState.currentMediaIndex, window.ragotModules.appState.fullMediaList.length);
            }

            // Remove any indexing progress indicator if it exists
            setAppState('asyncIndexingActive', false);
            hideIndexingStatus();
        } else {
            console.log("No more media files received from server.");
            setAppState('hasMoreMedia', false); // No more files returned
            if (!window.ragotModules.appState.hasMoreMedia) {
                setAppState('asyncIndexingActive', false);
                hideIndexingStatus();
            }
        }
        return data; // Return the fetched data
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Fetch aborted (loadMoreMedia).');
            // Don't show an alert for abort errors
        } else {
            console.error('Error loading more media:', error);
            toast.error('Failed to load more media. Please try again later.');
            // Optionally set hasMoreMedia = false or implement retry logic
            toggleSpinner(false);
        }
        return null; // Return null on error
    } finally {
        setAppState('isLoading', false);
        console.log("Loading finished.");
        // Hide loading indicator here reliably
        // if (window.ragotModules.appDom.spinnerContainer) window.ragotModules.appDom.spinnerContainer.style.display = 'none';
    }
}

/**
 * Clean up media resources
 * @param {boolean} aggressive - Deep cleanup if true
 */
function clearResources(aggressive = false) {
    console.log(`Clearing resources (aggressive: ${aggressive})`);
    setAppState('asyncIndexingActive', false);
    hideIndexingStatus();

    // Ensure video-controls UI state is fully reset before removing media nodes.
    window.ragotModules?.videoControls?.detachControls?.();

    // Clear media elements
    $$('.viewer-media', window.ragotModules.appDom.mediaViewer).forEach(el => {
        try {
            if (el.tagName === 'VIDEO') {
                el.pause();
                el.removeAttribute('src');
                el.load(); // Force release of video resources
            }
            el.remove();
        } catch (e) {
            console.error('Error cleaning up media element:', e);
        }
    });

    // Clear controls
    const existingControls = $('.controls-wrapper', window.ragotModules.appDom.mediaViewer);
    if (existingControls) {
        existingControls.remove();
    }

    // Clear indicators
    // Swipe indicators removed from semantic UI

    // Clear preload queue
    setAppState('preloadQueue', []);
    setAppState('isPreloading', false);

    // More aggressive cleanup on mobile or when explicitly requested
    if (aggressive || window.innerWidth <= 768) {
        console.log('Performing aggressive cleanup');
        // Clear the entire cache on aggressive cleanup
        window.ragotModules.appCache.clear();

        // Remove any detached video elements from the DOM
        $$('video').forEach(video => {
            if (!document.body.contains(video.parentElement)) {
                try {
                    video.pause();
                    video.removeAttribute('src');
                    video.load();
                    video.remove();
                } catch (e) {
                    console.error('Error removing detached video:', e);
                }
            }
        });

        // Use the performCacheCleanup function from cacheManager.js
        performCacheCleanup(true);
    } else {
        // Regular cleanup - limit cache size
        performCacheCleanup();
    }
}

/**
 * Preload next media items in background
 */
function preloadNextMedia() {
    if (window.ragotModules.appState.isPreloading || window.ragotModules.appState.preloadQueue.length === 0) return;

    // Get device memory if available, default to 4GB if not
    const deviceMemory = navigator.deviceMemory || 4;

    // Low-memory client optimization: use conservative cache size
    const adjustedMaxCacheSize = window.ragotModules.appRuntime.LOW_MEMORY_DEVICE ? Math.min(window.ragotModules.appRuntime.MAX_CACHE_SIZE, 10) : window.ragotModules.appRuntime.MAX_CACHE_SIZE;

    // Skip preloading if cache is getting too large
    if (window.ragotModules.appCache.size >= adjustedMaxCacheSize) {
        console.log(`Cache size (${window.ragotModules.appCache.size}) >= adjusted window.ragotModules.appRuntime.MAX_CACHE_SIZE (${adjustedMaxCacheSize}), skipping preload.`);
        // Force cache cleanup when we're at the limit
        performCacheCleanup(true);
        setAppState('isPreloading', false);
        return;
    }

    // Check if client browser is likely to be under memory pressure
    const isLowMemory = window.ragotModules.appRuntime.LOW_MEMORY_DEVICE || deviceMemory <= 2 ||
        (typeof navigator.deviceMemory === 'undefined' && window.ragotModules.appRuntime.MOBILE_DEVICE);

    // Limit concurrent preloads based on client device capabilities
    const maxConcurrentPreloads = isLowMemory ? 1 : 2;

    // Count active preloads (elements with preload attribute)
    const activePreloads = $$('video[preload="metadata"], img[fetchpriority="high"]').length;

    if (activePreloads >= maxConcurrentPreloads) {
        console.log(`Too many active preloads (${activePreloads}), deferring preload.`);
        // Try again later with a longer delay
        setTimeout(preloadNextMedia, 1000); // Increased from 500ms to 1000ms
        return;
    }

    setAppState('isPreloading', true);

    // Prioritize next item for immediate viewing
    const nextItems = window.ragotModules.appState.preloadQueue.slice(0, 1); // Only preload 1 at a time
    const currentIndex = window.ragotModules.appState.currentMediaIndex;

    // Get the next file to preload
    let file = null;
    batchAppState((state) => {
        file = state.preloadQueue.shift();
    }, { source: 'mediaLoader.preloadNextMedia.dequeue' });

    if (!file || hasInCache(file.url)) {
        setAppState('isPreloading', false);
        // Continue preloading next items immediately
        setTimeout(preloadNextMedia, 0);
        return;
    }

    console.log(`Preloading ${file.type}: ${file.name}`);
    let mediaElement;

    if (file.type === 'video') {
        // If the file has a thumbnailUrl, preload the thumbnail image instead of the video metadata
        if (file.thumbnailUrl) {
            console.log(`Preloading video thumbnail for: ${file.name}`);
            mediaElement = new Image();
            mediaElement.style.display = 'none'; // Keep it hidden

            // Add fetch priority hint for next items
            if (nextItems.includes(file)) {
                mediaElement.setAttribute('fetchpriority', 'high');
            }

            // Use a single onload handler with timeout clearing
            // Shorter timeout for low-memory clients to recover faster from stalled loads
            const timeoutMs = window.ragotModules.appRuntime.LOW_MEMORY_DEVICE ? 3000 : 5000;
            const loadTimeout = setTimeout(() => {
                console.warn(`Video thumbnail load timeout: ${file.name}`);
                if (document.body.contains(mediaElement)) {
                    document.body.removeChild(mediaElement);
                }
                setAppState('isPreloading', false);
                setTimeout(preloadNextMedia, 0); // Continue preloading
            }, timeoutMs);

            attr(mediaElement, {
                onLoad: () => {
                    clearTimeout(loadTimeout); // Clear timeout on successful load
                    console.log(`Video thumbnail loaded: ${file.name}`);
                    // Store the thumbnail IMAGE in the cache using the VIDEO'S URL as the key
                    addToCache(file.url, mediaElement);
                    // No need to remove from body here, it's already display:none
                    // if (document.body.contains(mediaElement)) {
                    //     document.body.removeChild(mediaElement);
                    // }
                    setAppState('isPreloading', false);
                    setTimeout(preloadNextMedia, 0); // Continue preloading
                },
                onError: () => {
                    clearTimeout(loadTimeout); // Clear timeout on error
                    console.error(`Error preloading video thumbnail: ${file.thumbnailUrl}`);
                    if (document.body.contains(mediaElement)) {
                        document.body.removeChild(mediaElement);
                    }
                    setAppState('isPreloading', false);
                    setTimeout(preloadNextMedia, 0); // Continue preloading
                }
            });

            document.body.appendChild(mediaElement); // Append to trigger load
            mediaElement.src = file.thumbnailUrl; // Set src to start loading
        } else {
            // If no thumbnail URL, create a minimal video element that only loads metadata
            console.log(`Preloading video metadata for: ${file.name} (no thumbnail)`);
            mediaElement = createElement('video', {
                preload: 'metadata',
                playsInline: true,
                muted: true,
                style: { display: 'none' }
            });
            mediaElement.setAttribute('playsinline', 'true');
            mediaElement.setAttribute('webkit-playsinline', 'true');
            mediaElement.setAttribute('controlsList', 'nodownload nofullscreen');
            mediaElement.disablePictureInPicture = true;

            // Add fetch priority hint for next items
            if (nextItems.includes(file)) {
                mediaElement.setAttribute('fetchpriority', 'high');
            }

            // Add error handling for videos
            attr(mediaElement, {
                onError: function () {
                    console.error(`Error preloading video: ${file.url}`);
                    if (document.body.contains(mediaElement)) {
                        document.body.removeChild(mediaElement);
                    }
                    setAppState('isPreloading', false);
                    // Continue preloading immediately
                    setTimeout(preloadNextMedia, 0);
                }
            });

            // Set a shorter timeout for faster recovery from stalled loading
            const metaTimeoutMs = window.ragotModules.appRuntime.LOW_MEMORY_DEVICE ? 2000 : 3000;
            const loadTimeout = setTimeout(() => {
                console.warn(`Video metadata load timeout: ${file.name}`);
                if (document.body.contains(mediaElement)) {
                    document.body.removeChild(mediaElement);
                }
                setAppState('isPreloading', false);
                // Continue preloading immediately
                setTimeout(preloadNextMedia, 0);
            }, metaTimeoutMs);

            // For videos, only preload metadata
            attr(mediaElement, {
                onLoadedMetadata: () => {
                    clearTimeout(loadTimeout);
                    console.log(`Video metadata loaded: ${file.name}`);
                    addToCache(file.url, mediaElement);
                    if (document.body.contains(mediaElement)) {
                        document.body.removeChild(mediaElement);
                    }
                    setAppState('isPreloading', false);
                    // Continue preloading immediately
                    setTimeout(preloadNextMedia, 0);
                }
            });

            // Use a data URL for the poster to avoid an extra network request
            mediaElement.poster = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9IiMxYTFhM2EiLz48L3N2Zz4=';

            document.body.appendChild(mediaElement);

            // Add source with type for better loading
            mediaElement.appendChild(createElement('source', { src: file.url, type: 'video/mp4' }));

            // Force load metadata only
            mediaElement.load();
        }
    } else if (file.type === 'image') {
        mediaElement = new Image();
        mediaElement.style.display = 'none';

        // Add fetch priority hint for next items
        if (nextItems.includes(file)) {
            mediaElement.setAttribute('fetchpriority', 'high');
        }

        // Set a shorter timeout for faster recovery on low-memory clients
        const imgTimeoutMs = window.ragotModules.appRuntime.LOW_MEMORY_DEVICE ? 3000 : 5000;
        const loadTimeout = setTimeout(() => {
            if (document.body.contains(mediaElement)) {
                document.body.removeChild(mediaElement);
            }
            setAppState('isPreloading', false);
            setTimeout(preloadNextMedia, 0);
        }, imgTimeoutMs);

        attr(mediaElement, {
            onLoad: () => {
                clearTimeout(loadTimeout);
                addToCache(file.url, mediaElement);
                if (document.body.contains(mediaElement)) {
                    document.body.removeChild(mediaElement);
                }
                setAppState('isPreloading', false);
                setTimeout(preloadNextMedia, 0);
            },
            onError: () => {
                clearTimeout(loadTimeout);
                if (document.body.contains(mediaElement)) {
                    document.body.removeChild(mediaElement);
                }
                setAppState('isPreloading', false);
                setTimeout(preloadNextMedia, 0);
            }
        });

        document.body.appendChild(mediaElement);

        // Use URL directly - browser caching improves performance on Pi
        // Only add cache-buster if image previously failed
        mediaElement.src = file.url;
    } else {
        // For unknown file types, create a placeholder element and cache it

        // Create placeholder element (simplified for performance)
        mediaElement = createElement('div', {
            className: 'unknown-file-placeholder',
            innerHTML: `
                <div class="unknown-file-placeholder__content">
                    <div class="unknown-file-placeholder__icon">${fileIcon(64)}</div>
                    <div class="unknown-file-placeholder__name">${file.displayName || file.name}</div>
                </div>
            `
        });

        // Cache the placeholder
        addToCache(file.url, mediaElement);
        setAppState('isPreloading', false);
        // Continue preloading immediately
        setTimeout(preloadNextMedia, 0);
    }
}

/**
 * Apply performance optimizations to video element
 * @param {HTMLVideoElement} videoElement - Video to optimize
 */
function optimizeVideoElement(videoElement) {
    // Set video attributes for faster loading
    videoElement.preload = 'metadata';
    videoElement.playsInline = true;
    videoElement.setAttribute('playsinline', 'true');
    videoElement.setAttribute('webkit-playsinline', 'true');

    // Add performance attributes
    videoElement.setAttribute('disableRemotePlayback', 'true');
    videoElement.disablePictureInPicture = true;

    // Set initial muted state for faster loading
    videoElement.muted = true;

    // Use a data URL for the poster to avoid an extra network request
    videoElement.poster = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9IiMxYTFhM2EiLz48L3N2Zz4=';

    // iOS specific optimizations
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
        // These attributes are needed for proper iOS video behavior
        videoElement.setAttribute('playsinline', 'true');
        videoElement.setAttribute('webkit-playsinline', 'true');
        videoElement.setAttribute('x-webkit-airplay', 'allow');

        // For iOS fullscreen support
        videoElement.setAttribute('webkit-allows-inline-media-playback', 'true');

    }


    return videoElement;
}

/**
 * Handle the case when no media files are found
 * @param {string} categoryId - The category ID
 * @param {number} pageSize - The page size for loading more media
 * @param {Function} resolve - The promise resolve function
 * @param {Function} reject - The promise reject function
 */
async function handleNoMediaFiles(categoryId, pageSize, resolve, reject) {
    try {
        // Check if this is an async indexing response with no files yet
        const response = await fetch(`/api/categories/${categoryId}/media?page=1&limit=1&_=${Date.now()}`, {
            headers: getShowHiddenHeaders()
        });
        const checkData = await response.json();

        if (checkData.async_indexing && checkData.indexing_progress < 100) {
            // This is an async indexing in progress - show a message and wait
            console.log('Async indexing in progress, waiting for files...');
            showIndexingStatus(checkData.indexing_progress);
        }
    } catch (checkError) {
        console.error("Error checking async indexing status:", checkError);

        // Special handling for sync mode as guest
        if (window.ragotModules.appState.syncModeEnabled && !window.ragotModules.appState.isHost) {
            console.log('In sync mode as guest with no media yet - waiting for sync updates');
            setupLayoutNavigation();
            resolve();
            return;
        }

        // Create a simple loading message
        console.log('No media files found in response or files array is empty after load.');
        const loadingMessage = createElement('div', {
            className: 'loading-message',
            innerHTML: `
        <div class="loading-message__content">
            <div class="loading-message__title">Loading Media</div>
            <div class="loading-message__meta">Please wait while files are being loaded...</div>
        </div>
    `
        });
        window.ragotModules.appDom.mediaViewer.appendChild(loadingMessage);

        // Store the element for later removal
        setAppState('loadingMessage', loadingMessage);

        // Poll for updates
        setTimeout(() => {
            if (window.ragotModules.appState.currentCategoryId === categoryId) {
                loadMoreMedia(pageSize, window.ragotModules.appState.currentFetchController.signal, false);

                // Remove the loading message after a delay
                setTimeout(() => {
                    if (window.ragotModules.appState.loadingMessage && document.body.contains(window.ragotModules.appState.loadingMessage)) {
                        window.ragotModules.appState.loadingMessage.remove();
                        setAppState('loadingMessage', null);
                    }
                }, 5000);
            }
        }, 2000);

        // Resolve the promise - we'll wait for updates
        resolve();
    }
}

export {
    viewCategory,
    loadMoreMedia,
    clearResources,
    clearResources as clearMediaCache,
    preloadNextMedia,
    optimizeVideoElement
};
