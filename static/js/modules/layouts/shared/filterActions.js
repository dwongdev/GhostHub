import { updateCategoryFilterPill } from '../../ui/categoryFilterPill.js';

function formatSubfolderPillName(subfolder, fallbackName) {
    if (!subfolder) return fallbackName;
    const leaf = subfolder.split('/').pop();
    if (!leaf) return fallbackName;
    return leaf.replace(/[-_]/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Creates reusable layout filter action handlers.
 *
 * @param {Object} options
 * @param {Function} options.isActive
 * @param {Function} options.resolveCategoryName
 * @param {Function} options.applyCategoryState
 * @param {Function} options.applyParentState
 * @param {Function} options.refreshForFilter
 * @param {Function} [options.applySubfolderState]
 * @param {Function} [options.beforeFilterChange]
 * @returns {{
 *  setCategoryFilter: Function,
 *  setParentFilter: Function,
 *  setSubfolderFilterAction: Function
 * }}
 */
export function createLayoutFilterActions({
    isActive,
    resolveCategoryName,
    applyCategoryState,
    applyParentState,
    refreshForFilter,
    applySubfolderState = null,
    beforeFilterChange = null
}) {
    function runBeforeFilterChange() {
        if (typeof beforeFilterChange === 'function') {
            beforeFilterChange();
        }
    }

    function setCategoryFilter(categoryId, categoryName = null) {
        if (!isActive()) return;
        runBeforeFilterChange();
        const resolvedName = resolveCategoryName(categoryId, categoryName);
        applyCategoryState({ categoryId, resolvedName });
        refreshForFilter();
        updateCategoryFilterPill(resolvedName);
    }

    function setParentFilter(parentName, categoryIds = null) {
        if (!isActive()) return;
        runBeforeFilterChange();
        applyParentState({ parentName, categoryIds });
        refreshForFilter();
        updateCategoryFilterPill(parentName);
    }

    function setSubfolderFilterAction(categoryId, subfolder, categoryName = null) {
        if (!isActive()) return;
        runBeforeFilterChange();
        const resolvedName = resolveCategoryName(categoryId, categoryName);

        if (typeof applySubfolderState === 'function') {
            applySubfolderState({ categoryId, subfolder, resolvedName });
        } else {
            applyCategoryState({ categoryId, resolvedName });
        }

        refreshForFilter();
        updateCategoryFilterPill(formatSubfolderPillName(subfolder, resolvedName));
    }

    return {
        setCategoryFilter,
        setParentFilter,
        setSubfolderFilterAction
    };
}

