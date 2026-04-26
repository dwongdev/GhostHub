/**
 * /play command
 * Starts auto-playing the current category.
 */

import { ensureFeatureAccess } from '../utils/authManager.js';

export const play = {
    description: '• Auto-plays the current category. Usage: /play [seconds] or /play stop',
    getHelpText: () => '• /play [sec]     Auto-play items (default 10s for images).\n• /play stop      Stop auto-play.',
    execute: async (socket, displayLocalMessage, args) => {
        const accessGranted = await ensureFeatureAccess();
        if (!accessGranted) {
            displayLocalMessage('Password required.', { icon: 'stop' });
            return;
        }

        if (!window.ragotModules || !window.ragotModules.mediaNavigation || typeof window.ragotModules.mediaNavigation.toggleAutoPlay !== 'function') {
            displayLocalMessage('Media navigation not available.', { icon: 'x' });
            return;
        }

        let interval = 10; // Default 10 seconds
        let action = 'start';

        if (args) {
            const arg = args.trim().toLowerCase();
            if (arg === 'stop' || arg === 'off') {
                action = 'stop';
            } else {
                const parsed = parseInt(arg, 10);
                if (!isNaN(parsed) && parsed > 0) {
                    interval = parsed;
                }
            }
        }

        if (action === 'stop') {
            window.ragotModules.mediaNavigation.toggleAutoPlay('stop');
            displayLocalMessage('Auto-play stopped.', { icon: 'stop' });
        } else {
            window.ragotModules.mediaNavigation.toggleAutoPlay(interval);
            displayLocalMessage(`Auto-play started (${interval}s).`, { icon: 'play' });
        }
    }
};
