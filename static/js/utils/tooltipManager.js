/**
 * tooltipManager.js
 * Promotes native title-based hints into shared GhostHub tooltips.
 */

const INTERACTIVE_SELECTOR = [
    'button',
    'a',
    'input',
    'select',
    'textarea',
    '[role="button"]',
    '[tabindex]'
].join(',');

let tooltipObserver = null;

function hasDom() {
    return typeof document !== 'undefined' && !!document.body;
}

function isInteractiveTooltipTarget(element) {
    return element instanceof HTMLElement && element.matches(INTERACTIVE_SELECTOR);
}

function getTooltipPosition(element) {
    if (element.closest('.gh-header')) return 'bottom';
    return 'top';
}

export function enhanceTooltipTarget(element) {
    if (!isInteractiveTooltipTarget(element)) return;

    const title = element.getAttribute('title');
    if (!title) return;

    if (!element.dataset.ghTooltip) {
        element.dataset.ghTooltip = title;
    }

    if (!element.dataset.ghTooltipPosition) {
        element.dataset.ghTooltipPosition = getTooltipPosition(element);
    }

    if (!element.getAttribute('aria-label')) {
        const visibleText = (element.textContent || '').trim();
        if (!visibleText) {
            element.setAttribute('aria-label', title);
        }
    }

    if (!element.dataset.ghNativeTitle) {
        element.dataset.ghNativeTitle = title;
    }

    element.removeAttribute('title');
}

export function refreshTooltipTargets(root = document.body) {
    if (!root || !(root instanceof HTMLElement || root instanceof Document || root instanceof DocumentFragment)) {
        return;
    }

    if (root instanceof HTMLElement) {
        enhanceTooltipTarget(root);
    }

    if (typeof root.querySelectorAll === 'function') {
        root.querySelectorAll('[title]').forEach((element) => enhanceTooltipTarget(element));
    }
}

export function initTooltipManager() {
    if (!hasDom()) return false;
    refreshTooltipTargets(document.body);

    if (tooltipObserver) return true;

    tooltipObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.target instanceof HTMLElement) {
                enhanceTooltipTarget(mutation.target);
                return;
            }

            mutation.addedNodes.forEach((node) => {
                if (node instanceof HTMLElement) {
                    refreshTooltipTargets(node);
                }
            });
        });
    });

    tooltipObserver.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['title']
    });

    return true;
}

export function destroyTooltipManager() {
    if (tooltipObserver) {
        tooltipObserver.disconnect();
        tooltipObserver = null;
    }
}
