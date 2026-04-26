/**
 * Tests for Media Navigation Module
 * Tests critical navigation logic and guard clauses.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock dependencies before imports
vi.mock('../../../core/app.js', () => ({
    app: {
        state: {
            currentMediaIndex: 0,
            fullMediaList: [
                { type: 'image', name: 'image1.jpg', url: '/media/image1.jpg' },
                { type: 'video', name: 'video1.mp4', url: '/media/video1.mp4' },
                { type: 'image', name: 'image2.jpg', url: '/media/image2.jpg' }
            ],
            hasMoreMedia: true,
            isLoading: false,
            navigationDisabled: false,
            currentCategoryId: 'test-category',
            trackingMode: 'category'
        },
        mediaCache: new Map()
    },
    mediaViewer: document.createElement('div'),
    spinnerContainer: document.createElement('div'),
    getMediaPerPage: vi.fn(() => 20),
    LOAD_MORE_THRESHOLD: 5,
    renderWindowSize: 3
}));

vi.mock('../../../utils/cacheManager.js', () => ({
    getFromCache: vi.fn(() => null),
    hasInCache: vi.fn(() => false),
    addToCache: vi.fn(),
    performCacheCleanup: vi.fn()
}));

vi.mock('./loader.js', () => ({
    loadMoreMedia: vi.fn(() => Promise.resolve()),
    preloadNextMedia: vi.fn(),
    clearResources: vi.fn()
}));

vi.mock('../ui/controller.js', () => ({
    setupControls: vi.fn(),
    toggleSpinner: vi.fn()
}));

vi.mock('./elementFactory.js', () => ({
    createVideoThumbnailElement: vi.fn(() => document.createElement('div')),
    createImageElement: vi.fn(() => document.createElement('img')),
    createPlaceholderElement: vi.fn(() => document.createElement('div')),
    createSubfolderElement: vi.fn(() => document.createElement('div')),
    updateMediaInfoOverlay: vi.fn()
}));

vi.mock('./videoPlayer.js', () => ({
    createActualVideoElement: vi.fn(() => document.createElement('video'))
}));

vi.mock('./transcodingPlayer.js', () => ({
    initTranscodingPlayer: vi.fn()
}));

vi.mock('./progressSync.js', () => ({
    initProgressSync: vi.fn(),
    emitMyStateUpdate: vi.fn(),
    getCurrentVideoProgress: vi.fn(() => null),
    updateMediaSession: vi.fn()
}));

vi.mock('./progressPersistence.js', () => ({
    getVideoProgressSnapshot: vi.fn(() => null),
    persistPlaybackProgress: vi.fn(() => Promise.resolve()),
    shouldMarkCompletedOnExit: vi.fn(() => false)
}));

vi.mock('./thumbnailHandler.js', () => ({
    initThumbnailHandler: vi.fn(),
    setupThumbnailClickListener: vi.fn(),
    cleanupThumbnailHandler: vi.fn(),
    activateThumbnailContainer: vi.fn()
}));

vi.mock('./quickActions.js', () => ({
    initQuickActionsManager: vi.fn(),
    ensureQuickActionsButton: vi.fn(),
    removeQuickActionsButton: vi.fn()
}));

vi.mock('./viewerUiController.js', () => ({
    initViewerUiController: vi.fn(),
    cleanupViewerUiController: vi.fn(),
    setViewerMode: vi.fn(),
    syncViewerUi: vi.fn(),
    VIEWER_MODES: { MEDIA: 'media', PHOTO: 'photo' }
}));

vi.mock('../playback/autoPlay.js', () => ({
    initAutoPlayManager: vi.fn(),
    isAutoPlayActive: vi.fn(() => false),
    handleAutoPlay: vi.fn(),
    toggleAutoPlay: vi.fn(),
    cleanupAutoPlayManager: vi.fn()
}));

vi.mock('../../../utils/progressDB.js', () => ({
    initProgressDB: vi.fn(() => Promise.resolve()),
    deleteVideoLocalProgress: vi.fn(() => Promise.resolve()),
    saveLocalProgress: vi.fn(() => Promise.resolve()),
    getLocalProgress: vi.fn(() => null),
    saveVideoLocalProgress: vi.fn(() => Promise.resolve()),
    getVideoLocalProgress: vi.fn(() => null),
    getCategoryVideoLocalProgress: vi.fn(() => Promise.resolve([])),
    getAllVideoLocalProgress: vi.fn(() => Promise.resolve([])),
    isUserAdmin: vi.fn(() => false),
    isSessionProgressEnabled: vi.fn(() => false),
    isProgressDBReady: vi.fn(() => true),
    isTvAuthorityForCategory: vi.fn(() => false)
}));

vi.mock('./download.js', () => ({
    initDownloadManager: vi.fn(),
    getCurrentMediaItem: vi.fn(() => null),
    downloadCurrentMedia: vi.fn(),
    ensureDownloadButton: vi.fn(),
    removeDownloadButton: vi.fn(),
    cleanupDownloadManager: vi.fn()
}));

vi.mock('../../../libs/ragot.esm.min.js', () => {
    class Module {
        constructor() { this._listeners = []; this._cleanups = []; this._timeouts = []; }
        start() { }
        stop() {
            this._listeners.forEach(l => l.target?.removeEventListener?.(l.type, l.handler));
            this._listeners = [];
            this._cleanups.forEach(fn => fn());
            this._cleanups = [];
            this._timeouts.forEach(id => clearTimeout(id));
            this._timeouts = [];
        }
        on(target, type, handler, options) {
            if (target) target.addEventListener(type, handler, options);
            this._listeners.push({ target, type, handler });
        }
        addCleanup(fn) { this._cleanups.push(fn); }
        timeout(fn, ms) { const id = setTimeout(fn, ms); this._timeouts.push(id); return id; }
        clearTimeout(id) { clearTimeout(id); }
    }
    class Component {
        constructor(state) { this.state = state || {}; this._isMounted = false; }
        setState(partial) { this.state = { ...this.state, ...partial }; this.render?.(); }
        mount() { this._isMounted = true; }
        unmount() { this._isMounted = false; }
    }
    const bus = {
        on: vi.fn(() => vi.fn()),
        emit: vi.fn(),
        off: vi.fn()
    };
    const createElement = vi.fn((tag, props, ...children) => {
        const el = document.createElement(typeof tag === 'string' ? tag : 'div');
        if (props) {
            Object.entries(props).forEach(([k, v]) => {
                if (k === 'className') el.className = v;
                else if (k === 'innerHTML') el.innerHTML = v;
                else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
                else if (k.startsWith('on') && typeof v === 'function') {
                    el.addEventListener(k.substring(2).toLowerCase(), v);
                } else el.setAttribute(k, v);
            });
        }
        children.flat().forEach(c => {
            if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
        });
        return el;
    });

    return {
        Module,
        Component,
        bus,
        createElement,
        $: vi.fn((sel, ctx) => (ctx || document).querySelector(sel)),
        $$: vi.fn((sel, ctx) => Array.from((ctx || document).querySelectorAll(sel))),
        attr: vi.fn((el, props) => {
            if (el && props) Object.entries(props).forEach(([k, v]) => el.setAttribute(k, v));
        }),
        css: vi.fn(),
        renderList: vi.fn(),
        renderGrid: vi.fn(),
        morphDOM: vi.fn(),
        clear: vi.fn(el => { if (el) el.innerHTML = ''; }),
        append: vi.fn((p, c) => p?.appendChild(c)),
        prepend: vi.fn((p, c) => p?.prepend(c)),
        remove: vi.fn(el => el?.remove()),
        show: vi.fn(el => { if (el) el.style.display = ''; }),
        hide: vi.fn(el => { if (el) el.style.display = 'none'; }),
        toggle: vi.fn((el, val) => { if (el) el.style.display = val ? '' : 'none'; }),
        createStateStore: vi.fn(() => ({ state: {}, set: vi.fn(), get: vi.fn() })),
        createSelector: vi.fn(fn => fn),
        createApp: vi.fn(),
        default: { bus, createElement, Module, Component }
    };
});

vi.mock('../../../utils/layoutUtils.js', () => ({
    setupLayoutNavigation: vi.fn(),
    cleanupLayoutNavigation: vi.fn(),
    onLayoutMediaRendered: vi.fn(),
    onLayoutViewerClosed: vi.fn()
}));

vi.mock('../../../utils/wakeLock.js', () => ({
    requestWakeLock: vi.fn(),
    releaseWakeLock: vi.fn()
}));

vi.mock('../../../utils/liveVisibility.js', () => ({
    refreshAllLayouts: vi.fn()
}));

vi.mock('../../../utils/appStateUtils.js', () => ({
    setAppState: vi.fn((key, value) => {
        if (window.ragotModules?.appState) window.ragotModules.appState[key] = value;
    }),
    getAppState: vi.fn(() => window.ragotModules?.appState || {})
}));

import {
    navigateMedia,
    initMediaNavigation
} from '../../../modules/media/navigation.js';

import { app, mediaViewer, spinnerContainer, getMediaPerPage } from '../../../core/app.js';
import { initProgressDB } from '../../../utils/progressDB.js';
import { initTranscodingPlayer } from '../../../modules/media/transcodingPlayer.js';
import { initDownloadManager } from '../../../modules/media/download.js';
import { initAutoPlayManager } from '../../../modules/playback/autoPlay.js';

describe('Media Navigation Module', () => {
    beforeEach(() => {
        // Reset app state
        app.state.currentMediaIndex = 0;
        app.state.fullMediaList = [
            { type: 'image', name: 'image1.jpg', url: '/media/image1.jpg' },
            { type: 'video', name: 'video1.mp4', url: '/media/video1.mp4' },
            { type: 'image', name: 'image2.jpg', url: '/media/image2.jpg' }
        ];
        app.state.navigationDisabled = false;
        app.state.hasMoreMedia = true;

        // Mock window properties
        window.fullscreenExited = false;
        window.ragotModules = {
            fullscreenManager: {
                hasRecentFullscreenExit: vi.fn(() => false)
            },
            appState: app.state,
            appStore: {
                getState: () => app.state,
                actions: {
                    setField: (key, value) => {
                        app.state[key] = value;
                        return value;
                    }
                },
                get: (key, fallbackValue = undefined) => {
                    const value = app.state[key];
                    return value === undefined ? fallbackValue : value;
                },
                set: (key, value) => {
                    app.state[key] = value;
                    return value;
                },
                patch: (partial) => {
                    if (partial && typeof partial === 'object') {
                        Object.assign(app.state, partial);
                    }
                    return app.state;
                }
            },
            appDom: {
                mediaViewer,
                spinnerContainer
            },
            appRuntime: {
                LOAD_MORE_THRESHOLD: 5,
                renderWindowSize: 3,
                getMediaPerPage
            },
            commandPopup: {
                isPopupVisible: vi.fn(() => false)
            }
        };

        // Reset mocks
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    describe('initMediaNavigation', () => {
        it('should initialize without throwing', () => {
            const mockSocket = { emit: vi.fn(), on: vi.fn() };

            expect(() => initMediaNavigation(mockSocket)).not.toThrow();
        });

        it('should work without socket instance', () => {
            expect(() => initMediaNavigation(null)).not.toThrow();
        });
    });

    describe('navigateMedia - Guard Clauses', () => {
        it('should ignore events from chat container', () => {
            const chatElement = document.createElement('div');
            chatElement.id = 'chat-container';
            const button = document.createElement('button');
            chatElement.appendChild(button);

            const event = {
                target: button
            };
            event.target.closest = vi.fn((selector) => {
                if (selector === '#chat-container') return chatElement;
                return null;
            });

            const initialIndex = app.state.currentMediaIndex;
            navigateMedia('next', event);

            // Should not navigate
            expect(app.state.currentMediaIndex).toBe(initialIndex);
        });

        it('should ignore navigation during fullscreen exit cooldown', () => {
            window.ragotModules.fullscreenManager.hasRecentFullscreenExit = vi.fn(() => true);

            const initialIndex = app.state.currentMediaIndex;
            navigateMedia('next');

            expect(app.state.currentMediaIndex).toBe(initialIndex);
        });

        it('should ignore navigation when command popup is visible', () => {
            window.ragotModules.commandPopup.isPopupVisible = vi.fn(() => true);

            const initialIndex = app.state.currentMediaIndex;
            navigateMedia('next');

            expect(app.state.currentMediaIndex).toBe(initialIndex);
        });

        it('should ignore directional navigation when disabled (sync mode)', () => {
            app.state.navigationDisabled = true;

            const initialIndex = app.state.currentMediaIndex;
            navigateMedia('next');
            expect(app.state.currentMediaIndex).toBe(initialIndex);

            navigateMedia('prev');
            expect(app.state.currentMediaIndex).toBe(initialIndex);
        });

        it('should not navigate before list start', () => {
            app.state.currentMediaIndex = 0;

            navigateMedia('prev');

            expect(app.state.currentMediaIndex).toBe(0);
        });

        it('should not navigate beyond list end when no more media', () => {
            app.state.currentMediaIndex = app.state.fullMediaList.length - 1;
            app.state.hasMoreMedia = false;

            navigateMedia('next');

            expect(app.state.currentMediaIndex).toBe(app.state.fullMediaList.length - 1);
        });
    });

    describe('State Management', () => {
        it('should handle empty media list', () => {
            app.state.fullMediaList = [];
            app.state.currentMediaIndex = 0;

            expect(() => navigateMedia('next')).not.toThrow();
        });

        it('should handle undefined direction (play/pause toggle)', () => {
            expect(() => navigateMedia()).not.toThrow();
        });
    });
});
