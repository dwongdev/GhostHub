import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { VideoControls } from '../../../modules/media/videoControls.js';

function createMockVideo() {
    const video = document.createElement('video');
    Object.defineProperty(video, 'duration', { value: 100, writable: true, configurable: true });
    Object.defineProperty(video, 'currentTime', { value: 20, writable: true, configurable: true });
    Object.defineProperty(video, 'paused', { value: true, writable: true, configurable: true });
    video.pause = vi.fn();
    video.play = vi.fn(() => Promise.resolve());
    return video;
}

function attachMockRefs(instance) {
    instance.refs.progressBar = {
        getBoundingClientRect: () => ({ left: 0, width: 100 }),
        classList: { add: vi.fn(), remove: vi.fn() }
    };
    instance.refs.progressPlayed = { style: {} };
    instance.refs.progressHandle = { style: {} };
    instance.refs.timeTooltip = {
        style: {},
        textContent: '',
        classList: { add: vi.fn(), remove: vi.fn() }
    };
    instance.refs.timeDisplay = { textContent: '' };
}

describe('videoControls scrubbing', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers();
        document.body.classList.remove('vc-scrub-no-select');
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('updates DOM during drag and commits seek on release', () => {
        const video = createMockVideo();
        const controls = new VideoControls(video, { name: 'test.mp4' });
        attachMockRefs(controls);
        controls._scheduleHide = vi.fn();

        // Start scrub at 75% of bar (width=100, left=0)
        controls._onScrubStart({ clientX: 75, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        expect(controls._isDragging).toBe(true);
        expect(controls._dragTime).toBeCloseTo(75);
        expect(video.currentTime).toBeCloseTo(75);

        // Move to 50%
        vi.advanceTimersByTime(100);
        controls._onScrubMove({ clientX: 50, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        expect(controls._dragTime).toBeCloseTo(50);
        expect(video.currentTime).toBeCloseTo(50);

        // Release — should commit seek
        controls._onScrubEnd({ stopPropagation: vi.fn() });
        expect(controls._isDragging).toBe(false);
        expect(video.currentTime).toBeCloseTo(50);
    });

    it('marks the video as scrub-preview active during drag and clears it after release', () => {
        const video = createMockVideo();
        const controls = new VideoControls(video, { name: 'test.mp4' });
        attachMockRefs(controls);
        controls._scheduleHide = vi.fn();

        controls._onScrubStart({ clientX: 30, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        vi.advanceTimersByTime(100);
        controls._onScrubMove({ clientX: 80, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        expect(video.getAttribute('data-scrub-preview-active')).toBe('true');
        expect(video.currentTime).toBe(80);

        controls._onScrubEnd({ stopPropagation: vi.fn() });
        vi.runAllTimers();
        expect(video.getAttribute('data-scrub-preview-active')).toBeNull();
        expect(video.currentTime).toBeCloseTo(80);
    });

    it('ignores scrubMove and scrubEnd when not dragging', () => {
        const video = createMockVideo();
        const controls = new VideoControls(video, { name: 'test.mp4' });
        attachMockRefs(controls);

        controls._onScrubMove({ clientX: 50, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        controls._onScrubEnd({ stopPropagation: vi.fn() });

        // Nothing should have changed
        expect(video.currentTime).toBe(20);
    });

    it('locks text selection during scrub and unlocks on end', () => {
        const video = createMockVideo();
        const controls = new VideoControls(video, { name: 'test.mp4' });
        attachMockRefs(controls);
        controls._scheduleHide = vi.fn();

        controls._onScrubStart({ clientX: 40, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        expect(document.body.classList.contains('vc-scrub-no-select')).toBe(true);

        controls._onScrubEnd({ stopPropagation: vi.fn() });
        expect(document.body.classList.contains('vc-scrub-no-select')).toBe(false);
    });

    it('resumes playback after scrub if video was playing', () => {
        const video = createMockVideo();
        Object.defineProperty(video, 'paused', { value: false, writable: true, configurable: true });
        const controls = new VideoControls(video, { name: 'test.mp4' });
        attachMockRefs(controls);
        controls._scheduleHide = vi.fn();

        controls._onScrubStart({ clientX: 40, preventDefault: vi.fn(), stopPropagation: vi.fn() });
        expect(video.pause).toHaveBeenCalled();

        controls._onScrubEnd({ stopPropagation: vi.fn() });
        expect(video.play).toHaveBeenCalled();
    });
});
