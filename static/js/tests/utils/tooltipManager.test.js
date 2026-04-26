import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('tooltipManager', () => {
    let initTooltipManager;
    let destroyTooltipManager;

    beforeEach(async () => {
        vi.resetModules();
        document.body.innerHTML = `
            <header class="gh-header">
                <button id="gh-header__btn" title="Settings"></button>
            </header>
            <main>
                <button id="body-btn" title="Refresh"></button>
            </main>
        `;

        ({ initTooltipManager, destroyTooltipManager } = await import('../../utils/tooltipManager.js'));
    });

    it('promotes title attributes into shared tooltip data attributes', () => {
        initTooltipManager();

        const headerBtn = document.getElementById('gh-header__btn');
        const bodyBtn = document.getElementById('body-btn');

        expect(headerBtn.dataset.ghTooltip).toBe('Settings');
        expect(headerBtn.dataset.ghTooltipPosition).toBe('bottom');
        expect(headerBtn.hasAttribute('title')).toBe(false);

        expect(bodyBtn.dataset.ghTooltip).toBe('Refresh');
        expect(bodyBtn.dataset.ghTooltipPosition).toBe('top');
        expect(bodyBtn.hasAttribute('title')).toBe(false);
    });

    it('enhances dynamically added title-based controls', async () => {
        initTooltipManager();

        const dynamic = document.createElement('button');
        dynamic.setAttribute('title', 'Delete theme');
        document.body.appendChild(dynamic);

        await Promise.resolve();

        expect(dynamic.dataset.ghTooltip).toBe('Delete theme');
        expect(dynamic.hasAttribute('title')).toBe(false);

        destroyTooltipManager();
    });
});
