/**
 * User Preferences Manager
 * Stores preferences with the active profile when one is selected.
 * Guest mode falls back to browser-local storage.
 */

import { getActiveProfileId, syncActiveProfile } from './profileUtils.js';

const GUEST_PREFS_KEY = 'ghosthub_guest_preferences';
const LEGACY_PREFS_KEY = 'ghosthub_user_preferences';

function getAppStore() {
    return window.ragotModules?.appStore || null;
}

function setStoreField(key, value) {
    const store = getAppStore();
    if (!store) return;

    if (store.actions?.setField) {
        store.actions.setField(key, value);
        return;
    }

    if (typeof store.set === 'function') {
        store.set(key, value);
    }
}

function getRawStoredGuestPreferences() {
    const guestStored = localStorage.getItem(GUEST_PREFS_KEY);
    if (guestStored) {
        return guestStored;
    }

    return localStorage.getItem(LEGACY_PREFS_KEY);
}

function normalizePreferences(prefs = {}) {
    const defaults = getDefaultPreferences();
    return {
        theme: prefs.theme ?? defaults.theme,
        layout: prefs.layout ?? defaults.layout,
        motion: prefs.motion ?? defaults.motion,
        features: {
            chat: prefs.features?.chat ?? defaults.features.chat,
            headerBranding: prefs.features?.headerBranding ?? defaults.features.headerBranding,
            search: prefs.features?.search ?? defaults.features.search,
            syncButton: prefs.features?.syncButton ?? defaults.features.syncButton
        }
    };
}

function clonePreferences(prefs) {
    return JSON.parse(JSON.stringify(normalizePreferences(prefs)));
}

function getActiveProfilePreferencesFromStore() {
    const store = getAppStore();
    const activeProfileId = getActiveProfileId();
    if (!store || !activeProfileId) {
        return null;
    }

    return normalizePreferences(store.get?.('activeProfilePreferences'));
}

function setActiveProfilePreferences(preferences) {
    setStoreField('activeProfilePreferences', normalizePreferences(preferences));
}

function persistGuestPreferences(prefs) {
    const normalized = normalizePreferences(prefs);

    if (normalized.theme === null &&
        normalized.layout === null &&
        normalized.motion === null &&
        normalized.features.chat === null &&
        normalized.features.headerBranding === null &&
        normalized.features.search === null &&
        normalized.features.syncButton === null) {
        localStorage.removeItem(GUEST_PREFS_KEY);
        localStorage.removeItem(LEGACY_PREFS_KEY);
        return;
    }

    localStorage.setItem(GUEST_PREFS_KEY, JSON.stringify(normalized));
    localStorage.removeItem(LEGACY_PREFS_KEY);
}

function getGuestPreferences() {
    try {
        const stored = getRawStoredGuestPreferences();
        if (!stored) {
            return getDefaultPreferences();
        }

        const parsed = JSON.parse(stored);
        if (parsed && typeof parsed === 'object' && parsed.scopes) {
            return normalizePreferences(parsed.scopes.__guest__);
        }

        return normalizePreferences(parsed);
    } catch (error) {
        console.error('Error loading guest preferences:', error);
        return getDefaultPreferences();
    }
}

function updatePreferenceValue(prefs, key, value) {
    const nextPrefs = clonePreferences(prefs);

    if (key.includes('.')) {
        const [parent, child] = key.split('.');
        if (nextPrefs[parent]) {
            nextPrefs[parent][child] = value;
        }
    } else {
        nextPrefs[key] = value;
    }

    return nextPrefs;
}

/**
 * Get default user preferences
 * @returns {Object} Default preferences object
 */
export function getDefaultPreferences() {
    return {
        theme: null,
        layout: null,
        motion: null,
        features: {
            chat: null,
            headerBranding: null,
            search: null,
            syncButton: null
        }
    };
}

/**
 * Get preferences for the active profile, or guest/browser preferences if no profile is active.
 * @returns {Object} User preferences object
 */
export function getUserPreferences() {
    const profilePrefs = getActiveProfilePreferencesFromStore();
    if (profilePrefs) {
        return profilePrefs;
    }

    return getGuestPreferences();
}

/**
 * Save a single user preference.
 * Active profile prefs are persisted to SQLite through the profile API.
 * Guest prefs are stored in localStorage.
 * @param {string} key - Preference key
 * @param {any} value - Preference value
 * @returns {Promise<Object>} Updated preferences object
 */
export async function saveUserPreference(key, value) {
    const activeProfileId = getActiveProfileId();
    const previousPrefs = getUserPreferences();
    const nextPrefs = updatePreferenceValue(previousPrefs, key, value);

    if (!activeProfileId) {
        persistGuestPreferences(nextPrefs);
        console.log(`Guest preference saved: ${key} = ${value}`);
        return nextPrefs;
    }

    setActiveProfilePreferences(nextPrefs);

    try {
        const response = await fetch(`/api/profiles/${encodeURIComponent(activeProfileId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preferences: nextPrefs })
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok || !data.profile) {
            throw new Error(data.error || data.message || 'Failed to save profile preferences.');
        }

        syncActiveProfile(data.profile);
        console.log(`Profile preference saved: ${key} = ${value}`);
        return normalizePreferences(data.profile.preferences);
    } catch (error) {
        setActiveProfilePreferences(previousPrefs);
        console.error('Error saving user preference:', error);
        throw error;
    }
}

/**
 * Get a single user preference with fallback to server config
 * @param {string} key - Preference key
 * @param {any} serverDefault - Fallback value from server config
 * @returns {any} Preference value (user pref or server default)
 */
export function getUserPreference(key, serverDefault) {
    const prefs = getUserPreferences();

    let value;
    if (key.includes('.')) {
        const [parent, child] = key.split('.');
        value = prefs[parent]?.[child];
    } else {
        value = prefs[key];
    }

    return value !== null && value !== undefined ? value : serverDefault;
}

/**
 * Clear all user preferences back to defaults.
 * @returns {Promise<Object>} Default preferences object
 */
export async function clearUserPreferences() {
    const defaults = getDefaultPreferences();
    const activeProfileId = getActiveProfileId();

    if (!activeProfileId) {
        persistGuestPreferences(defaults);
        return defaults;
    }

    const previousPrefs = getUserPreferences();
    setActiveProfilePreferences(defaults);

    try {
        const response = await fetch(`/api/profiles/${encodeURIComponent(activeProfileId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preferences: defaults })
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok || !data.profile) {
            throw new Error(data.error || data.message || 'Failed to clear profile preferences.');
        }

        syncActiveProfile(data.profile);
        return normalizePreferences(data.profile.preferences);
    } catch (error) {
        setActiveProfilePreferences(previousPrefs);
        console.error('Error clearing user preferences:', error);
        throw error;
    }
}

/**
 * Check if user has any custom preferences set
 * @returns {boolean} True if user has customized preferences
 */
export function hasCustomPreferences() {
    try {
        const prefs = getUserPreferences();
        const defaults = getDefaultPreferences();

        if (prefs.theme !== defaults.theme) return true;
        if (prefs.layout !== defaults.layout) return true;
        if (prefs.motion !== defaults.motion) return true;
        if (prefs.features?.chat !== defaults.features.chat) return true;
        if (prefs.features?.headerBranding !== defaults.features.headerBranding) return true;
        if (prefs.features?.search !== defaults.features.search) return true;
        if (prefs.features?.syncButton !== defaults.features.syncButton) return true;

        return false;
    } catch (error) {
        return false;
    }
}
