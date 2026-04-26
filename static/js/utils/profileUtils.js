/**
 * Profile persistence and presentation helpers.
 */

import { getCookieValue } from './cookieUtils.js';

const PROFILE_STORAGE_KEY = 'ghosthub_active_profile_id';
const PROFILE_NAME_KEY = 'ghosthub_active_profile_name';
const PROFILE_COLOR_KEY = 'ghosthub_active_profile_color';
const PROFILE_ICON_KEY = 'ghosthub_active_profile_icon';

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

export function getStoredProfileId() {
    return localStorage.getItem(PROFILE_STORAGE_KEY);
}

export function getActiveProfileId() {
    return window.ragotModules?.appStore?.get?.('activeProfileId')
        || getStoredProfileId()
        || null;
}

export function hasActiveProfile() {
    return Boolean(getActiveProfileId());
}

export function getStoredProfileName() {
    return localStorage.getItem(PROFILE_NAME_KEY);
}

export function getStoredProfileColor() {
    return localStorage.getItem(PROFILE_COLOR_KEY);
}

export function getStoredProfileIcon() {
    return localStorage.getItem(PROFILE_ICON_KEY);
}

export function setStoredProfile(id, name = null, avatarColor = null, avatarIcon = null) {
    if (!id) {
        clearStoredProfile();
        return;
    }

    localStorage.setItem(PROFILE_STORAGE_KEY, id);

    if (name) {
        localStorage.setItem(PROFILE_NAME_KEY, name);
    } else {
        localStorage.removeItem(PROFILE_NAME_KEY);
    }

    if (avatarColor) {
        localStorage.setItem(PROFILE_COLOR_KEY, avatarColor);
    } else {
        localStorage.removeItem(PROFILE_COLOR_KEY);
    }

    if (avatarIcon) {
        localStorage.setItem(PROFILE_ICON_KEY, avatarIcon);
    } else {
        localStorage.removeItem(PROFILE_ICON_KEY);
    }
}

export function clearStoredProfile() {
    localStorage.removeItem(PROFILE_STORAGE_KEY);
    localStorage.removeItem(PROFILE_NAME_KEY);
    localStorage.removeItem(PROFILE_COLOR_KEY);
    localStorage.removeItem(PROFILE_ICON_KEY);
}

export function syncActiveProfile(profile) {
    if (profile?.id) {
        setStoredProfile(
            profile.id,
            profile.name || null,
            profile.avatar_color || null,
            profile.avatar_icon || null,
        );
    } else {
        clearStoredProfile();
    }

    setStoreField('activeProfileId', profile?.id || null);
    setStoreField('activeProfileName', profile?.name || null);
    setStoreField('activeProfileColor', profile?.avatar_color || null);
    setStoreField('activeProfileIcon', profile?.avatar_icon || null);
    setStoreField('activeProfilePreferences', profile?.preferences || null);
}

export function getCurrentSessionKey() {
    const sessionId = getCookieValue('session_id');
    return sessionId ? sessionId.slice(0, 8) : null;
}

export function getProfileInitials(name = '') {
    const parts = String(name)
        .trim()
        .split(/\s+/)
        .filter(Boolean);

    if (parts.length === 0) return '?';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export function formatProfileTimestamp(timestamp) {
    if (!timestamp) return 'Never used';
    const date = new Date(timestamp * 1000);
    if (Number.isNaN(date.getTime())) return 'Unknown';
    return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

export function validateProfileName(name) {
    const normalized = String(name || '').trim().replace(/\s+/g, ' ');

    if (!normalized) {
        return 'Profile name is required.';
    }

    if (normalized.length > 24) {
        return 'Profile name must be 24 characters or fewer.';
    }

    if (!/^[A-Za-z0-9][A-Za-z0-9 -]{0,23}$/.test(normalized)) {
        return 'Use letters or numbers first, then letters, numbers, spaces, and hyphens only.';
    }

    return null;
}
