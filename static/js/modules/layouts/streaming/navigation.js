/**
 * Streaming Layout - Navigation
 * Handles opening media viewer and resume functionality
 */

import { ensureFeatureAccess } from '../../../utils/authManager.js';
import { getVideoProgress, getSubfolderFilter, getCategoryCache, getMediaFilter } from './state.js';
import { toggleSpinner } from '../../ui/controller.js';

/**
 * Open the media viewer at a specific index
 * Includes password protection check
 * @param {string} categoryId - Category ID
 * @param {number} startIndex - Starting index
 */
export async function openViewer(categoryId, startIndex = 0) {
    toggleSpinner(true);
    const accessGranted = await ensureFeatureAccess();
    if (!accessGranted) {
        toggleSpinner(false);
        return;
    }

    if (window.ragotModules?.mediaLoader?.viewCategory) {
        window.ragotModules.mediaLoader.viewCategory(categoryId, null, startIndex, getSubfolderFilter());
    } else {
        console.error('mediaLoader not available');
    }
}

/**
 * Open the media viewer for a specific media URL
 * Uses the cached media from the row if available to enable navigation
 * @param {string} categoryId - Category ID
 * @param {string} mediaUrl - URL of the media to view
 */
export async function openViewerByUrl(categoryId, mediaUrl) {
    toggleSpinner(true);
    const accessGranted = await ensureFeatureAccess();
    if (!accessGranted) {
        toggleSpinner(false);
        return;
    }

    if (!mediaUrl) {
        if (window.ragotModules?.mediaLoader?.viewCategory) {
            window.ragotModules.mediaLoader.viewCategory(categoryId, null, 0);
        }
        return;
    }

    // Set video progress in app.state BEFORE loading so mediaNavigation can resume
    const progressInfo = getVideoProgress(mediaUrl);

    if (progressInfo && progressInfo.video_timestamp > 0) {
        const appState = window.ragotModules?.appState;
        if (appState) {
            if (!appState.videoProgressMap) appState.videoProgressMap = {};
            appState.videoProgressMap[mediaUrl] = {
                video_timestamp: progressInfo.video_timestamp,
                video_duration: progressInfo.video_duration || 0
            };
            appState.trackingMode = 'video';
            appState.savedVideoTimestamp = progressInfo.video_timestamp;
            appState.savedVideoIndex = 0;
        }
    }

    if (window.ragotModules?.mediaLoader?.viewCategory) {
        // Try to find the full row list from cache to enable navigation
        const subfolder = getSubfolderFilter();
        const mediaFilter = getMediaFilter();
        const categoryCache = getCategoryCache(categoryId, subfolder, mediaFilter);

        if (categoryCache && categoryCache.media && categoryCache.media.length > 0) {
            // Find index of this media in the cached list
            const index = categoryCache.media.findIndex(m => m.url === mediaUrl);
            if (index !== -1) {
                console.log(`[StreamingNavigation] Found media in cache at index ${index}, passing full list (${categoryCache.media.length} items)`);
                // Pass the full cached list (with objects) and the correct starting index
                window.ragotModules.mediaLoader.viewCategory(categoryId, categoryCache.media, index, subfolder);
                return;
            }
        }

        // Fallback: pass just the one URL if not in cache (Continue Watching cards might not be in row cache)
        window.ragotModules.mediaLoader.viewCategory(categoryId, [mediaUrl], 0, subfolder);
    } else {
        console.error('mediaLoader not available');
    }
}
