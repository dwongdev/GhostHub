/**
 * Lightweight focus trap for modal surfaces and popovers.
 */

const FOCUSABLE_SELECTOR = [
    'a[href]:not([tabindex="-1"])',
    'area[href]:not([tabindex="-1"])',
    'button:not([disabled]):not([tabindex="-1"])',
    'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
    'select:not([disabled]):not([tabindex="-1"])',
    'textarea:not([disabled]):not([tabindex="-1"])',
    'iframe:not([tabindex="-1"])',
    '[contenteditable="true"]:not([tabindex="-1"])',
    '[tabindex]:not([tabindex="-1"])'
].join(', ');

function isFocusable(el) {
    if (!el || !el.isConnected) return false;
    if (el.hasAttribute('disabled') || el.getAttribute('aria-hidden') === 'true') return false;

    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;

    return el.getClientRects().length > 0;
}

function resolveTarget(target, container) {
    if (!target) return null;
    if (typeof target === 'function') return resolveTarget(target(container), container);
    if (typeof target === 'string') return container.querySelector(target);
    return target;
}

export function getFocusableElements(containerEl) {
    if (!containerEl) return [];
    return Array.from(containerEl.querySelectorAll(FOCUSABLE_SELECTOR)).filter(isFocusable);
}

export function createFocusTrap(containerEl, options = {}) {
    let active = false;
    let focusableElements = [];
    let returnFocusTarget = options.returnFocusTo || null;

    const doc = containerEl?.ownerDocument || document;

    const focusInitial = () => {
        const preferred = resolveTarget(options.initialFocus, containerEl);
        const focusTarget = isFocusable(preferred) ? preferred : focusableElements[0] || containerEl;
        if (!focusTarget) return;
        focusTarget.focus({ preventScroll: true });
    };

    const handleKeyDown = (event) => {
        if (!active || event.key !== 'Tab') return;

        updateElements();
        if (focusableElements.length === 0) {
            event.preventDefault();
            containerEl?.focus?.({ preventScroll: true });
            return;
        }

        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];
        const current = doc.activeElement;

        if (event.shiftKey) {
            if (current === first || !containerEl.contains(current)) {
                event.preventDefault();
                last.focus({ preventScroll: true });
            }
            return;
        }

        if (current === last || !containerEl.contains(current)) {
            event.preventDefault();
            first.focus({ preventScroll: true });
        }
    };

    const handleFocusIn = (event) => {
        if (!active || !containerEl || containerEl.contains(event.target)) return;
        updateElements();
        (focusableElements[0] || containerEl).focus({ preventScroll: true });
    };

    function updateElements() {
        focusableElements = getFocusableElements(containerEl);
        if (containerEl && !containerEl.hasAttribute('tabindex')) {
            containerEl.setAttribute('tabindex', '-1');
        }
        return focusableElements;
    }

    function activate() {
        if (active || !containerEl) return;
        if (!returnFocusTarget) {
            returnFocusTarget = options.returnFocusTo || doc.activeElement;
        }
        active = true;
        updateElements();
        doc.addEventListener('keydown', handleKeyDown, true);
        doc.addEventListener('focusin', handleFocusIn, true);
        requestAnimationFrame(() => {
            if (active) focusInitial();
        });
    }

    function deactivate({ restoreFocus = true } = {}) {
        if (!active) return;
        active = false;
        doc.removeEventListener('keydown', handleKeyDown, true);
        doc.removeEventListener('focusin', handleFocusIn, true);

        if (!restoreFocus) return;
        const nextFocus = resolveTarget(returnFocusTarget, doc) || returnFocusTarget;
        if (isFocusable(nextFocus)) {
            requestAnimationFrame(() => nextFocus.focus({ preventScroll: true }));
        }
    }

    return {
        activate,
        deactivate,
        updateElements
    };
}
