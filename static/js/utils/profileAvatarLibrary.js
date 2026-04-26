/**
 * Curated profile avatar library and shared avatar rendering helpers.
 */

import { createElement, append } from '../libs/ragot.esm.min.js';
import { getProfileInitials } from './profileUtils.js';

const PROFILE_AVATAR_DEFAULT_COLOR = '#6ea8fe';
const AVATAR_ICON_DEFAULTS = {
    strokeWidth: 1.85,
};

function createAvatarSvg(size, content, label = null) {
    const title = label ? `<title>${label}</title>` : '';
    const role = label ? 'img' : 'presentation';
    const ariaLabel = label ? ` aria-label="${label}"` : '';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${AVATAR_ICON_DEFAULTS.strokeWidth}" stroke-linecap="round" stroke-linejoin="round" role="${role}"${ariaLabel}>${title}${content}</svg>`;
}

/* ── Avatar-optimised icon renderers ─────────────────────────────── */

function ghostAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <path d="M12 2C7.58 2 4 5.58 4 10v11l2-2.5 2 2.5 2-2.5 2 2.5 2-2.5 2 2.5 2-2.5 2 2.5V10c0-4.42-3.58-8-8-8z"/>
        <circle cx="9.5" cy="10" r="1.25" fill="currentColor" stroke="none"/>
        <circle cx="14.5" cy="10" r="1.25" fill="currentColor" stroke="none"/>
    `, label);
}

function sparkAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <path d="M12 2l2.12 6.54L21 12l-6.88 3.46L12 22l-2.12-6.54L3 12l6.88-3.46L12 2z"/>
        <line x1="5" y1="3" x2="5.5" y2="5"/>
        <line x1="19" y1="19" x2="19.5" y2="21"/>
    `, label);
}

function clapperAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <path d="M4 4.5l16-1.5"/>
        <path d="M7.5 3l-2.5 6"/>
        <path d="M13.5 2.5l-2.5 6"/>
        <path d="M19.5 2l-2.5 6"/>
        <rect x="2" y="8" width="20" height="13" rx="2"/>
    `, label);
}

function cameraAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
        <circle cx="12" cy="13" r="4"/>
        <circle cx="12" cy="13" r="1.5" fill="currentColor" stroke="none"/>
    `, label);
}

function tvAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <rect x="2" y="7" width="20" height="14" rx="2"/>
        <path d="M8 3l4 4 4-4"/>
        <line x1="7" y1="14" x2="7.01" y2="14" stroke-width="2.5" stroke-linecap="round"/>
    `, label);
}

function beaconAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <circle cx="12" cy="14" r="2" fill="currentColor" stroke="none"/>
        <path d="M12 14V6"/>
        <path d="M8.5 11.5a5 5 0 0 1 7 0"/>
        <path d="M6 9a8.5 8.5 0 0 1 12 0"/>
        <path d="M12 16v3"/>
        <path d="M9 21h6"/>
    `, label);
}

function cometAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <circle cx="16.5" cy="7.5" r="3" fill="currentColor" stroke="currentColor" stroke-width="0.5"/>
        <path d="M14 10L3 19" stroke-width="2"/>
        <path d="M13.5 9.5L5 14.5" stroke-width="1.3" opacity="0.6"/>
        <path d="M14.5 10.5L8.5 19" stroke-width="1.3" opacity="0.6"/>
    `, label);
}

function maskAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <path d="M2 12c0-3.5 4.5-7 10-7s10 3.5 10 7-4.5 5.5-10 5.5S2 15.5 2 12z"/>
        <ellipse cx="8.5" cy="11" rx="2.5" ry="2" fill="currentColor" stroke="none"/>
        <ellipse cx="15.5" cy="11" rx="2.5" ry="2" fill="currentColor" stroke="none"/>
        <path d="M10.5 12.5c.5.5 1 .75 1.5.75s1-.25 1.5-.75"/>
    `, label);
}

function orbitAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none"/>
        <ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(-30 12 12)"/>
        <ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(30 12 12)"/>
        <circle cx="18" cy="6.5" r="1" fill="currentColor" stroke="none"/>
    `, label);
}

function crownAvatarIcon(size = 20, label = null) {
    return createAvatarSvg(size, `
        <path d="M3 18h18"/>
        <path d="M4 18l1-10 4.5 4L12 5l2.5 7 4.5-4 1 10z" fill="currentColor" opacity="0.15" stroke="none"/>
        <path d="M4 18l1-10 4.5 4L12 5l2.5 7 4.5-4 1 10"/>
        <circle cx="5" cy="7" r="1" fill="currentColor" stroke="none"/>
        <circle cx="12" cy="3.5" r="1" fill="currentColor" stroke="none"/>
        <circle cx="19" cy="7" r="1" fill="currentColor" stroke="none"/>
    `, label);
}

const PROFILE_AVATAR_LIBRARY = [
    { id: 'ghost', label: 'Ghost', render: ghostAvatarIcon },
    { id: 'spark', label: 'Spark', render: sparkAvatarIcon },
    { id: 'clapper', label: 'Clapper', render: clapperAvatarIcon },
    { id: 'camera', label: 'Camera', render: cameraAvatarIcon },
    { id: 'tv', label: 'TV', render: tvAvatarIcon },
    { id: 'beacon', label: 'Beacon', render: beaconAvatarIcon },
    { id: 'comet', label: 'Comet', render: cometAvatarIcon },
    { id: 'mask', label: 'Mask', render: maskAvatarIcon },
    { id: 'orbit', label: 'Orbit', render: orbitAvatarIcon },
    { id: 'crown', label: 'Crown', render: crownAvatarIcon },
];

const PROFILE_AVATAR_CHOICES = [
    { id: null, label: 'Letters' },
    ...PROFILE_AVATAR_LIBRARY.map(({ id, label }) => ({ id, label })),
];

const PROFILE_AVATAR_BY_ID = new Map(
    PROFILE_AVATAR_LIBRARY.map((avatar) => [avatar.id, avatar])
);

export function getDefaultProfileAvatarColor() {
    return PROFILE_AVATAR_DEFAULT_COLOR;
}

export function getProfileAvatarChoices() {
    return PROFILE_AVATAR_CHOICES.map((choice) => ({ ...choice }));
}

export function normalizeProfileAvatarIcon(iconId) {
    if (iconId in { null: true, undefined: true, '': true }) {
        return null;
    }

    const normalized = String(iconId).trim().toLowerCase();
    return PROFILE_AVATAR_BY_ID.has(normalized) ? normalized : null;
}

export function getProfileAvatarSvg(iconId, size = 20, label = null) {
    const normalized = normalizeProfileAvatarIcon(iconId);
    if (!normalized) {
        return '';
    }

    return PROFILE_AVATAR_BY_ID.get(normalized).render(size, label);
}

export function applyProfileAvatar(element, profile = {}, options = {}) {
    if (!element) {
        return element;
    }

    const name = profile?.name || '';
    const avatarColor = profile?.avatar_color || null;
    const avatarIcon = normalizeProfileAvatarIcon(profile?.avatar_icon);
    const iconSize = options.iconSize || 20;
    const initialsFallback = options.initialsFallback || 'AB';

    element.classList.toggle('gh-profile-avatar--icon', Boolean(avatarIcon));
    element.style.background = avatarColor || '';

    if (avatarIcon) {
        element.textContent = '';
        element.innerHTML = getProfileAvatarSvg(avatarIcon, iconSize, profile?.name || null);
        return element;
    }

    element.innerHTML = '';
    element.textContent = name ? getProfileInitials(name) : initialsFallback;
    return element;
}

export function createProfileAvatar(profile = {}, sizeClass = '', options = {}) {
    const avatar = createElement('span', {
        className: `gh-profile-avatar ${sizeClass}`.trim(),
    });
    return applyProfileAvatar(avatar, profile, options);
}

export function createProfileAvatarPicker(options = {}) {
    const {
        getName = () => '',
        getColor = () => PROFILE_AVATAR_DEFAULT_COLOR,
        initialIcon = null,
        onChange = null,
        disabled = false,
        label = 'Avatar',
        hint = 'Scroll to pick a symbol or keep initials.',
    } = options;

    let selectedIcon = normalizeProfileAvatarIcon(initialIcon);
    const controls = [];

    const root = createElement('div', {
        className: 'gh-avatar-library',
    });
    const selectedLabel = createElement('span', {
        className: 'gh-avatar-library__selected-label',
    });

    append(root,
        createElement('div', { className: 'gh-avatar-library__header' },
            createElement('div', { className: 'gh-avatar-library__copy' },
                createElement('span', {
                    className: 'gh-avatar-library__legend',
                    textContent: label
                }),
                createElement('span', {
                    className: 'gh-avatar-library__hint',
                    textContent: hint
                })
            ),
            selectedLabel
        )
    );

    const rail = createElement('div', {
        className: 'gh-avatar-library__rail',
        role: 'listbox',
        'aria-label': label,
    });
    root.appendChild(rail);

    getProfileAvatarChoices().forEach((choice) => {
        const preview = createProfileAvatar({
            name: getName() || '',
            avatar_color: getColor() || PROFILE_AVATAR_DEFAULT_COLOR,
            avatar_icon: choice.id,
        }, 'gh-profile-avatar--picker', {
            initialsFallback: 'AZ',
            iconSize: 18,
        });
        const button = createElement('button', {
            type: 'button',
            className: 'gh-avatar-library__option',
            disabled,
            role: 'option',
            onClick: () => {
                selectedIcon = choice.id;
                refresh();
                if (typeof onChange === 'function') {
                    onChange(selectedIcon);
                }
            }
        });

        append(button,
            preview,
            createElement('span', {
                className: 'gh-avatar-library__option-label',
                textContent: choice.label
            })
        );

        controls.push({ choice, button, preview });
        rail.appendChild(button);
    });

    function refresh() {
        const name = getName() || '';
        const color = getColor() || PROFILE_AVATAR_DEFAULT_COLOR;

        controls.forEach(({ choice, button, preview }) => {
            applyProfileAvatar(preview, {
                name,
                avatar_color: color,
                avatar_icon: choice.id,
            }, {
                initialsFallback: 'AZ',
                iconSize: 18,
            });
            const isSelected = selectedIcon === choice.id || (!selectedIcon && !choice.id);
            button.classList.toggle('is-selected', isSelected);
            button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            button.setAttribute('aria-selected', isSelected ? 'true' : 'false');
        });

        const activeChoice = PROFILE_AVATAR_CHOICES.find((choice) =>
            choice.id === selectedIcon || (!choice.id && !selectedIcon)
        );
        selectedLabel.textContent = activeChoice?.label || 'Letters';
    }

    refresh();

    return {
        element: root,
        getValue: () => selectedIcon,
        setValue: (nextIcon) => {
            selectedIcon = normalizeProfileAvatarIcon(nextIcon);
            refresh();
        },
        refresh,
    };
}
