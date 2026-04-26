import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('viewTransitions', () => {
    let withOptionalViewTransition;
    let canUseViewTransitions;

    beforeEach(async () => {
        vi.resetModules();
        document.documentElement.className = '';
        delete document.startViewTransition;
        window.matchMedia = vi.fn().mockReturnValue({ matches: false });

        ({ withOptionalViewTransition, canUseViewTransitions } = await import('../../utils/viewTransitions.js'));
    });

    it('runs the update and applies the fallback class when transitions are unavailable', () => {
        const update = vi.fn();
        vi.useFakeTimers();

        withOptionalViewTransition(update, {
            fallbackClass: 'gh-transition-layout',
            durationMs: 220
        });

        expect(update).toHaveBeenCalledOnce();
        expect(document.documentElement.classList.contains('gh-transition-layout')).toBe(true);
        vi.advanceTimersByTime(221);
        expect(document.documentElement.classList.contains('gh-transition-layout')).toBe(false);
        vi.useRealTimers();
    });

    it('reports view transitions as enabled when supported and motion is not reduced', async () => {
        document.startViewTransition = vi.fn((cb) => {
            cb();
            return { finished: Promise.resolve() };
        });

        ({ canUseViewTransitions } = await import('../../utils/viewTransitions.js'));
        expect(canUseViewTransitions()).toBe(true);
    });
});
