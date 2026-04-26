/**
 * /remove command
 * Removes the current media item from the shared session playlist.
 * Only works when viewing the Shared Session Playlist category.
 */

import { setAppState } from '../utils/appStateUtils.js';

export const remove = {
    description: '- Removes the current item from the Shared Session Playlist.',
    getHelpText: () => '- /remove  Remove current item from Shared Playlist.',
    execute: async (socket, displayLocalMessage, args) => {
        const appState = window.ragotModules?.appState;
        if (!appState) {
            displayLocalMessage('App not ready.', { icon: 'x' });
            return;
        }

        // Check if viewing the session playlist
        if (appState.currentCategoryId !== 'session-playlist') {
            displayLocalMessage('Only works in the Shared Playlist.', { icon: 'x' });
            return;
        }

        const currentIndex = appState.currentMediaIndex;
        const currentList = appState.fullMediaList || [];

        if (currentIndex == null || currentIndex < 0 || currentIndex >= currentList.length) {
            displayLocalMessage('No item selected.', { icon: 'x' });
            return;
        }

        const currentItem = currentList[currentIndex];

        try {
            const response = await fetch('/api/session/playlist/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentItem.url })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                displayLocalMessage(`Removed "${currentItem.name}" from playlist.`, { icon: 'checkCircle' });

                // Navigate to next item or go back to categories if playlist is now empty
                if (currentList.length <= 1) {
                    // Last item removed, go back to category view
                    if (window.ragotModules?.mediaNavigation?.goBackToCategories) {
                        window.ragotModules.mediaNavigation.goBackToCategories();
                    }
                } else {
                    // Update state through the store; produce a new array rather than mutating in-place
                    const updatedList = currentList.filter((_, i) => i !== currentIndex);
                    setAppState('fullMediaList', updatedList);
                    const newIndex = Math.min(currentIndex, updatedList.length - 1);
                    if (window.ragotModules?.mediaNavigation?.renderMediaWindow) {
                        window.ragotModules.mediaNavigation.renderMediaWindow(newIndex);
                    }
                }
            } else {
                displayLocalMessage(data.message || 'Failed to remove.', { icon: 'x' });
            }
        } catch (error) {
            console.error('/remove command error:', error);
            displayLocalMessage('Failed to remove.', { icon: 'x' });
        }
    }
};
