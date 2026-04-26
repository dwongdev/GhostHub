/**
 * Media Element Factory
 * Creates video, image, and placeholder DOM elements for media playback.
 * 
 * @module media/elementFactory
 */

import { videoIcon, imageIcon, fileIcon, clapperIcon, folderIcon } from '../../utils/icons.js';
import { isAutoPlayActive } from '../playback/autoPlay.js';
import { formatSubfolderName } from '../../utils/subfolderUtils.js';
import { createElement, css, attr, $ } from '../../libs/ragot.esm.min.js';

// Formats that browsers CANNOT play natively - need transcoding
export const UNPLAYABLE_FORMATS = ['mkv', 'avi', 'wmv', 'flv', 'ts', 'm2ts', 'mpg', 'mpeg', 'vob'];

/**
 * Check if a file format requires transcoding to play in browser
 * @param {string} filename - The filename to check
 * @returns {boolean} True if format cannot play natively in browser
 */
export function requiresTranscoding(filename) {
    const ext = filename.toLowerCase().split('.').pop();
    return UNPLAYABLE_FORMATS.includes(ext);
}

/**
 * Create a "cannot play" placeholder for incompatible formats
 * @param {Object} file - The file object
 * @param {string} reason - Why it can't play
 * @returns {HTMLElement} The placeholder element
 */
export function createCannotPlayElement(file, reason) {
    const ext = file.name.split('.').pop().toUpperCase();
    const container = createElement('div', {
        className: 'viewer-media cannot-play-container'
    },
        createElement('div', {
            className: 'cannot-play-container__content',
            innerHTML: `
                <div class="cannot-play-container__icon">${clapperIcon(48)}</div>
                <strong class="cannot-play-container__title">Cannot play this video</strong>
                <small class="cannot-play-container__meta">
                    ${ext} format requires transcoding.<br>
                    ${reason}
                </small>
            `
        })
    );

    return container;
}

/**
 * Create a video thumbnail container (with overlay) for the given file.
 * @param {Object}  file     – The file object (must have file.url, file.name, file.thumbnailUrl)
 * @param {boolean} isActive – Whether this is the active media
 * @returns {HTMLElement} – The thumbnail container with overlay
 */
export function createVideoThumbnailElement(file, isActive) {
    // Check if format requires transcoding
    if (requiresTranscoding(file.name)) {
        const ghoststream = window.ragotModules?.ghoststreamManager;

        if (!ghoststream?.isAvailable?.()) {
            console.log(`[Playback] ${file.name}: format requires transcoding but GhostStream unavailable`);
            return createCannotPlayElement(file, 'No transcoding server connected.');
        }
    }

    const container = createElement('div', {
        className: `viewer-media video-thumbnail-container${isActive ? ' active' : ''}`,
        'data-video-src': file.url,
        'data-file-info': JSON.stringify(file)
    });

    const thumbnailImage = createElement('img', {
        className: 'video-thumbnail-image',
        alt: file.name,
        src: file.thumbnailUrl || '/static/icons/Ghosthub192.png',
        loading: isActive ? 'eager' : 'lazy'
    });

    if (file.thumbnailUrl) {
        css(thumbnailImage, { opacity: '0' });
    } else {
        css(thumbnailImage, {
            opacity: '1', objectFit: 'contain', padding: '20%', background: '#1a1a2e'
        });
    }

    if (isActive && thumbnailImage.decode && file.thumbnailUrl) {
        thumbnailImage.decode().catch(() => { });
    }

    const playOverlay = createElement('div', { className: 'play-icon-overlay' });

    // Centered filename label
    const fileLabel = createElement('div', {
        className: 'vc-thumb-label',
        textContent: file.displayName || file.name
    });

    css(playOverlay, { opacity: '0', transition: 'opacity 0.2s ease' });
    css(fileLabel, { opacity: '0', transition: 'opacity 0.2s ease' });

    const revealOverlay = () => {
        css(playOverlay, { opacity: '1' });
        css(fileLabel, { opacity: '1' });
    };

    container.appendChild(thumbnailImage);
    container.appendChild(playOverlay);
    container.appendChild(fileLabel);

    if (thumbnailImage.complete && thumbnailImage.naturalWidth > 0) {
        css(thumbnailImage, { opacity: '1' });
        revealOverlay();
    } else {
        attr(thumbnailImage, {
            onLoad: () => {
                css(thumbnailImage, { opacity: '1' });
                revealOverlay();
            },
            onError: () => {
                attr(thumbnailImage, { onError: null });
                thumbnailImage.src = '/static/icons/Ghosthub192.png';
                css(thumbnailImage, {
                    opacity: '1', objectFit: 'contain', padding: '20%', background: '#1a1a2e'
                });
                revealOverlay();
            }
        });
    }

    return container;
}

/**
 * Create an image element for the given file
 * @param {Object} file - The file object
 * @param {boolean} isActive - Whether this image is the active viewer item
 * @returns {HTMLImageElement} - The created image element
 */
export function createImageElement(file, isActive = false) {
    const placeholder = createPlaceholderElement(file, 'image');

    let lastTapTime = 0;
    function openViewer() {
        if (window.ragotModules?.fullscreenManager?.hasRecentFullscreenExit?.()) return;
        if (window.ragotModules?.photoViewer) {
            window.ragotModules.photoViewer.openPhotoViewer(file.url, file.name);
        }
    }

    const mediaElement = createElement('img', {
        alt: file.name,
        loading: isActive ? 'eager' : 'lazy',
        decoding: 'async',
        src: file.url,
        onError: () => {
            console.error(`Error loading image: ${file.url}`);
            attr(mediaElement, { onError: null });

            if (mediaElement.parentNode) {
                mediaElement.parentNode.replaceChild(placeholder, mediaElement);
            }
        },
        onDblClick: () => openViewer(),
        onTouchEnd: (e) => {
            const now = Date.now();
            if (now - lastTapTime < 300) {
                lastTapTime = 0;
                openViewer();
            } else {
                lastTapTime = now;
            }
        }
    });

    return mediaElement;
}

/**
 * Create a placeholder element for unknown or failed media
 * @param {Object} file - The file object
 * @param {string} type - The type of placeholder ('video', 'image', or undefined)
 * @returns {HTMLDivElement} - The created placeholder element
 */
export function createPlaceholderElement(file, type) {
    const mediaElement = createElement('div', {
        className: 'unknown-file-placeholder'
    });

    const iconDiv = createElement('div', {
        className: 'unknown-file-placeholder__icon',
        innerHTML: type === 'video' ? videoIcon(64) : type === 'image' ? imageIcon(64) : fileIcon(64)
    });

    const nameDiv = createElement('div', {
        textContent: file.displayName || file.name,
        className: 'unknown-file-placeholder__name'
    });

    const typeText = type === 'video' ? 'Video failed to load'
        : type === 'image' ? 'Image failed to load'
            : `Unsupported file type: ${file.type || 'unknown'}`;
    const typeDiv = createElement('div', {
        textContent: typeText,
        className: 'unknown-file-placeholder__meta'
    });

    const content = createElement('div', {
        className: 'unknown-file-placeholder__content',
        children: [iconDiv, nameDiv, typeDiv]
    });

    mediaElement.appendChild(content);

    return mediaElement;
}

/**
 * Update the media info overlay with current file information
 * @param {Object} file - The current media file object
 */
export function updateMediaInfoOverlay(file) {
    if (!file) return;

    const overlay = $('.media-info-overlay');
    if (!overlay) return;

    const filename = $('.filename', overlay);
    const metadata = $('.metadata', overlay);

    if (filename && metadata) {
        filename.textContent = file.displayName || file.name || 'Unknown file';

        let sizeText = '';
        if (file.size) {
            const sizeInMB = file.size / (1024 * 1024);
            sizeText = sizeInMB < 1 ?
                `${Math.round(sizeInMB * 1000) / 10} KB` :
                `${Math.round(sizeInMB * 10) / 10} MB`;
        }

        let dimensionsText = '';
        if (file.width && file.height) {
            dimensionsText = `${file.width} × ${file.height}`;
        }

        let dateText = '';
        if (file.date) {
            const date = new Date(file.date);
            dateText = date.toLocaleDateString();
        }

        const dimensionsSpan = $('.dimensions', metadata);
        const sizeSpan = $('.size', metadata);
        const dateSpan = $('.date', metadata);

        if (dimensionsSpan) dimensionsSpan.textContent = dimensionsText || 'Unknown dimensions';
        if (sizeSpan) sizeSpan.textContent = sizeText || 'Unknown size';
        if (dateSpan) dateSpan.textContent = dateText || 'Unknown date';
    }
}

/**
 * Create a subfolder card element for the Media Viewer swipe view.
 * Shown in place of broken subfolder file paths.
 * @param {Object} file - The subfolder marker object (isSubfolder=true)
 * @param {Function} onNavigate - Callback(categoryId, subfolderName) to navigate to subfolder
 * @returns {HTMLElement} The subfolder card element
 */
export function createSubfolderElement(file, onNavigate) {
    const container = createElement('div', { className: 'viewer-media subfolder-card-container' });

    const displayName = formatSubfolderName(file.subfolderName);
    const info = file.subfolderInfo || {};
    const count = info.count || 0;
    const fileLabel = count === 1 ? 'item' : 'items';
    const typeIcon = info.containsVideo ? videoIcon(20) : imageIcon(20);

    // Dynamic background if thumbnail is available
    if (file.thumbnailUrl) {
        const bg = createElement('div', {
            className: 'subfolder-swipe-bg',
            style: { backgroundImage: `url(${file.thumbnailUrl})` }
        });
        container.appendChild(bg);
    }

    const card = createElement('div', {
        className: 'subfolder-swipe-card',
        onClick: () => {
            if (onNavigate) {
                onNavigate(file.categoryId, file.subfolderName);
            }
        }
    },
        createElement('div', { className: 'subfolder-swipe-icon', innerHTML: folderIcon(72) }),
        createElement('div', { className: 'subfolder-swipe-name', textContent: displayName }),
        createElement('div', { className: 'subfolder-swipe-meta' },
            createElement('span', { innerHTML: typeIcon }),
            createElement('span', { textContent: ` ${count} ${fileLabel}` })
        ),
        createElement('button', {
            className: 'subfolder-swipe-btn',
            textContent: 'Browse Folder',
            onClick: (e) => {
                e.stopPropagation();
                if (onNavigate) {
                    onNavigate(file.categoryId, file.subfolderName);
                }
            }
        })
    );

    container.appendChild(card);

    return container;
}
