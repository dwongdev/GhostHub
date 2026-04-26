import { Module, $ } from '../../../libs/ragot.esm.min.js';
import { APP_EVENTS } from '../../../core/appEvents.js';
import { toggleSpinner } from '../../ui/controller.js';

/**
 * Creates a reusable layout-change lifecycle owner.
 * The returned ensure function starts exactly one Module instance and wires
 * bus-level layout-change behavior for the given layout key.
 *
 * @param {Object} options
 * @param {string} options.layoutName
 * @param {Function} options.initLayout
 * @param {Function} options.cleanupLayout
 * @param {Function} [options.shouldInit]
 * @returns {Function}
 */
export function createLayoutChangeLifecycle({
    layoutName,
    initLayout,
    cleanupLayout,
    shouldInit = () => !!window.ragotModules?.appStore?.get?.('config', {})?.python_config
}) {
    let lifecycle = null;

    function restoreViewerIfNeeded() {
        const mediaViewer = $('#media-viewer');
        if (!mediaViewer || mediaViewer.classList.contains('hidden')) return;

        mediaViewer.classList.remove('hidden');
        toggleSpinner(false);
    }

    return function ensureLayoutLifecycle() {
        if (lifecycle) return lifecycle;

        lifecycle = new Module();
        lifecycle.start();
        lifecycle.listen(APP_EVENTS.LAYOUT_CHANGED, async (detail) => {
            if (detail?.layout === layoutName) {
                if (shouldInit()) {
                    await initLayout();
                }
            } else {
                cleanupLayout();
            }

            restoreViewerIfNeeded();
        });

        return lifecycle;
    };
}
