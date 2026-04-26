/**
 * View Command Module
 * Handles the /view {name_or_id} command which allows a user to jump to another user's shared view.
 * Accepts a profile name, session ID, or session ID prefix.
 */

import { ensureFeatureAccess } from '../utils/authManager.js';
import { SOCKET_EVENTS } from '../core/socketEvents.js';

// Define the functions first
async function executeView(socket, displayLocalMessage, arg) {
  const accessGranted = await ensureFeatureAccess();
  if (!accessGranted) {
    displayLocalMessage('Password required.', { icon: 'stop' });
    return;
  }

  const target = arg ? arg.trim() : null;

  if (!target) {
    displayLocalMessage('Specify a profile name or session ID.', { icon: 'lightbulb' });
    return;
  }

  socket.emit(SOCKET_EVENTS.REQUEST_VIEW_INFO, { target_session_id: target });
  displayLocalMessage(`Viewing ${target}.`, { icon: 'eye' });
}

function getViewHelpText() {
  return '• /view {name or id}  Jump to another user\'s shared view (password protected)';
}

// Export the command object
export const view = {
  description: "Jump to another user's shared view using their profile name or session ID.",
  execute: executeView,
  getHelpText: getViewHelpText
};
