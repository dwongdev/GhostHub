/**
 * Collapsible Folder Tree Component
 * Shared between gallery drag-drop and file manager modal
 *
 * Features:
 * - Expandable/collapsible folders
 * - Click to select folder
 * - Visual hierarchy with indentation
 * - Respects hidden categories from backend
 * - Optional hide/unhide toggle buttons for content management
 */

import { folderClosedIcon, folderOpenIcon, chevronDownIcon, eyeOffIcon, eyeIcon } from './icons.js';
import { createElement, attr, $, $$, append, clear, createIcon } from '../libs/ragot.esm.min.js';

// Hide/Unhide icons
const HIDE_ICON = eyeOffIcon(14);
const SHOW_ICON = eyeIcon(14);

function collapseChildren(container) {
    if (!container) return;
    container.classList.add('collapsed');
}

function expandChildren(container) {
    if (!container) return;
    container.classList.remove('collapsed');
}

/**
 * Render a collapsible folder tree into a container
 * @param {HTMLElement} container - Container element to render into
 * @param {Array} folders - Array of folder objects with children from API
 * @param {Object} options - Configuration options
 * @param {Function} options.onSelect - Callback when folder is selected ({path, relativePath}) => void
 * @param {string} options.drivePath - Root drive path for relative path calculation
 * @param {boolean} options.showRoot - Whether to show "Root" option (default true)
 * @param {string} options.newFolderName - If set, shows "Create new folder" option and selects it
 * @param {string} options.folderIcon - HTML for folder icon (required)
 * @param {boolean} options.manageMode - If true, show hide/unhide toggle buttons
 * @param {Function} options.onToggleHide - Callback when hide/unhide is toggled ({categoryId, hidden, folderName}) => Promise
 * @returns {Object} - { getSelected: () => {path, relativePath, fullPath}, filter: (query) => void }
 */
export function renderFolderTree(container, folders, options = {}) {
    const {
        onSelect = () => { },
        drivePath = '',
        showRoot = true,
        newFolderName = null,
        folderIcon = folderClosedIcon(16),
        manageMode = false,
        onToggleHide = null
    } = options;

    clear(container);
    attr(container, { role: 'tree', 'aria-label': 'Folder tree' });

    // State
    let selectedPath = newFolderName ? `new:${newFolderName}` : 'root';
    let selectedRelative = newFolderName || '';
    let selectedElement = null;

    const isTreeItemVisible = (element) => {
        if (!element || element.classList.contains('folder-search-hidden')) return false;
        return !element.closest('.folder-tree-children.collapsed, .folder-tree-children.folder-search-hidden');
    };

    const getVisibleTreeItems = () => {
        return $$('.folder-tree-item[role="treeitem"]', container).filter(isTreeItemVisible);
    };

    const syncFocusableTreeItem = (elementToFocus = selectedElement) => {
        $$('.folder-tree-item[role="treeitem"]', container).forEach((item) => {
            item.tabIndex = item === elementToFocus ? 0 : -1;
        });
    };

    const focusTreeItem = (element) => {
        if (!element) return;
        syncFocusableTreeItem(element);
        element.focus({ preventScroll: true });
    };

    const moveTreeFocus = (currentElement, direction) => {
        const items = getVisibleTreeItems();
        if (items.length === 0) return;
        const currentIndex = Math.max(0, items.indexOf(currentElement));
        const nextIndex = Math.min(items.length - 1, Math.max(0, currentIndex + direction));
        focusTreeItem(items[nextIndex]);
    };

    const focusBoundaryTreeItem = (position) => {
        const items = getVisibleTreeItems();
        if (items.length === 0) return;
        focusTreeItem(position === 'end' ? items[items.length - 1] : items[0]);
    };

    const selectFolder = (element, path, relativePath, options = {}) => {
        const { shouldFocus = false } = options;
        if (selectedElement) {
            selectedElement.classList.remove('selected');
            selectedElement.setAttribute('aria-selected', 'false');
        }
        element.classList.add('selected');
        element.setAttribute('aria-selected', 'true');
        selectedElement = element;
        selectedPath = path;
        selectedRelative = relativePath;
        syncFocusableTreeItem(element);
        if (shouldFocus) focusTreeItem(element);
        onSelect({ path, relativePath, fullPath: path });
    };

    const attachLinearTreeNavigation = (element, onSelectCurrent) => {
        attr(element, {
            onKeyDown: (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectCurrent();
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    moveTreeFocus(element, 1);
                    return;
                }
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    moveTreeFocus(element, -1);
                    return;
                }
                if (e.key === 'Home') {
                    e.preventDefault();
                    focusBoundaryTreeItem('start');
                    return;
                }
                if (e.key === 'End') {
                    e.preventDefault();
                    focusBoundaryTreeItem('end');
                }
            }
        });
    };

    // "Create new folder" option if provided
    if (newFolderName) {
        const newItem = createElement('div', {
            className: 'folder-tree-item folder-tree-new selected',
            role: 'treeitem',
            tabindex: '0',
            'aria-selected': 'true',
            onClick: (e) => {
                e.stopPropagation();
                selectFolder(newItem, `new:${newFolderName}`, newFolderName, { shouldFocus: true });
            }
        });
        append(newItem, [
            createElement('span', { className: 'folder-tree-toggle' }),
            createIcon(folderIcon, 'folder-tree-icon'),
            createElement('span', { className: 'folder-tree-name', textContent: `Create new "${newFolderName}"` })
        ]);
        append(container, newItem);
        selectedElement = newItem;
        attachLinearTreeNavigation(newItem, () => selectFolder(newItem, `new:${newFolderName}`, newFolderName, { shouldFocus: true }));
    }

    // Root option
    if (showRoot) {
        const rootItem = createElement('div', {
            className: 'folder-tree-item folder-tree-root' + (!newFolderName ? ' selected' : ''),
            role: 'treeitem',
            tabindex: newFolderName ? '-1' : '0',
            'aria-selected': newFolderName ? 'false' : 'true',
            onClick: (e) => {
                e.stopPropagation();
                selectFolder(rootItem, 'root', '', { shouldFocus: true });
            }
        });
        append(rootItem, [
            createElement('span', { className: 'folder-tree-toggle' }),
            createIcon(folderOpenIcon(16), 'folder-tree-icon'),
            createElement('span', { className: 'folder-tree-name', textContent: 'Root of drive' })
        ]);
        append(container, rootItem);
        if (!newFolderName) {
            selectedElement = rootItem;
        }
        attachLinearTreeNavigation(rootItem, () => selectFolder(rootItem, 'root', '', { shouldFocus: true }));
    }

    // Render folder tree recursively
    const renderFolder = (folder, depth, parentEl) => {
        const hasChildren = folder.children && folder.children.length > 0;
        const relativePath = drivePath
            ? folder.path.replace(drivePath, '').replace(/^[\\\/]/, '').replace(/\\/g, '/')
            : folder.name;
        const isHidden = folder.hidden === true;
        const categoryId = folder.category_id || null;

        const item = createElement('div', {
            className: 'folder-tree-item' + (isHidden ? ' folder-tree-hidden' : ''),
            style: { paddingLeft: (depth * 16 + 8) + 'px' },
            dataset: { categoryId: categoryId || '' },
            role: 'treeitem',
            tabindex: '-1',
            'aria-selected': 'false',
            ...(hasChildren ? { 'aria-expanded': 'false' } : {})
        });

        // Toggle arrow
        const toggle = createElement('span', {
            className: 'folder-tree-toggle' + (hasChildren ? ' has-children' : ''),
        });
        if (hasChildren) {
            append(toggle, createIcon(chevronDownIcon(12), 'chevron-right'));
        }
        append(item, toggle);

        // Icon (starts closed, will update when toggled)
        const icon = createIcon(hasChildren ? folderClosedIcon(16) : folderIcon, 'folder-tree-icon');
        append(item, icon);

        // Name container (for name + badge)
        const nameContainer = createElement('span', { className: 'folder-tree-name-container' });

        append(nameContainer, createElement('span', { className: 'folder-tree-name', textContent: folder.name }));

        // Hidden badge (if hidden and in manage mode)
        if (manageMode && isHidden) {
            append(nameContainer, createElement('span', { className: 'folder-tree-hidden-badge', textContent: 'Hidden' }));
        }

        append(item, nameContainer);

        // Hide/Unhide toggle button (only in manage mode)
        if (manageMode && categoryId && onToggleHide) {
            const hideBtn = createElement('button', {
                className: 'folder-tree-hide-btn' + (isHidden ? ' is-hidden' : ''),
                innerHTML: isHidden ? SHOW_ICON : HIDE_ICON,
                title: isHidden ? 'Unhide folder' : 'Hide folder',
                onClick: async (e) => {
                    e.stopPropagation();
                    hideBtn.disabled = true;
                    try {
                        await onToggleHide({
                            categoryId: categoryId,
                            hidden: isHidden,
                            folderName: folder.name
                        });

                        // Note: isHidden logic here refers to the state BEFORE the click
                        // So if it was hidden, now it's unhidden (show), and vice versa
                        const newHiddenState = !isHidden;

                        // UI update for children is handled by re-rendering the whole tree usually,
                        // but if not, we should visually update children to reflect the cascade
                        if (childrenContainer) {
                            const childBtns = $$('.folder-tree-hide-btn', childrenContainer);
                            childBtns.forEach(btn => {
                                // Update icon and class based on parent's new state
                                if (newHiddenState) {
                                    // Parent was just hidden -> hide all children visually
                                    btn.classList.add('is-hidden');
                                    btn.innerHTML = SHOW_ICON;
                                    btn.title = 'Unhide folder';
                                    // Also update the row style
                                    const row = btn.closest('.folder-tree-item');
                                    if (row) {
                                        row.classList.add('folder-tree-hidden');
                                        // Add badge if needed
                                        const nc = $('.folder-tree-name-container', row);
                                        if (nc && !$('.folder-tree-hidden-badge', nc)) {
                                            append(nc, createElement('span', { className: 'folder-tree-hidden-badge', textContent: 'Hidden' }));
                                        }
                                    }
                                }
                            });
                        }

                    } catch (err) {
                        console.error('Error toggling folder hide:', err);
                    } finally {
                        hideBtn.disabled = false;
                    }
                }
            });
            append(item, hideBtn);
        }

        // Children container
        let childrenContainer = null;
        if (hasChildren) {
            childrenContainer = createElement('div', { className: 'folder-tree-children collapsed' });
            for (const child of folder.children) {
                renderFolder(child, depth + 1, childrenContainer);
            }
        }

        // Toggle expand/collapse
        attr(toggle, {
            onClick: (e) => {
                e.stopPropagation();
                if (!hasChildren) return;
                const isCollapsed = !childrenContainer.classList.contains('collapsed');
                if (isCollapsed) collapseChildren(childrenContainer);
                else expandChildren(childrenContainer);
                item.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
                const chevron = $('.chevron-right', toggle);
                if (chevron) {
                    chevron.style.transform = isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)';
                }
                // Update folder icon based on expanded state
                icon.innerHTML = isCollapsed ? folderClosedIcon(16) : folderOpenIcon(16);
            }
        });

        // Select folder
        attr(item, {
            onClick: (e) => {
                e.stopPropagation();
                selectFolder(item, folder.path, relativePath, { shouldFocus: true });
            },
            onKeyDown: (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectFolder(item, folder.path, relativePath, { shouldFocus: true });
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    moveTreeFocus(item, 1);
                    return;
                }
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    moveTreeFocus(item, -1);
                    return;
                }
                if (e.key === 'Home') {
                    e.preventDefault();
                    focusBoundaryTreeItem('start');
                    return;
                }
                if (e.key === 'End') {
                    e.preventDefault();
                    focusBoundaryTreeItem('end');
                    return;
                }
                if (e.key === 'ArrowRight' && hasChildren && childrenContainer.classList.contains('collapsed')) {
                    e.preventDefault();
                    expandChildren(childrenContainer);
                    item.setAttribute('aria-expanded', 'true');
                    icon.innerHTML = folderOpenIcon(16);
                    return;
                }
                if (e.key === 'ArrowRight' && hasChildren) {
                    e.preventDefault();
                    const firstChild = childrenContainer?.querySelector('.folder-tree-item[role="treeitem"]');
                    if (firstChild) focusTreeItem(firstChild);
                    return;
                }
                if (e.key === 'ArrowLeft' && hasChildren && !childrenContainer.classList.contains('collapsed')) {
                    e.preventDefault();
                    collapseChildren(childrenContainer);
                    item.setAttribute('aria-expanded', 'false');
                    icon.innerHTML = folderClosedIcon(16);
                    return;
                }
                if (e.key === 'ArrowLeft') {
                    const parentChildren = item.parentElement?.closest('.folder-tree-children');
                    const parentItem = parentChildren?.previousElementSibling;
                    if (parentItem?.classList.contains('folder-tree-item')) {
                        e.preventDefault();
                        focusTreeItem(parentItem);
                    }
                }
            }
        });

        append(parentEl, item);
        if (childrenContainer) append(parentEl, childrenContainer);
    };

    /**
     * Filter the tree by a query string
     * @param {string} query 
     */
    const filter = (query) => {
        const q = query.toLowerCase().trim();
        const items = $$('.folder-tree-item', container);
        const children = $$('.folder-tree-children', container);

        // Reset
        items.forEach(el => {
            el.classList.remove('folder-search-hidden');
            const nameEl = $('.folder-tree-name', el);
            if (nameEl && nameEl.dataset.originalText) {
                nameEl.textContent = nameEl.dataset.originalText;
            }
        });
        children.forEach(el => el.classList.remove('folder-search-hidden'));

        if (!q) return;

        // Hide all initially
        items.forEach(el => el.classList.add('folder-search-hidden'));
        children.forEach(el => el.classList.add('folder-search-hidden'));

        items.forEach(el => {
            const nameEl = $('.folder-tree-name', el);
            if (!nameEl) return;

            if (!nameEl.dataset.originalText) {
                nameEl.dataset.originalText = nameEl.textContent;
            }

            const text = nameEl.dataset.originalText;
            const idx = text.toLowerCase().indexOf(q);

            if (idx !== -1) {
                // Match found
                el.classList.remove('folder-search-hidden');

                // Highlight
                const matchedPart = text.substring(idx, idx + q.length);
                const before = text.substring(0, idx);
                const after = text.substring(idx + q.length);

                clear(nameEl);
                append(nameEl, [
                    before,
                    createElement('span', { className: 'folder-search-highlight', textContent: matchedPart }),
                    after
                ]);

                // Show all parents and their child containers
                let current = el;
                while (current && current !== container) {
                    if (current.classList.contains('folder-tree-children')) {
                        current.classList.remove('folder-search-hidden');
                        expandChildren(current);

                        const parentItem = current.previousElementSibling;
                        if (parentItem && parentItem.classList.contains('folder-tree-item')) {
                            parentItem.classList.remove('folder-search-hidden');

                            // Update icons/chevron
                            const tgl = $('.folder-tree-toggle', parentItem);
                            if (tgl) {
                                const chv = $('.chevron-right', tgl);
                                if (chv) chv.style.transform = 'rotate(90deg)';
                            }
                            const icn = $('.folder-tree-icon', parentItem);
                            if (icn) icn.innerHTML = folderOpenIcon(16);
                        }
                    }
                    current = current.parentElement;
                }
            }
        });
    };

    // Render all top-level folders
    for (const folder of folders) {
        renderFolder(folder, 0, container);
    }

    syncFocusableTreeItem(selectedElement);

    // Return API for getting current selection
    return {
        getSelected: () => ({ path: selectedPath, relativePath: selectedRelative, fullPath: selectedPath }),
        filter
    };
}
