/**
 * Streaming Layout - Row Components
 *
 * StreamingRowsComponent (Component)
 *   - Mounts into #streaming-content-container
 *   - State-driven via setState() but uses imperative row management internally.
 *   - Each category row is an interactive horizontal scroller built on VirtualScroller.
 *   - VirtualScroller handles bidirectional chunk loading, eviction, and sentinel
 *     lifecycle — no custom IO or sentinels in this file.
 *   - Per-row VirtualScroller instances are tracked in _rowVSes (keyed by row element)
 *     and unmounted on the next rebuild or component stop.
 */

import { calculateProgress } from '../../../utils/layoutUtils.js';
import { videoIcon, imageIcon, tvIcon, sparkleIcon, userIcon, usersIcon, folderFilledIcon } from '../../../utils/icons.js';
import { buildThumbnailPlaceholderLayerAttrs } from '../../../utils/mediaUtils.js';
import {
    getCategoryCache,
    getMediaFilter,
    getSubfolderFilter,
    getCategoryIdFilter,
} from './state.js';
import { loadMoreMedia } from './data.js';
import { observeLazyImage, primeLazyImage } from './lazyLoad.js';
import {
    createContinueWatchingCard,
    createMediaItemCard,
    createSubfolderCard,
    updateCardProgress,
    updateContinueWatchingCard
} from './cards.js';
import { isSubfolderFile } from '../../../utils/subfolderUtils.js';
import { Component, VirtualScroller, createElement, append, prepend, clear, renderList, $, $$ } from '../../../libs/ragot.esm.min.js';
import { handleSubfolderClick as _handleSubfolderClick } from '../shared/subfolderNavigation.js';

// ── Constants ─────────────────────────────────────────────────────────────────

const CARDS_PER_CHUNK = 20;
const MAX_CHUNKS = 5;
const ROW_SCROLL_AMOUNT = 400;
const ROW_PREFETCH_MULTIPLIER = 2;
const THUMB_PRIME_BUFFER_PX = 520;
// Pre-load well outside the visible edge so rows feel populated before the
// user lands on the next shelf segment.
const H_ROOT_MARGIN = '0px 1200px 0px 1200px';

export function shouldPrefetchNextChunk(scrollLeft, clientWidth, scrollWidth, multiplier = ROW_PREFETCH_MULTIPLIER) {
    return scrollLeft + clientWidth * multiplier >= scrollWidth;
}

export function isWithinPrimeWindow(rectLeft, rectRight, viewportWidth, bufferPx = THUMB_PRIME_BUFFER_PX) {
    return rectRight >= -bufferPx && rectLeft <= viewportWidth + bufferPx;
}

function createWhatsNewCard(media) {
    const card = createMediaItemCard(media, media.categoryId, 0, { forceEager: true });
    append(card, createElement('span', { className: 'streaming-card-category-badge', textContent: media.categoryName || '' }));
    return card;
}

// ── Header meta helpers ───────────────────────────────────────────────────────

function formatPathSegment(segment) {
    return String(segment || '').trim().replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function getRowHeaderMeta(category, activeSubfolderFilter) {
    const name = category?.name || '';

    if (activeSubfolderFilter) {
        const parts = activeSubfolderFilter.split('/').map(formatPathSegment).filter(Boolean);
        return {
            title: parts[parts.length - 1] || name,
            breadcrumbPath: [name, ...parts.slice(0, -1)].filter(Boolean).join(' > ') || null
        };
    }

    const parenMatch = name.match(/^(.+?)\s*\((.+)\)$/);
    if (parenMatch) {
        return { title: parenMatch[1].trim(), breadcrumbPath: parenMatch[2].trim() };
    }

    return { title: name, breadcrumbPath: null };
}

function filterMediaItems(mediaItems, mediaFilter) {
    if (!mediaFilter || mediaFilter === 'all') return mediaItems;
    return mediaItems.filter(m => {
        const type = m.type || (m.url?.match(/\.(mp4|webm|mkv|avi|mov)$/i) ? 'video' : 'image');
        return mediaFilter === 'video' ? type === 'video' : type === 'image';
    });
}

// ── Row shell factory ─────────────────────────────────────────────────────────

function buildRowShell(title, rowId, icon, count, activeUsers, categoryId, breadcrumbPath) {
    const countText = count === 1 ? '1 item' : `${count} items`;

    const leftBtn = createElement('button', {
        className: 'streaming-row-scroll-btn left at-start',
        'aria-label': 'Scroll left',
        innerHTML: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>'
    });
    const rightBtn = createElement('button', {
        className: 'streaming-row-scroll-btn right',
        'aria-label': 'Scroll right',
        innerHTML: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>'
    });
    const scrollContainer = createElement('div', { className: 'streaming-scroll-container' });

    const rowEl = createElement('div', {
        className: 'streaming-row',
        id: `row-${rowId}`,
        ...(categoryId ? { dataset: { categoryId } } : {})
    });

    append(rowEl,
        createElement('div', { className: 'streaming-row-header' },
            createElement('div', { className: 'streaming-row-title-group' },
                createElement('h2', { className: 'streaming-row-title' },
                    createElement('span', { className: 'row-icon', innerHTML: icon }),
                    createElement('span', { className: 'streaming-row-title-text', textContent: ` ${title} ` }),
                    createElement('span', { className: 'streaming-row-count', textContent: `(${countText})` }),
                    activeUsers > 0 ? createElement('span', {
                        className: 'streaming-row-activity',
                        innerHTML: `${activeUsers === 1 ? userIcon(14) : usersIcon(14)} ${activeUsers} watching`
                    }) : null
                ),
                breadcrumbPath ? createElement('div', { className: 'streaming-row-breadcrumb', title: breadcrumbPath },
                    createElement('span', { className: 'streaming-row-breadcrumb-icon', innerHTML: folderFilledIcon(12) }),
                    createElement('span', { className: 'streaming-row-breadcrumb-path', textContent: breadcrumbPath })
                ) : null
            ),
            categoryId ? createElement('div', { className: 'streaming-row-progress-container' }) : null
        ),
        leftBtn,
        scrollContainer,
        rightBtn
    );

    return { rowEl, scrollContainer, leftBtn, rightBtn };
}

function buildLoadingCard(index) {
    return createElement('div', {
        className: 'streaming-card streaming-card-skeleton',
        style: { '--card-index': index },
        'aria-hidden': 'true'
    },
        createElement('div', {
            className: 'streaming-card-thumb-wrap',
            dataset: { thumbnailHost: '' }
        },
            createElement('div', buildThumbnailPlaceholderLayerAttrs({
                className: 'streaming-card-skeleton-placeholder',
                state: 'pending'
            }))
        ),
        createElement('div', { className: 'streaming-card-info' },
            createElement('div', { className: 'streaming-card-title streaming-card-skeleton-line' }),
            createElement('div', { className: 'streaming-card-meta streaming-card-skeleton-line short' })
        )
    );
}

function buildLoadingRow(rowId, title, icon, cardCount = 6) {
    const { rowEl, scrollContainer } = buildRowShell(title, rowId, icon, cardCount, 0, null, null);
    for (let i = 0; i < cardCount; i++) {
        append(scrollContainer, buildLoadingCard(i));
    }
    return rowEl;
}

function getStateCache(categoryMediaCache, categoryId, subfolder = null, mediaFilter = 'all') {
    const key = `${categoryId}|sf:${subfolder || ''}|mf:${mediaFilter || 'all'}`;
    const direct = categoryMediaCache?.[key];
    if (direct) return direct;
    if (mediaFilter && mediaFilter !== 'all') {
        return categoryMediaCache?.[`${categoryId}|sf:${subfolder || ''}|mf:all`] || null;
    }
    return null;
}

function hasIndexingActivity(categoriesData, categoryMediaCache, mediaFilter, categoryIdFilter, subfolderFilter) {
    return (categoriesData || []).some((category) => {
        const activeSubfolder = (subfolderFilter && categoryIdFilter === category?.id) ? subfolderFilter : null;
        const cache = getStateCache(categoryMediaCache, category?.id, activeSubfolder, mediaFilter);
        return cache?.loading === true || cache?.asyncIndexing === true;
    });
}

// ── StreamingRowsComponent ────────────────────────────────────────────────────

export class StreamingRowsComponent extends Component {
    constructor() {
        super({
            categoriesData: [],
            continueWatchingData: [],
            whatsNewData: [],
            categoryMediaCache: {},
            videoProgressMap: {},
            continueWatchingLoading: false,
            whatsNewLoading: false,
            mediaFilter: 'all',
            categoryIdFilter: null,
            subfolderFilter: null,
            isLoading: true,
        });
        // Tracks VirtualScroller instances keyed by composite key
        // `${category.id}|${activeSubfolder || ''}` — stable across rebuilds.
        // Recycled (not unmounted) on _rebuildRows(); fully unmounted on stop.
        this._rowVSes = new Map();
        // Tracks AbortControllers for scroll button listeners on static rows
        // (CW, What's New) that don't use VirtualScroller.
        this._rowACs = new Map();
        this._rowPrefetches = new Map();
    }

    /**
     * render() builds the static container shell only.
     * Actual row content is managed imperatively in _rebuildRows().
     * This keeps render() pure (no side effects) per RAGOT contract.
     */
    render() {
        return createElement('div', { className: 'streaming-rows-root' });
    }

    /**
     * Override setState to drive imperative row management instead of morphDOM.
     * morphDOM on complex interactive rows causes IO leaks and scroll-position loss.
     * Suppresses card entry animation on state-driven refreshes (not initial mount).
     *
     * Optimization: when only secondary-row keys change (continueWatchingData,
     * whatsNewData) we patch just those rows in-place rather than tearing down
     * and rebuilding every VirtualScroller-backed category row. This prevents the
     * visible pop-in that happened when the viewer closed and triggered a CW refresh.
     */
    setState(newState) {
        const prev = this.state;
        this.state = { ...this.state, ...newState };
        if (!this.element || !this._isMounted) return;

        const changedKeys = Object.keys(newState);
        const secondaryOnlyKeys = new Set([
            'continueWatchingData',
            'whatsNewData',
            'continueWatchingLoading',
            'whatsNewLoading',
            'categoryMediaCache'
        ]);
        const isSecondaryOnly = changedKeys.length > 0 && changedKeys.every(k => secondaryOnlyKeys.has(k));

        if (isSecondaryOnly) {
            // Patch only the rows whose data actually changed, leaving VS category rows intact.
            // Pass the changed key set so _rebuildSecondaryRows skips untouched rows entirely.
            this._rebuildSecondaryRows(new Set(changedKeys));
            return;
        }

        this._rebuildRows();
    }

    onStart() {
        this._rebuildRows();

        // Delegated keyboard navigation for streaming cards (roving tabindex)
        this.on(this.element, 'keydown', (e) => {
            const card = e.target.closest('.streaming-card');
            if (!card) return;

            const scrollContainer = card.closest('.streaming-scroll-container');
            if (!scrollContainer) return;

            let target = null;

            if (e.key === 'ArrowRight') {
                target = card.nextElementSibling;
                while (target && !target.classList.contains('streaming-card')) {
                    target = target.nextElementSibling;
                }
            } else if (e.key === 'ArrowLeft') {
                target = card.previousElementSibling;
                while (target && !target.classList.contains('streaming-card')) {
                    target = target.previousElementSibling;
                }
            } else if (e.key === 'ArrowDown') {
                // Move to same position in the next row
                const row = scrollContainer.closest('.streaming-row');
                const nextRow = row?.nextElementSibling;
                if (nextRow) {
                    const nextCards = nextRow.querySelectorAll('.streaming-card');
                    const cards = scrollContainer.querySelectorAll('.streaming-card');
                    const idx = Array.prototype.indexOf.call(cards, card);
                    target = nextCards[Math.min(idx, nextCards.length - 1)] || null;
                }
            } else if (e.key === 'ArrowUp') {
                const row = scrollContainer.closest('.streaming-row');
                const prevRow = row?.previousElementSibling;
                if (prevRow) {
                    const prevCards = prevRow.querySelectorAll('.streaming-card');
                    const cards = scrollContainer.querySelectorAll('.streaming-card');
                    const idx = Array.prototype.indexOf.call(cards, card);
                    target = prevCards[Math.min(idx, prevCards.length - 1)] || null;
                }
            } else if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                card.click();
                return;
            }

            if (target) {
                e.preventDefault();
                card.setAttribute('tabindex', '-1');
                target.setAttribute('tabindex', '0');
                target.focus();
                target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
            }
        });
    }

    onStop() {
        this._destroyAllRows();
    }

    // ── Private: row management ───────────────────────────────────────────────

    _destroyAllRows() {
        for (const vs of this._rowVSes.values()) {
            try { vs.unmount(); } catch (_) { /* ignore */ }
        }
        this._rowVSes.clear();
        for (const ac of this._rowACs.values()) {
            try { ac.abort(); } catch (_) { /* ignore */ }
        }
        this._rowACs.clear();
        this._rowPrefetches.clear();
    }

    _findCategoryRow(categoryId) {
        return $$(`.streaming-row[data-category-id]`, this.element)
            .find((rowEl) => rowEl?.dataset?.categoryId === String(categoryId)) || null;
    }

    _cleanupCategoryRow(categoryId, activeSubfolder, rowEl = null) {
        const targetRow = rowEl || this._findCategoryRow(categoryId);
        if (targetRow) {
            const ac = this._rowACs.get(targetRow);
            if (ac) {
                try { ac.abort(); } catch (_) { /* ignore */ }
                this._rowACs.delete(targetRow);
            }
            targetRow.remove();
        }

        const vsKey = `${categoryId}|${activeSubfolder || ''}`;
        const vs = this._rowVSes.get(vsKey);
        if (vs) {
            try { vs.unmount(); } catch (_) { /* ignore */ }
            this._rowVSes.delete(vsKey);
        }
    }

    refreshCategoryRow(categoryId) {
        if (!this.element || !categoryId) return false;

        const { categoriesData, mediaFilter, categoryIdFilter, subfolderFilter } = this.state;
        const categoryIndex = (categoriesData || []).findIndex((category) => category?.id === categoryId);
        if (categoryIndex < 0) return false;

        const category = categoriesData[categoryIndex];
        const activeSubfolder = (subfolderFilter && categoryIdFilter === category.id) ? subfolderFilter : null;
        const existingRow = this._findCategoryRow(categoryId);
        const savedScrollLeft = existingRow?.querySelector('.streaming-scroll-container')?.scrollLeft || 0;

        let insertBeforeNode = existingRow?.nextElementSibling || null;
        if (!insertBeforeNode) {
            for (let i = categoryIndex + 1; i < categoriesData.length; i++) {
                const nextRow = this._findCategoryRow(categoriesData[i]?.id);
                if (nextRow) {
                    insertBeforeNode = nextRow;
                    break;
                }
            }
        }

        this._cleanupCategoryRow(category.id, activeSubfolder, existingRow);

        const rowEl = this._buildCategoryRow(
            category,
            categoryIndex,
            mediaFilter,
            categoryIdFilter,
            subfolderFilter,
            insertBeforeNode
        );

        if (rowEl && savedScrollLeft > 0) {
            requestAnimationFrame(() => {
                const scrollContainer = rowEl.querySelector('.streaming-scroll-container');
                if (scrollContainer) scrollContainer.scrollLeft = savedScrollLeft;
            });
        }

        return !!rowEl;
    }

    _rebuildRows() {
        if (!this.element) return;

        const {
            categoriesData,
            continueWatchingData,
            whatsNewData,
            categoryMediaCache,
            continueWatchingLoading,
            whatsNewLoading,
            mediaFilter,
            categoryIdFilter,
            subfolderFilter,
            isLoading
        } = this.state;
        const showContinueWatchingLoading = (!continueWatchingData || continueWatchingData.length === 0) && continueWatchingLoading === true;
        const showWhatsNewLoading = (!whatsNewData || whatsNewData.length === 0)
            && (whatsNewLoading === true || hasIndexingActivity(categoriesData, categoryMediaCache, mediaFilter, categoryIdFilter, subfolderFilter));

        // Save horizontal scroll positions of existing rows before tearing down
        const savedScrolls = new Map();
        this.element.querySelectorAll('.streaming-row[id]').forEach(rowEl => {
            const sc = rowEl.querySelector('.streaming-scroll-container');
            if (sc && sc.scrollLeft > 0) savedScrolls.set(rowEl.id, sc.scrollLeft);
        });

        // Abort scroll button listeners — these are always re-wired to new DOM
        for (const ac of this._rowACs.values()) {
            try { ac.abort(); } catch (_) { /* ignore */ }
        }
        this._rowACs.clear();

        // Compute which VS keys will be needed in this rebuild so we can
        // recycle survivors and unmount stale ones after the DOM is rebuilt.
        const nextVSKeys = new Set();
        if (categoriesData) {
            for (const cat of categoriesData) {
                const activeSf = (subfolderFilter && categoryIdFilter === cat.id) ? subfolderFilter : null;
                nextVSKeys.add(`${cat.id}|${activeSf || ''}`);
            }
        }

        // Recycle VS elements out of the DOM before we clear the container.
        // recycle() strips chunks and detaches this.element — the sentinel
        // wrapper is kept in memory for reuse by _buildCategoryRow.
        for (const [key, vs] of this._rowVSes) {
            if (nextVSKeys.has(key)) {
                try { vs.recycle(); } catch (_) { /* ignore */ }
            } else {
                try { vs.unmount(); } catch (_) { /* ignore */ }
                this._rowVSes.delete(key);
            }
        }

        clear(this.element);

        // Continue Watching — fresh row, renderList seeds _listKey for _rebuildSecondaryRows patching
        if (continueWatchingData && continueWatchingData.length > 0) {
            const { rowEl, scrollContainer } = buildRowShell('Continue Watching', 'continue-watching', tvIcon(16), continueWatchingData.length, 0, null, null);
            renderList(
                scrollContainer,
                continueWatchingData,
                item => item.videoUrl,
                item => createContinueWatchingCard(item),
                updateContinueWatchingCard
            );
            this._wireScrollButtons(rowEl);
            prepend(this.element, rowEl);
        } else if (showContinueWatchingLoading) {
            prepend(this.element, buildLoadingRow('continue-watching', 'Continue Watching', tvIcon(16), 4));
        }

        // What's New — fresh row, renderList seeds _listKey
        if (whatsNewData && whatsNewData.length > 0) {
            const { rowEl, scrollContainer } = buildRowShell("What's New", 'whats-new', sparkleIcon(16), whatsNewData.length, 0, null, null);
            renderList(scrollContainer, whatsNewData, media => media.url, createWhatsNewCard);
            this._wireScrollButtons(rowEl);
            const cw = this.element.querySelector('#row-continue-watching');
            if (cw) cw.after(rowEl);
            else prepend(this.element, rowEl);
        } else if (showWhatsNewLoading) {
            const loadingRow = buildLoadingRow('whats-new', "What's New", sparkleIcon(16), 4);
            const cw = this.element.querySelector('#row-continue-watching');
            if (cw) cw.after(loadingRow);
            else prepend(this.element, loadingRow);
        }

        // Category rows — paginated via VirtualScroller
        if (categoriesData && categoriesData.length > 0) {
            categoriesData.forEach((cat, i) => {
                this._buildCategoryRow(cat, i, mediaFilter, categoryIdFilter, subfolderFilter);
            });
        } else if (isLoading) {
            append(this.element, buildLoadingRow('loading-0', 'Loading Library', sparkleIcon(16)));
            append(this.element, buildLoadingRow('loading-1', 'Loading Shows', tvIcon(16)));
            append(this.element, buildLoadingRow('loading-2', 'Loading Movies', videoIcon(16)));
        } else if (!isLoading) {
            append(this.element, createElement('div', { className: 'streaming-no-media' },
                createElement('p', { className: 'streaming-no-media-title', textContent: 'No media yet' }),
                createElement('p', { className: 'streaming-no-media-sub', textContent: 'Add a media folder in the admin panel to get started.' })
            ));
        }

        // Restore scroll positions after paint
        if (savedScrolls.size > 0) {
            requestAnimationFrame(() => {
                savedScrolls.forEach((scrollLeft, rowId) => {
                    const rowEl = document.getElementById(rowId);
                    if (!rowEl) return;
                    const sc = rowEl.querySelector('.streaming-scroll-container');
                    if (sc) sc.scrollLeft = scrollLeft;
                });
            });
        }
    }

    /**
     * Surgically rebuild only the rows whose data actually changed, without touching
     * any VirtualScroller-backed category rows.
     *
     * @param {Set<string>} changedKeys - Which state keys changed (e.g. Set{'continueWatchingData'})
     */
    _rebuildSecondaryRows(changedKeys = new Set(['continueWatchingData', 'whatsNewData'])) {
        if (!this.element) return;
        const {
            categoriesData,
            continueWatchingData,
            whatsNewData,
            categoryMediaCache,
            continueWatchingLoading,
            whatsNewLoading,
            mediaFilter,
            categoryIdFilter,
            subfolderFilter
        } = this.state;
        const showContinueWatchingLoading = (!continueWatchingData || continueWatchingData.length === 0) && continueWatchingLoading === true;
        const showWhatsNewLoading = (!whatsNewData || whatsNewData.length === 0)
            && (whatsNewLoading === true || hasIndexingActivity(categoriesData, categoryMediaCache, mediaFilter, categoryIdFilter, subfolderFilter));

        // ── Continue Watching ──
        if (changedKeys.has('continueWatchingData') || changedKeys.has('continueWatchingLoading')) {
            const existingCW = this.element.querySelector('#row-continue-watching');
            if (continueWatchingData && continueWatchingData.length > 0) {
                const sc = existingCW?.querySelector('.streaming-scroll-container');
                // Only patch in place when the row already has real (keyed) cards.
                // A loading row has skeleton cards with no _listKey — renderList would
                // leave the skeletons in place and append real cards behind them.
                const hasRealCards = sc && !sc.querySelector('.streaming-card-skeleton');
                if (hasRealCards) {
                    renderList(
                        sc,
                        continueWatchingData,
                        item => item.videoUrl,
                        item => createContinueWatchingCard(item),
                        updateContinueWatchingCard
                    );
                } else {
                    if (existingCW) existingCW.remove();
                    const { rowEl, scrollContainer } = buildRowShell(
                        'Continue Watching', 'continue-watching', tvIcon(16), continueWatchingData.length, 0, null, null
                    );
                    renderList(
                        scrollContainer,
                        continueWatchingData,
                        item => item.videoUrl,
                        item => createContinueWatchingCard(item),
                        updateContinueWatchingCard
                    );
                    this._wireScrollButtons(rowEl);
                    prepend(this.element, rowEl);
                }
            } else {
                if (existingCW) existingCW.remove();
                if (showContinueWatchingLoading) {
                    prepend(this.element, buildLoadingRow('continue-watching', 'Continue Watching', tvIcon(16), 4));
                }
            }
        }

        // ── What's New ──
        if (changedKeys.has('whatsNewData') || changedKeys.has('whatsNewLoading') || changedKeys.has('categoryMediaCache')) {
            const existingWN = this.element.querySelector('#row-whats-new');
            if (whatsNewData && whatsNewData.length > 0) {
                const sc = existingWN?.querySelector('.streaming-scroll-container');
                const hasRealCards = sc && !sc.querySelector('.streaming-card-skeleton');
                if (hasRealCards) {
                    renderList(sc, whatsNewData, media => media.url, media => {
                        const card = createMediaItemCard(media, media.categoryId, 0, { forceEager: true });
                        append(card, createElement('span', { className: 'streaming-card-category-badge', textContent: media.categoryName || '' }));
                        return card;
                    });
                } else {
                    if (existingWN) existingWN.remove();
                    const { rowEl, scrollContainer } = buildRowShell(
                        "What's New", 'whats-new', sparkleIcon(16), whatsNewData.length, 0, null, null
                    );
                    renderList(scrollContainer, whatsNewData, media => media.url, media => {
                        const card = createMediaItemCard(media, media.categoryId, 0, { forceEager: true });
                        append(card, createElement('span', { className: 'streaming-card-category-badge', textContent: media.categoryName || '' }));
                        return card;
                    });
                    this._wireScrollButtons(rowEl);
                    const cw = this.element.querySelector('#row-continue-watching');
                    if (cw) cw.after(rowEl);
                    else prepend(this.element, rowEl);
                }
            } else {
                if (existingWN) existingWN.remove();
                if (showWhatsNewLoading) {
                    const loadingRow = buildLoadingRow('whats-new', "What's New", sparkleIcon(16), 4);
                    const cw = this.element.querySelector('#row-continue-watching');
                    if (cw) cw.after(loadingRow);
                    else prepend(this.element, loadingRow);
                }
            }
        }
    }

    /**
     * Wire scroll left/right buttons for static rows (CW, What's New).
     * These rows have all cards rendered upfront — no VirtualScroller needed.
     */
    _wireScrollButtons(rowEl) {
        const scrollContainer = rowEl.querySelector('.streaming-scroll-container');
        const leftBtn = rowEl.querySelector('.streaming-row-scroll-btn.left');
        const rightBtn = rowEl.querySelector('.streaming-row-scroll-btn.right');
        if (!scrollContainer || !leftBtn || !rightBtn) return;

        const ac = new AbortController();
        const { signal } = ac;
        this._rowACs.set(rowEl, ac);

        const updateButtons = () => {
            const { scrollLeft, scrollWidth, clientWidth } = scrollContainer;
            leftBtn.classList.toggle('at-start', scrollLeft <= 0);
            rightBtn.classList.toggle('at-end', scrollWidth - clientWidth - scrollLeft <= 1);
        };

        scrollContainer.addEventListener('scroll', updateButtons, { passive: true, signal });
        leftBtn.addEventListener('click', () => scrollContainer.scrollBy({ left: -ROW_SCROLL_AMOUNT, behavior: 'smooth' }), { signal });
        rightBtn.addEventListener('click', () => scrollContainer.scrollBy({ left: ROW_SCROLL_AMOUNT, behavior: 'smooth' }), { signal });
        requestAnimationFrame(updateButtons);
    }

    _primeVisibleRowThumbnails(scrollContainer) {
        if (!scrollContainer) return;
        const viewportWidth = scrollContainer.clientWidth || window.innerWidth || 0;
        $$('img.streaming-card-thumbnail[data-src]', scrollContainer).forEach((img) => {
            const rect = img.getBoundingClientRect();
            if (!isWithinPrimeWindow(rect.left, rect.right, viewportWidth)) return;
            primeLazyImage(img, { fetchPriority: rect.left >= 0 && rect.right <= viewportWidth ? 'high' : 'auto' });
        });
    }

    _prefetchNextRowPage(vsKey, categoryId) {
        if (!categoryId) return;
        if (this._rowPrefetches.has(vsKey)) return;

        const job = loadMoreMedia(categoryId)
            .catch(() => [])
            .finally(() => {
                this._rowPrefetches.delete(vsKey);
            });

        this._rowPrefetches.set(vsKey, job);
    }

    _buildCategoryRow(category, rowOrder, mediaFilter, categoryIdFilter, subfolderFilter, insertBeforeNode = null) {
        const activeSubfolder = (subfolderFilter && categoryIdFilter === category.id) ? subfolderFilter : null;
        const mountRow = (rowEl) => {
            if (insertBeforeNode && insertBeforeNode.parentNode === this.element) {
                this.element.insertBefore(rowEl, insertBeforeNode);
                return;
            }
            append(this.element, rowEl);
        };

        // The API never filters by media type — it always returns all items.
        // Fall back to the mf:all cache entry if a filter-specific key is missing
        // so filterMediaItems() below can do client-side filtering correctly.
        const cache = getCategoryCache(category.id, activeSubfolder, mediaFilter)
            || (mediaFilter && mediaFilter !== 'all' ? getCategoryCache(category.id, activeSubfolder, 'all') : null);
        const rawMedia = cache?.media || [];
        const subfolders = cache?.subfolders || [];

        const filtered = filterMediaItems(rawMedia, mediaFilter);
        const directItems = activeSubfolder
            ? filtered
            : (subfolders.length > 0 ? filtered.filter(m => !isSubfolderFile(m)) : filtered);

        // When a media-type filter is active, skip rows that have nothing to show
        // (no matching direct items and no subfolders). Without this guard the row
        // renders as an empty placeholder shell with a VirtualScroller that has 0 items.
        if (mediaFilter && mediaFilter !== 'all' && directItems.length === 0 && subfolders.length === 0) {
            return null;
        }

        const hasVideos = filtered.some(m => m.type === 'video') ||
            category.containsVideo === true ||
            subfolders.some(sf => sf.contains_video);

        const icon = hasVideos ? videoIcon(18) : imageIcon(18);
        const { title, breadcrumbPath } = getRowHeaderMeta(category, activeSubfolder);
        const count = directItems.length + subfolders.length;

        const { rowEl, scrollContainer, leftBtn, rightBtn } = buildRowShell(
            title,
            `category-${category.id}`,
            icon,
            count,
            category.active_users || 0,
            category.id,
            breadcrumbPath
        );

        if (count === 0 && (cache?.loading === true || cache?.asyncIndexing === true)) {
            mountRow(rowEl);
            for (let i = 0; i < 3; i++) {
                append(scrollContainer, buildLoadingCard(i));
            }
            leftBtn.classList.add('at-start');
            rightBtn.classList.add('at-end');
            return rowEl;
        }

        // Append to the rows root FIRST so that elements are in the document
        // before we mount/rebind components like VirtualScroller. This avoids
        // the [RAGOT] mount-to-detached warning.
        mountRow(rowEl);

        const subfolderCards = subfolders.map((sf, idx) =>
            createSubfolderCard(
                { name: sf.name, count: sf.count, containsVideo: sf.contains_video, thumbnailUrl: sf.thumbnail_url || null, categoryId: category.id },
                (cId, sfName) => _handleSubfolderClick(cId, sfName, getSubfolderFilter, getCategoryIdFilter),
                idx
            )
        );

        // Subfolder cards are always visible — prepend them directly into the scroll
        // container outside the VS chunk system so they're never evicted.
        subfolderCards.forEach(card => append(scrollContainer, card));
        const sfCount = subfolderCards.length;

        // Total items known so far (may grow as more pages are fetched)
        const knownTotal = directItems.length;
        const hasMore = cache?.hasMore ?? false;

        // Stable key for this row — survives DOM rebuilds across setState() calls.
        const vsKey = `${category.id}|${activeSubfolder || ''}`;

        // Data-dependent options rebuilt on every render so closures are fresh.
        const liveOptions = {
            chunkContainer: scrollContainer,
            root: scrollContainer,
            totalItems: () => {
                // Re-read cache on every IO check so newly fetched pages expand the window
                const mf = getMediaFilter();
                const fresh = getCategoryCache(category.id, activeSubfolder, mf)
                    || (mf && mf !== 'all' ? getCategoryCache(category.id, activeSubfolder, 'all') : null);
                if (!fresh) return knownTotal;
                const total = fresh.media ? filterMediaItems(
                    activeSubfolder ? fresh.media : (fresh.subfolders?.length > 0 ? fresh.media.filter(m => !isSubfolderFile(m)) : fresh.media),
                    getMediaFilter()
                ).length : knownTotal;
                return fresh.hasMore ? total + CARDS_PER_CHUNK : total;
            },
            renderChunk: async (chunkIndex) => {
                const items = await this._getChunkItems(
                    chunkIndex, category.id, activeSubfolder, directItems, cache
                );
                if (!items || items.length === 0) return null;

                // display:contents makes the wrapper transparent to flex — cards
                // appear as direct children of scrollContainer for layout purposes.
                const chunk = createElement('div', { style: { display: 'contents' } });
                items.forEach((media, idx) => {
                    const globalIdx = sfCount + chunkIndex * CARDS_PER_CHUNK + idx;
                    const card = createMediaItemCard(media, category.id, globalIdx, {
                        forceEager: rowOrder < 3 && chunkIndex === 0 && idx < 6
                    });
                    append(chunk, card);
                });

                // Observe any lazy images in this chunk
                $$('img[data-src]', chunk).forEach(img => observeLazyImage(img));
                return chunk;
            },
        };

        let vs = this._rowVSes.get(vsKey);
        if (vs) {
            // Recycled instance — sentinels are detached but preserved.
            // rebind() reattaches into the new scrollContainer and reconnects IO.
            vs.rebind(liveOptions, scrollContainer);
        } else {
            // First time for this category+subfolder combination.
            vs = new VirtualScroller({
                ...liveOptions,
                rootMargin: H_ROOT_MARGIN,
                chunkSize: CARDS_PER_CHUNK,
                maxChunks: MAX_CHUNKS,
                childPoolSize: MAX_CHUNKS,
                initialChunks: 1,
                // display:contents means offsetWidth/Height = 0 — measure card widths
                measureChunk: (el) => {
                    let w = 0;
                    for (const card of el.children) {
                        const style = getComputedStyle(card);
                        w += card.offsetWidth
                            + parseFloat(style.marginLeft || 0)
                            + parseFloat(style.marginRight || 0);
                    }
                    return w;
                },
                // Width-preserving inline flex spacer (not a block that would break flex row)
                buildPlaceholder: (_i, px) => createElement('div', {
                    style: `flex:none;width:${px}px;height:1px;pointer-events:none`
                }),
            });
            // VS mounts its sentinel container into scrollContainer.
            // The vs-container gets display:contents from CSS so it's layout-transparent.
            vs.mount(scrollContainer);
        }
        this._rowVSes.set(vsKey, vs);

        // Wire scroll buttons — must happen after VS mounts so scrollWidth is accurate
        const updateButtons = () => {
            const { scrollLeft, scrollWidth, clientWidth } = scrollContainer;
            leftBtn.classList.toggle('at-start', scrollLeft <= 0);
            rightBtn.classList.toggle('at-end', scrollWidth - clientWidth - scrollLeft <= 1);
            this._primeVisibleRowThumbnails(scrollContainer);
            if (shouldPrefetchNextChunk(scrollLeft, clientWidth, scrollWidth) && (getCategoryCache(category.id, activeSubfolder, getMediaFilter())?.hasMore ?? false)) {
                this._prefetchNextRowPage(vsKey, category.id);
            }
        };
        const ac = new AbortController();
        const { signal } = ac;
        this._rowACs.set(rowEl, ac);
        scrollContainer.addEventListener('scroll', updateButtons, { passive: true, signal });
        leftBtn.addEventListener('click', () => scrollContainer.scrollBy({ left: -ROW_SCROLL_AMOUNT, behavior: 'smooth' }), { signal });
        rightBtn.addEventListener('click', () => scrollContainer.scrollBy({ left: ROW_SCROLL_AMOUNT, behavior: 'smooth' }), { signal });
        requestAnimationFrame(() => {
            updateButtons();
            this._primeVisibleRowThumbnails(scrollContainer);
            if (rowOrder < 2 && (getCategoryCache(category.id, activeSubfolder, getMediaFilter())?.hasMore ?? hasMore)) {
                this._prefetchNextRowPage(vsKey, category.id);
            }
        });

        return rowEl;
    }

    /**
     * Return the items for a given chunk index, fetching from the API if needed.
     * First chunk uses already-fetched cache data; subsequent chunks trigger loadMoreMedia.
     */
    async _getChunkItems(chunkIndex, categoryId, activeSubfolder, initialItems, initialCache) {
        const start = chunkIndex * CARDS_PER_CHUNK;
        const end = start + CARDS_PER_CHUNK;

        // Read current cache — may have grown from previous chunk loads.
        // Fall back to mf:all since the API always returns unfiltered items.
        const mf = getMediaFilter();
        const cache = getCategoryCache(categoryId, activeSubfolder, mf)
            || (mf && mf !== 'all' ? getCategoryCache(categoryId, activeSubfolder, 'all') : null)
            || initialCache;
        const allMedia = cache?.media || initialItems;
        const filtered = filterMediaItems(
            activeSubfolder ? allMedia : (cache?.subfolders?.length > 0 ? allMedia.filter(m => !isSubfolderFile(m)) : allMedia),
            getMediaFilter()
        );

        // If we already have enough items in cache, slice directly
        if (filtered.length > start) {
            return filtered.slice(start, end);
        }

        // Need more from the API
        if (!cache?.hasMore) return [];

        const newMedia = await loadMoreMedia(categoryId);
        if (!newMedia || newMedia.length === 0) return [];

        // Re-read cache after fetch
        const fresh = getCategoryCache(categoryId, activeSubfolder, mf)
            || (mf && mf !== 'all' ? getCategoryCache(categoryId, activeSubfolder, 'all') : null)
            || cache;
        const freshAll = fresh?.media || allMedia;
        const freshFiltered = filterMediaItems(
            activeSubfolder ? freshAll : (fresh?.subfolders?.length > 0 ? freshAll.filter(m => !isSubfolderFile(m)) : freshAll),
            getMediaFilter()
        );
        return freshFiltered.slice(start, end);
    }
}

// ── Progress bar helpers ──────────────────────────────────────────────────────

const _progressBarRAF = (() => {
    let rafId = null;
    return {
        schedule() {
            if (rafId) return;
            rafId = requestAnimationFrame(() => { rafId = null; _updateProgressNow(); });
        },
        cancel() {
            if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
        }
    };
})();

export function updateMediaCardProgressBars() { _progressBarRAF.schedule(); }
export function cancelMediaCardProgressBars() { _progressBarRAF.cancel(); }

function _updateProgressNow() {
    const container = document.getElementById('streaming-container');
    if (!container) return;
    const vpm = window.ragotModules?.streamingLayout?._getVideoProgressMap?.() || {};
    container.querySelectorAll('.streaming-card[data-media-url][data-media-type="video"]').forEach(card => {

        const url = card.dataset.mediaUrl;
        if (!url) return;
        let p = vpm[url];
        if (!p) { try { p = vpm[encodeURI(url)]; } catch (_) { /* ignore */ } }
        if (!p) { try { p = vpm[decodeURIComponent(url)]; } catch (_) { /* ignore */ } }
        if (p && p.video_timestamp > 0 && p.video_duration > 0) {
            updateCardProgress(card, calculateProgress(p.video_timestamp, p.video_duration));
        }
    });
}
