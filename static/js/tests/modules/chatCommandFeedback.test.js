import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../modules/chat/commandHandler.js', () => ({
    initCommandHandler: vi.fn(() => ({
        commands: {},
        processCommand: vi.fn(() => false)
    }))
}));

vi.mock('../../modules/chat/commandPopup.js', () => ({
    initCommandPopup: vi.fn(() => ({
        isPopupVisible: vi.fn(() => false),
        hideCommandPopup: vi.fn()
    }))
}));

vi.mock('../../utils/authManager.js', () => ({
    ensureFeatureAccess: vi.fn(() => Promise.resolve(true))
}));

const toastShow = vi.fn();

vi.mock('../../utils/notificationManager.js', () => ({
    toast: {
        show: toastShow,
        info: vi.fn(),
        success: vi.fn(),
        warning: vi.fn(),
        error: vi.fn()
    }
}));

describe('ChatComponent command feedback', () => {
    let ChatComponent;
    let chat;

    beforeEach(async () => {
        vi.clearAllMocks();
        ({ ChatComponent } = await import('../../modules/chat/manager.js'));
        chat = new ChatComponent({ emit: vi.fn() });
        chat.displayLocalSystemMessage = vi.fn();
    });

    it('sends html strings to notifications instead of the chat log', () => {
        chat.displayCommandFeedback('<strong>Help</strong>', { isHtml: true, icon: 'lightbulb' });

        expect(toastShow).toHaveBeenCalledWith('<strong>Help</strong>', 'info', {
            isHtml: true,
            persist: true
        });
        expect(chat.displayLocalSystemMessage).not.toHaveBeenCalled();
    });

    it('keeps interactive html elements in the chat log', () => {
        const results = document.createElement('div');
        results.textContent = 'Search results';

        chat.displayCommandFeedback(results, { isHtml: true, icon: 'search' });

        expect(chat.displayLocalSystemMessage).toHaveBeenCalledWith(results, expect.objectContaining({
            isHtml: true,
            icon: 'search'
        }));
        expect(toastShow).not.toHaveBeenCalled();
    });
});
