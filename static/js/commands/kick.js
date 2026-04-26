/**
 * Kick Command Module
 * Allows administrators to kick users from the session and temporarily block their IP.
 * Accepts a profile name, user ID, or session ID prefix.
 */

import { SOCKET_EVENTS } from '../core/socketEvents.js';

export const kick = {
    description: '• Kicks a user and blocks their IP for the current session (Admin only).',
    getHelpText: () => '/kick <name or id>: Kicks a user and temporarily blocks their IP (Admin only).',
    execute: async (socket, displayLocalMessage, args) => {
        if (!args || args.trim() === '') {
            displayLocalMessage('Specify a profile name or user ID.', { icon: 'lightbulb' });
            return;
        }

        const target_user_id = args.trim();

        // Client-side admin check
        try {
            const response = await fetch('/api/admin/status');
            if (!response.ok) {
                displayLocalMessage('Could not verify admin status.', { icon: 'x' });
                console.error('Failed to fetch admin status:', response.status);
                return;
            }
            const adminStatus = await response.json();

            if (!adminStatus.isAdmin) {
                displayLocalMessage('Admin only.', { icon: 'stop' });
                return;
            }

            // If admin, proceed to emit the kick event
            socket.emit(SOCKET_EVENTS.ADMIN_KICK_USER, { target_user_id: target_user_id });
            displayLocalMessage(`Kicked ${target_user_id}.`, { icon: 'checkCircle' });

        } catch (error) {
            displayLocalMessage('Kick failed.', { icon: 'x' });
            console.error('Error during kick command execution:', error);
        }
    }
};
