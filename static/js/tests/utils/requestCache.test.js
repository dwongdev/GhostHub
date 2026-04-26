/**
 * Request Cache & Deduplication Tests
 * ------------------------------------
 * Critical infrastructure: prevents thundering-herd API calls on Pi.
 * Verifies deduplication, cache-key isolation, timeout behavior,
 * and correct cleanup after resolution/rejection.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// The module has internal state (inFlightRequests Map), so we reset between tests
let cachedFetch, clearRequestCache, getInFlightCount;

beforeEach(async () => {
    vi.resetModules();
    const mod = await import('../../utils/requestCache.js');
    cachedFetch = mod.cachedFetch;
    clearRequestCache = mod.clearRequestCache;
    getInFlightCount = mod.getInFlightCount;

    // Provide a controllable fetch mock
    global.fetch = vi.fn();
    global.AbortController = class {
        constructor() {
            this.signal = { aborted: false };
            this.abort = vi.fn(() => { this.signal.aborted = true; });
        }
    };
});

afterEach(() => {
    clearRequestCache();
    vi.restoreAllMocks();
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

function mockResponse(body = {}, ok = true) {
    // Each response needs to support .clone() just like the real Fetch API
    const makeRes = () => ({
        ok,
        status: ok ? 200 : 500,
        json: () => Promise.resolve(body),
        text: () => Promise.resolve(JSON.stringify(body)),
        clone() { return makeRes(); }
    });
    return makeRes();
}

// ─── Deduplication ────────────────────────────────────────────────────────────

describe('Request Deduplication', () => {
    it('deduplicates simultaneous GET requests to the same URL', async () => {
        const response = mockResponse({ categories: [] });
        global.fetch.mockResolvedValue(response);

        // Fire two requests simultaneously — only ONE fetch should happen
        const [r1, r2] = await Promise.all([
            cachedFetch('/api/categories'),
            cachedFetch('/api/categories')
        ]);

        expect(global.fetch).toHaveBeenCalledTimes(1);
        // Both should resolve to usable response clones
        expect((await r1.json()).categories).toEqual([]);
        expect((await r2.json()).categories).toEqual([]);
    });

    it('does NOT deduplicate requests with different URLs', async () => {
        global.fetch.mockResolvedValue(mockResponse());

        await Promise.all([
            cachedFetch('/api/categories'),
            cachedFetch('/api/media/list')
        ]);

        expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('does NOT deduplicate GET vs POST to the same URL', async () => {
        global.fetch.mockResolvedValue(mockResponse());

        await Promise.all([
            cachedFetch('/api/progress', {}),
            cachedFetch('/api/progress', { method: 'POST' })
        ]);

        expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('does NOT deduplicate requests with different headers', async () => {
        global.fetch.mockResolvedValue(mockResponse());

        await Promise.all([
            cachedFetch('/api/data', { headers: { 'X-Session': 'aaa' } }),
            cachedFetch('/api/data', { headers: { 'X-Session': 'bbb' } })
        ]);

        expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('allows a second request after the first resolves', async () => {
        global.fetch.mockResolvedValue(mockResponse({ call: 1 }));
        await cachedFetch('/api/data');

        global.fetch.mockResolvedValue(mockResponse({ call: 2 }));
        const r2 = await cachedFetch('/api/data');

        expect(global.fetch).toHaveBeenCalledTimes(2);
        expect(await r2.json()).toEqual({ call: 2 });
    });
});

// ─── Cache Key Isolation ──────────────────────────────────────────────────────

describe('Cache Key Generation', () => {
    it('treats missing method as GET', async () => {
        global.fetch.mockResolvedValue(mockResponse());

        await Promise.all([
            cachedFetch('/api/data'),
            cachedFetch('/api/data', { method: 'GET' })
        ]);

        // Both should share the same cache key → 1 fetch
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('includes headers in cache key', async () => {
        global.fetch.mockResolvedValue(mockResponse());

        await Promise.all([
            cachedFetch('/api/data', { headers: { 'Accept': 'application/json' } }),
            cachedFetch('/api/data')  // no headers
        ]);

        expect(global.fetch).toHaveBeenCalledTimes(2);
    });
});

// ─── In-Flight Counter ────────────────────────────────────────────────────────

describe('In-Flight Tracking', () => {
    it('starts at zero', () => {
        expect(getInFlightCount()).toBe(0);
    });

    it('tracks in-flight requests', async () => {
        let resolveRequest;
        global.fetch.mockReturnValue(new Promise(r => { resolveRequest = r; }));

        const promise = cachedFetch('/api/slow');
        expect(getInFlightCount()).toBe(1);

        resolveRequest(mockResponse());
        await promise;
        expect(getInFlightCount()).toBe(0);
    });

    it('cleans up on rejection', async () => {
        global.fetch.mockRejectedValue(new Error('network down'));

        await cachedFetch('/api/fail').catch(() => { });
        expect(getInFlightCount()).toBe(0);
    });
});

// ─── Error Handling ───────────────────────────────────────────────────────────

describe('Error Handling', () => {
    it('propagates fetch errors', async () => {
        global.fetch.mockRejectedValue(new Error('Connection refused'));

        await expect(cachedFetch('/api/offline')).rejects.toThrow('Connection refused');
    });

    it('does not cache errored requests for future callers', async () => {
        global.fetch.mockRejectedValueOnce(new Error('temporary'));
        await cachedFetch('/api/flaky').catch(() => { });

        // Second call should trigger a new fetch
        global.fetch.mockResolvedValue(mockResponse({ recovered: true }));
        const r = await cachedFetch('/api/flaky');
        expect(await r.json()).toEqual({ recovered: true });
        expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('propagates same error to all concurrent callers', async () => {
        global.fetch.mockRejectedValue(new Error('boom'));

        const results = await Promise.allSettled([
            cachedFetch('/api/blow-up'),
            cachedFetch('/api/blow-up')
        ]);

        expect(results[0].status).toBe('rejected');
        expect(results[1].status).toBe('rejected');
        expect(results[0].reason.message).toBe('boom');
        expect(results[1].reason.message).toBe('boom');
        // Only 1 actual fetch
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });
});

// ─── clearRequestCache ───────────────────────────────────────────────────────

describe('clearRequestCache', () => {
    it('resets in-flight count to zero', async () => {
        let resolveRequest;
        global.fetch.mockReturnValue(new Promise(r => { resolveRequest = r; }));

        cachedFetch('/api/pending');
        expect(getInFlightCount()).toBe(1);

        clearRequestCache();
        expect(getInFlightCount()).toBe(0);

        resolveRequest(mockResponse());
    });
});

// ─── Timeout Behavior ────────────────────────────────────────────────────────

describe('Timeout', () => {
    it('passes abort signal to fetch', async () => {
        global.fetch.mockResolvedValue(mockResponse());
        await cachedFetch('/api/data');

        // Verify that fetch was called with a signal
        const callArgs = global.fetch.mock.calls[0];
        expect(callArgs[1]).toHaveProperty('signal');
    });

    it('respects custom timeout option', async () => {
        global.fetch.mockResolvedValue(mockResponse());
        await cachedFetch('/api/data', { timeout: 5000 });

        // The timeout option should be stripped from fetch options
        const passedOptions = global.fetch.mock.calls[0][1];
        expect(passedOptions.timeout).toBeUndefined();
    });

    it('uses user-provided signal over auto-generated one', async () => {
        const userController = new AbortController();
        global.fetch.mockResolvedValue(mockResponse());

        await cachedFetch('/api/data', { signal: userController.signal });

        const passedOptions = global.fetch.mock.calls[0][1];
        expect(passedOptions.signal).toBe(userController.signal);
    });
});
