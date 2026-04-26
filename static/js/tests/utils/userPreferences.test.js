/**
 * User Preferences Tests
 * ----------------------
 * Profile-backed preferences must stay isolated to the selected profile,
 * while guest mode continues to work browser-locally.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
    clearUserPreferences,
    getDefaultPreferences,
    getUserPreference,
    getUserPreferences,
    hasCustomPreferences,
    saveUserPreference,
} from '../../utils/userPreferences.js';
import { clearStoredProfile, syncActiveProfile } from '../../utils/profileUtils.js';

const GUEST_PREFS_KEY = 'ghosthub_guest_preferences';
const LEGACY_PREFS_KEY = 'ghosthub_user_preferences';

function createStore(initialState = {}) {
    const state = { ...initialState };
    return {
        get(key, fallback = null) {
            return Object.prototype.hasOwnProperty.call(state, key) ? state[key] : fallback;
        },
        set(key, value) {
            state[key] = value;
        },
        actions: {
            setField(key, value) {
                state[key] = value;
            }
        }
    };
}

beforeEach(() => {
    localStorage.clear();
    clearStoredProfile();
    vi.clearAllMocks();
    global.fetch = vi.fn();
    window.ragotModules = {
        appStore: createStore(),
    };
});

describe('getDefaultPreferences', () => {
    it('returns all-null defaults', () => {
        const defaults = getDefaultPreferences();
        expect(defaults.theme).toBeNull();
        expect(defaults.layout).toBeNull();
        expect(defaults.motion).toBeNull();
        expect(defaults.features.chat).toBeNull();
        expect(defaults.features.headerBranding).toBeNull();
        expect(defaults.features.search).toBeNull();
        expect(defaults.features.syncButton).toBeNull();
    });
});

describe('guest preferences', () => {
    it('returns defaults when guest storage is empty', () => {
        expect(getUserPreferences()).toEqual(getDefaultPreferences());
    });

    it('loads guest preferences from localStorage', () => {
        localStorage.setItem(GUEST_PREFS_KEY, JSON.stringify({
            theme: 'dark',
            layout: 'gallery',
            motion: 'reduced',
            features: { chat: false, headerBranding: true, search: true, syncButton: false },
        }));

        const prefs = getUserPreferences();
        expect(prefs.theme).toBe('dark');
        expect(prefs.layout).toBe('gallery');
        expect(prefs.motion).toBe('reduced');
        expect(prefs.features.chat).toBe(false);
        expect(prefs.features.syncButton).toBe(false);
    });

    it('falls back to the legacy guest key', () => {
        localStorage.setItem(LEGACY_PREFS_KEY, JSON.stringify({
            theme: 'nord',
            features: { chat: false },
        }));

        const prefs = getUserPreferences();
        expect(prefs.theme).toBe('nord');
        expect(prefs.features.chat).toBe(false);
    });

    it('saves guest preferences locally when no profile is active', async () => {
        const result = await saveUserPreference('layout', 'streaming');
        const stored = JSON.parse(localStorage.getItem(GUEST_PREFS_KEY));

        expect(result.layout).toBe('streaming');
        expect(stored.layout).toBe('streaming');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('clears guest preferences locally', async () => {
        await saveUserPreference('theme', 'midnight');
        const result = await clearUserPreferences();

        expect(result).toEqual(getDefaultPreferences());
        expect(localStorage.getItem(GUEST_PREFS_KEY)).toBeNull();
    });
});

describe('active profile preferences', () => {
    beforeEach(() => {
        syncActiveProfile({
            id: 'profile-1',
            name: 'Profile One',
            avatar_color: '#112233',
            preferences: {
                theme: 'midnight',
                layout: 'gallery',
                motion: null,
                features: {
                    chat: false,
                    headerBranding: true,
                    search: true,
                    syncButton: true,
                },
            },
        });
    });

    it('reads preferences from the active profile store', () => {
        const prefs = getUserPreferences();
        expect(prefs.theme).toBe('midnight');
        expect(prefs.layout).toBe('gallery');
        expect(prefs.features.chat).toBe(false);
    });

    it('returns a single active profile preference with fallback', () => {
        expect(getUserPreference('theme', 'dark')).toBe('midnight');
        expect(getUserPreference('features.chat', true)).toBe(false);
        expect(getUserPreference('motion', 'system')).toBe('system');
    });

    it('persists active profile preferences through the profile API', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                profile: {
                    id: 'profile-1',
                    name: 'Profile One',
                    avatar_color: '#112233',
                    preferences: {
                        theme: 'nord',
                        layout: 'gallery',
                        motion: null,
                        features: {
                            chat: false,
                            headerBranding: true,
                            search: false,
                            syncButton: true,
                        },
                    },
                },
            }),
        });

        const result = await saveUserPreference('features.search', false);

        expect(global.fetch).toHaveBeenCalledWith('/api/profiles/profile-1', expect.objectContaining({
            method: 'PATCH',
        }));
        expect(result.features.search).toBe(false);
        expect(window.ragotModules.appStore.get('activeProfilePreferences').features.search).toBe(false);
    });

    it('reverts optimistic profile changes when the API save fails', async () => {
        global.fetch.mockResolvedValue({
            ok: false,
            json: async () => ({ error: 'Nope' }),
        });

        await expect(saveUserPreference('theme', 'nord')).rejects.toThrow('Nope');
        expect(window.ragotModules.appStore.get('activeProfilePreferences').theme).toBe('midnight');
    });

    it('clears active profile preferences through the profile API', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                profile: {
                    id: 'profile-1',
                    name: 'Profile One',
                    avatar_color: '#112233',
                    preferences: getDefaultPreferences(),
                },
            }),
        });

        const result = await clearUserPreferences();
        expect(result).toEqual(getDefaultPreferences());
        expect(window.ragotModules.appStore.get('activeProfilePreferences')).toEqual(getDefaultPreferences());
    });
});

describe('hasCustomPreferences', () => {
    it('returns false for defaults', () => {
        expect(hasCustomPreferences()).toBe(false);
    });

    it('returns true when guest preferences are customized', async () => {
        await saveUserPreference('theme', 'light');
        expect(hasCustomPreferences()).toBe(true);
    });

    it('returns true when active profile preferences are customized', () => {
        syncActiveProfile({
            id: 'profile-2',
            name: 'Profile Two',
            avatar_color: '#334455',
            preferences: {
                theme: null,
                layout: null,
                motion: null,
                features: {
                    chat: false,
                    headerBranding: null,
                    search: null,
                    syncButton: null,
                },
            },
        });

        expect(hasCustomPreferences()).toBe(true);
    });
});
