/**
 * Logger Utility
 * Provides debug logging that can be toggled via config.
 * In production, set DEBUG_MODE to false to silence all debug logs.
 */

import { getConfigValue } from './configManager.js';

// Cache the original console methods
const originalConsole = {
    log: console.log.bind(console),
    warn: console.warn.bind(console),
    error: console.error.bind(console),
    info: console.info.bind(console),
    debug: console.debug.bind(console)
};

// Check if debug mode is enabled
function isDebugEnabled() {
    // Check config first, default to false for production
    return getConfigValue('python_config.DEBUG_MODE', false);
}

/**
 * Initialize the logger - call this after config is loaded
 * Overwrites console.log to respect DEBUG_MODE setting
 */
function initLogger() {
    const debugEnabled = isDebugEnabled();
    
    if (!debugEnabled) {
        // Silence console.log and console.debug in production
        console.log = () => {};
        console.debug = () => {};
        // Keep warn and error for important messages
        originalConsole.log('[Logger] Debug logging disabled for production');
    } else {
        // Restore original methods if debug is enabled
        console.log = originalConsole.log;
        console.debug = originalConsole.debug;
        console.log('[Logger] Debug logging enabled');
    }
}

/**
 * Force log - always outputs regardless of debug mode
 * Use for critical messages that should always appear
 */
function forceLog(...args) {
    originalConsole.log(...args);
}

/**
 * Force warn - always outputs regardless of debug mode
 */
function forceWarn(...args) {
    originalConsole.warn(...args);
}

/**
 * Force error - always outputs regardless of debug mode
 */
function forceError(...args) {
    originalConsole.error(...args);
}

export { initLogger, isDebugEnabled, forceLog, forceWarn, forceError, originalConsole };
