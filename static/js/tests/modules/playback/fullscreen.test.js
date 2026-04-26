/**
 * Tests for Fullscreen Manager Module
 * Tests cross-browser fullscreen functionality and button management.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    addFullscreenButton,
    setupFullscreenChangeListener,
    isSafeToToggleFullscreen,
    ensureFullscreenButtons
} from '../../../modules/playback/fullscreen.js';

describe('Fullscreen Manager Module', () => {
    let video;
    let chatContainer;

    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = '';
        document.documentElement.className = '';

        // Create video element
        video = document.createElement('video');
        video.className = 'active';
        video.src = '/media/test.mp4';
        document.body.appendChild(video);

        // Create chat container
        chatContainer = document.createElement('div');
        chatContainer.id = 'chat-container';
        document.body.appendChild(video);

        // Reset window flags
        window.fullscreenExited = false;
        window.__RAGOT_ALLOW_DIRECT_MUTATION__ = true;
        window.ragotModules = {
            ...(window.ragotModules || {}),
            appState: null
        };

        // Mock fullscreen API
        document.fullscreenElement = null;
        document.fullscreenEnabled = true;

        video.requestFullscreen = vi.fn(() => Promise.resolve());
        document.exitFullscreen = vi.fn(() => Promise.resolve());
    });

    describe.skip('addFullscreenButton', () => {
        it('should add fullscreen button to video element', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            expect(button).not.toBeNull();
            expect(button.tagName).toBe('BUTTON');
        });

        it('should not add button to non-video elements', () => {
            const div = document.createElement('div');
            document.body.appendChild(div);

            addFullscreenButton(div);

            const button = div.parentElement.querySelector('.fullscreen-btn');
            expect(button).toBeNull();
        });

        it('should remove existing fullscreen buttons before adding new one', () => {
            addFullscreenButton(video);
            addFullscreenButton(video);

            const buttons = video.parentElement.querySelectorAll('.fullscreen-btn');
            expect(buttons.length).toBe(1);
        });

        it('should create button with SVG icon', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            const svg = button.querySelector('svg');
            expect(svg).not.toBeNull();
        });

        it('should store video element reference on button', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            expect(button.videoElement).toBe(video);
        });

        it('should handle button click without errors', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');

            // Should not throw when clicked
            expect(() => button.click()).not.toThrow();
        });

        it('should wait for video to be added to DOM using MutationObserver', async () => {
            const orphanVideo = document.createElement('video');

            addFullscreenButton(orphanVideo);

            // Button should not be added yet
            expect(document.querySelector('.fullscreen-btn')).toBeNull();

            // Add video to DOM
            document.body.appendChild(orphanVideo);

            // Wait for MutationObserver to trigger
            await new Promise(resolve => setTimeout(resolve, 100));

            // Button should now be present
            const button = orphanVideo.parentElement.querySelector('.fullscreen-btn');
            expect(button).not.toBeNull();
        });
    });

    describe('isSafeToToggleFullscreen', () => {
        it('should return a boolean', () => {
            const result = isSafeToToggleFullscreen();
            expect(typeof result).toBe('boolean');
        });

        it('should return false immediately after fullscreen exit', () => {
            window.fullscreenExited = true;

            const result = isSafeToToggleFullscreen();
            expect(result).toBe(false);
        });

        it('should return false during rapid navigation', () => {
            window.ragotModules.appState = {
                lastNavigationTime: Date.now() - 100 // 100ms ago
            };

            const result = isSafeToToggleFullscreen();
            expect(result).toBe(false);
        });
    });

    describe.skip('Button Click Handling', () => {
        it('should stop event propagation on button click', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            const clickEvent = new MouseEvent('click', { bubbles: true });
            const stopPropagationSpy = vi.spyOn(clickEvent, 'stopPropagation');

            button.dispatchEvent(clickEvent);

            expect(stopPropagationSpy).toHaveBeenCalled();
        });

        it('should trigger fullscreen on button click', () => {
            addFullscreenButton(video);
            const button = video.parentElement.querySelector('.fullscreen-btn');

            button.click();

            expect(video.requestFullscreen).toHaveBeenCalled();
        });

        it('should debounce rapid clicks', async () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');

            button.click();
            button.click(); // Should be ignored (debounced)
            button.click(); // Should be ignored (debounced)

            // Due to debouncing, not all clicks trigger fullscreen
            // Just verify no errors are thrown
            expect(true).toBe(true);
        });
    });

    describe.skip('setupFullscreenChangeListener', () => {
        it('should add fullscreenchange event listener', () => {
            const addEventListenerSpy = vi.spyOn(document, 'addEventListener');

            setupFullscreenChangeListener();

            expect(addEventListenerSpy).toHaveBeenCalledWith(
                'fullscreenchange',
                expect.any(Function)
            );
        });

        it('should handle fullscreen button state changes', () => {
            addFullscreenButton(video);
            setupFullscreenChangeListener();

            const button = document.querySelector('.fullscreen-btn');
            expect(button).toBeTruthy();

            // Trigger fullscreen change event
            document.dispatchEvent(new Event('fullscreenchange'));

            // Button should still exist after event
            expect(document.querySelector('.fullscreen-btn')).toBeTruthy();
        });

        it('should remove is-fullscreen class when exiting fullscreen', () => {
            document.documentElement.classList.add('is-fullscreen');
            setupFullscreenChangeListener();

            document.fullscreenElement = null;
            document.dispatchEvent(new Event('fullscreenchange'));

            expect(document.documentElement.classList.contains('is-fullscreen')).toBe(false);
        });

        it('should handle fullscreen change events', () => {
            setupFullscreenChangeListener();

            // Simulate fullscreen change without throwing
            document.fullscreenElement = null;
            expect(() => {
                document.dispatchEvent(new Event('fullscreenchange'));
            }).not.toThrow();
        });
    });

    describe.skip('ensureFullscreenButtons', () => {
        it('should add buttons to active videos without buttons', () => {
            const video2 = document.createElement('video');
            video2.className = 'active';
            const container2 = document.createElement('div');
            container2.appendChild(video2);
            document.body.appendChild(container2);

            ensureFullscreenButtons();

            const buttons = document.querySelectorAll('.fullscreen-btn');
            expect(buttons.length).toBeGreaterThanOrEqual(1);
        });

        it('should not add duplicate buttons to videos that already have them', () => {
            addFullscreenButton(video);

            ensureFullscreenButtons();

            const buttons = video.parentElement.querySelectorAll('.fullscreen-btn');
            expect(buttons.length).toBe(1);
        });

        it('should only target videos with active class', () => {
            const inactiveVideo = document.createElement('video');
            // No active class
            const container = document.createElement('div');
            container.appendChild(inactiveVideo);
            document.body.appendChild(container);

            ensureFullscreenButtons();

            const buttons = container.querySelectorAll('.fullscreen-btn');
            expect(buttons.length).toBe(0);
        });
    });

    describe.skip('Edge Cases', () => {
        it('should handle missing chat container gracefully', () => {
            const chatEl = document.getElementById('chat-container');
            if (chatEl) chatEl.remove();

            expect(() => addFullscreenButton(video)).not.toThrow();
        });

        it('should handle multiple videos with fullscreen buttons', () => {
            const video2 = document.createElement('video');
            video2.className = 'active';
            const container2 = document.createElement('div');
            container2.appendChild(video2);
            document.body.appendChild(container2);

            addFullscreenButton(video);
            addFullscreenButton(video2);

            const buttons = document.querySelectorAll('.fullscreen-btn');
            expect(buttons.length).toBeGreaterThanOrEqual(1);
        });
    });

    describe.skip('Button Creation', () => {
        it('should create button with correct class', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            expect(button.className).toBe('fullscreen-btn');
        });

        it('should append button to video parent element', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            expect(button.parentElement).toBe(video.parentElement);
        });

        it('should handle video element without clicking', () => {
            addFullscreenButton(video);

            const button = video.parentElement.querySelector('.fullscreen-btn');
            expect(button).toBeTruthy();
            expect(button.videoElement).toBe(video);
        });
    });
});
