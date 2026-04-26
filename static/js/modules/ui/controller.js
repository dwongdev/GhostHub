/**
 * UI Controller Module
 * Handles UI-related functionality like controls and indicators
 */

import {
    initConfigModal,
    openConfigModal as importedOpenConfigModal,
    initTunnelModal,
    openTunnelModal as importedOpenTunnelModal
} from '../config/index.js';
import { openFileManager as importedOpenFileManager } from '../admin/files.js';
import { Module, createElement, css, $, $$ } from '../../libs/ragot.esm.min.js';
import { getAppState, setAppState } from '../../utils/appStateUtils.js';
import { setupLayoutNavigation, cleanupLayoutNavigation } from '../../utils/layoutUtils.js';
let uiControllerLifecycle = null;

function requireAppState() {
    const appState = getAppState();
    if (!appState) throw new Error('[uiController] appState service is not registered');
    return appState;
}

function requireMediaViewer() {
    const mediaViewer = window.ragotModules?.appDom?.mediaViewer;
    if (!mediaViewer) throw new Error('[uiController] appDom.mediaViewer is not registered');
    return mediaViewer;
}

function isMobileDevice() {
    return Boolean(window.ragotModules?.appRuntime?.MOBILE_DEVICE);
}

class UIControllerLifecycle extends Module {
    onStart() {
        initConfigModal();
        initTunnelModal();

        const configBtn = $('#config-toggle-btn');
        const tunnelBtn = $('#tunnel-toggle-btn');
        if (configBtn) this.on(configBtn, 'click', openConfigModal);
        if (tunnelBtn) this.on(tunnelBtn, 'click', openTunnelModal);
    }
}

function attachScopedUiListener(target, type, handler, options) {
    if (!target) return;
    if (!uiControllerLifecycle) {
        uiControllerLifecycle = new UIControllerLifecycle();
        uiControllerLifecycle.start();
    }
    uiControllerLifecycle.on(target, type, handler, options);
}

/**
 * Setup controls for media viewing - with mobile-specific handling
 */
export function setupControls() {
    try {
        const appState = requireAppState();
        const mediaViewer = requireMediaViewer();

        // Idempotency check: don't add duplicate wrappers
        if (appState.controlsContainer && mediaViewer.contains(appState.controlsContainer)) {
            console.log("[UIController] Controls wrapper already exists, skipping creation");
            return;
        }

        // Create a wrapper for easier removal
        appState.controlsContainer = createElement('div', {
            className: 'controls-wrapper',
            style: { position: 'absolute', top: '0', left: '0', width: '100%', height: '100%', pointerEvents: 'none', zIndex: '100' }
        });

        // ... (rest of the logic for back button etc remains similar but avoid re-cloning if possible)
        const backButton = $('#permanent-gh-back-btn');
        if (backButton) {
            backButton.style.display = 'flex';

            // Re-setup handlers to ensure they use latest context
            const newBackButton = backButton.cloneNode(true);
            if (backButton.parentNode) {
                backButton.parentNode.replaceChild(newBackButton, backButton);
            }

            if (isMobileDevice()) {
                let backButtonOverlay = $('#mobile-back-overlay');
                if (!backButtonOverlay) {
                    backButtonOverlay = createElement('div', {
                        id: 'mobile-back-overlay',
                        style: { position: 'fixed', top: '0', left: '0', width: '120px', height: '120px', zIndex: '10000000', backgroundColor: 'transparent', pointerEvents: 'auto', display: 'none' }
                    });
                    attachScopedUiListener(backButtonOverlay, 'touchstart', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        window.ragotModules?.mediaNavigation?.goBackToCategories?.();
                    }, { passive: false });
                    document.body.appendChild(backButtonOverlay);
                }
                if (!mediaViewer.classList.contains('hidden')) {
                    backButtonOverlay.style.display = 'block';
                }
            }

            attachScopedUiListener(newBackButton, 'click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                window.ragotModules?.mediaNavigation?.goBackToCategories?.();
            });
        }

        mediaViewer.appendChild(appState.controlsContainer);
    } catch (controlsError) {
        console.error("!!! Error inside setupControls:", controlsError);
    }
}

/**
 * Show or hide the loading spinner
 * @param {boolean} show - Whether to show or hide the spinner
 */
export function toggleSpinner(show) {
    // Try both the global spinner and any viewer-specific spinners
    const spinners = $$('.spinner-container');
    spinners.forEach(spinner => {
        spinner.style.display = show ? 'flex' : 'none';
        if (show) {
            spinner.style.opacity = '1';
            spinner.style.visibility = 'visible';
        }
    });

    if (show) {
        console.log('[UIController] Spinner toggled ON');
    }
}

/**
 * Disable navigation controls for guests in sync mode
 * Modified to allow chat interaction and video tapping while preventing swipe navigation
 */
function disableNavigationControls() {
    // Set a flag in app state to indicate that navigation should be disabled
    setAppState('navigationDisabled', true);

    // Create an overlay that covers only the media area to prevent direct swipes
    const mediaOverlay = createElement('div', {
        id: 'media-navigation-overlay',
        style: { position: 'absolute', top: '0', left: '0', width: '100%', height: '100%', zIndex: '999', backgroundColor: 'transparent', pointerEvents: 'none' }
    });

    // Add the overlay to the media viewer only (not covering chat)
    const mediaViewer = $('#media-viewer');
    if (mediaViewer) {
        mediaViewer.appendChild(mediaOverlay); // Append the overlay to media-viewer
    }

    // Cleanup layout-specific navigation
    cleanupLayoutNavigation();

    console.log('Navigation controls disabled for guest in sync mode - swipe navigation prevented, tapping allowed');
}

/**
 * Re-enable navigation controls when sync mode is disabled
 */
function enableNavigationControls() {
    // Clear the navigation disabled flag
    setAppState('navigationDisabled', false);

    // Re-setup layout-specific navigation
    setupLayoutNavigation();

    // Re-setup the controls (including the back button)
    setupControls();

    // Remove the media overlay
    const mediaOverlay = $('#media-navigation-overlay');
    if (mediaOverlay) {
        mediaOverlay.remove();
    }

    // Remove the guest message
    const message = $('#guest-message');
    if (message) {
        message.remove();
    }

    console.log('Navigation controls re-enabled - swipe navigation allowed');
}



// Re-export openConfigModal so other modules can access it via uiController if needed
const openConfigModal = importedOpenConfigModal;
const openTunnelModal = importedOpenTunnelModal;
const openFileManager = importedOpenFileManager;

function initUIController() {
    if (!uiControllerLifecycle) {
        uiControllerLifecycle = new UIControllerLifecycle();
    }
    uiControllerLifecycle.start();
}

function cleanupUIController() {
    if (uiControllerLifecycle) {
        uiControllerLifecycle.stop();
        uiControllerLifecycle = null;
    }
}

export {
    initUIController,
    cleanupUIController,
    disableNavigationControls,
    enableNavigationControls,
    openConfigModal,
    openTunnelModal,
    openFileManager,
    updateSyncToggleButton
};

/**
 * Update sync toggle button appearance
 */
function updateSyncToggleButton() {
    const appState = requireAppState();
    const syncToggleBtn = $('#sync-toggle-btn');
    if (!syncToggleBtn) return;

    let buttonText = 'Sync';

    if (appState.syncModeEnabled) {
        buttonText = appState.isHost ? 'Stop Host' : 'Leave Sync';
        syncToggleBtn.classList.add('active');
    } else {
        syncToggleBtn.classList.remove('active');
    }

    syncToggleBtn.textContent = buttonText;
}
