import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('notificationManager', () => {
    let toast;
    let dialog;
    let initNotificationManager;

    beforeEach(async () => {
        vi.useFakeTimers();
        vi.resetModules();

        document.body.innerHTML = '';
        window.requestAnimationFrame = vi.fn((callback) => {
            callback();
            return 1;
        });
        window.cancelAnimationFrame = vi.fn();

        ({ toast, dialog, initNotificationManager } = await import('../../utils/notificationManager.js'));
    });

    afterEach(() => {
        vi.runOnlyPendingTimers();
        vi.useRealTimers();
    });

    it('caps visible toasts and allows manual dismissal', () => {
        for (let i = 0; i < 6; i++) {
            toast.info(`Toast ${i + 1}`);
        }

        expect(document.querySelectorAll('.gh-toast').length).toBe(6);

        vi.advanceTimersByTime(220);
        expect(document.querySelectorAll('.gh-toast').length).toBe(5);

        const closeBtn = document.querySelector('.gh-toast__close');
        closeBtn.click();

        vi.advanceTimersByTime(220);
        expect(document.querySelectorAll('.gh-toast').length).toBe(4);
    });

    it('prewarms notification roots during init', () => {
        expect(document.getElementById('toast-container')).toBeNull();
        expect(document.getElementById('dialog-overlay')).toBeNull();

        expect(initNotificationManager()).toBe(true);

        expect(document.getElementById('toast-container')).not.toBeNull();
        expect(document.getElementById('dialog-overlay')).not.toBeNull();
    });

    it('renders html notifications without auto-dismissing them', () => {
        toast.show('<strong>Available commands</strong>', 'info', {
            isHtml: true,
            persist: true
        });

        const message = document.querySelector('.gh-toast__message');
        expect(message.innerHTML).toContain('<strong>Available commands</strong>');

        vi.advanceTimersByTime(3500);
        expect(document.querySelector('.gh-toast')).not.toBeNull();
    });

    it('submits prompt dialogs on Enter', async () => {
        const pending = dialog.prompt('Enter a value');
        const input = document.querySelector('.gh-dialog__input');

        expect(input).not.toBeNull();
        input.value = 'GhostHub';

        document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            bubbles: true,
        }));

        vi.advanceTimersByTime(180);
        await expect(pending).resolves.toBe('GhostHub');
        expect(document.querySelector('.gh-dialog')).toBeNull();
    });

    it('settles the previous dialog when a new one replaces it', async () => {
        const firstDialog = dialog.confirm('First dialog');
        const secondDialog = dialog.confirm('Second dialog');

        await expect(firstDialog).resolves.toBe(false);
        expect(document.querySelectorAll('.gh-dialog').length).toBe(1);

        document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Escape',
            bubbles: true,
        }));

        vi.advanceTimersByTime(180);
        await expect(secondDialog).resolves.toBe(false);
        expect(document.querySelector('.gh-dialog')).toBeNull();
    });
});
