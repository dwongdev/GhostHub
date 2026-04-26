import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('focusManager', () => {
    let scheduleAutofocus;
    let rafQueue;

    beforeEach(async () => {
        vi.resetModules();
        document.body.innerHTML = `
            <button id="source">Open</button>
            <button id="other">Elsewhere</button>
            <input id="target" type="text" value="GhostHub" />
        `;

        rafQueue = [];
        window.requestAnimationFrame = (callback) => {
            rafQueue.push(callback);
            return rafQueue.length;
        };

        ({ scheduleAutofocus } = await import('../../utils/focusManager.js'));
    });

    function flushRaf() {
        while (rafQueue.length > 0) {
            const callback = rafQueue.shift();
            callback();
        }
    }

    it('focuses the target when the original trigger still owns focus', () => {
        const source = document.getElementById('source');
        const target = document.getElementById('target');

        source.focus();
        scheduleAutofocus(target);
        flushRaf();

        expect(document.activeElement).toBe(target);
    });

    it('does not steal focus after the user moved to another control', () => {
        const source = document.getElementById('source');
        const other = document.getElementById('other');
        const target = document.getElementById('target');

        source.focus();
        scheduleAutofocus(target, { frames: 1 });
        other.focus();
        flushRaf();

        expect(document.activeElement).toBe(other);
    });

    it('can still force focus for explicit modal-style autofocus', () => {
        const source = document.getElementById('source');
        const other = document.getElementById('other');
        const target = document.getElementById('target');

        source.focus();
        scheduleAutofocus(target, { frames: 1, force: true });
        other.focus();
        flushRaf();

        expect(document.activeElement).toBe(target);
    });
});
