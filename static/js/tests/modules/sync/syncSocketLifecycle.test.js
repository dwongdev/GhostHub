import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../modules/ui/controller.js', () => ({
    updateSyncToggleButton: vi.fn(),
    disableNavigationControls: vi.fn(),
    enableNavigationControls: vi.fn(),
}));

vi.mock('../../../modules/media/navigation.js', () => ({
    renderMediaWindow: vi.fn(),
}));

vi.mock('../../../utils/configManager.js', () => ({
    getConfigValue: vi.fn((_, fallback) => fallback),
}));

vi.mock('../../../modules/media/loader.js', () => ({
    viewCategory: vi.fn(),
}));

vi.mock('../../../utils/authManager.js', () => ({
    ensureFeatureAccess: vi.fn(async () => true),
}));

vi.mock('../../../utils/layoutUtils.js', () => ({
    navigateToMedia: vi.fn(async () => true),
    getCurrentLayout: vi.fn(() => 'streaming'),
}));

vi.mock('../../../utils/cookieUtils.js', () => ({
    getCookieValue: vi.fn(() => 'session-1'),
}));

vi.mock('../../../libs/ragot.esm.min.js', () => {
    class MockModule {
        start() {
            return this;
        }

        timeout(callback) {
            callback();
            return 1;
        }

        clearTimers() {}

        on() {
            return this;
        }

        off() {
            return this;
        }

        interval() {
            return 1;
        }

        clearInterval() {}

        onSocket(target, event, handler) {
            target.on(event, handler);
            return this;
        }

        offSocket(target, event, handler) {
            target.off(event, handler);
            return this;
        }

        stop() {
            return this;
        }
    }

    return {
        Module: MockModule,
        $: vi.fn(() => null),
        attr: vi.fn(),
    };
});

vi.mock('../../../utils/appStateUtils.js', () => {
    const state = {
        syncModeEnabled: false,
        isHost: false,
        currentCategoryId: null,
        currentMediaIndex: 0,
        fullMediaList: [],
        hasMoreMedia: false,
        savedVideoTimestamp: null,
        savedVideoIndex: null,
        savedVideoCategoryId: null,
    };

    return {
        setAppState: vi.fn((key, value) => {
            state[key] = value;
        }),
        batchAppState: vi.fn((updater) => {
            updater(state);
        }),
        getAppState: vi.fn(() => state),
        createAppSelector: vi.fn((selectors, projector) => () => projector(...selectors.map((selector) => selector(state)))),
    };
});

vi.mock('../../../utils/notificationManager.js', () => ({
    toast: {
        error: vi.fn(),
        show: vi.fn(),
    },
}));

vi.mock('../../../core/socketEvents.js', () => ({
    SOCKET_EVENTS: {
        JOIN_SYNC: 'join_sync',
        LEAVE_SYNC: 'leave_sync',
        HEARTBEAT: 'heartbeat',
        HEARTBEAT_RESPONSE: 'heartbeat_response',
        SYNC_ENABLED: 'sync_enabled',
        SYNC_DISABLED: 'sync_disabled',
        PLAYBACK_SYNC: 'playback_sync',
    },
}));

function createMockSocket({ connected = false, active = false, readyState = 'closed' } = {}) {
    const handlers = {};

    return {
        handlers,
        connected,
        active,
        id: 'socket-1',
        io: { _readyState: readyState },
        emit: vi.fn(),
        connect: vi.fn(),
        disconnect: vi.fn(),
        on: vi.fn((event, handler) => {
            handlers[event] = handler;
        }),
        off: vi.fn((event, handler) => {
            if (handlers[event] === handler) {
                delete handlers[event];
            }
        }),
    };
}

async function loadSyncManager() {
    return import('../../../modules/sync/manager.js');
}

describe('Sync socket lifecycle', () => {
    beforeEach(() => {
        vi.resetModules();
        vi.clearAllMocks();
        document.body.innerHTML = '<div id="sync-status-display"></div>';
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ active: false, is_host: false }),
        });
        window.ragotModules = {
            appState: {
                syncModeEnabled: false,
                isHost: false,
                currentCategoryId: null,
                currentMediaIndex: 0,
                fullMediaList: [],
                hasMoreMedia: false,
            },
            appRuntime: {
                MOBILE_DEVICE: false,
                getMediaPerPage: () => 10,
            },
            mediaLoader: {
                clearResources: vi.fn(),
                loadMoreMedia: vi.fn(async () => {}),
            },
            videoControls: {
                isControlsAttached: vi.fn(() => false),
                detachControls: vi.fn(),
                getPlaybackState: vi.fn(() => null),
            },
            mediaNavigation: {
                activateVideoThumbnail: vi.fn(() => true),
                goBackToCategories: vi.fn(),
            },
        };
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('does not disconnect the shared app socket during sync cleanup', async () => {
        const socket = createMockSocket({ connected: true, active: true, readyState: 'open' });
        const syncManager = await loadSyncManager();

        syncManager.initSync(socket);
        syncManager.cleanupSyncManager();

        expect(socket.disconnect).not.toHaveBeenCalled();
    });

    it('skips duplicate reconnect attempts while the socket is already opening', async () => {
        const socket = createMockSocket({ connected: false, active: true, readyState: 'opening' });
        const syncManager = await loadSyncManager();

        syncManager.initSync(socket);
        socket.handlers.disconnect?.('transport close');

        expect(socket.connect).not.toHaveBeenCalled();
    });
});
