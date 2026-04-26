import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createLayoutSocketHandlerManager } from '../../../../modules/layouts/shared/socketHandlers.js';

describe('layout socket handlers', () => {
    let socket;
    let handlers;
    let originalRagotModules;

    beforeEach(() => {
        vi.useFakeTimers();
        handlers = {};
        socket = {
            on: vi.fn((event, handler) => {
                handlers[event] = handler;
            }),
            off: vi.fn((event, handler) => {
                if (handlers[event] === handler) delete handlers[event];
            })
        };

        originalRagotModules = window.ragotModules;
        window.ragotModules = {
            mediaLoader: { clearMediaCache: vi.fn() },
            cacheManager: { clearCache: vi.fn() }
        };
    });

    afterEach(() => {
        vi.runOnlyPendingTimers();
        vi.useRealTimers();
        window.ragotModules = originalRagotModules;
    });

    it('does not trigger a server force refresh when reveal hidden is toggled', async () => {
        const refresh = vi.fn();
        const syncShowHiddenFromEvent = vi.fn().mockResolvedValue(undefined);

        const manager = createLayoutSocketHandlerManager({
            isActive: () => true,
            refresh,
            syncShowHiddenFromEvent,
            forceRefreshOnShowHiddenToggle: false
        });

        manager.register(socket);

        await handlers.category_updated({
            reason: 'show_hidden_enabled',
            show_hidden: true
        });

        await vi.advanceTimersByTimeAsync(800);

        expect(syncShowHiddenFromEvent).toHaveBeenCalledWith({
            reason: 'show_hidden_enabled',
            show_hidden: true
        });
        expect(window.ragotModules.mediaLoader.clearMediaCache).toHaveBeenCalledTimes(1);
        expect(window.ragotModules.cacheManager.clearCache).toHaveBeenCalledTimes(1);
        expect(refresh).toHaveBeenCalledWith(false, false, true);
    });

    it('uses force refresh for usb mount changes', () => {
        const refresh = vi.fn();
        const syncShowHiddenFromEvent = vi.fn().mockResolvedValue(undefined);

        const manager = createLayoutSocketHandlerManager({
            isActive: () => true,
            refresh,
            syncShowHiddenFromEvent,
            forceRefreshOnShowHiddenToggle: false
        });

        manager.register(socket);
        handlers.usb_mounts_changed({ force_refresh: true });

        expect(window.ragotModules.mediaLoader.clearMediaCache).toHaveBeenCalledTimes(1);
        expect(window.ragotModules.cacheManager.clearCache).toHaveBeenCalledTimes(1);
        expect(refresh).toHaveBeenCalledWith(true, false, true);
    });

    it('does not use force refresh for usb unmount-only changes', () => {
        const refresh = vi.fn();
        const syncShowHiddenFromEvent = vi.fn().mockResolvedValue(undefined);

        const manager = createLayoutSocketHandlerManager({
            isActive: () => true,
            refresh,
            syncShowHiddenFromEvent,
            forceRefreshOnShowHiddenToggle: false
        });

        manager.register(socket);
        handlers.usb_mounts_changed({ force_refresh: false });

        expect(window.ragotModules.mediaLoader.clearMediaCache).toHaveBeenCalledTimes(1);
        expect(window.ragotModules.cacheManager.clearCache).toHaveBeenCalledTimes(1);
        expect(refresh).toHaveBeenCalledWith(false, false, true);
    });
});
