/**
 * Gallery Layout - Navigation
 * Handles opening media viewer from gallery
 */

import { ensureFeatureAccess } from '../../../utils/authManager.js';
import { toggleSpinner } from '../../ui/controller.js';

/**
 * Open the media viewer for a specific media item
 * @param {string} categoryId - Category ID
 * @param {string} mediaUrl - URL of the media to view (used to find index after load)
 * @param {number} index - Index in category (optional)
 */
export async function openViewer(categoryId, mediaUrl, index = 0) {
    toggleSpinner(true);
    const accessGranted = await ensureFeatureAccess();
    if (!accessGranted) {
        toggleSpinner(false);
        return;
    }

    if (!categoryId) {
        console.error('[GalleryLayout] No category ID provided');
        return;
    }

    if (window.ragotModules?.mediaLoader?.viewCategory) {
        // Use forced_order to ensure the clicked media loads first
        // mediaLoader.viewCategory now has a MAX_SEARCH_PAGES limit to prevent freezing
        if (mediaUrl) {
            await window.ragotModules.mediaLoader.viewCategory(categoryId, [mediaUrl], 0);
        } else {
            await window.ragotModules.mediaLoader.viewCategory(categoryId, null, index);
        }
    } else {
        console.error('[GalleryLayout] mediaLoader not available');
    }
}

/**
 * Open viewer at a specific index in a category
 * @param {string} categoryId 
 * @param {number} index 
 */
export async function openViewerAtIndex(categoryId, index) {
    toggleSpinner(true);
    const accessGranted = await ensureFeatureAccess();
    if (!accessGranted) {
        toggleSpinner(false);
        return;
    }

    if (window.ragotModules?.mediaLoader?.viewCategory) {
        window.ragotModules.mediaLoader.viewCategory(categoryId, null, index);
    }
}
