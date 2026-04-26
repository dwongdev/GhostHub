import { describe, it, expect, beforeEach } from 'vitest';

import {
  clearStoredProfile,
  formatProfileTimestamp,
  getCurrentSessionKey,
  getProfileInitials,
  getStoredProfileColor,
  getStoredProfileId,
  getStoredProfileIcon,
  getStoredProfileName,
  setStoredProfile,
  syncActiveProfile,
  validateProfileName,
} from '../../utils/profileUtils.js';

describe('profileUtils', () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = 'session_id=test-session-12345678; path=/';
    window.ragotModules.appStore.set('activeProfileId', null);
    window.ragotModules.appStore.set('activeProfileName', null);
    window.ragotModules.appStore.set('activeProfileColor', null);
    window.ragotModules.appStore.set('activeProfileIcon', null);
  });

  it('stores and clears profile data', () => {
    setStoredProfile('profile-1', 'Movie Night', '#112233', 'ghost');

    expect(getStoredProfileId()).toBe('profile-1');
    expect(getStoredProfileName()).toBe('Movie Night');
    expect(getStoredProfileColor()).toBe('#112233');
    expect(getStoredProfileIcon()).toBe('ghost');

    clearStoredProfile();

    expect(getStoredProfileId()).toBeNull();
    expect(getStoredProfileName()).toBeNull();
    expect(getStoredProfileColor()).toBeNull();
    expect(getStoredProfileIcon()).toBeNull();
  });

  it('syncs active profile into app state', () => {
    syncActiveProfile({
      id: 'profile-7',
      name: 'Sam',
      avatar_color: '#abcdef',
      avatar_icon: 'orbit'
    });

    expect(window.ragotModules.appStore.get('activeProfileId')).toBe('profile-7');
    expect(window.ragotModules.appStore.get('activeProfileName')).toBe('Sam');
    expect(window.ragotModules.appStore.get('activeProfileColor')).toBe('#abcdef');
    expect(window.ragotModules.appStore.get('activeProfileIcon')).toBe('orbit');
  });

  it('derives initials and session key', () => {
    expect(getProfileInitials('Movie Night')).toBe('MN');
    expect(getProfileInitials('solo')).toBe('SO');
    expect(getCurrentSessionKey()).toBe('test-ses');
  });

  it('validates profile names', () => {
    expect(validateProfileName('')).toContain('required');
    expect(validateProfileName('this name is way too long for the limit')).toContain('24 characters');
    expect(validateProfileName('Bad!Name')).toContain('letters, numbers');
    expect(validateProfileName('Family Room')).toBeNull();
  });

  it('formats timestamps defensively', () => {
    expect(formatProfileTimestamp(0)).toBe('Never used');
    expect(typeof formatProfileTimestamp(1710000000)).toBe('string');
  });
});
