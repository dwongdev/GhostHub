import { unlockIcon, lockIcon, shieldCheckIcon } from '../../utils/icons.js';
import { refreshAllLayouts } from '../../utils/liveVisibility.js';
import { Module, $, $$ } from '../../libs/ragot.esm.min.js';
import { setAppState } from '../../utils/appStateUtils.js';
import { toast, dialog } from '../../utils/notificationManager.js';
import { SOCKET_EVENTS } from '../../core/socketEvents.js';

// SVG Icons
const ICONS = {
    OPEN_LOCK: unlockIcon(24),
    LOCKED: lockIcon(24),
    ADMIN_ACTIVE: shieldCheckIcon(24)
};

let adminLockBtn;
let adminFeatureElements;
let activeSocket = null;
let socketHandlers = null;
let adminSocketLifecycle = null;

class AdminControlsLifecycle extends Module {
    onStart() {
        if (adminLockBtn) {
            this.on(adminLockBtn, 'click', toggleAdminRole);
        }
    }
}

let adminControlsLifecycle = null;

class AdminSocketLifecycle extends Module {
    constructor(socket, handlers) {
        super();
        this.socket = socket;
        this.handlers = handlers;
    }

    onStart() {
        if (!this.socket || !this.handlers) return;
        this.onSocket(this.socket, SOCKET_EVENTS.ADMIN_STATUS_UPDATE, this.handlers.onAdminStatusUpdate);
        this.onSocket(this.socket, SOCKET_EVENTS.YOU_HAVE_BEEN_KICKED, this.handlers.onKicked);
        this.onSocket(this.socket, SOCKET_EVENTS.ADMIN_KICK_CONFIRMATION, this.handlers.onKickConfirmation);
    }
}

export async function fetchAdminStatusAndUpdateUI() {
    try {
        const response = await fetch('/api/admin/status');
        if (!response.ok) {
            console.error('Failed to fetch admin status:', response.status);
            applyUIState(false, false); // Default to non-admin, role not claimed
            return;
        }
        const data = await response.json();
        applyUIState(data.isAdmin, data.roleClaimedByAnyone);
    } catch (error) {
        console.error('Error fetching admin status:', error);
        applyUIState(false, false);
    }
}

function applyUIState(isCurrentUserAdmin, isRoleClaimedByAnyone) {
    setAppState('isAdmin', isCurrentUserAdmin);

    // Directly update TV cast button visibility (more reliable than events)
    // Config is already updated above, so tvCastManager will see correct value
    if (window.ragotModules?.tvCastManager?.refreshCastButtonVisibility) {
        window.ragotModules.tvCastManager.refreshCastButtonVisibility();
    }

    if (!adminLockBtn || !adminFeatureElements) {
        return;
    }

    adminFeatureElements.forEach(el => {
        if (isCurrentUserAdmin) {
            // Restore original display style based on element type/class
            if (el.classList.contains('gh-header__btn')) {
                el.style.display = 'flex';
            } else if (el.id === 'add-category-link') {
                el.style.display = 'inline-block';
            } else {
                el.style.display = '';
            }
        } else {
            el.style.display = 'none';
        }
    });

    if (isCurrentUserAdmin) {
        adminLockBtn.innerHTML = ICONS.ADMIN_ACTIVE;
        adminLockBtn.title = 'Admin Active (click to release)';
        adminLockBtn.disabled = false;
    } else if (isRoleClaimedByAnyone) {
        adminLockBtn.innerHTML = ICONS.LOCKED;
        adminLockBtn.title = 'Admin Role Claimed (click to Reclaim with password)';
        adminLockBtn.disabled = false; // Enable button for reclaim prompt
    } else {
        adminLockBtn.innerHTML = ICONS.OPEN_LOCK;
        adminLockBtn.title = 'Claim Admin Role';
        adminLockBtn.disabled = false;
    }
}

async function toggleAdminRole() {
    if (!adminLockBtn) return;
    adminLockBtn.disabled = true; // Prevent double-clicks

    try {
        // Check current status to decide action
        const statusResp = await fetch('/api/admin/status');
        const status = statusResp.ok ? await statusResp.json() : { isAdmin: false, roleClaimedByAnyone: false };

        if (status.isAdmin) {
            // Standard Release
            const resp = await fetch('/api/admin/release', { method: 'POST' });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                console.warn(`Admin release failed: ${data.message || 'Request failed'}`);
            }
        } else if (status.roleClaimedByAnyone) {
            // Reclaim Attempt
            const password = await dialog.prompt('Enter admin password to reclaim:', { placeholder: 'Admin password...' });
            if (password === null) {
                adminLockBtn.disabled = false;
                return; // User cancelled
            }

            const resp = await fetch('/api/admin/claim', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });

            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                toast.error(data.message || 'Reclaim failed. Incorrect password?');
            } else {
                toast.success('Admin role reclaimed successfully!');
            }
        } else {
            // Standard Claim
            const resp = await fetch('/api/admin/claim', { method: 'POST' });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                console.warn(`Admin claim failed: ${data.message || 'Request failed'}`);
            }
        }
    } catch (error) {
        console.error('Error toggling admin role:', error);
    } finally {
        // Refresh UI and re-enable button
        await fetchAdminStatusAndUpdateUI();

        // Claim/unclaim should refresh visibility-driven UI (hero/continue watching),
        // but must not force cache-busting thumbnail/media revalidation.
        try {
            await refreshAllLayouts(false, true);
        } catch (refreshErr) {
            console.warn('Error refreshing views after admin toggle:', refreshErr);
        }
    }
}

export function initAdminControls() {
    adminLockBtn = $('#adminLockBtn');
    // Query all elements that should only be visible to admins
    adminFeatureElements = $$('.admin-feature');

    if (adminLockBtn) {
        if (!adminControlsLifecycle) {
            adminControlsLifecycle = new AdminControlsLifecycle();
        }
        adminControlsLifecycle.start();
        fetchAdminStatusAndUpdateUI(); // Initial check on page load
    } else {
        console.warn('Admin lock button (#adminLockBtn) not found.');
    }
}

/**
 * Register socket event handlers owned by the admin module.
 * Called once after socket is created in main.js Phase 3.
 * @param {Object} socket - Socket.IO client instance
 */
export function registerSocketHandlers(socket) {
    if (adminSocketLifecycle) {
        adminSocketLifecycle.stop();
        adminSocketLifecycle = null;
    }

    socketHandlers = {
        onAdminStatusUpdate: async () => {
            try {
                await fetchAdminStatusAndUpdateUI();
            } catch (e) {
                console.error('[Admin] Error refreshing admin status:', e);
            }
        },
        onKicked: (data) => {
            socket.disconnect();
            document.body.innerHTML = `<div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); color: white; display: flex; justify-content: center; align-items: center; text-align: center; font-size: 2em; z-index: 9999;">${data.message}<br/>Please close this tab.</div>`;
            window.location.reload();
        },
        onKickConfirmation: (data) => {
            if (window.ragotModules?.chatManager?.displayLocalSystemMessage) {
                window.ragotModules.chatManager.displayLocalSystemMessage(data.message, false, false);
            } else if (window.ragotModules?.chatManager?.displayLocalMessage) {
                // Backward tolerance for legacy chat API shape.
                window.ragotModules.chatManager.displayLocalMessage(data.message, data.success ? 'info' : 'error');
            } else {
                console.warn('[Admin] Kick confirmation received without chat UI:', data);
            }
        }
    };

    activeSocket = socket;
    adminSocketLifecycle = new AdminSocketLifecycle(socket, socketHandlers);
    adminSocketLifecycle.start();
}

/**
 * Optional teardown for tests/hot-reload flows.
 */
export function cleanupAdminControls() {
    if (adminControlsLifecycle) {
        adminControlsLifecycle.stop();
        adminControlsLifecycle = null;
    }

    if (adminSocketLifecycle) {
        adminSocketLifecycle.stop();
        adminSocketLifecycle = null;
    }

    activeSocket = null;
    socketHandlers = null;
}
