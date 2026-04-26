/**
 * Fullscreen Manager Module
 * Handles fullscreen functionality for videos across different browsers
 */

import { fullscreenIcon } from '../../utils/icons.js';
import { Module, $, $$ } from '../../libs/ragot.esm.min.js';

// Detect iOS device
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

// Cross-browser fullscreen API methods
function getFullscreenAPI(element) {
    // Return the appropriate fullscreen API methods based on browser support
    const apis = {
        requestFullscreen: element.requestFullscreen ||
            element.webkitRequestFullscreen ||
            element.mozRequestFullScreen ||
            element.msRequestFullscreen,
        exitFullscreen: document.exitFullscreen ||
            document.webkitExitFullscreen ||
            document.mozCancelFullScreen ||
            document.msExitFullscreen,
        fullscreenElement: document.fullscreenElement ||
            document.webkitFullscreenElement ||
            document.mozFullScreenElement ||
            document.msFullscreenElement,
        fullscreenEnabled: document.fullscreenEnabled ||
            document.webkitFullscreenEnabled ||
            document.mozFullScreenEnabled ||
            document.msFullscreenEnabled,
        fullscreenchange: 'fullscreenchange',
        fullscreenerror: 'fullscreenerror'
    };

    // Set the correct event names based on browser
    if (element.webkitRequestFullscreen) {
        apis.fullscreenchange = 'webkitfullscreenchange';
        apis.fullscreenerror = 'webkitfullscreenerror';
    } else if (element.mozRequestFullScreen) {
        apis.fullscreenchange = 'mozfullscreenchange';
        apis.fullscreenerror = 'mozfullscreenerror';
    } else if (element.msRequestFullscreen) {
        apis.fullscreenchange = 'MSFullscreenChange';
        apis.fullscreenerror = 'MSFullscreenError';
    }

    return apis;
}

let fullscreenLifecycle = null;
let fullscreenExitedRecently = false;

class FullscreenLifecycle extends Module {
    constructor() {
        super();
        this.onFullscreenChange = this.onFullscreenChange.bind(this);
        this.fullscreenEvent = 'fullscreenchange';
    }

    onStart() {
        const fullscreenAPI = getFullscreenAPI(document.documentElement);
        this.fullscreenEvent = fullscreenAPI.fullscreenchange || 'fullscreenchange';
        this.on(document, this.fullscreenEvent, this.onFullscreenChange);
    }

    onFullscreenChange() {
        const fullscreenAPI = getFullscreenAPI(document.documentElement);
        const isFullscreen = !!document[fullscreenAPI.fullscreenElement];
        console.log(`Fullscreen state changed: ${isFullscreen ? 'entered' : 'exited'}`);

        const fullscreenBtns = $$('.fullscreen-btn');
        fullscreenBtns.forEach(btn => {
            btn.classList.toggle('active', isFullscreen);
        });

        if (isFullscreen) {
            ensureChatVisibilityInFullscreen();
        } else {
            document.documentElement.classList.remove('is-fullscreen');

            const chatContainer = $('#chat-container');
            if (chatContainer) {
                chatContainer.style.zIndex = '';
                this.timeout(() => {
                    fullscreenExitedRecently = true;
                    this.timeout(() => {
                        fullscreenExitedRecently = false;
                    }, 1000);
                }, 100);
            }
        }
    }
}

// Toggle fullscreen for a video element
function toggleFullscreen(videoElement) {
    // Get chat container reference
    const chatContainer = $('#chat-container');
    const isVideo = videoElement && videoElement.tagName === 'VIDEO';

    // Special handling for iOS
    if (isIOS && isVideo) {
        // For iOS, we need to use the webkitEnterFullscreen API
        // Check for webkitEnterFullscreen function instead of webkitSupportsFullscreen
        // because the function exists even when webkitSupportsFullscreen returns false
        if (typeof videoElement.webkitEnterFullscreen === 'function') {
            if (!videoElement.webkitDisplayingFullscreen) {
                // Temporarily remove playsinline attribute for iOS fullscreen
                videoElement.removeAttribute('playsinline');
                videoElement.removeAttribute('webkit-playsinline');

                // Request fullscreen
                videoElement.webkitEnterFullscreen();

                // Play the video (iOS requires playback to be initiated by user action)
                videoElement.play().catch(e => console.error("iOS play failed:", e));
            } else {
                // Exit fullscreen
                videoElement.webkitExitFullscreen();

                // Restore playsinline attribute
                videoElement.setAttribute('playsinline', 'true');
                videoElement.setAttribute('webkit-playsinline', 'true');
            }
        } else {
            console.warn("iOS fullscreen not supported for this video");

            // Fallback: try standard fullscreen API
            tryStandardFullscreen(videoElement);
        }
    } else {
        // Standard fullscreen for non-iOS devices
        tryStandardFullscreen(videoElement);
    }
}

// Try standard fullscreen API
function tryStandardFullscreen(videoElement) {
    const fullscreenAPI = getFullscreenAPI(videoElement);

    if (!document[fullscreenAPI.fullscreenElement]) {
        // Enter fullscreen
        videoElement[fullscreenAPI.requestFullscreen]()
            .then(() => {
                // Ensure chat container remains visible in fullscreen
                ensureChatVisibilityInFullscreen();
            })
            .catch(err => {
                console.error(`Error attempting to enable fullscreen: ${err.message}`);
            });
    } else {
        // Exit fullscreen
        document[fullscreenAPI.exitFullscreen]();
    }
}

// Ensure chat container remains visible in fullscreen
function ensureChatVisibilityInFullscreen() {
    // Get chat container reference
    const chatContainer = $('#chat-container');
    if (!chatContainer) return;

    // Add a class to indicate fullscreen mode
    document.documentElement.classList.add('is-fullscreen');

    // Make sure chat is visible above fullscreen content
    chatContainer.style.zIndex = '9999';
}

// Add fullscreen button to video
function addFullscreenButton(mediaElement) {
    // Redundant - fullscreen button is now handled by videoControls overlay
}

// Helper function to actually add the fullscreen button to a video element
function addFullscreenButtonToElement(mediaElement) {
    // Redundant - fullscreen button is now handled by videoControls overlay
}

// Handle fullscreen change events
function setupFullscreenChangeListener() {
    if (!fullscreenLifecycle) {
        fullscreenLifecycle = new FullscreenLifecycle();
    }
    fullscreenLifecycle.start();
}

function cleanupFullscreenChangeListener() {
    if (fullscreenLifecycle) {
        fullscreenLifecycle.stop();
        fullscreenLifecycle = null;
    }
}

// Add a function to check if we're in a safe state to toggle fullscreen
function isSafeToToggleFullscreen() {
    // If we've just exited fullscreen, prevent immediate re-entry
    if (fullscreenExitedRecently) {
        console.log('Preventing immediate fullscreen re-entry after exit');
        return false;
    }

    // Check if we're currently in the middle of a rapid navigation
    const appState = window.ragotModules?.appState;
    if (appState) {
        const now = Date.now();
        const lastNavTime = appState.lastNavigationTime || 0;

        // If we've navigated within the last 300ms, consider it unsafe
        if (now - lastNavTime < 300) {
            console.log('Preventing fullscreen during rapid navigation');
            return false;
        }
    }

    // Check if the document is in a state where fullscreen is allowed
    const fullscreenAPI = getFullscreenAPI(document.documentElement);
    if (!document[fullscreenAPI.fullscreenEnabled]) {
        console.log('Fullscreen not enabled in document');
        return false;
    }

    return true;
}

// Function to ensure fullscreen buttons are added to all active videos
// This can be called periodically to ensure buttons are present
function ensureFullscreenButtons() {
    const activeVideos = $$('video.active');
    activeVideos.forEach(video => {
        // Check if this video already has a fullscreen button
        const hasButton = video.parentElement &&
            $('.fullscreen-btn', video.parentElement);

        if (!hasButton) {
            console.log('Adding missing fullscreen button to active video');
            addFullscreenButton(video);
        }
    });
}

function hasRecentFullscreenExit() {
    return fullscreenExitedRecently;
}

export {
    toggleFullscreen,
    addFullscreenButton,
    setupFullscreenChangeListener,
    cleanupFullscreenChangeListener,
    isSafeToToggleFullscreen,
    ensureFullscreenButtons,
    hasRecentFullscreenExit
};
