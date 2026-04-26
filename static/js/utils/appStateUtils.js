/**
 * App state mutation helpers.
 *
 * Thin wrappers over `window.ragotModules.appStore` — the canonical RAGOT
 * StateStore for all app-level state. Use these instead of accessing the store
 * directly so call sites stay decoupled from the registry lookup.
 *
 * State mutations go through `appStore.actions.*` (registered in app.js) so
 * every write carries source-tagged metadata automatically.
 */
import { createSelector } from '../libs/ragot.esm.min.js';

function getAppStore() {
    return window.ragotModules?.appStore;
}

/**
 * Get the live proxied app state object.
 * @returns {Object}
 */
export function getAppState() {
    return getAppStore()?.getState() ?? {};
}

/**
 * Read a single app state value via dot-path.
 * @param {string} path
 * @param {*} [fallback]
 * @returns {*}
 */
export function getAppStateValue(path, fallback = undefined) {
    return getAppStore()?.get(path, fallback) ?? fallback;
}

/**
 * Set a single app state field.
 * Routes through `appStore.actions.setField` so the write is source-tagged.
 * @param {string} key
 * @param {*} value
 */
export function setAppState(key, value) {
    getAppStore()?.actions.setField(key, value);
}

/**
 * Shallow-merge a partial object into app state.
 * Routes through `appStore.actions.patchState`.
 * @param {Object} partial
 */
export function patchAppState(partial) {
    getAppStore()?.actions.patchState(partial);
}

/**
 * Run a transactional batch mutation against app state.
 * Routes through `appStore.actions.batchState`.
 * @param {Function} mutator - receives (stateProxy, store)
 */
export function batchAppState(mutator) {
    getAppStore()?.actions.batchState(mutator);
}

/**
 * Subscribe to app state updates.
 * @param {Function} subscriber
 * @param {Object} [options]
 * @returns {Function} unsubscribe
 */
export function watchAppState(subscriber, options = {}) {
    return getAppStore()?.subscribe(subscriber, options) ?? (() => {});
}

/**
 * Create a memoized selector for app state usage.
 * @param {Function[]} inputSelectors
 * @param {Function} resultFunc
 * @returns {Function}
 */
export function createAppSelector(inputSelectors, resultFunc) {
    return createSelector(inputSelectors, resultFunc);
}
