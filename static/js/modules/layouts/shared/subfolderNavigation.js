/**
 * Shared subfolder navigation helper for streaming layout.
 *
 * Handles the click action on subfolder cards — navigates to a child auto-category
 * or appends the clicked subfolder to the current subfolder path filter.
 *
 * Accepts state getters as parameters so this utility stays decoupled from any
 * specific layout's state module.
 *
 * @param {string} categoryId
 * @param {string} subfolderName
 * @param {Function} getSubfolderFilter - Returns current subfolder filter string or null
 * @param {Function} getCategoryIdFilter - Returns current category ID filter or null
 */
export function handleSubfolderClick(categoryId, subfolderName, getSubfolderFilter, getCategoryIdFilter) {
    const layoutModule = window.ragotModules?.streamingLayout;
    if (!layoutModule) return;

    if (categoryId && categoryId.startsWith('auto::') && typeof layoutModule.setCategoryFilter === 'function') {
        const derivedId = `${categoryId}::${subfolderName}`;
        const displayName = subfolderName
            ? subfolderName.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
            : subfolderName;
        layoutModule.setCategoryFilter(derivedId, displayName);
        return;
    }

    if (typeof layoutModule.setSubfolderFilterAction === 'function') {
        const currentSubfolder = getSubfolderFilter();
        const currentCategoryFilter = getCategoryIdFilter();
        let newSubfolderPath = subfolderName;

        if (currentSubfolder && currentCategoryFilter === categoryId) {
            newSubfolderPath = currentSubfolder.replace(/\/$/, '') + '/' + subfolderName;
        }

        layoutModule.setSubfolderFilterAction(categoryId, newSubfolderPath);
    }
}
