/**
 * GhostHub Icon Utility
 * Provides inline SVG icons for offline-first media server
 * All icons use currentColor for theme compatibility
 */

const ICON_DEFAULTS = {
    size: 20,
    strokeWidth: 2
};

/**
 * Creates an SVG element with common attributes
 * @param {number} size - Icon size in pixels
 * @param {string} content - SVG content (paths, shapes, etc.)
 * @param {string} viewBox - SVG viewBox attribute
 * @param {string|null} label - Optional accessibility label for screen readers
 * @returns {string} SVG markup
 */
function createSvg(size, content, viewBox = '0 0 24 24', label = null) {
    const title = label ? `<title>${label}</title>` : '';
    const role = label ? 'img' : 'presentation';
    const ariaLabel = label ? ` aria-label="${label}"` : '';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${viewBox}" fill="none" stroke="currentColor" stroke-width="${ICON_DEFAULTS.strokeWidth}" stroke-linecap="round" stroke-linejoin="round" role="${role}"${ariaLabel}>${title}${content}</svg>`;
}

/**
 * Video/Film icon - for video files and categories containing videos
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function videoIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/>
        <line x1="7" y1="2" x2="7" y2="22"/>
        <line x1="17" y1="2" x2="17" y2="22"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
        <line x1="2" y1="7" x2="7" y2="7"/>
        <line x1="2" y1="17" x2="7" y2="17"/>
        <line x1="17" y1="17" x2="22" y2="17"/>
        <line x1="17" y1="7" x2="22" y2="7"/>
    `, '0 0 24 24', label);
}

/**
 * Image/Photo icon - for image files and photo categories
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function imageIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21"/>
    `, '0 0 24 24', label);
}

/**
 * Folder icon - for directories/categories
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function folderIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    `, '0 0 24 24', label);
}

/**
 * Filled folder icon - for compact breadcrumb/path indicators
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function folderFilledIcon(size = ICON_DEFAULTS.size, label = null) {
    const title = label ? `<title>${label}</title>` : '';
    const role = label ? 'img' : 'presentation';
    const ariaLabel = label ? ` aria-label="${label}"` : '';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" stroke="none" role="${role}"${ariaLabel}>${title}<path d="M10 4l2 2h8a1 1 0 0 1 1 1v1H3V5a1 1 0 0 1 1-1h6zm11 5H3v10a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V9z"/></svg>`;
}

/**
 * Play icon - for video playback indicators
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @param {string} fill - Fill color (default: 'none')
 * @returns {string} SVG markup
 */
export function playIcon(size = ICON_DEFAULTS.size, label = null, fill = 'none') {
    const fillAttr = fill !== 'none' ? ` fill="${fill}"` : '';
    const title = label ? `<title>${label}</title>` : '';
    const role = label ? 'img' : 'presentation';
    const ariaLabel = label ? ` aria-label="${label}"` : '';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24"${fillAttr} stroke="currentColor" stroke-width="${ICON_DEFAULTS.strokeWidth}" stroke-linecap="round" stroke-linejoin="round" role="${role}"${ariaLabel}>${title}<polygon points="5 3 19 12 5 21"/></svg>`;
}

/**
 * Pause icon - for video pause button
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function pauseIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="6" y="4" width="4" height="16" rx="1"/>
        <rect x="14" y="4" width="4" height="16" rx="1"/>
    `, '0 0 24 24', label);
}

/**
 * Skip back icon - for rewinding (10s counter-clockwise arrow)
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function skipBackIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polygon points="11 19 2 12 11 5 11 19"/>
        <polygon points="22 19 13 12 22 5 22 19"/>
    `, '0 0 24 24', label);
}

/**
 * Skip forward icon - for fast forwarding (10s clockwise arrow)
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function skipForwardIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polygon points="13 19 22 12 13 5 13 19"/>
        <polygon points="2 19 11 12 2 5 2 19"/>
    `, '0 0 24 24', label);
}

/**
 * Subtitles/CC icon - for subtitle/closed captions button
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function subtitleIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="2" y="4" width="20" height="16" rx="2"/>
        <path d="M7 12h4"/>
        <path d="M13 12h4"/>
        <path d="M5 16h14"/>
    `, '0 0 24 24', label);
}

/**
 * Picture-in-Picture icon - for PiP mode toggle
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function pipIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <rect x="12" y="10" width="8" height="5" rx="1" fill="currentColor"/>
    `, '0 0 24 24', label);
}

/**
 * Fullscreen/Maximize icon - for fullscreen toggle
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function fullscreenIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M8 3H5a2 2 0 0 0-2 2v3"/>
        <path d="M21 8V5a2 2 0 0 0-2-2h-3"/>
        <path d="M3 16v3a2 2 0 0 0 2 2h3"/>
        <path d="M16 21h3a2 2 0 0 0 2-2v-3"/>
    `, '0 0 24 24', label);
}

/**
 * Mute icon - speaker with slash
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function muteIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <line x1="23" y1="9" x2="17" y2="15"/>
        <line x1="17" y1="9" x2="23" y2="15"/>
    `, '0 0 24 24', label);
}

/**
 * Unmute icon - speaker without slash
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function unmuteIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        <path d="M15 9a4 4 0 0 1 0 6"/>
        <path d="M17.5 6.5a7 7 0 0 1 0 11"/>
    `, '0 0 24 24', label);
}

/**
 * Exit fullscreen/Minimize icon - for exiting fullscreen
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function exitFullscreenIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M4 14h3a2 2 0 0 1 2 2v3"/>
        <path d="M20 10h-3a2 2 0 0 1-2-2V5"/>
        <path d="M14 4v3a2 2 0 0 0 2 2h3"/>
        <path d="M10 20v-3a2 2 0 0 0-2-2H5"/>
    `, '0 0 24 24', label);
}

/**
 * File icon - for generic/unknown files
 */
export function fileIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
    `, '0 0 24 24', label);
}

/**
 * Archive/ZIP icon - for compressed files
 */
export function archiveIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <path d="M10 12h1v2h2v-2h1" stroke-width="1.5"/>
        <path d="M10 18h4"/>
    `, '0 0 24 24', label);
}

/**
 * Question/Unknown icon - for unknown types
 */
export function unknownIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <circle cx="12" cy="12" r="10"/>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
    `, '0 0 24 24', label);
}

/**
 * Refresh/Processing icon - for loading states
 */
export function refreshIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polyline points="23 4 23 10 17 10"/>
        <polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    `, '0 0 24 24', label);
}

/**
 * Download icon
 */
export function downloadIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
    `, '0 0 24 24', label);
}

/**
 * Check/Success icon - simple checkmark
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function checkIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polyline points="20 6 9 17 4 12"/>
    `, '0 0 24 24', label);
}

/**
 * Warning/Alert icon
 */
export function warningIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
    `, '0 0 24 24', label);
}

/**
 * Clock/Pending icon
 */
export function clockIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 6v6l4 2"/>
    `, '0 0 24 24', label);
}

/**
 * TV/Monitor icon - for Continue Watching, TV casting
 */
export function tvIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="2" y="7" width="20" height="15" rx="2"/>
        <path d="M17 2l-5 5-5-5"/>
    `, '0 0 24 24', label);
}

/**
 * Sparkle/Star icon - for What's New, featured content
 */
export function sparkleIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M12 2l2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 2z"/>
        <line x1="5" y1="3" x2="5.01" y2="5" stroke-width="2.5" stroke-linecap="round"/>
        <line x1="20" y1="18" x2="20.01" y2="20" stroke-width="2.5" stroke-linecap="round"/>
    `, '0 0 24 24', label);
}

/**
 * Single user icon - for single viewer
 */
export function userIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
    `, '0 0 24 24', label);
}

/**
 * Multiple users icon - for viewer count
 */
export function usersIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    `, '0 0 24 24', label);
}

/**
 * Ghost icon - for hiding/hidden categories
 */
export function ghostIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M12 2C7.58 2 4 5.58 4 10v11l2-2.5 2 2.5 2-2.5 2 2.5 2-2.5 2 2.5 2-2.5 2 2.5V10c0-4.42-3.58-8-8-8z"/>
        <circle cx="9.5" cy="10" r="1.25" fill="currentColor" stroke="none"/>
        <circle cx="14.5" cy="10" r="1.25" fill="currentColor" stroke="none"/>
    `, '0 0 24 24', label);
}

/**
 * Clapper/Movie icon - for loading states, video actions
 */
export function clapperIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="2" y="8" width="20" height="14" rx="2"/>
        <path d="M2 8l16-5"/>
        <path d="M7 3l-2.5 5"/>
        <path d="M13 1.2l-2.5 5"/>
        <path d="M19 -0.6l-2.5 5"/>
    `, '0 0 24 24', label);
}

/**
 * Folder (closed) icon - for collapsed folders
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function folderClosedIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
    `, '0 0 24 24', label);
}

/**
 * Folder (open) icon - for expanded/active folders
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function folderOpenIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M6 14l1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"/>
    `, '0 0 24 24', label);
}

/**
 * Arrow up icon - for swipe/scroll indicators
 */
export function arrowUpIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <line x1="12" y1="19" x2="12" y2="5"/>
        <polyline points="5 12 12 5 19 12"/>
    `, '0 0 24 24', label);
}

/**
 * Arrow down icon - for swipe/scroll indicators
 */
export function arrowDownIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <line x1="12" y1="5" x2="12" y2="19"/>
        <polyline points="19 12 12 19 5 12"/>
    `, '0 0 24 24', label);
}

/**
 * Arrow left icon - for back navigation
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function arrowLeftIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <line x1="19" y1="12" x2="5" y2="12"/>
        <polyline points="12 19 5 12 12 5"/>
    `, '0 0 24 24', label);
}

/**
 * Chevron down icon - for dropdowns/expandable sections
 */
export function chevronDownIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polyline points="6 9 12 15 18 9"/>
    `, '0 0 24 24', label);
}

/**
 * Chevron up icon - for scroll to top, collapsing
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function chevronUpIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polyline points="18 15 12 9 6 15"/>
    `, '0 0 24 24', label);
}

/**
 * Gear/Settings icon - for configuration, quality selector
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function gearIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
        <circle cx="12" cy="12" r="3"/>
    `, '0 0 24 24', label);
}

/**
 * Lightbulb icon - for tips, info messages
 */
export function lightbulbIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M9 18h6"/>
        <path d="M10 22h4"/>
        <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8a6 6 0 0 0-12 0c0 1.06.28 2.06 1.5 3.5.76.76 1.23 1.52 1.41 2.5"/>
    `, '0 0 24 24', label);
}

/**
 * Desktop/Monitor icon - for desktop devices, servers
 */
export function desktopIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
    `, '0 0 24 24', label);
}

/**
 * Mobile/Phone icon - for mobile devices, app badges
 */
export function mobileIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
        <line x1="12" y1="18" x2="12.01" y2="18"/>
    `, '0 0 24 24', label);
}

/**
 * Globe with signal waves icon - for remote access, network connectivity
 */
export function globeSignalIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <circle cx="12" cy="12" r="10"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        <path d="M2 7.5h20" opacity="0.4"/>
        <path d="M2 16.5h20" opacity="0.4"/>
    `, '0 0 24 24', label);
}

/**
 * Lightning bolt icon - for speed, transcoding, power
 */
export function lightningIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    `, '0 0 24 24', label);
}

/**
 * Camera icon - for photo/image galleries
 */
export function cameraIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
        <circle cx="12" cy="13" r="4"/>
    `, '0 0 24 24', label);
}

/**
 * Disk/Save icon - for cached content, save actions
 */
export function diskIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
        <polyline points="17 21 17 13 7 13 7 21"/>
        <polyline points="7 3 7 8 15 8"/>
    `, '0 0 24 24', label);
}

/**
 * X icon - for close, cancel, error
 */
export function xIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
    `, '0 0 24 24', label);
}

/**
 * Check with circle icon - for success, completed
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function checkCircleIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
    `, '0 0 24 24', label);
}

/**
 * Stop/Block icon - for blocking, stopping actions
 */
export function stopIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <circle cx="12" cy="12" r="10"/>
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
    `, '0 0 24 24', label);
}

/**
 * Lock icon - for locked/secure state
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function lockIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    `, '0 0 24 24', label);
}

/**
 * Unlock icon - for unlocked/open state
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function unlockIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 9.9-1"/>
    `, '0 0 24 24', label);
}

/**
 * Shield check icon - for admin/active protection
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function shieldCheckIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        <path d="m9 12 2 2 4-4"/>
    `, '0 0 24 24', label);
}

/**
 * Eye icon - for view action
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function eyeIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
    `, '0 0 24 24', label);
}

/**
 * Eye off icon - for hidden/invisible state
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function eyeOffIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
    `, '0 0 24 24', label);
}

/**
 * Trash icon - for delete/kick action
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function trashIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    `, '0 0 24 24', label);
}

/**
 * Upload icon - for file upload
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function uploadIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
    `, '0 0 24 24', label);
}

/**
 * Droplet icon - for theme/color picker
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function dropletIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
    `, '0 0 24 24', label);
}

/**
 * Cast icon - for TV casting
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function castIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M2 16.1A5 5 0 0 1 5.9 20M2 12.05A9 9 0 0 1 9.95 20M2 8V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6"/>
        <line x1="2" y1="20" x2="2.01" y2="20"/>
    `, '0 0 24 24', label);
}

/**
 * Rotate/sync icon - for syncing progress
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function rotateIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
    `, '0 0 24 24', label);
}

/**
 * Hard drive icon - for storage drives
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function hardDriveIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <line x1="22" y1="12" x2="2" y2="12"/>
        <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>
        <line x1="6" y1="16" x2="6.01" y2="16"/>
        <line x1="10" y1="16" x2="10.01" y2="16"/>
    `, '0 0 24 24', label);
}

/**
 * USB icon - for USB drives
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function usbIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <rect x="7" y="2" width="10" height="14" rx="1"/>
        <path d="M9 16h6v4a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2v-4z"/>
        <line x1="10" y1="6" x2="10" y2="9"/>
        <line x1="14" y1="6" x2="14" y2="9"/>
    `, '0 0 24 24', label);
}

/**
 * Plus icon - for adding items
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function plusIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
    `, '0 0 24 24', label);
}

/**
 * Cancel/X circle icon - for cancel actions
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function cancelIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
    `, '0 0 24 24', label);
}

/**
 * Search icon - for search functionality
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function searchIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <circle cx="11" cy="11" r="8"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    `, '0 0 24 24', label);
}

/**
 * Edit/Pencil icon - for rename/edit actions
 * @param {number} size - Icon size in pixels
 * @param {string|null} label - Optional accessibility label
 * @returns {string} SVG markup
 */
export function editIcon(size = ICON_DEFAULTS.size, label = null) {
    return createSvg(size, `
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    `, '0 0 24 24', label);
}

/**
 * USB port indicator — 2x2 dot grid with one active port highlighted.
 * @param {number} size - Icon size in pixels
 * @param {number|null} activePort - Port index 0-3 to highlight (top-left, bottom-left, top-right, bottom-right)
 * @returns {string} SVG markup
 */
export function usbPortIcon(size = ICON_DEFAULTS.size, activePort = null) {
    const positions = [
        { x: 2, y: 2 },   // 0: top-left
        { x: 2, y: 12 },  // 1: bottom-left
        { x: 12, y: 2 },  // 2: top-right
        { x: 12, y: 12 }, // 3: bottom-right
    ];
    const rects = positions.map((pos, i) => {
        const fill = i === activePort ? 'var(--accent-color)' : 'none';
        return `<rect x="${pos.x}" y="${pos.y}" width="8" height="8" rx="1.5" fill="${fill}" stroke="currentColor" stroke-width="1.5"/>`;
    }).join('');
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 22 22" role="presentation">${rects}</svg>`;
}

/**
 * Get icon by media type
 * @param {string} type - 'video', 'image', 'folder', 'file', 'archive', 'unknown'
 * @param {number} size - Icon size in pixels
 * @returns {string} SVG markup
 */
export function getMediaIcon(type, size = ICON_DEFAULTS.size) {
    switch (type) {
        case 'video':
            return videoIcon(size);
        case 'image':
        case 'photo':
            return imageIcon(size);
        case 'folder':
        case 'category':
            return folderIcon(size);
        case 'archive':
        case 'zip':
            return archiveIcon(size);
        case 'file':
            return fileIcon(size);
        case 'refresh':
        case 'processing':
            return refreshIcon(size);
        case 'download':
            return downloadIcon(size);
        case 'play':
            return playIcon(size);
        default:
            return unknownIcon(size);
    }
}

/**
 * Wrap icon in a span with optional class
 * @param {string} iconHtml - SVG markup
 * @param {string} className - Optional CSS class
 * @returns {string} Wrapped icon HTML
 */
export function wrapIcon(iconHtml, className = 'icon') {
    return `<span class="${className}">${iconHtml}</span>`;
}

export default {
    videoIcon,
    imageIcon,
    folderIcon,
    playIcon,
    pauseIcon,
    skipBackIcon,
    skipForwardIcon,
    subtitleIcon,
    pipIcon,
    fullscreenIcon,
    exitFullscreenIcon,
    fileIcon,
    archiveIcon,
    unknownIcon,
    refreshIcon,
    downloadIcon,
    checkIcon,
    warningIcon,
    clockIcon,
    tvIcon,
    sparkleIcon,
    userIcon,
    usersIcon,
    ghostIcon,
    clapperIcon,
    folderClosedIcon,
    folderOpenIcon,
    arrowUpIcon,
    arrowDownIcon,
    arrowLeftIcon,
    chevronDownIcon,
    chevronUpIcon,
    gearIcon,
    lightbulbIcon,
    desktopIcon,
    mobileIcon,
    globeSignalIcon,
    lightningIcon,
    cameraIcon,
    diskIcon,
    xIcon,
    checkCircleIcon,
    stopIcon,
    lockIcon,
    unlockIcon,
    shieldCheckIcon,
    eyeIcon,
    eyeOffIcon,
    trashIcon,
    uploadIcon,
    dropletIcon,
    castIcon,
    rotateIcon,
    hardDriveIcon,
    usbIcon,
    plusIcon,
    cancelIcon,
    searchIcon,
    editIcon,
    usbPortIcon,
    getMediaIcon,
    wrapIcon
};
