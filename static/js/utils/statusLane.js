/**
 * statusLane.js
 * Shared persistent bottom status lane for long-running app work.
 *
 * This is intentionally separate from transient toast notifications:
 * - toasts are short-lived confirmations/errors
 * - the status lane is for ongoing background work like indexing or thumbnail generation
 */

import { createElement } from '../libs/ragot.esm.min.js';

const DEFAULT_PRIORITY = 100;
const LIBRARY_PROCESSING_GROUP = 'library-processing';

let laneElement = null;
const statusEntries = new Map();

function hasDomRoot() {
    return typeof document !== 'undefined' && !!document.body;
}

function ensureLaneElement() {
    if (!hasDomRoot()) return null;
    if (laneElement && laneElement.isConnected) return laneElement;

    laneElement = createElement('div', {
        id: 'gh-status-lane',
        className: 'gh-status-lane',
        role: 'status',
        'aria-live': 'polite',
        hidden: true
    }, [
        createElement('div', { className: 'gh-status-lane__icon', 'aria-hidden': 'true' }),
        createElement('div', { className: 'gh-status-lane__body' }, [
            createElement('div', { className: 'gh-status-lane__title' }),
            createElement('div', { className: 'gh-status-lane__meta' })
        ])
    ]);

    document.body.appendChild(laneElement);
    return laneElement;
}

function isVisibleElement(element) {
    if (!element) return false;
    if (element.hidden) return false;
    const computed = window.getComputedStyle ? window.getComputedStyle(element) : null;
    if (!computed) return true;
    return computed.display !== 'none' && computed.visibility !== 'hidden';
}

function shouldRenderOnHomeScreen() {
    const mediaViewer = document.getElementById('media-viewer');
    if (mediaViewer && !mediaViewer.classList.contains('hidden')) return false;

    const expandedChat = document.querySelector('#chat-container.expanded');
    if (expandedChat) return false;

    const searchDropdown = document.getElementById('gh-search');
    if (isVisibleElement(searchDropdown)) return false;

    const dialogOverlay = document.getElementById('dialog-overlay');
    if (dialogOverlay?.classList.contains('gh-dialog-overlay--visible')) return false;

    const tvModal = document.getElementById('tv-player-modal');
    if (tvModal?.classList.contains('visible')) return false;

    return true;
}

function mergeLibraryProcessingGroup(entries) {
    const indexingEntry = entries.find((entry) => entry.key === 'library-indexing');
    const thumbnailEntry = entries.find((entry) => entry.key === 'thumbnail-generation');

    if (indexingEntry && thumbnailEntry) {
        return {
            key: LIBRARY_PROCESSING_GROUP,
            title: 'Preparing library',
            meta: [indexingEntry.meta, thumbnailEntry.meta].filter(Boolean).join(' • '),
            tone: indexingEntry.tone || thumbnailEntry.tone || 'info',
            busy: indexingEntry.busy !== false || thumbnailEntry.busy !== false,
            priority: Math.min(indexingEntry.priority ?? DEFAULT_PRIORITY, thumbnailEntry.priority ?? DEFAULT_PRIORITY),
            updatedAt: Math.max(indexingEntry.updatedAt || 0, thumbnailEntry.updatedAt || 0)
        };
    }

    return entries[0] || null;
}

function mergeGroupEntries(entries) {
    if (!entries || entries.length === 0) return null;
    const groupName = entries[0].group;

    if (groupName === LIBRARY_PROCESSING_GROUP) {
        return mergeLibraryProcessingGroup(entries);
    }

    const sorted = [...entries].sort((a, b) => {
        const priorityDelta = (a.priority ?? DEFAULT_PRIORITY) - (b.priority ?? DEFAULT_PRIORITY);
        if (priorityDelta !== 0) return priorityDelta;
        return (b.updatedAt || 0) - (a.updatedAt || 0);
    });

    return sorted[0];
}

function getTopEntry() {
    const entries = Array.from(statusEntries.values());
    if (entries.length === 0) return null;

    const groupedEntries = new Map();
    entries.forEach((entry) => {
        const groupKey = entry.group || entry.key;
        if (!groupedEntries.has(groupKey)) {
            groupedEntries.set(groupKey, []);
        }
        groupedEntries.get(groupKey).push(entry);
    });

    const mergedGroups = Array.from(groupedEntries.values())
        .map((group) => mergeGroupEntries(group))
        .filter(Boolean);

    mergedGroups.sort((a, b) => {
        const priorityDelta = (a.priority ?? DEFAULT_PRIORITY) - (b.priority ?? DEFAULT_PRIORITY);
        if (priorityDelta !== 0) return priorityDelta;
        return (b.updatedAt || 0) - (a.updatedAt || 0);
    });

    return mergedGroups[0];
}

function renderLane() {
    const lane = ensureLaneElement();
    if (!lane) return;

    const topEntry = getTopEntry();
    if (!topEntry) {
        lane.hidden = true;
        lane.className = 'gh-status-lane';
        return;
    }

    if (!shouldRenderOnHomeScreen()) {
        lane.hidden = true;
        lane.className = 'gh-status-lane';
        return;
    }

    const titleEl = lane.querySelector('.gh-status-lane__title');
    const metaEl = lane.querySelector('.gh-status-lane__meta');
    const iconEl = lane.querySelector('.gh-status-lane__icon');

    lane.hidden = false;
    lane.className = `gh-status-lane gh-status-lane--${topEntry.tone || 'info'}${topEntry.busy ? ' is-busy' : ''}`;

    if (titleEl) titleEl.textContent = topEntry.title || '';
    if (metaEl) {
        metaEl.textContent = topEntry.meta || '';
        metaEl.hidden = !topEntry.meta;
    }
    if (iconEl) {
        iconEl.className = `gh-status-lane__icon gh-status-lane__icon--${topEntry.busy ? 'busy' : 'idle'}`;
    }
}

export function showStatusLane(key, options = {}) {
    if (!key) {
        throw new Error('statusLane key is required');
    }

    statusEntries.set(key, {
        key,
        group: options.group || null,
        title: options.title || '',
        meta: options.meta || '',
        tone: options.tone || 'info',
        busy: options.busy !== false,
        priority: Number.isFinite(options.priority) ? options.priority : DEFAULT_PRIORITY,
        updatedAt: Date.now()
    });

    renderLane();
}

export function hideStatusLane(key) {
    if (!key) return;
    statusEntries.delete(key);
    renderLane();
}

export function clearStatusLane() {
    statusEntries.clear();
    renderLane();
}

export function getStatusLaneSnapshot() {
    return Array.from(statusEntries.values()).map((entry) => ({ ...entry }));
}
