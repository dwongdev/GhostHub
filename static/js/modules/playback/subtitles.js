/**
 * Subtitle Manager Module
 * -----------------------
 * Handles subtitle loading and display for video elements.
 * - Fetches subtitle tracks from the API when subtitles are enabled
 * - Injects <track> elements into video elements
 * - Removes old tracks when switching videos
 * - Uses browser's native subtitle UI
 */

import { getConfigValue } from '../../utils/configManager.js';
import { createElement, $$ } from '../../libs/ragot.esm.min.js';

// Cache for subtitle data to avoid repeated API calls
const subtitleCache = new Map();

// Track elements currently added to videos (WeakMap: video -> track elements)
const videoTrackMap = new WeakMap();

/**
 * Check if subtitles feature is enabled in config.
 * @returns {boolean}
 */
export function isSubtitlesEnabled() {
    return getConfigValue('python_config.ENABLE_SUBTITLES', false) === true;
}

/**
 * Fetch available subtitles for a video URL.
 * @param {string} videoUrl - The media URL of the video
 * @returns {Promise<Array>} Array of subtitle track objects
 */
export async function fetchSubtitles(videoUrl) {
    if (!isSubtitlesEnabled()) {
        return [];
    }

    // Check cache first
    if (subtitleCache.has(videoUrl)) {
        return subtitleCache.get(videoUrl);
    }

    try {
        const response = await fetch(`/api/subtitles/video?video_url=${encodeURIComponent(videoUrl)}`);
        
        if (!response.ok) {
            console.warn(`Failed to fetch subtitles for ${videoUrl}: ${response.status}`);
            return [];
        }

        const subtitles = await response.json();
        
        // Cache the result (even empty arrays to avoid repeat requests)
        subtitleCache.set(videoUrl, subtitles);
        
        if (subtitles.length > 0) {
            console.log(`[Subtitles] Found ${subtitles.length} subtitle tracks for ${videoUrl}`);
        }
        
        return subtitles;
    } catch (error) {
        console.error(`[Subtitles] Error fetching subtitles:`, error);
        return [];
    }
}

/**
 * Remove all subtitle tracks from a video element.
 * @param {HTMLVideoElement} videoElement 
 */
export function removeSubtitles(videoElement) {
    if (!videoElement || videoElement.tagName !== 'VIDEO') {
        return;
    }

    // Get tracked elements
    const trackedElements = videoTrackMap.get(videoElement);
    if (trackedElements) {
        trackedElements.forEach(track => {
            try {
                track.remove();
            } catch (e) { /* ignore */ }
        });
        videoTrackMap.delete(videoElement);
    }

    // Also remove any remaining track elements (fallback)
    const existingTracks = $$('track', videoElement);
    existingTracks.forEach(track => track.remove());
}

/**
 * Add subtitle tracks to a video element.
 * @param {HTMLVideoElement} videoElement - The video element to add tracks to
 * @param {Array} subtitles - Array of subtitle track objects from the API
 */
export function addSubtitleTracks(videoElement, subtitles) {
    if (!videoElement || videoElement.tagName !== 'VIDEO' || !subtitles || subtitles.length === 0) {
        return;
    }

    // Remove any existing tracks first
    removeSubtitles(videoElement);

    const trackElements = [];

    subtitles.forEach((sub, index) => {
        const track = createElement('track', {
            kind: 'subtitles',
            src: sub.url,
            label: sub.label || `Track ${index + 1}`,
            srclang: sub.language || 'en',
            default: sub.default && index === 0
        });

        videoElement.appendChild(track);
        trackElements.push(track);
    });

    // Store track references for cleanup
    videoTrackMap.set(videoElement, trackElements);

    console.log(`[Subtitles] Added ${trackElements.length} subtitle tracks to video`);
}

/**
 * Load subtitles for a video element.
 * Fetches subtitle data and injects track elements.
 * @param {HTMLVideoElement} videoElement - The video element
 * @param {string} videoUrl - The media URL of the video
 * @returns {Promise<boolean>} True if subtitles were loaded
 */
export async function loadSubtitlesForVideo(videoElement, videoUrl) {
    if (!isSubtitlesEnabled()) {
        return false;
    }

    if (!videoElement || videoElement.tagName !== 'VIDEO' || !videoUrl) {
        return false;
    }

    try {
        const subtitles = await fetchSubtitles(videoUrl);
        
        if (subtitles.length > 0) {
            addSubtitleTracks(videoElement, subtitles);
            return true;
        }
        
        return false;
    } catch (error) {
        console.error(`[Subtitles] Error loading subtitles:`, error);
        return false;
    }
}

/**
 * Clear the client-side subtitle cache.
 * Useful when categories change or on memory cleanup.
 */
export function clearSubtitleCache() {
    subtitleCache.clear();
}

/**
 * Get the number of cached subtitle entries.
 * @returns {number}
 */
export function getCacheSize() {
    return subtitleCache.size;
}

// Export a default object for easy access via window.ragotModules
export default {
    isSubtitlesEnabled,
    fetchSubtitles,
    removeSubtitles,
    addSubtitleTracks,
    loadSubtitlesForVideo,
    clearSubtitleCache,
    getCacheSize
};
