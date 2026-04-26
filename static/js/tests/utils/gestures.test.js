/**
 * Tests for gestures module
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
    setupSharedGestures,
    cleanupSharedGestures,
    areSharedGesturesAttached
} from '../../utils/gestures.js';

describe('gestures', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        cleanupSharedGestures();

        document.body.innerHTML = `
            <div id="media-viewer" class="hidden">
                <div class="viewer-media active">
                    <video class="active"></video>
                </div>
            </div>
        `;
    });

    afterEach(() => {
        cleanupSharedGestures();
        vi.useRealTimers();
        document.body.innerHTML = '';
    });

    describe('setupSharedGestures', () => {
        it('attaches event listeners when called', () => {
            const addEventListenerSpy = vi.spyOn(document.body, 'addEventListener');

            setupSharedGestures();

            expect(addEventListenerSpy).toHaveBeenCalledWith('touchstart', expect.any(Function), { passive: false });
            expect(addEventListenerSpy).toHaveBeenCalledWith('touchmove', expect.any(Function), { passive: false });
            expect(addEventListenerSpy).toHaveBeenCalledWith('touchend', expect.any(Function), { passive: false });
        });

        it('does not attach twice', () => {
            setupSharedGestures();
            const addEventListenerSpy = vi.spyOn(document.body, 'addEventListener');

            setupSharedGestures();

            expect(addEventListenerSpy).not.toHaveBeenCalled();
        });

        it('sets gesturesAttached to true', () => {
            expect(areSharedGesturesAttached()).toBe(false);

            setupSharedGestures();

            expect(areSharedGesturesAttached()).toBe(true);
        });
    });

    describe('cleanupSharedGestures', () => {
        it('removes event listeners when called', () => {
            setupSharedGestures();
            const removeEventListenerSpy = vi.spyOn(document.body, 'removeEventListener');

            cleanupSharedGestures();

            expect(removeEventListenerSpy).toHaveBeenCalledWith('touchstart', expect.any(Function), { passive: false });
            expect(removeEventListenerSpy).toHaveBeenCalledWith('touchmove', expect.any(Function), { passive: false });
            expect(removeEventListenerSpy).toHaveBeenCalledWith('touchend', expect.any(Function), { passive: false });
        });

        it('sets gesturesAttached to false', () => {
            setupSharedGestures();
            expect(areSharedGesturesAttached()).toBe(true);

            cleanupSharedGestures();

            expect(areSharedGesturesAttached()).toBe(false);
        });

        it('handles cleanup when not attached', () => {
            const removeEventListenerSpy = vi.spyOn(document.body, 'removeEventListener');

            cleanupSharedGestures();

            expect(removeEventListenerSpy).not.toHaveBeenCalled();
        });
    });

    describe('areSharedGesturesAttached', () => {
        it('returns false initially', () => {
            expect(areSharedGesturesAttached()).toBe(false);
        });

        it('returns true after setup', () => {
            setupSharedGestures();
            expect(areSharedGesturesAttached()).toBe(true);
        });

        it('returns false after cleanup', () => {
            setupSharedGestures();
            cleanupSharedGestures();
            expect(areSharedGesturesAttached()).toBe(false);
        });
    });

    describe('areSharedGesturesAttached', () => {
        it('returns false initially', () => {
            expect(areSharedGesturesAttached()).toBe(false);
        });

        it('returns true after setup', () => {
            setupSharedGestures();
            expect(areSharedGesturesAttached()).toBe(true);
        });

        it('returns false after cleanup', () => {
            setupSharedGestures();
            cleanupSharedGestures();
            expect(areSharedGesturesAttached()).toBe(false);
        });
    });

    describe('event listener attachment', () => {
        it('attaches touch event listeners on setup', () => {
            const addEventListenerSpy = vi.spyOn(document.body, 'addEventListener');

            setupSharedGestures();

            expect(addEventListenerSpy).toHaveBeenCalledWith('touchstart', expect.any(Function), { passive: false });
        });

        it('removes touch event listeners on cleanup', () => {
            setupSharedGestures();
            const removeEventListenerSpy = vi.spyOn(document.body, 'removeEventListener');

            cleanupSharedGestures();

            expect(removeEventListenerSpy).toHaveBeenCalledWith('touchstart', expect.any(Function), { passive: false });
        });
    });
});
