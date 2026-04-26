/**
 * Unhide Command Module
 * Handles the /unhide command which permanently unhides ALL categories (admin-only)
 */

import { isUserAdmin } from '../utils/progressDB.js';

async function executeUnhide(socket, displayLocalMessage, arg) {
  // Check if admin
  if (!isUserAdmin()) {
    displayLocalMessage('Admin only.', { icon: 'stop' });
    return;
  }

  try {
    // Call API to unhide all categories
    const response = await fetch('/api/admin/categories/unhide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    });

    const result = await response.json();

    if (response.ok && result.success) {
      displayLocalMessage('All categories unhidden.', { icon: 'checkCircle' });

      // Note: Layout refresh is handled by socket 'category_updated' event
    } else {
      displayLocalMessage(result.error || 'Failed to unhide.', { icon: 'x' });
    }
  } catch (error) {
    console.error('Error unhiding categories:', error);
    displayLocalMessage('Failed to unhide.', { icon: 'x' });
  }
}

function getUnhideHelpText() {
  return '• /unhide           Permanently unhide ALL categories (admin-only)';
}

// Export the command object
export const unhide = {
  description: "Permanently unhide ALL hidden categories (admin-only)",
  execute: executeUnhide,
  getHelpText: getUnhideHelpText
};
