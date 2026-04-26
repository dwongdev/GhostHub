/**
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { VirtualScroller } from '../../libs/ragot.esm.min.js';

function makeHost(id) {
    const el = document.createElement('div');
    el.id = id;
    document.body.appendChild(el);
    return el;
}

function makeChildOptions() {
    return {
        totalItems: () => 1,
        chunkSize: 1,
        maxChunks: 1,
        renderChunk: () => document.createElement('div'),
    };
}

function makeParentOptions(childPoolSize = 1) {
    return {
        totalItems: () => 1,
        chunkSize: 1,
        maxChunks: 1,
        childPoolSize,
        renderChunk: () => document.createElement('div'),
    };
}

describe('VirtualScroller recycle nested lifecycle', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.clearAllMocks();
        globalThis.IntersectionObserver = window.IntersectionObserver;
    });

    it('clears child tracking on recycle so rebind does not duplicate chunk children', () => {
        const parentHost = makeHost('parent-host');
        const railA = makeHost('rail-a');
        const railB = makeHost('rail-b');

        const parent = new VirtualScroller(makeParentOptions(1));
        parent.mount(parentHost);

        parent._visibleChunks.add(0);
        const firstChild = parent.acquireChild(0, makeChildOptions(), railA);
        expect(parent._childScrollers.get(0)).toHaveLength(1);

        parent.recycle();
        expect(parent._childScrollers.size).toBe(0);
        expect(parent._childPool).toHaveLength(1);

        parent.rebind({}, parentHost);
        parent._visibleChunks.add(0);
        const reboundChild = parent.acquireChild(0, makeChildOptions(), railB);

        expect(reboundChild).toBe(firstChild);
        expect(parent._childScrollers.get(0)).toHaveLength(1);

        parent.unmount();
    });

    it('bounds pooled children during recycle and unmounts overflow', () => {
        const parentHost = makeHost('parent-host');
        const railA = makeHost('rail-a');
        const railB = makeHost('rail-b');

        const parent = new VirtualScroller(makeParentOptions(1));
        parent.mount(parentHost);

        parent._visibleChunks.add(0);
        const childA = parent.acquireChild(0, makeChildOptions(), railA);
        parent._visibleChunks.add(1);
        const childB = parent.acquireChild(1, makeChildOptions(), railB);

        const recycleA = vi.spyOn(childA, 'recycle');
        const recycleB = vi.spyOn(childB, 'recycle');
        const unmountA = vi.spyOn(childA, 'unmount');
        const unmountB = vi.spyOn(childB, 'unmount');

        parent.recycle();

        expect(parent._childScrollers.size).toBe(0);
        expect(parent._childPool).toHaveLength(1);
        expect(recycleA.mock.calls.length + recycleB.mock.calls.length).toBe(1);
        expect(unmountA.mock.calls.length + unmountB.mock.calls.length).toBe(1);

        parent.unmount();
    });

    it('removes failed async chunk shells so retries do not accumulate duplicates', async () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const renderChunk = vi.fn(() => Promise.reject(new Error('boom')));
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const vs = new VirtualScroller({
            totalItems: () => 1,
            chunkSize: 1,
            maxChunks: 1,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk,
        });

        vs.mount(host);

        await vs._loadChunk(0);
        expect(chunkParent.querySelectorAll('[data-vs-chunk="0"]')).toHaveLength(0);
        expect(vs.getVisibleChunks().has(0)).toBe(false);

        await vs._loadChunk(0);
        expect(renderChunk).toHaveBeenCalledTimes(2);
        expect(chunkParent.querySelectorAll('[data-vs-chunk="0"]')).toHaveLength(0);

        vs.unmount();
        rafSpy.mockRestore();
    });

    it('replaces stale chunk shells when reinserting a chunk', () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const vs = new VirtualScroller({
            totalItems: () => 1,
            chunkSize: 1,
            maxChunks: 1,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk: () => document.createElement('div'),
        });

        vs.mount(host);

        const staleShell = document.createElement('div');
        staleShell.dataset.vsChunk = '0';
        staleShell.className = 'stale-shell';
        chunkParent.appendChild(staleShell);

        const nextChunk = document.createElement('div');
        nextChunk.dataset.vsChunk = '0';
        nextChunk.className = 'fresh-shell';

        vs._insertChunkEl(nextChunk, 0, chunkParent);

        expect(chunkParent.querySelectorAll('[data-vs-chunk="0"]')).toHaveLength(1);
        expect(chunkParent.querySelector('.fresh-shell')).toBe(nextChunk);
        expect(chunkParent.querySelector('.stale-shell')).toBeNull();

        vs.unmount();
    });

    it('keeps infinite-scroll cleanup count flat across recycle rebind loops', () => {
        const host = makeHost('vs-host');
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const vs = new VirtualScroller({
            totalItems: () => 1,
            chunkSize: 1,
            maxChunks: 1,
            renderChunk: () => document.createElement('div'),
        });

        vs.mount(host);
        const baselineCleanupCount = vs._lc._cleanups.length;

        for (let i = 0; i < 3; i++) {
            vs.recycle();
            vs.rebind({}, host);
            expect(vs._lc._cleanups.length).toBe(baselineCleanupCount);
        }

        vs.unmount();
        rafSpy.mockRestore();
    });

    it('evicts the direct parent chunk instead of a nested child chunk with the same index', () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const vs = new VirtualScroller({
            totalItems: () => 3,
            chunkSize: 1,
            maxChunks: 2,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk: () => document.createElement('div'),
        });

        vs.mount(host);

        const parentChunkZero = document.createElement('div');
        parentChunkZero.dataset.vsChunk = '0';
        const nestedChildChunkOne = document.createElement('div');
        nestedChildChunkOne.dataset.vsChunk = '1';
        nestedChildChunkOne.className = 'nested-child';
        parentChunkZero.appendChild(nestedChildChunkOne);

        const parentChunkOne = document.createElement('div');
        parentChunkOne.dataset.vsChunk = '1';
        parentChunkOne.className = 'parent-one';

        chunkParent.appendChild(parentChunkZero);
        chunkParent.appendChild(parentChunkOne);
        vs._visibleChunks.add(0);
        vs._visibleChunks.add(1);

        vs._evictChunk(1);

        expect(chunkParent.children).not.toContain(parentChunkOne);
        expect(chunkParent.children).toContain(parentChunkZero);
        expect(parentChunkZero.querySelector('.nested-child')).not.toBeNull();
        expect(chunkParent.querySelectorAll(':scope > [data-vs-placeholder="1"]')).toHaveLength(1);
        expect(vs.getVisibleChunks()).toEqual(new Set([0]));

        vs.unmount();
    });

    it('reloads into the direct parent placeholder instead of replacing nested child content', () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const vs = new VirtualScroller({
            totalItems: () => 3,
            chunkSize: 1,
            maxChunks: 2,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk: () => document.createElement('div'),
        });

        vs.mount(host);

        const parentChunkZero = document.createElement('div');
        parentChunkZero.dataset.vsChunk = '0';
        const nestedChildChunkOne = document.createElement('div');
        nestedChildChunkOne.dataset.vsChunk = '1';
        nestedChildChunkOne.className = 'nested-child';
        parentChunkZero.appendChild(nestedChildChunkOne);

        const placeholderOne = document.createElement('div');
        placeholderOne.dataset.vsPlaceholder = '1';
        placeholderOne.className = 'parent-placeholder';

        chunkParent.appendChild(parentChunkZero);
        chunkParent.appendChild(placeholderOne);

        const reloadedParentChunkOne = document.createElement('div');
        reloadedParentChunkOne.dataset.vsChunk = '1';
        reloadedParentChunkOne.className = 'reloaded-parent';

        vs._insertChunkEl(reloadedParentChunkOne, 1, chunkParent);

        expect(parentChunkZero.querySelector('.nested-child')).not.toBeNull();
        expect(chunkParent.querySelectorAll(':scope > [data-vs-chunk="1"]')).toHaveLength(1);
        expect(chunkParent.querySelector(':scope > .reloaded-parent')).toBe(reloadedParentChunkOne);
        expect(chunkParent.querySelector(':scope > .parent-placeholder')).toBeNull();

        vs.unmount();
    });

    it('retains one placeholder per evicted chunk in the current runtime path', () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const vs = new VirtualScroller({
            totalItems: () => 30,
            chunkSize: 1,
            maxChunks: 3,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk: (i) => {
                const el = document.createElement('div');
                el.textContent = `chunk-${i}`;
                return el;
            },
        });

        vs.mount(host);
        vs._loadChunk(0);
        vs._loadChunk(1);
        vs._loadChunk(2);

        for (let next = 3; next < 20; next++) {
            vs._evictChunk(next - 3);
            vs._loadChunk(next);
        }

        const managedNodes = Array.from(chunkParent.children).filter((el) => {
            return (
                el.dataset.vsChunk !== undefined ||
                el.dataset.vsPlaceholder !== undefined ||
                el.dataset.vsPlaceholderStart !== undefined
            );
        });

        expect(vs.getVisibleChunks()).toEqual(new Set([17, 18, 19]));
        // Current behavior uses simple per-index placeholders (data-vs-placeholder).
        expect(chunkParent.querySelectorAll('[data-vs-placeholder-start]')).toHaveLength(0);
        expect(chunkParent.querySelectorAll('[data-vs-placeholder]')).toHaveLength(17);
        expect(managedNodes).toHaveLength(20);

        vs.unmount();
        rafSpy.mockRestore();
    });

    it('ignores stale async results when the same chunk index is reloaded', async () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        let resolveFirst;
        let resolveSecond;
        const renderChunk = vi.fn((i) => new Promise((resolve) => {
            if (!resolveFirst) {
                resolveFirst = () => {
                    const el = document.createElement('div');
                    el.className = 'old-chunk';
                    el.textContent = `old-${i}`;
                    resolve(el);
                };
            } else {
                resolveSecond = () => {
                    const el = document.createElement('div');
                    el.className = 'new-chunk';
                    el.textContent = `new-${i}`;
                    resolve(el);
                };
            }
        }));

        const vs = new VirtualScroller({
            totalItems: () => 1,
            chunkSize: 1,
            maxChunks: 1,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk,
        });

        vs.mount(host);

        const firstLoad = vs._loadChunk(0);
        vs._evictChunk(0);
        const secondLoad = vs._loadChunk(0);

        resolveFirst();
        await firstLoad;
        expect(chunkParent.querySelector('.old-chunk')).toBeNull();

        resolveSecond();
        await secondLoad;
        expect(chunkParent.querySelector('.new-chunk')).not.toBeNull();
        expect(chunkParent.querySelector('.old-chunk')).toBeNull();
        expect(chunkParent.querySelectorAll('[data-vs-chunk="0"]')).toHaveLength(1);

        vs.unmount();
        rafSpy.mockRestore();
    });

    it('clears the loading shell when the current async load resolves null', async () => {
        const host = makeHost('vs-host');
        const chunkParent = makeHost('chunk-parent');
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const vs = new VirtualScroller({
            totalItems: () => 1,
            chunkSize: 1,
            maxChunks: 1,
            initialChunks: 0,
            chunkContainer: chunkParent,
            renderChunk: () => Promise.resolve(null),
        });

        vs.mount(host);

        await vs._loadChunk(0);

        expect(vs.getVisibleChunks().size).toBe(0);
        expect(chunkParent.querySelectorAll('[data-vs-chunk="0"]')).toHaveLength(0);

        vs.unmount();
        rafSpy.mockRestore();
    });

    it('propagates async parent loads to infinite scroll so eviction waits for commit', async () => {
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

        const host = makeHost('vs-host');
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        let resolveChunkThree;
        const vs = new VirtualScroller({
            totalItems: () => 10,
            chunkSize: 1,
            maxChunks: 3,
            initialChunks: 3,
            renderChunk: (i) => {
                if (i < 3) {
                    const el = document.createElement('div');
                    el.textContent = `chunk-${i}`;
                    return el;
                }
                return new Promise((resolve) => {
                    resolveChunkThree = () => {
                        const el = document.createElement('div');
                        el.textContent = `chunk-${i}`;
                        resolve(el);
                    };
                });
            },
        });

        vs.mount(host);

        const observerCallback = callbacks[0];
        observerCallback([{ target: vs.refs.bottomSentinel, isIntersecting: true }]);

        expect(vs.getVisibleChunks()).toEqual(new Set([0, 1, 2, 3]));

        resolveChunkThree();
        await new Promise((resolve) => setTimeout(resolve, 0));

        expect(vs.getVisibleChunks()).toEqual(new Set([1, 2, 3]));

        vs.unmount();
        rafSpy.mockRestore();
    });

    it('keeps sentinels flanking the live chunk instead of adjacent placeholders', () => {
        const host = makeHost('vs-host');
        const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
            cb();
            return 1;
        });
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

        const vs = new VirtualScroller({
            totalItems: () => 30,
            chunkSize: 1,
            maxChunks: 3,
            initialChunks: 0,
            renderChunk: () => document.createElement('div'),
        });

        vs.mount(host);

        const leadingPlaceholder = document.createElement('div');
        leadingPlaceholder.dataset.vsPlaceholderStart = '0';
        leadingPlaceholder.dataset.vsPlaceholderEnd = '9';

        const liveChunk = document.createElement('div');
        liveChunk.dataset.vsChunk = '10';

        const trailingPlaceholder = document.createElement('div');
        trailingPlaceholder.dataset.vsPlaceholderStart = '11';
        trailingPlaceholder.dataset.vsPlaceholderEnd = '20';

        vs.element.insertBefore(leadingPlaceholder, vs.refs.topSentinel);
        vs.element.insertBefore(liveChunk, vs.refs.bottomSentinel);
        vs.element.insertBefore(trailingPlaceholder, vs.refs.bottomSentinel);
        vs._visibleChunks.add(10);

        vs.reset();

        expect(Array.from(vs.element.children)).toEqual([
            leadingPlaceholder,
            vs.refs.topSentinel,
            liveChunk,
            vs.refs.bottomSentinel,
            trailingPlaceholder,
        ]);

        vs.unmount();
        rafSpy.mockRestore();
    });
});
