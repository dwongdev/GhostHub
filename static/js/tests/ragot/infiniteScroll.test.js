/**
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createInfiniteScroll } from '../../libs/ragot.esm.min.js';

describe('createInfiniteScroll', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.clearAllMocks();
        globalThis.IntersectionObserver = window.IntersectionObserver;
    });

    it('ignores opposite-direction intersections while an async load is in flight', async () => {
        const callbacks = [];
        window.IntersectionObserver = vi.fn().mockImplementation((callback) => {
            callbacks.push(callback);
            return {
                observe: vi.fn(),
                unobserve: vi.fn(),
                disconnect: vi.fn(),
            };
        });
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        document.body.appendChild(topSentinel);
        document.body.appendChild(sentinel);

        const visible = new Set([0, 1, 2]);
        let resolveBottom;
        let resolveTop;
        const onLoadMore = vi.fn((index) => new Promise((resolve) => {
            if (index === 3) resolveBottom = resolve;
            if (index === 0) resolveTop = resolve;
        }));
        const onEvictChunk = vi.fn((index) => {
            visible.delete(index);
        });

        createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 10,
            visibleChunks: () => visible,
            onLoadMore: (index) => {
                const promise = onLoadMore(index);
                if (index === 3) {
                    promise.then(() => visible.add(3));
                }
                if (index === 0) {
                    promise.then(() => visible.add(0));
                }
                return promise;
            },
            onEvictChunk,
        });

        const observerCallback = callbacks[0];
        observerCallback([{ target: sentinel, isIntersecting: true }]);
        observerCallback([{ target: topSentinel, isIntersecting: true }]);

        expect(onLoadMore).toHaveBeenCalledTimes(1);
        expect(onLoadMore).toHaveBeenNthCalledWith(1, 3);
        expect(onEvictChunk).not.toHaveBeenCalled();

        resolveBottom();
        await Promise.resolve();
        await Promise.resolve();

        // Current primitive behavior: no direction queue.
        // A top intersection received while bottom is loading is ignored.
        expect(onLoadMore).toHaveBeenCalledTimes(1);
        expect(onEvictChunk).toHaveBeenCalledTimes(1);
        expect(onEvictChunk).toHaveBeenNthCalledWith(1, 0);

        observerCallback([{ target: topSentinel, isIntersecting: true }]);
        expect(onLoadMore).toHaveBeenCalledTimes(2);
        expect(onLoadMore).toHaveBeenNthCalledWith(2, 0);

        resolveTop();
        await Promise.resolve();
        await Promise.resolve();

        expect(onEvictChunk).toHaveBeenCalledTimes(2);
        expect(onEvictChunk).toHaveBeenNthCalledWith(2, 3);

        rafSpy.mockRestore();
    });

    it('waits for sentinels and root to connect before observing', () => {
        const observer = {
            observe: vi.fn(),
            unobserve: vi.fn(),
            disconnect: vi.fn(),
        };
        window.IntersectionObserver = vi.fn().mockImplementation(() => observer);
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafQueue = [];
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            rafQueue.push(cb);
            return rafQueue.length;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const root = document.createElement('div');
        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        root.appendChild(topSentinel);
        root.appendChild(sentinel);

        const controller = createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            root,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 10,
            visibleChunks: () => new Set([0]),
            onLoadMore: vi.fn(),
            onEvictChunk: vi.fn(),
        });

        expect(observer.observe).not.toHaveBeenCalled();

        document.body.appendChild(root);
        const tick = rafQueue.shift();
        tick();

        // Should observe immediately upon connection, even if 0x0
        expect(observer.observe).toHaveBeenCalledTimes(2);
        expect(observer.observe).toHaveBeenNthCalledWith(1, sentinel);
        expect(observer.observe).toHaveBeenNthCalledWith(2, topSentinel);

        controller.destroy();
        rafSpy.mockRestore();
    });

    it('defers eviction until an async load settles', async () => {
        const callbacks = [];
        window.IntersectionObserver = vi.fn().mockImplementation((callback) => {
            callbacks.push(callback);
            return {
                observe: vi.fn(),
                unobserve: vi.fn(),
                disconnect: vi.fn(),
            };
        });
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        document.body.appendChild(topSentinel);
        document.body.appendChild(sentinel);

        const visible = new Set([0, 1, 2]);
        let resolveLoad;
        const onLoadMore = vi.fn((index) => new Promise((resolve) => {
            resolveLoad = () => {
                visible.add(index);
                resolve();
            };
        }));
        const onEvictChunk = vi.fn((index) => {
            visible.delete(index);
        });

        createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 10,
            visibleChunks: () => visible,
            onLoadMore,
            onEvictChunk,
        });

        const observerCallback = callbacks[0];
        observerCallback([{ target: sentinel, isIntersecting: true }]);

        expect(onLoadMore).toHaveBeenCalledWith(3);
        expect(onEvictChunk).not.toHaveBeenCalled();

        resolveLoad();
        await Promise.resolve();
        await Promise.resolve();

        expect(onEvictChunk).toHaveBeenCalledTimes(1);
        expect(onEvictChunk).toHaveBeenCalledWith(0);
        rafSpy.mockRestore();
    });

    it('repositions sentinels relative to the live visible chunk element', () => {
        const observer = {
            observe: vi.fn(),
            unobserve: vi.fn(),
            disconnect: vi.fn(),
        };
        window.IntersectionObserver = vi.fn().mockImplementation(() => observer);
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const host = document.createElement('div');
        document.body.appendChild(host);

        const topSentinel = document.createElement('div');
        const bottomSentinel = document.createElement('div');
        const leadingPlaceholder = document.createElement('div');
        leadingPlaceholder.dataset.vsPlaceholderStart = '0';
        leadingPlaceholder.dataset.vsPlaceholderEnd = '9';
        const liveChunk = document.createElement('div');
        liveChunk.dataset.vsChunk = '10';
        const trailingPlaceholder = document.createElement('div');
        trailingPlaceholder.dataset.vsPlaceholderStart = '11';
        trailingPlaceholder.dataset.vsPlaceholderEnd = '20';

        host.append(topSentinel, liveChunk, bottomSentinel);

        const controller = createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel: bottomSentinel,
            topSentinel,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 30,
            visibleChunks: () => new Set([10]),
            getChunkEl: () => liveChunk,
            onLoadMore: vi.fn(),
            onEvictChunk: vi.fn(),
        });

        host.insertBefore(leadingPlaceholder, liveChunk);
        host.insertBefore(trailingPlaceholder, bottomSentinel);

        controller.reset();

        expect(host.children[0]).toBe(leadingPlaceholder);
        expect(host.children[1]).toBe(topSentinel);
        expect(host.children[2]).toBe(liveChunk);
        expect(host.children[3]).toBe(bottomSentinel);
        expect(host.children[4]).toBe(trailingPlaceholder);

        controller.destroy();
        rafSpy.mockRestore();
    });

    it('ignores unknown shouldLoadMore option and still applies default load behavior', () => {
        const callbacks = [];
        window.IntersectionObserver = vi.fn().mockImplementation((callback) => {
            callbacks.push(callback);
            return {
                observe: vi.fn(),
                unobserve: vi.fn(),
                disconnect: vi.fn(),
            };
        });
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        document.body.appendChild(topSentinel);
        document.body.appendChild(sentinel);

        const onLoadMore = vi.fn();

        createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 10,
            visibleChunks: () => new Set([0]),
            onLoadMore,
            onEvictChunk: vi.fn(),
            shouldLoadMore: () => false,
        });

        const observerCallback = callbacks[0];
        observerCallback([{ target: sentinel, isIntersecting: true }]);

        expect(onLoadMore).toHaveBeenCalledTimes(1);
        expect(onLoadMore).toHaveBeenCalledWith(1);
    });

    it('requires a fresh top intersection after bottom async load settles', async () => {
        const callbacks = [];
        window.IntersectionObserver = vi.fn().mockImplementation((callback) => {
            callbacks.push(callback);
            return {
                observe: vi.fn(),
                unobserve: vi.fn(),
                disconnect: vi.fn(),
            };
        });
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const root = document.createElement('div');
        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        root.appendChild(topSentinel);
        root.appendChild(sentinel);
        document.body.appendChild(root);
        Object.defineProperty(root, 'clientHeight', {
            configurable: true,
            value: 320,
        });

        root.scrollTop = 120;

        const visible = new Set([5, 6, 7]);
        let resolveBottom;
        let resolveTop;
        const onLoadMore = vi.fn((index) => new Promise((resolve) => {
            if (index === 8) {
                resolveBottom = () => {
                    visible.add(8);
                    resolve();
                };
            }
            if (index === 5) {
                resolveTop = () => {
                    visible.add(5);
                    resolve();
                };
            }
        }));
        const onEvictChunk = vi.fn((index) => {
            visible.delete(index);
        });

        createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            root,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 20,
            visibleChunks: () => visible,
            onLoadMore,
            onEvictChunk,
        });

        root.scrollTop = 40;
        root.dispatchEvent(new Event('scroll'));

        const observerCallback = callbacks[0];
        observerCallback([{ target: sentinel, isIntersecting: true }]);
        observerCallback([{ target: topSentinel, isIntersecting: true }]);
        observerCallback([{ target: sentinel, isIntersecting: true }]);

        expect(onLoadMore).toHaveBeenCalledTimes(1);
        expect(onLoadMore).toHaveBeenNthCalledWith(1, 8);

        resolveBottom();
        await Promise.resolve();
        await Promise.resolve();

        expect(onEvictChunk).toHaveBeenCalledWith(5);
        // Top events that happened during the bottom in-flight window were ignored.
        expect(onLoadMore).toHaveBeenCalledTimes(1);
        observerCallback([{ target: topSentinel, isIntersecting: true }]);
        expect(onLoadMore).toHaveBeenCalledTimes(2);
        expect(onLoadMore).toHaveBeenNthCalledWith(2, 5);

        resolveTop();
        await Promise.resolve();
        await Promise.resolve();

        expect(onEvictChunk).toHaveBeenNthCalledWith(2, 8);
        rafSpy.mockRestore();
    });

    it('defers bottom load when it would evict chunk 0 while top sentinel intersects, then retries on exit', async () => {
        const callbacks = [];
        window.IntersectionObserver = vi.fn().mockImplementation((callback) => {
            callbacks.push(callback);
            return {
                observe: vi.fn(),
                unobserve: vi.fn(),
                disconnect: vi.fn(),
            };
        });
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        document.body.appendChild(topSentinel);
        document.body.appendChild(sentinel);

        const visible = new Set([0, 1, 2]);
        const onLoadMore = vi.fn();
        const onEvictChunk = vi.fn();

        createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 10,
            visibleChunks: () => visible,
            onLoadMore,
            onEvictChunk,
        });

        const observerCallback = callbacks[0];

        // Top sentinel is intersecting and chunk 0 is the min at maxChunks —
        // bottom load would evict chunk 0 which would immediately be reloaded,
        // so it should be deferred.
        observerCallback([{ target: topSentinel, isIntersecting: true }]);
        observerCallback([{ target: sentinel, isIntersecting: true }]);

        expect(onLoadMore).not.toHaveBeenCalled();

        // Top sentinel exits the root margin — deferred bottom load should retry.
        observerCallback([{ target: topSentinel, isIntersecting: false }]);

        expect(onLoadMore).toHaveBeenCalledTimes(1);
        expect(onLoadMore).toHaveBeenCalledWith(3);

        rafSpy.mockRestore();
    });

    it('allows bottom load when below maxChunks even with chunk 0 visible and top intersecting', () => {
        const callbacks = [];
        window.IntersectionObserver = vi.fn().mockImplementation((callback) => {
            callbacks.push(callback);
            return {
                observe: vi.fn(),
                unobserve: vi.fn(),
                disconnect: vi.fn(),
            };
        });
        globalThis.IntersectionObserver = window.IntersectionObserver;

        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const sentinel = document.createElement('div');
        const topSentinel = document.createElement('div');
        document.body.appendChild(topSentinel);
        document.body.appendChild(sentinel);

        // Only 1 chunk visible — well below maxChunks of 3.
        // Bottom load should proceed even with chunk 0 and top intersecting.
        const visible = new Set([0]);
        const onLoadMore = vi.fn();
        const onEvictChunk = vi.fn();

        createInfiniteScroll({
            _lc: {
                addCleanup: vi.fn(() => () => true),
            },
        }, {
            sentinel,
            topSentinel,
            chunkSize: 1,
            maxChunks: 3,
            totalItems: () => 10,
            visibleChunks: () => visible,
            onLoadMore,
            onEvictChunk,
        });

        const observerCallback = callbacks[0];
        observerCallback([{ target: topSentinel, isIntersecting: true }]);
        observerCallback([{ target: sentinel, isIntersecting: true }]);

        expect(onLoadMore).toHaveBeenCalledTimes(1);
        expect(onLoadMore).toHaveBeenCalledWith(1);

        rafSpy.mockRestore();
    });
});
