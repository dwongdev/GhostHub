import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../utils/showHiddenManager.js', () => ({
    appendShowHiddenParam: vi.fn((url) => url)
}));

vi.mock('../../../utils/progressDB.js', () => ({
    isUserAdmin: vi.fn(() => false),
    isSessionProgressEnabled: vi.fn(() => false)
}));

describe('streaming cards', () => {
    let createMediaItemCard, createContinueWatchingCard, updateContinueWatchingCard, createSubfolderCard;

    beforeEach(async () => {
        vi.useFakeTimers();
        vi.resetModules();
        document.body.innerHTML = '<div id="streaming-container"></div>';

        const cardsModule = await import('../../../modules/layouts/streaming/cards.js');
        createMediaItemCard = cardsModule.createMediaItemCard;
        createContinueWatchingCard = cardsModule.createContinueWatchingCard;
        updateContinueWatchingCard = cardsModule.updateContinueWatchingCard;
        createSubfolderCard = cardsModule.createSubfolderCard;
    });

    it('creates a video card with a placeholder layer', () => {
        const card = createMediaItemCard({
            url: '/media/cat-1/movie.mp4',
            type: 'video',
            name: 'Movie.mp4',
            thumbnailUrl: '/thumbnails/cat-1/movie.jpeg'
        }, 'cat-1', 0, { forceEager: true });

        expect(card.classList.contains('streaming-card')).toBe(true);
        expect(card.querySelector('.streaming-card-thumbnail')).not.toBeNull();
        expect(card.querySelector('.gh-thumbnail-placeholder-layer')).not.toBeNull();
    });

    it('sets pending state on eager thumbnail images', () => {
        const card = createMediaItemCard({
            url: '/media/cat-1/movie.mp4',
            type: 'video',
            name: 'Movie.mp4',
            thumbnailUrl: '/thumbnails/cat-1/movie.jpeg'
        }, 'cat-1', 0, { forceEager: true });

        const primary = card.querySelector('.streaming-card-thumbnail');
        const placeholder = card.querySelector('.gh-thumbnail-placeholder-layer');

        expect(primary).not.toBeNull();
        expect(placeholder).not.toBeNull();
        expect(primary.getAttribute('data-image-state')).toBe('pending');
        expect(placeholder.hasAttribute('hidden')).toBe(false);
    });

    it('keeps shimmer alive during eager thumbnail retries', () => {
        const card = createMediaItemCard({
            url: '/media/cat-1/movie.mp4',
            type: 'video',
            name: 'Movie.mp4',
            thumbnailUrl: '/thumbnails/cat-1/movie.jpeg'
        }, 'cat-1', 0, { forceEager: true });

        const primary = card.querySelector('.streaming-card-thumbnail');
        const placeholder = card.querySelector('.gh-thumbnail-placeholder-layer');

        primary.onerror();

        // During retries with preservePlaceholderOnError, the placeholder
        // stays in pending state (shimmer continues) instead of error state.
        expect(primary.getAttribute('data-image-state')).toBe('pending');
        expect(primary.getAttribute('src')).toBe(null);
        expect(placeholder.hasAttribute('hidden')).toBe(false);
        expect(placeholder.getAttribute('data-thumbnail-state')).toBe('pending');

        vi.advanceTimersByTime(2000);

        expect(primary.getAttribute('data-image-state')).toBe('pending');
    });

    it('renders a consistent placeholder shell for continue watching cards', () => {
        const card = createContinueWatchingCard({
            videoUrl: '/media/cat-2/show.mp4',
            categoryId: 'cat-2',
            categoryName: 'Shows',
            thumbnailUrl: '/thumbnails/cat-2/show.jpeg',
            videoTimestamp: 120,
            videoDuration: 300
        });

        const primary = card.querySelector('.streaming-card-thumbnail');
        const placeholder = card.querySelector('.gh-thumbnail-placeholder-layer');

        expect(primary).not.toBeNull();
        expect(placeholder).not.toBeNull();
        expect(placeholder.hasAttribute('hidden')).toBe(false);
        expect(primary.getAttribute('data-image-state')).toBe('pending');
    });

    it('shows progress bar for partially watched continue watching cards', () => {
        const card = createContinueWatchingCard({
            videoUrl: '/media/cat-1/movie.mp4',
            categoryId: 'cat-1',
            categoryName: 'Movies',
            thumbnailUrl: '/thumbnails/cat-1/movie.jpeg',
            videoTimestamp: 180,
            videoDuration: 600
        });

        const progressFill = card.querySelector('.streaming-card-progress-fill');
        expect(progressFill).not.toBeNull();
        expect(progressFill.style.width).toBe('30%');
    });

    it('updates an existing continue watching card progress in place', () => {
        const card = createContinueWatchingCard({
            videoUrl: '/media/cat-1/movie.mp4',
            categoryId: 'cat-1',
            categoryName: 'Movies',
            thumbnailUrl: '/thumbnails/cat-1/movie.jpeg',
            videoTimestamp: 180,
            videoDuration: 600
        });

        updateContinueWatchingCard(card, {
            videoUrl: '/media/cat-1/movie.mp4',
            categoryId: 'cat-1',
            categoryName: 'Movies',
            thumbnailUrl: '/thumbnails/cat-1/movie.jpeg',
            videoTimestamp: 300,
            videoDuration: 600
        });

        const progressFill = card.querySelector('.streaming-card-progress-fill');
        expect(progressFill).not.toBeNull();
        expect(progressFill.style.width).toBe('50%');
    });

    it('renders media item card without thumbnail url', () => {
        const card = createMediaItemCard({
            url: '/media/cat-1/clip.mp4',
            type: 'video',
            name: 'clip.mp4'
        }, 'cat-1', 0);

        const placeholder = card.querySelector('.gh-thumbnail-placeholder-layer');
        expect(placeholder).not.toBeNull();
        expect(card.querySelector('.streaming-card-thumbnail')).toBeNull();
    });

    it('applies forceEager without crashing on image-less cards', () => {
        const card = createMediaItemCard({
            url: '/media/cat-1/clip.mp4',
            type: 'video',
            name: 'clip.mp4'
        }, 'cat-1', 0, { forceEager: true });

        expect(card.classList.contains('streaming-card')).toBe(true);
    });

    it('renders subfolder cards with the shared thumbnail shell', () => {
        const card = createSubfolderCard({
            name: 'ShowA',
            count: 3,
            thumbnailUrl: '/media/auto::ghost::sda2::TV::ShowA/Poster.jpg',
            categoryId: 'auto::ghost::sda2::TV'
        });

        expect(card.querySelector('.gh-thumbnail-placeholder-layer')).not.toBeNull();
        expect(card.querySelector('.subfolder-thumb-img')).not.toBeNull();
    });
});
