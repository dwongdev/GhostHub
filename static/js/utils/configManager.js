/**
 * Configuration Manager
 * Handles fetching, storing, and saving application configuration for the frontend.
 */

import { bus } from '../libs/ragot.esm.min.js';
import { APP_EVENTS } from '../core/appEvents.js';

let currentConfig = {};
let initialConfigFetched = false;
const startupTime = Date.now();
const STARTUP_GRACE_PERIOD = 3000; // 3 seconds grace period for initial module loading
const DEFAULT_CONFIG = {
    python_config: {
        SAVE_VIDEO_PROGRESS: true
    },
    javascript_config: {}
};

function applyConfigDefaults(rawConfig) {
    const config = rawConfig && typeof rawConfig === 'object' ? rawConfig : {};
    const pythonConfig = (config.python_config && typeof config.python_config === 'object')
        ? config.python_config
        : {};
    const javascriptConfig = (config.javascript_config && typeof config.javascript_config === 'object')
        ? config.javascript_config
        : {};

    return {
        ...config,
        python_config: {
            ...DEFAULT_CONFIG.python_config,
            ...pythonConfig
        },
        javascript_config: {
            ...DEFAULT_CONFIG.javascript_config,
            ...javascriptConfig
        }
    };
}

function persistConfigToStore(config) {
    const appStore = window.ragotModules?.appStore;
    if (appStore?.set) {
        appStore.set('config', config, { source: 'configManager.persistConfigToStore' });
    }
}

/**
 * Fetches the application configuration from the server.
 * Stores it locally and syncs it into appStore.config.
 * @returns {Promise<Object>} The fetched configuration.
 */
async function fetchAndApplyConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) {
            throw new Error(`Failed to fetch config: ${response.status} ${response.statusText}`);
        }
        currentConfig = applyConfigDefaults(await response.json());
        persistConfigToStore(currentConfig);
        initialConfigFetched = true;
        console.log('Application configuration loaded:', currentConfig);
        // Log the password protection status using getConfigValue for consistency
        console.log('Password protection active:', getConfigValue('isPasswordProtectionActive', false));
        
        // Notify listeners that config is loaded.
        bus.emit(APP_EVENTS.CONFIG_LOADED, currentConfig);
        return currentConfig;
    } catch (error) {
        console.error('Error fetching application configuration:', error);
        const fallbackConfig = window.ragotModules?.appStore?.get?.('config', {});
        currentConfig = applyConfigDefaults(fallbackConfig || {});
        persistConfigToStore(currentConfig);
        return currentConfig; // Return current (possibly default/empty) config
    }
}

/**
 * Gets a configuration value using a dot-separated path.
 * @param {string} path - The dot-separated path to the config value (e.g., "javascript_config.core_app.media_per_page_desktop").
 * @param {*} defaultValue - The value to return if the path is not found.
 * @returns {*} The configuration value or the default value.
 */
function getConfigValue(path, defaultValue) {
    // Only warn after grace period - early module loading is expected to use defaults
    if (!initialConfigFetched && (Date.now() - startupTime) > STARTUP_GRACE_PERIOD) {
        console.warn('ConfigManager: Attempted to get config value before initial fetch completed. Consider awaiting fetchAndApplyConfig() or ensuring it runs first.');
    }
    const keys = path.split('.');
    let value = currentConfig;
    for (const key of keys) {
        if (value && typeof value === 'object' && key in value) {
            value = value[key];
        } else {
            return defaultValue;
        }
    }
    return value;
}

/**
 * Saves the provided configuration data to the server.
 * @param {Object} newConfigData - The complete configuration object to save.
 * @returns {Promise<Object>} The server's response.
 */
async function saveConfig(newConfigData) {
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(newConfigData),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Failed to save config and parse error response.' }));
            throw new Error(errorData.error || `Failed to save config: ${response.status} ${response.statusText}`);
        }
        const result = await response.json();
        // Update local config cache on successful save
        // newConfigData is what was sent. The result from server contains the message and potentially updated flags.
        currentConfig = { ...newConfigData }; 
        if (result.isPasswordProtectionActive !== undefined) {
            currentConfig.isPasswordProtectionActive = result.isPasswordProtectionActive;
        }
        persistConfigToStore(currentConfig);
        console.log('Configuration saved successfully:', result.message);
        console.log('Password protection now active:', getConfigValue('isPasswordProtectionActive', false));
        return result;
    } catch (error) {
        console.error('Error saving application configuration:', error);
        throw error; // Re-throw to be handled by the caller
    }
}

function getCurrentConfig() {
    return currentConfig;
}

export { fetchAndApplyConfig, getConfigValue, saveConfig, getCurrentConfig };
