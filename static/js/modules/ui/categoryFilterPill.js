/**
 * Category Filter Pill UI helpers
 */

import { attr, toggle, $, $$ } from '../../libs/ragot.esm.min.js';

/**
 * Extract the leaf name: the part before any parenthetical breadcrumb
 * e.g. "Action (Movies › sda2 › ghost)" -> "Action"
 * @param {string} categoryName
 * @returns {string}
 */
export function getLeafName(categoryName) {
    if (!categoryName) return '';

    // Handle parenthetical breadcrumbs: "Action (Movies › sda2 › ghost)" -> "Action"
    let name = categoryName.includes('(')
        ? categoryName.split('(')[0].trim()
        : categoryName.trim();

    // Handle breadcrumb separators: "Movies › sda2 › ghost" -> "ghost"
    if (name.includes(' › ')) {
        const parts = name.split(' › ');
        name = parts[parts.length - 1].trim();
    } else if (name.includes(' > ')) {
        const parts = name.split(' > ');
        name = parts[parts.length - 1].trim();
    }

    return name;
}

/**
 * Update the category filter pill across layouts.
 * @param {string|null} categoryName - Selected category name.
 */
export function updateCategoryFilterPill(categoryName) {
    const pills = $$('[data-category-filter-pill]');
    pills.forEach((pill) => {
        // Ensure fade-toggle class and a11y attrs are present
        if (!pill.classList.contains('gh-fade-toggle')) {
            pill.classList.add('gh-fade-toggle');
            pill.setAttribute('role', 'button');
            pill.setAttribute('tabindex', '0');
            pill.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    pill.click();
                }
            });
        }

        if (categoryName) {
            pill.textContent = getLeafName(categoryName);
            pill.classList.add('pill--active');
            pill.removeAttribute('data-hidden');

            // Attach managed click-to-clear handler
            attr(pill, { onClick: handlePillClear });
        } else {
            pill.textContent = '';
            pill.classList.remove('pill--active');
            pill.setAttribute('data-hidden', '');
            attr(pill, { onClick: null });
        }

        // Also hide/show the wrapper container so it doesn't occupy flex space
        const wrapper = pill.closest('.category-active-filter');
        if (wrapper) {
            if (!wrapper.classList.contains('gh-fade-toggle')) {
                wrapper.classList.add('gh-fade-toggle');
            }
            if (categoryName) {
                wrapper.removeAttribute('data-hidden');
            } else {
                wrapper.setAttribute('data-hidden', '');
            }
        }
    });
}

/**
 * Handle pill click: navigate back or clear filters on the active layout.
 * Scroll-to-top is handled by the layout navigation functions themselves
 * (setCategoryFilter / setSubfolderFilterAction) so we don't need to
 * manage it here.
 */
export function handlePillClear() {
    const currentLayout = document.documentElement.getAttribute('data-layout');
    let layoutModule = null;

    if (currentLayout === 'streaming') {
        layoutModule = window.ragotModules?.streamingLayout;
    } else if (currentLayout === 'gallery') {
        layoutModule = window.ragotModules?.galleryLayout;
    }

    if (layoutModule) {
        // Professional Step-back logic: If in a subfolder, go to parent subfolder or category root
        if (typeof layoutModule.getSubfolderFilter === 'function' &&
            typeof layoutModule.setSubfolderFilterAction === 'function') {

            const currentSubfolder = layoutModule.getSubfolderFilter();
            if (currentSubfolder) {
                const parts = currentSubfolder.split('/').filter(Boolean);
                parts.pop(); // Remove leaf folder
                const parentPath = parts.join('/');

                const categoryId = typeof layoutModule.getCategoryIdFilter === 'function'
                    ? layoutModule.getCategoryIdFilter()
                    : null;

                if (parentPath) {
                    console.log(`[Pill] Stepping back to parent subfolder: ${parentPath}`);
                    layoutModule.setSubfolderFilterAction(categoryId, parentPath);
                    return;
                } else if (categoryId) {
                    console.log(`[Pill] Stepping back to category root: ${categoryId}`);
                    if (categoryId.startsWith('auto::')) {
                        const fallbackName = resolveAutoCategoryDisplayName(layoutModule, categoryId);
                        layoutModule.setCategoryFilter(categoryId, fallbackName);
                    } else {
                        layoutModule.setCategoryFilter(categoryId);
                    }
                    return;
                }
            }
        }

        // Auto category step-back: if no subfolder filter, walk up the auto:: chain
        const categoryId = (typeof layoutModule.getCategoryIdFilter === 'function')
            ? layoutModule.getCategoryIdFilter()
            : null;
        if (categoryId && categoryId.startsWith('auto::')) {
            const parts = categoryId.split('::');
            if (parts.length > 2 && typeof layoutModule.setCategoryFilter === 'function') {
                const parentId = parts.slice(0, -1).join('::');
                const parentLeaf = parts[parts.length - 2] || '';
                if (parentLeaf.toLowerCase() === 'ghost') {
                    console.log('[Pill] Stepping back past hidden root');
                    layoutModule.setCategoryFilter(null, null);
                } else {
                    console.log(`[Pill] Stepping back to parent category: ${parentId}`);
                    layoutModule.setCategoryFilter(parentId, resolveAutoCategoryDisplayName(layoutModule, parentId));
                }
                return;
            }
        }

        // Default fallback: Clear all filters (category, parent, subfolder) and reload
        if (typeof layoutModule.setCategoryFilter === 'function') {
            console.log('[Pill] Clearing all filters');
            layoutModule.setCategoryFilter(null, null);
        }
    }
}

/**
 * Persistent id→display-name cache. The layouts overwrite categoriesData with
 * a single entry while a filter is active, so the parent's display name (which
 * encodes the user-defined drive label) would otherwise be lost when stepping
 * back through the pill. We seed this cache from every category fetch and use
 * it as the source of truth for auto-category step-back labels.
 */
const _categoryNameCache = new Map();

export function rememberCategoryNames(categories) {
    if (!Array.isArray(categories)) return;
    for (const category of categories) {
        if (!category) continue;
        const id = category.id || category.category_id;
        const name = category.name || category.category_name;
        if (id && name) _categoryNameCache.set(id, name);
    }
}

export function rememberCategoryName(id, name) {
    if (id && name) _categoryNameCache.set(id, name);
}

/**
 * Resolve the display name for an auto:: category id, preferring the
 * server-provided name (which carries the renamed-USB label) from the
 * persistent cache. Falls back to the active layout's categoriesData and
 * finally to a title-cased leaf.
 */
function resolveAutoCategoryDisplayName(layoutModule, categoryId) {
    if (!categoryId) return null;
    const cached = _categoryNameCache.get(categoryId);
    if (cached) return cached;
    try {
        const categories = (typeof layoutModule?.getCategoriesData === 'function')
            ? layoutModule.getCategoriesData()
            : null;
        const resolved = resolveCategoryName(categoryId, categories || [], null);
        if (resolved) return resolved;
    } catch (_) { /* fall through */ }
    return formatAutoCategoryName(categoryId);
}

function formatAutoCategoryName(categoryId) {
    if (!categoryId || !categoryId.startsWith('auto::')) return null;
    const parts = categoryId.split('::').filter(Boolean);
    const leaf = parts[parts.length - 1];
    if (!leaf) return null;
    return leaf.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Resolve category name from available data.
 * @param {string} categoryId - Category ID.
 * @param {Array} categories - Categories data array.
 * @param {string|null} fallbackName - Name from caller.
 * @returns {string|null}
 */
export function resolveCategoryName(categoryId, categories = [], fallbackName = null) {
    if (fallbackName) return fallbackName;
    if (!categoryId) return null;

    const match = categories.find((category) => (
        category?.id === categoryId || category?.category_id === categoryId
    ));

    return match?.name || match?.category_name || null;
}

let pendingScroll = false;

/**
 * Request that the filter bar be scrolled into view after the next render.
 * Used when navigating categories to skip the large hero section.
 */
export function requestFilterBarScroll() {
    pendingScroll = true;
}

/**
 * Perform any pending filter bar scrolls.
 * Called by layout renderers after content is loaded and DOM is stable.
 */
export function flushFilterBarScroll() {
    if (!pendingScroll) return;
    pendingScroll = false;

    // Use a small timeout to ensure DOM is ready and hero height is stable
    setTimeout(() => {
        const filterBar = $('.streaming-filter-bar');
        const nextFilterBar = filterBar || $('.gh-streaming__filter-bar');
        if (nextFilterBar) {
            nextFilterBar.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }, 150);
}
