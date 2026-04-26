/**
 * Gallery Layout - Auto-Collapse Component
 * Improved auto-collapse logic with better viewport detection and timing
 */

import { getContainer } from '../state.js';
import { $, $$, Module } from '../../../../libs/ragot.esm.min.js';

let autoCollapseObserver = null;
let autoCollapseModule = null;
let isZooming = false;
const dateGroupState = new Map();

/**
 * Clear date group state (call on refresh/filter change)
 */
export function clearDateGroupState() {
    dateGroupState.clear();
}

/**
 * Get date group state
 */
export function getDateGroupState() {
    return dateGroupState;
}

/**
 * Set zooming flag (prevents auto-collapse during zoom)
 */
export function setIsZooming(value) {
    isZooming = value;
}

/**
 * Setup IntersectionObserver to auto-collapse expanded date groups when scrolling away
 * Improved with better viewport detection and timing
 */
export function setupAutoCollapseObserver(collapseCallback) {
    cleanupAutoCollapseObserver();

    const container = getContainer();
    const scrollArea = container ? $('.gallery-scroll-area', container) : null;
    if (!scrollArea) return;

    autoCollapseModule = new Module();
    autoCollapseModule.start();

    autoCollapseObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const dateKey = entry.target.dataset.date;
            const state = dateGroupState.get(dateKey);

            if (!entry.isIntersecting && state?.expanded && !isZooming) {
                autoCollapseModule.timeout(() => {
                    if (!entry.target.isConnected) return;
                    const stillExpanded = dateGroupState.get(dateKey)?.expanded;
                    if (!stillExpanded) return;

                    const rect = entry.target.getBoundingClientRect();
                    const scrollRect = scrollArea.getBoundingClientRect();
                    const margin = 200;
                    const isOutOfView =
                        rect.bottom < scrollRect.top - margin ||
                        rect.top > scrollRect.bottom + margin;

                    if (isOutOfView && collapseCallback) {
                        collapseCallback(dateKey);
                    }
                }, 800);
            }
        });
    }, {
        root: scrollArea,
        rootMargin: '-150px 0px',
        threshold: [0, 0.1]
    });

    autoCollapseModule.addCleanup(() => {
        if (autoCollapseObserver) {
            autoCollapseObserver.disconnect();
            autoCollapseObserver = null;
        }
    });

    $$('.gallery-date-group', container).forEach(group => {
        autoCollapseObserver.observe(group);
    });
}

/**
 * Cleanup auto-collapse observer
 */
export function cleanupAutoCollapseObserver() {
    if (autoCollapseModule) {
        autoCollapseModule.stop(); // also disconnects observer via addCleanup
        autoCollapseModule = null;
    }
    // Safety: in case cleanup is called before setup, or observer was set without module
    if (autoCollapseObserver) {
        autoCollapseObserver.disconnect();
        autoCollapseObserver = null;
    }
}
