/**
 * Hide Command Module
 * Handles the /hide command which hides the current category from all users (admin-only)
 */

import { isUserAdmin } from '../utils/progressDB.js';

async function executeHide(socket, displayLocalMessage, arg) {
  const appState = window.ragotModules?.appState;
  if (!appState) {
    displayLocalMessage('App not ready.', { icon: 'x' });
    return;
  }

  // Check if admin
  if (!isUserAdmin()) {
    displayLocalMessage('Admin only.', { icon: 'stop' });
    return;
  }

  // Get current category
  const categoryId = appState.currentCategoryId;
  if (!categoryId) {
    displayLocalMessage('No category open.', { icon: 'x' });
    return;
  }

  const categoryName = appState.currentCategoryName || categoryId;

  try {
    // Call API to hide category
    const response = await fetch('/api/admin/categories/hide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ category_id: categoryId })
    });

    const result = await response.json();

    if (response.ok && result.success) {
      displayLocalMessage(`Hidden "${categoryName}" from all users.`, { icon: 'checkCircle' });

      // Note: Layout refresh is handled by socket 'category_updated' event
    } else {
      displayLocalMessage(result.error || 'Failed to hide.', { icon: 'x' });
    }
  } catch (error) {
    console.error('Error hiding category:', error);
    displayLocalMessage('Failed to hide.', { icon: 'x' });
  }
}

function getHideHelpText() {
  return '• /hide             Hide current category from everyone (admin-only, covert)';
}

// Export the command object
export const hide = {
  description: "Hide the current category from all users (admin-only, covert hiding)",
  execute: executeHide,
  getHelpText: getHideHelpText
};

