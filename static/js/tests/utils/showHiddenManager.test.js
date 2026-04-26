/**
 * Tests for showHiddenManager module
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { bus } from '../../libs/ragot.esm.min.js';
import { APP_EVENTS } from '../../core/appEvents.js';
import {
    isShowHiddenEnabled,
    enableShowHidden,
    disableShowHidden,
    getShowHiddenHeaders,
    appendShowHiddenParam,
    checkRevealHiddenStatus
} from '../../utils/showHiddenManager.js';

describe('showHiddenManager', () => {
    let originalAppConfig;

    beforeEach(() => {
        sessionStorage.clear();
        vi.restoreAllMocks();
        originalAppConfig = window.appConfig;
        window.appConfig = { is_admin: true };
        // isUserAdmin() reads from ragotModules.appStore, not window.appConfig directly
        window.ragotModules.appStore.set('isAdmin', true);
    });

    afterEach(() => {
        sessionStorage.clear();
        vi.restoreAllMocks();
        window.appConfig = originalAppConfig;
        window.ragotModules.appStore.set('isAdmin', false);
    });

    describe('isShowHiddenEnabled', () => {
        it('returns false when not set', () => {
            expect(isShowHiddenEnabled()).toBe(false);
        });

        it('returns true when set to true', () => {
            sessionStorage.setItem('show_hidden', 'true');
            expect(isShowHiddenEnabled()).toBe(true);
        });

        it('returns false when set to false', () => {
            sessionStorage.setItem('show_hidden', 'false');
            expect(isShowHiddenEnabled()).toBe(false);
        });
    });

    describe('enableShowHidden', () => {
        it('sets sessionStorage item', () => {
            enableShowHidden();
            expect(sessionStorage.getItem('show_hidden')).toBe('true');
        });

        it('emits show hidden toggled event', () => {
            const eventSpy = vi.fn();
            const unsub = bus.on(APP_EVENTS.SHOW_HIDDEN_TOGGLED, eventSpy);

            enableShowHidden();

            expect(eventSpy).toHaveBeenCalledTimes(1);
            expect(eventSpy.mock.calls[0][0].showHidden).toBe(true);
            unsub();
        });
    });

    describe('disableShowHidden', () => {
        it('removes sessionStorage item', () => {
            sessionStorage.setItem('show_hidden', 'true');
            disableShowHidden();
            expect(sessionStorage.getItem('show_hidden')).toBe(null);
        });

        it('emits show hidden toggled event', () => {
            const eventSpy = vi.fn();
            const unsub = bus.on(APP_EVENTS.SHOW_HIDDEN_TOGGLED, eventSpy);
            sessionStorage.setItem('show_hidden', 'true');

            disableShowHidden();

            expect(eventSpy).toHaveBeenCalledTimes(1);
            expect(eventSpy.mock.calls[0][0].showHidden).toBe(false);
            unsub();
        });
    });

    describe('getShowHiddenHeaders', () => {
        it('returns empty object when disabled', () => {
            expect(getShowHiddenHeaders()).toEqual({});
        });

        it('returns header object when enabled', () => {
            enableShowHidden();
            const headers = getShowHiddenHeaders();

            expect(headers['X-Show-Hidden']).toBe('true');
        });
    });

    describe('appendShowHiddenParam', () => {
        it('returns original URL when disabled', () => {
            const url = 'http://example.com/image.jpg';
            expect(appendShowHiddenParam(url)).toBe(url);
        });

        it('appends query param when enabled', () => {
            enableShowHidden();
            const url = 'http://example.com/image.jpg';
            const result = appendShowHiddenParam(url);

            expect(result).toBe('http://example.com/image.jpg?show_hidden=true');
        });

        it('uses & separator when URL has query params', () => {
            enableShowHidden();
            const url = 'http://example.com/image.jpg?width=100';
            const result = appendShowHiddenParam(url);

            expect(result).toBe('http://example.com/image.jpg?width=100&show_hidden=true');
        });

        it('returns null when input is null and disabled', () => {
            expect(appendShowHiddenParam(null)).toBe(null);
        });

        it('returns null when input is null and enabled', () => {
            enableShowHidden();
            expect(appendShowHiddenParam(null)).toBe(null);
        });
    });

    describe('checkRevealHiddenStatus', () => {
        it('returns true when server reports active', async () => {
            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ active: true })
            });

            enableShowHidden();
            const result = await checkRevealHiddenStatus();

            expect(result).toBe(true);
            expect(isShowHiddenEnabled()).toBe(true);
        });

        it('disables when server reports inactive', async () => {
            global.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ active: false })
            });

            enableShowHidden();
            const result = await checkRevealHiddenStatus();

            expect(result).toBe(false);
            expect(isShowHiddenEnabled()).toBe(false);
        });

        it('disables on network error', async () => {
            global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

            enableShowHidden();
            const result = await checkRevealHiddenStatus();

            expect(result).toBe(false);
            expect(isShowHiddenEnabled()).toBe(false);
        });

        it('disables on non-ok response', async () => {
            global.fetch = vi.fn().mockResolvedValue({
                ok: false,
                status: 500
            });

            enableShowHidden();
            const result = await checkRevealHiddenStatus();

            expect(result).toBe(false);
            expect(isShowHiddenEnabled()).toBe(false);
        });
    });
});
