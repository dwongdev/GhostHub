import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('statusLane', () => {
    let showStatusLane;
    let hideStatusLane;
    let clearStatusLane;

    beforeEach(async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date('2026-03-24T12:00:00Z'));
        vi.resetModules();
        document.body.innerHTML = '';

        ({ showStatusLane, hideStatusLane, clearStatusLane } = await import('../../utils/statusLane.js'));
    });

    it('renders a shared lane and falls back to the next active entry', () => {
        showStatusLane('thumbnails', {
            title: 'Generating thumbnails',
            meta: '4.2 thumbnails/sec • 12 generated',
            priority: 20
        });

        showStatusLane('library-indexing', {
            title: 'Indexing media',
            meta: '62% complete',
            priority: 10
        });

        const lane = document.getElementById('gh-status-lane');
        expect(lane).not.toBeNull();
        expect(lane.hidden).toBe(false);
        expect(lane.querySelector('.gh-status-lane__title').textContent).toBe('Indexing media');

        hideStatusLane('library-indexing');
        expect(lane.querySelector('.gh-status-lane__title').textContent).toBe('Generating thumbnails');
    });

    it('merges related library-processing entries into one lane state', () => {
        showStatusLane('thumbnail-generation', {
            group: 'library-processing',
            title: 'Generating thumbnails',
            meta: '5.1 thumbnails/sec • 42 generated',
            priority: 20
        });

        showStatusLane('library-indexing', {
            group: 'library-processing',
            title: 'Indexing media',
            meta: '62% complete',
            priority: 10
        });

        const lane = document.getElementById('gh-status-lane');
        expect(lane.querySelector('.gh-status-lane__title').textContent).toBe('Preparing library');
        expect(lane.querySelector('.gh-status-lane__meta').textContent).toBe('62% complete • 5.1 thumbnails/sec • 42 generated');
    });

    it('hides the lane when all entries are cleared', () => {
        showStatusLane('library-indexing', {
            title: 'Indexing media',
            meta: '18% complete'
        });

        const lane = document.getElementById('gh-status-lane');
        expect(lane.hidden).toBe(false);

        clearStatusLane();
        expect(lane.hidden).toBe(true);
    });
});
