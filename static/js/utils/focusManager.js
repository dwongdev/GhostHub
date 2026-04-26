/**
 * Shared autofocus helpers.
 * Keeps focus timing and text-selection behavior consistent across surfaces.
 */

function resolveTarget(target) {
    if (!target) return null;
    if (typeof target === 'function') return resolveTarget(target());
    return target;
}

function isCoarsePointer() {
    return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(pointer: coarse)').matches;
}

function isMeaningfulFocusedElement(el, doc = document) {
    return !!el
        && el !== doc.body
        && el !== doc.documentElement
        && typeof el.focus === 'function';
}

export function scheduleAutofocus(target, options = {}) {
    const {
        preventScroll = true,
        frames = 1,
        selectionBehavior = 'none',
        respectExistingFocus = true,
        force = false
    } = options;

    let cancelled = false;
    const initialTarget = resolveTarget(target);
    const ownerDocument = initialTarget?.ownerDocument || document;
    const scheduledFrom = ownerDocument?.activeElement || null;

    const applySelection = (el) => {
        if (!el) return;
        if (selectionBehavior === 'select-all' && typeof el.select === 'function') {
            el.select();
            return;
        }
        if (selectionBehavior === 'select-all-desktop' && !isCoarsePointer() && typeof el.select === 'function') {
            el.select();
            return;
        }
        if (selectionBehavior === 'cursor-end' && typeof el.setSelectionRange === 'function') {
            const valueLength = el.value?.length || 0;
            el.setSelectionRange(valueLength, valueLength);
        }
    };

    const run = (remainingFrames) => {
        if (cancelled) return;
        if (remainingFrames > 0) {
            requestAnimationFrame(() => run(remainingFrames - 1));
            return;
        }

        const el = resolveTarget(target);
        if (!el?.focus) return;

        const doc = el.ownerDocument || ownerDocument;
        const activeElement = doc?.activeElement || null;
        const targetContainsActive = typeof el.contains === 'function' && el.contains(activeElement);
        const activeContainsTarget = typeof activeElement?.contains === 'function' && activeElement.contains(el);

        if (
            !force
            && respectExistingFocus
            && isMeaningfulFocusedElement(activeElement, doc)
            && activeElement !== scheduledFrom
            && activeElement !== el
            && !targetContainsActive
            && !activeContainsTarget
        ) {
            return;
        }

        el.focus({ preventScroll });
        applySelection(el);
    };

    run(frames);

    return () => {
        cancelled = true;
    };
}
