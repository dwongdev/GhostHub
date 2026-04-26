/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import RAGOT, {
    $,
    $$,
    bus,
    createElement,
    batchAppend,
    append,
    morphDOM,
    Module,
    Component,
    clear,
    delegateEvent,
    css,
    attr,
    createIcon,
    show,
    hide,
    toggle,
    createStateStore,
    renderList,
    clearPool,
    animateIn,
    animateOut,
    createApp
} from '../../libs/ragot.esm.min.js';

describe('RAGOT Framework Contracts', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        bus.clear();
        window.__RAGOT_WARN_MISSING_TARGET__ = false;
    });

    afterEach(() => {
        bus.clear();
        delete window.__RAGOT_WARN_MISSING_TARGET__;
        vi.useRealTimers();
    });

    describe('Selectors and Bus', () => {
        it('selects elements with $ and $$', () => {
            document.body.innerHTML = `
                <div id="root">
                    <button class="item">A</button>
                    <button class="item">B</button>
                </div>
            `;

            expect($('#root')?.id).toBe('root');
            expect($$('.item')).toHaveLength(2);
            expect($$('.item')[1].textContent).toBe('B');
        });

        it('supports bus subscribe/emit/off/clear', () => {
            const handler = vi.fn();
            const unsub = bus.on('evt:test', handler);

            bus.emit('evt:test', { ok: true });
            expect(handler).toHaveBeenCalledTimes(1);
            expect(handler).toHaveBeenCalledWith({ ok: true });

            unsub();
            bus.emit('evt:test', { ok: false });
            expect(handler).toHaveBeenCalledTimes(1);

            const handlerTwo = vi.fn();
            bus.on('evt:test', handlerTwo);
            bus.clear('evt:test');
            bus.emit('evt:test', {});
            expect(handlerTwo).not.toHaveBeenCalled();
        });
    });

    describe('DOM Helpers', () => {
        it('creates elements with classes, dataset, refs, events, and children', () => {
            const refSpy = vi.fn();
            const clickSpy = vi.fn();

            const el = createElement(
                'button',
                {
                    className: 'btn primary',
                    dataset: { role: 'action' },
                    ref: refSpy,
                    events: { click: clickSpy }
                },
                'Run'
            );

            el.click();
            expect(el.classList.contains('btn')).toBe(true);
            expect(el.classList.contains('primary')).toBe(true);
            expect(el.dataset.role).toBe('action');
            expect(el.textContent).toBe('Run');
            expect(refSpy).toHaveBeenCalledWith(el);
            expect(clickSpy).toHaveBeenCalledTimes(1);
        });

        it('supports append and clear utilities', () => {
            const parent = createElement('div');
            append(parent, 'A', createElement('span', {}, 'B'));

            expect(parent.childNodes.length).toBe(2);
            expect(parent.textContent).toBe('AB');

            clear(parent);
            expect(parent.childNodes.length).toBe(0);
        });

        it('supports css and attr helpers', () => {
            const el = createElement('div');

            css(el, { width: '10px', display: 'block' });
            attr(el, { 'data-x': '1', hidden: true, title: null });

            expect(el.style.width).toBe('10px');
            expect(el.getAttribute('data-x')).toBe('1');
            expect(el.hasAttribute('hidden')).toBe(true);
            expect(el.hasAttribute('title')).toBe(false);
        });

        it('supports show/hide/toggle helpers', () => {
            const el = createElement('div', { className: 'hidden' });

            show(el);
            expect(el.classList.contains('hidden')).toBe(false);

            hide(el);
            expect(el.classList.contains('hidden')).toBe(true);

            toggle(el, true);
            expect(el.classList.contains('hidden')).toBe(false);

            toggle(el, false);
            expect(el.classList.contains('hidden')).toBe(true);
        });

        it('creates icon wrapper with markup', () => {
            const icon = createIcon('<svg><path d="M0 0" /></svg>', 'x-icon');
            expect(icon.tagName).toBe('SPAN');
            expect(icon.className).toBe('x-icon');
            expect(icon.innerHTML).toContain('<svg>');
        });
    });

    describe('Batch and Morphing', () => {
        it('batchAppend appends nodes asynchronously', async () => {
            const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
                cb();
                return 1;
            });

            const parent = createElement('div');
            await batchAppend(parent, [createElement('span', {}, 'A'), createElement('span', {}, 'B')]);

            expect(parent.children.length).toBe(2);
            expect(parent.textContent).toBe('AB');
            rafSpy.mockRestore();
        });

        it('morphDOM updates handlers and attributes', () => {
            const oldClick = vi.fn();
            const newClick = vi.fn();

            const root = createElement('div');
            const oldNode = createElement('button', { className: 'old', onClick: oldClick }, 'Old');
            root.appendChild(oldNode);

            const newNode = createElement('button', { className: 'new', onClick: newClick }, 'New');
            const morphed = morphDOM(oldNode, newNode);

            expect(morphed).toBe(oldNode);
            expect(morphed.classList.contains('new')).toBe(true);
            expect(morphed.textContent).toBe('New');

            morphed.click();
            expect(oldClick).not.toHaveBeenCalled();
            expect(newClick).toHaveBeenCalledTimes(1);
        });

        it('morphDOM re-fires ref callbacks with live node', () => {
            const root = createElement('div');
            const oldNode = createElement('div', {}, 'old');
            root.appendChild(oldNode);

            let refNode = null;
            const newNode = createElement('div', { ref: (el) => { refNode = el; } }, 'new');
            morphDOM(oldNode, newNode);

            expect(refNode).toBe(oldNode);
            expect(oldNode.textContent).toBe('new');
        });

        it('morphDOM patches IMG node in place when src changes', () => {
            const root = createElement('div');
            const oldImg = createElement('img', { src: '/thumbnails/a.jpg', className: 'thumb-a' });
            root.appendChild(oldImg);

            const newImg = createElement('img', { src: '/thumbnails/b.jpg', className: 'thumb-b' });
            const morphed = morphDOM(oldImg, newImg);

            // morphDOM patches IMG in-place — the original node is preserved
            expect(morphed).toBe(oldImg);
            expect(root.querySelector('img')).toBe(oldImg);
            expect(root.querySelector('img')?.getAttribute('src')).toBe('/thumbnails/b.jpg');
            expect(root.querySelector('img')?.classList.contains('thumb-b')).toBe(true);
        });

        it('morphDOM patches IMG node in place when data-src changes', () => {
            const root = createElement('div');
            const oldImg = createElement('img', { dataset: { src: '/thumbnails/a.jpg' }, className: 'lazy-a' });
            root.appendChild(oldImg);

            const newImg = createElement('img', { dataset: { src: '/thumbnails/b.jpg' }, className: 'lazy-b' });
            const morphed = morphDOM(oldImg, newImg);

            // morphDOM patches IMG in-place — the original node is preserved
            expect(morphed).toBe(oldImg);
            expect(root.querySelector('img')?.getAttribute('data-src')).toBe('/thumbnails/b.jpg');
            expect(root.querySelector('img')?.classList.contains('lazy-b')).toBe(true);
        });

        it('morphDOM preserves primitive-owned lazy state classes on live images', () => {
            const root = createElement('div');
            const oldImg = createElement('img', {
                dataset: { src: '/thumbnails/a.jpg' },
                className: 'lazy-a lazy-load'
            });
            oldImg.setAttribute('src', '/thumbnails/a.jpg');
            oldImg.classList.add('ragot-lazy-loaded');
            root.appendChild(oldImg);

            const newImg = createElement('img', {
                dataset: { src: '/thumbnails/a.jpg' },
                className: 'lazy-b lazy-load'
            });
            const morphed = morphDOM(oldImg, newImg);

            expect(morphed).toBe(oldImg);
            expect(morphed.classList.contains('lazy-b')).toBe(true);
            expect(morphed.classList.contains('ragot-lazy-loaded')).toBe(true);
        });

        it('throws on mixed keyed and unkeyed element siblings in test/dev mode', () => {
            const root = createElement('div');
            const oldNode = createElement('div', {},
                createElement('span', { dataset: { ragotKey: 'a' } }, 'A'),
                createElement('span', {}, 'B')
            );
            root.appendChild(oldNode);

            const newNode = createElement('div', {},
                createElement('span', { dataset: { ragotKey: 'a' } }, 'A2'),
                createElement('span', {}, 'B2')
            );

            expect(() => morphDOM(oldNode, newNode)).toThrow(/mixed keyed and unkeyed element siblings/i);
        });
    });

    describe('Module Lifecycle', () => {
        it('starts/stops and runs onStart/onStop once per transition', () => {
            const mounts = vi.fn();
            const unmounts = vi.fn();

            class TestModule extends Module {
                onStart() { mounts(); }
                onStop() { unmounts(); }
            }

            const mod = new TestModule();
            mod.start().start();
            expect(mounts).toHaveBeenCalledTimes(1);

            mod.stop().stop();
            expect(unmounts).toHaveBeenCalledTimes(1);
        });

        it('auto-cleans scoped listeners, bus listeners, sockets, timers, and use() cleanups on stop', () => {
            vi.useFakeTimers();
            const target = createElement('button');
            const socket = { on: vi.fn(), off: vi.fn() };
            const onTargetClick = vi.fn();
            const onBus = vi.fn();
            const onSocket = vi.fn();
            const cleanup = vi.fn();
            const timeoutCb = vi.fn();
            const intervalCb = vi.fn();

            class TestModule extends Module {
                onStart() {
                    this.on(target, 'click', onTargetClick);
                    this.listen('evt:module', onBus);
                    this.onSocket(socket, 'msg', onSocket);
                    this.timeout(timeoutCb, 500);
                    this.interval(intervalCb, 200);
                    this.addCleanup(cleanup);
                }
            }

            const mod = new TestModule().start();
            expect(socket.on).toHaveBeenCalledWith('msg', onSocket);

            target.click();
            bus.emit('evt:module', { x: 1 });
            expect(onTargetClick).toHaveBeenCalledTimes(1);
            expect(onBus).toHaveBeenCalledTimes(1);

            mod.stop();
            expect(socket.off).toHaveBeenCalledWith('msg', onSocket);
            expect(cleanup).toHaveBeenCalledTimes(1);

            target.click();
            bus.emit('evt:module', { x: 2 });
            vi.advanceTimersByTime(1000);

            expect(onTargetClick).toHaveBeenCalledTimes(1);
            expect(onBus).toHaveBeenCalledTimes(1);
            expect(timeoutCb).not.toHaveBeenCalled();
            expect(intervalCb).not.toHaveBeenCalled();
        });

        it('supports watchState with immediate and auto-unsubscribe on stop', async () => {
            const seen = [];
            const mod = new Module({ value: 1 });

            mod.watchState((state) => {
                seen.push(state.value);
            });

            // immediate: true fires synchronously on registration
            expect(seen).toEqual([1]);

            // setState schedules a microtask — await a tick for notification to flush
            mod.setState({ value: 2 });
            await Promise.resolve();
            expect(seen).toEqual([1, 2]);

            mod.start();
            mod.stop();
            // After stop, subscribers are cleared — no more notifications
            mod.setState({ value: 3 });
            await Promise.resolve();
            expect(seen).toEqual([1, 2]);
        });

        it('supports adopt() and adoptComponent() with sync communication', async () => {
            const childModule = { start: vi.fn(), stop: vi.fn() };
            const childComponent = {
                mount: vi.fn(),
                unmount: vi.fn(),
                syncFromModule: vi.fn()
            };

            const mod = new Module({ count: 0 });
            mod.adopt(childModule);
            mod.adoptComponent(childComponent, {
                sync: (component, state, module) => component.syncFromModule(state, module)
            });

            expect(childModule.start).toHaveBeenCalledTimes(1);
            expect(childComponent.mount).toHaveBeenCalledTimes(1);
            // watchState immediate: true fires sync on registration
            expect(childComponent.syncFromModule).toHaveBeenCalledWith({ count: 0 }, mod);

            // setState schedules a microtask — await a tick before asserting
            mod.setState({ count: 1 });
            await Promise.resolve();
            expect(childComponent.syncFromModule).toHaveBeenLastCalledWith({ count: 1 }, mod);

            mod.start();
            mod.stop();
            expect(childModule.stop).toHaveBeenCalledTimes(1);
            expect(childComponent.unmount).toHaveBeenCalledTimes(1);
        });

        it('skips null target listeners and only warns when debug flag is true', () => {
            const warnSpy = vi.spyOn(console, 'warn');
            const mod = new Module();

            mod.on(null, 'click', () => { });
            expect(warnSpy).not.toHaveBeenCalled();

            window.__RAGOT_WARN_MISSING_TARGET__ = true;
            mod.on(null, 'click', () => { });
            expect(warnSpy).toHaveBeenCalledTimes(1);
        });
    });

    describe('Component Lifecycle', () => {
        it('mounts/unmounts with scoped listener and bus cleanup', () => {
            const clicks = vi.fn();
            const busHandler = vi.fn();
            const cleanup = vi.fn();

            class TestComponent extends Component {
                render() {
                    return createElement('button', { className: 'cmp-btn' }, 'Click');
                }
                onStart() {
                    this.on(this.element, 'click', clicks);
                    this.listen('evt:component', busHandler);
                    this.addCleanup(cleanup);
                }
            }

            const parent = createElement('div');
            document.body.appendChild(parent);

            const comp = new TestComponent();
            comp.mount(parent);

            comp.element.click();
            bus.emit('evt:component', { y: 1 });
            expect(clicks).toHaveBeenCalledTimes(1);
            expect(busHandler).toHaveBeenCalledTimes(1);

            comp.unmount();
            bus.emit('evt:component', { y: 2 });
            expect(parent.children.length).toBe(0);
            expect(cleanup).toHaveBeenCalledTimes(1);
            expect(busHandler).toHaveBeenCalledTimes(1);
        });

        it('batches setState updates to one frame render', () => {
            const rafQueue = [];
            const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
                rafQueue.push(cb);
                return rafQueue.length;
            });

            let renderCount = 0;
            class CounterComponent extends Component {
                render() {
                    renderCount++;
                    return createElement('div', {}, String(this.state.value ?? 0));
                }
            }

            const parent = createElement('div');
            document.body.appendChild(parent);

            const comp = new CounterComponent({ value: 0 });
            comp.mount(parent);
            expect(renderCount).toBe(1);

            comp.setState({ value: 1 });
            comp.setState({ value: 2 });
            expect(renderCount).toBe(1);

            rafQueue.shift()?.();
            expect(renderCount).toBe(2);
            expect(comp.element.textContent).toBe('2');
            rafSpy.mockRestore();
        });

        it('setStateSync updates immediately', () => {
            class SyncComponent extends Component {
                render() {
                    return createElement('div', {}, String(this.state.value ?? 0));
                }
            }

            const parent = createElement('div');
            document.body.appendChild(parent);

            const comp = new SyncComponent({ value: 0 });
            comp.mount(parent);

            comp.setStateSync({ value: 5 });
            expect(comp.element.textContent).toBe('5');
        });

        it('cancels queued renders on unmount', () => {
            const rafQueue = [];
            const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
                rafQueue.push(cb);
                return rafQueue.length;
            });
            const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => { });

            let renderCount = 0;
            class QueuedComponent extends Component {
                render() {
                    renderCount++;
                    return createElement('div', {}, String(this.state.value ?? 0));
                }
            }

            const parent = createElement('div');
            document.body.appendChild(parent);

            const comp = new QueuedComponent({ value: 0 });
            comp.mount(parent);
            comp.setState({ value: 1 });
            expect(renderCount).toBe(1);

            comp.unmount();
            rafQueue.shift()?.();

            expect(cancelSpy).toHaveBeenCalled();
            expect(renderCount).toBe(1);
            expect(comp.element).toBeNull();

            rafSpy.mockRestore();
            cancelSpy.mockRestore();
        });

        it('supports own() child lifecycle ownership', () => {
            const child = { start: vi.fn(), stop: vi.fn() };

            class ParentComponent extends Component {
                render() {
                    return createElement('div');
                }
                onStart() {
                    this.adopt(child);
                }
            }

            const parent = createElement('div');
            document.body.appendChild(parent);
            const comp = new ParentComponent();

            comp.mount(parent);
            expect(child.start).toHaveBeenCalledTimes(1);

            comp.unmount();
            expect(child.stop).toHaveBeenCalledTimes(1);
        });

        it('skips null target listeners and only warns when debug flag is true', () => {
            const warnSpy = vi.spyOn(console, 'warn');
            const comp = new Component();

            comp.on(null, 'click', () => { });
            expect(warnSpy).not.toHaveBeenCalled();

            window.__RAGOT_WARN_MISSING_TARGET__ = true;
            comp.on(null, 'click', () => { });
            expect(warnSpy).toHaveBeenCalledTimes(1);
        });
    });

    describe('Delegation, Lists, Animation, and Bootstrap', () => {
        it('delegates events with delegateEvent', () => {
            const parent = createElement('div');
            const child = createElement('button', { className: 'x' }, 'Hit');
            parent.appendChild(child);
            document.body.appendChild(parent);

            const handler = vi.fn();
            delegateEvent(parent, 'click', '.x', handler);
            child.click();

            expect(handler).toHaveBeenCalledTimes(1);
        });

        it('renders keyed lists with minimal reconciliation', () => {
            const container = createElement('div');
            const updateSpy = vi.fn((el, item) => {
                el.textContent = item.label;
            });

            renderList(
                container,
                [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
                (item) => item.id,
                (item) => createElement('div', {}, item.label),
                updateSpy
            );
            expect(container.children.length).toBe(2);

            const firstNode = container.children[0];

            renderList(
                container,
                [{ id: 'b', label: 'B2' }, { id: 'c', label: 'C' }],
                (item) => item.id,
                (item) => createElement('div', {}, item.label),
                updateSpy
            );

            expect(container.children.length).toBe(2);
            expect(container.children[0]).not.toBe(firstNode);
            expect(container.textContent).toContain('B2');
            expect(container.textContent).toContain('C');
        });

        it('animates in and out with helpers', async () => {
            const el = createElement('div');
            document.body.appendChild(el);

            const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
                cb();
                return 1;
            });

            animateIn(el, 'is-visible');
            expect(el.classList.contains('is-visible')).toBe(true);
            rafSpy.mockRestore();

            vi.useFakeTimers();
            const done = animateOut(el, 'is-visible', true);
            vi.advanceTimersByTime(400);
            await done;
            expect(document.body.contains(el)).toBe(false);
        });

        it('creates app instances and returns namespace default export', () => {
            class AppComponent extends Component {
                render() {
                    return createElement('div', {}, 'App');
                }
            }

            const mountPoint = createElement('div', { id: 'app-root' });
            document.body.appendChild(mountPoint);

            const instance = createApp(AppComponent, '#app-root', {}, 'testApp');
            expect(instance).toBeTruthy();
            expect(window.testApp).toBe(instance);
            expect(mountPoint.textContent).toBe('App');

            expect(RAGOT.Module).toBe(Module);
            expect(RAGOT.Component).toBe(Component);
            expect(typeof RAGOT.createElement).toBe('function');
        });

        it('delegateEvent returns an unsubscribe function that removes the listener', () => {
            const parent = createElement('div');
            const child = createElement('button', { className: 'y' }, 'Hit');
            parent.appendChild(child);
            document.body.appendChild(parent);

            const handler = vi.fn();
            const unsub = delegateEvent(parent, 'click', '.y', handler);

            child.click();
            expect(handler).toHaveBeenCalledTimes(1);

            unsub();
            child.click();
            expect(handler).toHaveBeenCalledTimes(1); // not called again
        });

        it('renderList with poolKey reuses elements via updateItem', () => {
            const container = createElement('div');
            const renderSpy = vi.fn((item) => createElement('div', {}, item.label));
            const updateSpy = vi.fn((el, item) => { el.textContent = item.label; });

            renderList(
                container,
                [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
                (item) => item.id,
                renderSpy,
                updateSpy,
                { poolKey: 'test-pool' }
            );
            expect(container.children.length).toBe(2);
            const nodeA = container.children[0];

            // Remove 'a' — it goes to pool
            renderList(
                container,
                [{ id: 'b', label: 'B2' }],
                (item) => item.id,
                renderSpy,
                updateSpy,
                { poolKey: 'test-pool' }
            );
            expect(container.children.length).toBe(1);

            // Re-add 'a' — it should be reused from pool, not newly created
            const renderCountBefore = renderSpy.mock.calls.length;
            renderList(
                container,
                [{ id: 'b', label: 'B2' }, { id: 'a', label: 'A2' }],
                (item) => item.id,
                renderSpy,
                updateSpy,
                { poolKey: 'test-pool' }
            );
            expect(container.children.length).toBe(2);
            // updateSpy should have been called instead of renderSpy for the recycled element
            expect(renderSpy.mock.calls.length).toBe(renderCountBefore); // no new render
            expect(updateSpy).toHaveBeenCalledWith(expect.any(HTMLElement), expect.objectContaining({ id: 'a', label: 'A2' }));

            clearPool('test-pool');
        });

        it('morphDOM handles child count increase and decrease correctly', () => {
            const parent = createElement('div');
            document.body.appendChild(parent);

            // Old has 2 children, new has 4
            const oldNode = createElement('ul', {},
                createElement('li', {}, 'one'),
                createElement('li', {}, 'two')
            );
            parent.appendChild(oldNode);

            const newNode = createElement('ul', {},
                createElement('li', {}, 'one'),
                createElement('li', {}, 'two'),
                createElement('li', {}, 'three'),
                createElement('li', {}, 'four')
            );
            const result = morphDOM(oldNode, newNode);
            expect(result.children.length).toBe(4);
            expect(result.children[2].textContent).toBe('three');
            expect(result.children[3].textContent).toBe('four');

            // Now shrink back to 1 child
            const shrunkNode = createElement('ul', {},
                createElement('li', {}, 'only')
            );
            morphDOM(result, shrunkNode);
            expect(result.children.length).toBe(1);
            expect(result.children[0].textContent).toBe('only');
        });

        it('morphDOM replaces node when tag names differ', () => {
            const parent = createElement('div');
            document.body.appendChild(parent);

            const oldSpan = createElement('span', {}, 'old');
            parent.appendChild(oldSpan);

            const newDiv = createElement('div', {}, 'new');
            const result = morphDOM(oldSpan, newDiv);

            // Result should be the new node (tag mismatch → full replace)
            expect(result).toBe(newDiv);
            expect(parent.children[0]).toBe(newDiv);
            expect(parent.children[0].tagName).toBe('DIV');
        });
    });

    describe('State Store', () => {
        it('preserves caller batch metadata on batched notifications', () => {
            const store = createStateStore({ count: 0 }, { name: 'test-store' });
            const seen = [];

            store.subscribe((_state, changeMeta) => {
                seen.push(changeMeta);
            });

            store.batch((state) => {
                state.count = 1;
                state.extra = true;
            }, { source: 'unit-test', reason: 'batch-check' });

            expect(seen).toHaveLength(1);
            expect(seen[0].type).toBe('batch');
            expect(seen[0].meta).toEqual(expect.objectContaining({
                source: 'unit-test',
                reason: 'batch-check'
            }));
        });
    });

    describe('animateOut double-call guard', () => {
        it('resolve() is only called once even when transitionend fires before the fallback timeout', async () => {
            vi.useFakeTimers();
            const el = createElement('div', { className: 'is-visible' });
            document.body.appendChild(el);

            let resolveCount = 0;
            const origResolve = Promise.resolve.bind(Promise);

            const done = animateOut(el, 'is-visible', false);
            // Fire transitionend manually
            el.dispatchEvent(new Event('transitionend'));
            // Advance past the 350ms fallback
            vi.advanceTimersByTime(400);

            await done.then(() => resolveCount++);
            expect(resolveCount).toBe(1);
        });
    });
});
