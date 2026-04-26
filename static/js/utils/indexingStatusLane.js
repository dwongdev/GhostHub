import { showStatusLane, hideStatusLane } from './statusLane.js';

const INDEXING_STATUS_KEY = 'library-indexing';

export function showIndexingStatus(progress = null, options = {}) {
    const safeProgress = Number.isFinite(progress)
        ? Math.max(0, Math.min(100, Number(progress)))
        : null;

    showStatusLane(INDEXING_STATUS_KEY, {
        group: 'library-processing',
        title: options.title || (safeProgress === null ? 'Preparing library' : 'Indexing media'),
        meta: options.meta || (safeProgress === null
            ? 'New items will appear as they are discovered'
            : `${safeProgress}% complete`),
        tone: options.tone || 'info',
        busy: options.busy !== false,
        priority: Number.isFinite(options.priority) ? options.priority : 10
    });
}

export function hideIndexingStatus() {
    hideStatusLane(INDEXING_STATUS_KEY);
}
