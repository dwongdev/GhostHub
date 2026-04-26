/**
 * Thumbnail progress UI helpers currently used by streaming cards.
 *
 * The older generic overlay/badge/autopoll helpers were unused in the app and
 * had drifted into legacy surface area. Keep this module focused on the simple
 * inline progress bar that streaming still renders for pending thumbnails.
 */

import { createElement, show, hide, $ } from '../../libs/ragot.esm.min.js';

function getProgressColor(progress) {
    if (progress > 70) return '#4ade80';
    if (progress > 30) return '#fbbf24';
    return '#fb923c';
}

export function createSimpleProgressBar(options = {}) {
    const { categoryId, showPercentage = true } = options;

    if (!categoryId) {
        throw new Error('categoryId is required');
    }

    return createElement('div', {
        className: 'thumbnail-simple-progress hidden',
        dataset: { categoryId },
        innerHTML: `
            <div class="progress-bar-track">
                <div class="progress-bar-fill" style="width: 0%;"></div>
            </div>
            ${showPercentage ? '<div class="progress-percentage">0%</div>' : ''}
        `
    });
}

export function updateSimpleProgressBar(progressBar, status) {
    if (!progressBar) {
        console.warn('[ThumbnailProgressUI] No progress bar element provided');
        return;
    }

    const { status: state, progress = 0 } = status;

    if (state === 'generating') {
        show(progressBar);
        progressBar.classList.remove('pending');

        const fill = $('.progress-bar-fill', progressBar);
        if (fill) {
            fill.style.width = `${progress}%`;
            fill.style.backgroundColor = getProgressColor(progress);
        }

        const percentageText = $('.progress-percentage', progressBar);
        if (percentageText) {
            show(percentageText);
            percentageText.textContent = `${progress}%`;
        }
        return;
    }

    if (state === 'pending') {
        show(progressBar);
        progressBar.classList.add('pending');

        const fill = $('.progress-bar-fill', progressBar);
        if (fill) {
            fill.style.width = '100%';
            fill.style.backgroundColor = '#666';
        }

        const percentageText = $('.progress-percentage', progressBar);
        if (percentageText) hide(percentageText);
        return;
    }

    if (state === 'complete' || state === 'idle') {
        hide(progressBar);
        progressBar.classList.remove('pending');
    }
}
