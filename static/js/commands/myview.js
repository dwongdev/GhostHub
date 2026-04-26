/**
 * MyView Command Module
 * Handles the /myview command which shares the user's current view with others in chat
 */

import { ensureFeatureAccess } from '../utils/authManager.js'; // Import the new auth utility
import { SOCKET_EVENTS } from '../core/socketEvents.js';

// Define the functions first
async function executeMyView(socket, displayLocalMessage, arg) {
  const appState = window.ragotModules?.appState;
  if (!appState) {
    displayLocalMessage('App not ready.', { icon: 'x', surface: 'chat' });
    return;
  }

  const accessGranted = await ensureFeatureAccess();
  if (!accessGranted) {
    displayLocalMessage('Password required.', { icon: 'stop', surface: 'chat' });
    return;
  }

  const categoryId = appState.currentCategoryId;
  const index = appState.currentMediaIndex;
  const sessionId = socket.id;

  if (!categoryId || index == null) {
    displayLocalMessage('No media open.', { icon: 'x', surface: 'chat' });
    return;
  }

  // Emit to server for rebroadcast
  socket.emit(SOCKET_EVENTS.COMMAND, {
    cmd: 'myview',
    arg: { category_id: categoryId, index },
    from: sessionId
  });
  displayLocalMessage('View shared.', { icon: 'cast', surface: 'chat' });
}

function getMyViewHelpText() {
  return '• /myview           Share your current view with others';
}

// Export the command object
export const myview = {
  description: "Share your current media view with others in the chat.",
  keepChatOpen: true,
  execute: executeMyView,
  getHelpText: getMyViewHelpText
};
