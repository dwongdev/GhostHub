import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mocks = vi.hoisted(() => ({
    ensureDownloadButton: vi.fn(),
    setFloatingDownloadVisible: vi.fn(),
    ensureQuickActionsButton: vi.fn(),
    setQuickActionsVisibility: vi.fn()
}));

vi.mock('../../../modules/media/download.js', () => ({
    ensureDownloadButton: mocks.ensureDownloadButton,
    setFloatingDownloadVisible: mocks.setFloatingDownloadVisible
}));

vi.mock('../../../modules/media/quickActions.js', () => ({
    ensureQuickActionsButton: mocks.ensureQuickActionsButton,
    setQuickActionsVisibility: mocks.setQuickActionsVisibility
}));

import {
    initViewerUiController,
    cleanupViewerUiController,
    setViewerMode,
    syncViewerUi,
    getViewerMode,
    VIEWER_MODES
} from '../../../modules/media/viewerUiController.js';

describe('viewerUiController', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        cleanupViewerUiController();
    });

    afterEach(() => {
        cleanupViewerUiController();
    });

    it('should apply floating visibility in media mode on init', () => {
        initViewerUiController();

        expect(mocks.ensureDownloadButton).toHaveBeenCalled();
        expect(mocks.ensureQuickActionsButton).toHaveBeenCalled();
        expect(mocks.setFloatingDownloadVisible).toHaveBeenCalledWith(true);
        expect(mocks.setQuickActionsVisibility).toHaveBeenCalledWith(true);
    });

    it('should hide floating actions in video controls mode', () => {
        initViewerUiController();
        setViewerMode(VIEWER_MODES.VIDEO_CONTROLS);

        expect(getViewerMode()).toBe(VIEWER_MODES.VIDEO_CONTROLS);
        expect(mocks.setFloatingDownloadVisible).toHaveBeenLastCalledWith(false);
        expect(mocks.setQuickActionsVisibility).toHaveBeenLastCalledWith(false);
    });

    it('should hide floating actions in photo viewer mode', () => {
        initViewerUiController();
        setViewerMode(VIEWER_MODES.PHOTO_VIEWER);

        expect(getViewerMode()).toBe(VIEWER_MODES.PHOTO_VIEWER);
        expect(mocks.setFloatingDownloadVisible).toHaveBeenLastCalledWith(false);
        expect(mocks.setQuickActionsVisibility).toHaveBeenLastCalledWith(false);
    });

    it('should restore floating actions when returning to media mode', () => {
        initViewerUiController();
        setViewerMode(VIEWER_MODES.VIDEO_CONTROLS);
        setViewerMode(VIEWER_MODES.MEDIA);

        expect(getViewerMode()).toBe(VIEWER_MODES.MEDIA);
        expect(mocks.setFloatingDownloadVisible).toHaveBeenLastCalledWith(true);
        expect(mocks.setQuickActionsVisibility).toHaveBeenLastCalledWith(true);
    });

    it('should resync current mode visibility on demand', () => {
        initViewerUiController();
        setViewerMode(VIEWER_MODES.PHOTO_VIEWER);
        vi.clearAllMocks();

        syncViewerUi();

        expect(mocks.setFloatingDownloadVisible).toHaveBeenCalledWith(false);
        expect(mocks.setQuickActionsVisibility).toHaveBeenCalledWith(false);
    });
});
