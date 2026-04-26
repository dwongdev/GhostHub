import { describe, expect, it, vi } from 'vitest';

import {
  applyProfileAvatar,
  createProfileAvatar,
  createProfileAvatarPicker,
  getProfileAvatarSvg,
  normalizeProfileAvatarIcon,
} from '../../utils/profileAvatarLibrary.js';

describe('profileAvatarLibrary', () => {
  it('normalizes avatar icon ids against the curated library', () => {
    expect(normalizeProfileAvatarIcon('GHOST')).toBe('ghost');
    expect(normalizeProfileAvatarIcon('not-a-real-icon')).toBeNull();
    expect(normalizeProfileAvatarIcon(null)).toBeNull();
  });

  it('renders svg avatars when an icon is selected', () => {
    const avatar = createProfileAvatar({
      name: 'Movie Night',
      avatar_color: '#123456',
      avatar_icon: 'ghost',
    });

    expect(avatar.classList.contains('gh-profile-avatar--icon')).toBe(true);
    expect(avatar.innerHTML).toContain('<svg');
    expect(avatar.style.background).toBe('rgb(18, 52, 86)');
  });

  it('falls back to initials for unknown icons', () => {
    const avatar = createProfileAvatar({
      name: 'Movie Night',
      avatar_icon: 'unknown-icon',
    });

    expect(avatar.classList.contains('gh-profile-avatar--icon')).toBe(false);
    expect(avatar.textContent).toBe('MN');
  });

  it('updates an existing avatar element in place', () => {
    const avatar = document.createElement('span');
    avatar.className = 'gh-profile-avatar';

    applyProfileAvatar(avatar, { name: 'Sam', avatar_icon: 'orbit' });
    expect(avatar.innerHTML).toContain('<svg');
    expect(avatar.innerHTML).toContain('aria-label="Sam"');

    applyProfileAvatar(avatar, { name: 'Sam Lee', avatar_icon: null });
    expect(avatar.textContent).toBe('SL');
  });

  it('builds a picker that reports the chosen icon', () => {
    const onChange = vi.fn();
    const picker = createProfileAvatarPicker({
      getName: () => 'Nova',
      getColor: () => '#112233',
      initialIcon: 'ghost',
      onChange,
    });

    const buttons = picker.element.querySelectorAll('.gh-avatar-library__option');
    expect(buttons.length).toBeGreaterThan(3);

    buttons[2].click();
    expect(onChange).toHaveBeenCalled();
    expect(typeof picker.getValue() === 'string' || picker.getValue() === null).toBe(true);
  });
});
