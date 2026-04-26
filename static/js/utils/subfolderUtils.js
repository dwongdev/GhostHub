/**
 * Subfolder Utilities
 * Handles detection and grouping of subfolder media items within categories.
 * Used by both streaming and default layouts to show subfolder cards
 * instead of broken subfolder file paths.
 *
 * @module utils/subfolderUtils
 */

/**
 * Check if a media item is from a subfolder (has '/' in its name)
 * Uses displayName if available (stripped of current filter prefix) for nested navigation support
 * @param {Object} file - Media file object with 'name' or 'displayName' property
 * @returns {boolean} True if file is inside a subfolder
 */
export function isSubfolderFile(file) {
    if (!file) return false;
    // Prefer displayName which is relative to current subfolder filter
    const pathToCheck = file.displayName || file.name;
    if (!pathToCheck) return false;
    return pathToCheck.includes('/');
}

/**
 * Get the immediate subfolder name from a file path
 * e.g., "monster/file.mp4" -> "monster"
 * e.g., "monster/deep/file.mp4" -> "monster"
 * @param {Object} file - Media file object with 'name' property
 * @returns {string|null} The immediate subfolder name or null if direct file
 */
export function getSubfolderName(file) {
    if (!file) return null;
    const pathToCheck = file.displayName || file.name;
    if (!pathToCheck) return null;
    const parts = pathToCheck.split('/');
    if (parts.length <= 1) return null;
    return parts[0];
}

/**
 * Extract unique immediate subfolders from a list of media items.
 * Returns subfolder summary objects with name, count, thumbnail info.
 *
 * @param {Array} mediaItems - Array of media file objects from API
 * @param {string} categoryId - Parent category ID
 * @returns {Array} Array of subfolder objects: {name, count, containsVideo, thumbnailUrl, firstFileUrl}
 */
export function extractSubfolders(mediaItems, categoryId) {
    if (!mediaItems || !mediaItems.length) return [];

    const subfolderMap = new Map();

    for (const file of mediaItems) {
        const subName = getSubfolderName(file);
        if (!subName) continue;

        if (!subfolderMap.has(subName)) {
            subfolderMap.set(subName, {
                name: subName,
                count: 0,
                containsVideo: false,
                thumbnailUrl: null,
                firstFileUrl: null,
                categoryId: categoryId
            });
        }

        const info = subfolderMap.get(subName);
        info.count++;

        if (file.type === 'video') {
            info.containsVideo = true;
            if (!info.thumbnailUrl && file.thumbnailUrl) {
                info.thumbnailUrl = file.thumbnailUrl;
            }
        }

        if (!info.firstFileUrl) {
            info.firstFileUrl = file.url;
            // Use image files as thumbnail if no video thumbnail
            if (!info.thumbnailUrl && file.type === 'image') {
                info.thumbnailUrl = file.url;
            }
        }
    }

    return Array.from(subfolderMap.values());
}

/**
 * Extract subfolders from the API response's subfolders field.
 * Falls back to extracting from media items if not present.
 *
 * @param {Object} apiResponse - Full API response from media endpoint
 * @param {string} categoryId - Category ID
 * @returns {Array} Array of subfolder objects
 */
export function getSubfoldersFromResponse(apiResponse, categoryId) {
    // Prefer server-provided subfolder info (complete, not limited by pagination)
    if (apiResponse && apiResponse.subfolders && apiResponse.subfolders.length > 0) {
        return apiResponse.subfolders.map(sf => ({
            name: sf.name,
            count: sf.count,
            containsVideo: sf.contains_video,
            thumbnailUrl: sf.thumbnail_url || null,
            firstFileUrl: null,
            categoryId: categoryId
        }));
    }

    // Fallback: extract from loaded media items
    if (apiResponse && apiResponse.files) {
        return extractSubfolders(apiResponse.files, categoryId);
    }

    return [];
}

/**
 * Filter media items to only include direct files (not in subfolders)
 * @param {Array} mediaItems - Array of media file objects
 * @returns {Array} Filtered array with only direct (non-subfolder) files
 */
export function filterDirectFiles(mediaItems) {
    if (!mediaItems || !mediaItems.length) return [];
    return mediaItems.filter(file => !isSubfolderFile(file));
}

/**
 * Process a media list and replace subfolder file groups with subfolder marker entries.
 * Used by the default layout TikTok view to insert folder cards into the swipe feed.
 *
 * @param {Array} mediaItems - Array of media file objects from API
 * @param {string} categoryId - Parent category ID
 * @param {Array|null} subfolderInfo - Pre-fetched subfolder info from API (optional)
 * @returns {Object} {items: Array, subfolders: Array} - processed media list and subfolder info
 */
export function processMediaWithSubfolders(mediaItems, categoryId, subfolderInfo = null) {
    const subfolders = subfolderInfo || extractSubfolders(mediaItems, categoryId);
    if (!mediaItems || !mediaItems.length) {
        if (subfolders && subfolders.length > 0) {
            const items = subfolders.map(sf => ({
                name: sf.name,
                type: 'subfolder',
                isSubfolder: true,
                subfolderName: sf.name,
                subfolderInfo: sf,
                url: `subfolder://${categoryId}/${sf.name}`,
                thumbnailUrl: sf.thumbnailUrl || null,
                categoryId: categoryId
            }));
            return { items, subfolders };
        }
        return { items: [], subfolders: [] };
    }

    if (subfolders.length === 0) {
        return { items: mediaItems, subfolders: [] };
    }

    // Build the processed list: direct files + one entry per subfolder
    const processedItems = [];
    const seenSubfolders = new Set();

    for (const file of mediaItems) {
        const subName = getSubfolderName(file);

        if (!subName) {
            // Direct file - include as-is
            processedItems.push(file);
        } else if (!seenSubfolders.has(subName)) {
            // First file from this subfolder - insert a subfolder marker
            seenSubfolders.add(subName);
            const subInfo = subfolders.find(sf => sf.name === subName);

            processedItems.push({
                name: subName,
                type: 'subfolder',
                isSubfolder: true,
                subfolderName: subName,
                subfolderInfo: subInfo || {
                    name: subName,
                    count: 0,
                    containsVideo: false,
                    thumbnailUrl: null,
                    categoryId: categoryId
                },
                url: `subfolder://${categoryId}/${subName}`,
                thumbnailUrl: subInfo?.thumbnailUrl || null,
                categoryId: categoryId
            });
        }
        // else: subsequent files from same subfolder - skip
    }

    return { items: processedItems, subfolders };
}

/**
 * Format subfolder name for display (capitalize first letter, replace hyphens/underscores)
 * @param {string} name - Raw subfolder name
 * @returns {string} Formatted display name
 */
export function formatSubfolderName(name) {
    if (!name) return '';
    return name
        .replace(/[-_]/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}
