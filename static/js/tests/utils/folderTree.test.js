import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('folderTree', () => {
    let renderFolderTree;
    let onSelect;

    beforeEach(async () => {
        vi.resetModules();
        document.body.innerHTML = '<div id="tree-root"></div>';
        ({ renderFolderTree } = await import('../../utils/folderTree.js'));
        onSelect = vi.fn();
    });

    function buildTree() {
        const container = document.getElementById('tree-root');
        renderFolderTree(container, [
            {
                name: 'Movies',
                path: '/media/usb/Movies',
                children: [
                    {
                        name: 'Classics',
                        path: '/media/usb/Movies/Classics',
                        children: []
                    }
                ]
            },
            {
                name: 'Photos',
                path: '/media/usb/Photos',
                children: []
            }
        ], {
            drivePath: '/media/usb',
            onSelect
        });

        return container;
    }

    it('renders the root option and exposes selection API', () => {
        const container = buildTree();
        const treeApi = renderFolderTree(container, [], {
            drivePath: '/media/usb',
            showRoot: true,
            onSelect
        });

        expect(container.querySelector('.folder-tree-root')).not.toBeNull();
        expect(treeApi.getSelected()).toEqual({
            path: 'root',
            relativePath: '',
            fullPath: 'root'
        });
    });

    it('shows hidden folder state in manage mode', () => {
        const container = document.getElementById('tree-root');
        renderFolderTree(container, [
            {
                name: 'Private',
                path: '/media/usb/Private',
                hidden: true,
                category_id: 'cat-private',
                children: []
            }
        ], {
            drivePath: '/media/usb',
            manageMode: true,
            onSelect,
            onToggleHide: vi.fn()
        });

        expect(container.querySelector('.folder-tree-hidden')).not.toBeNull();
        expect(container.querySelector('.folder-tree-hidden-badge')?.textContent).toBe('Hidden');
    });

    it('moves keyboard focus through visible tree items with arrow keys', () => {
        const container = buildTree();
        const treeItems = container.querySelectorAll('.folder-tree-item[role="treeitem"]');
        const rootItem = treeItems[0];

        rootItem.focus();
        rootItem.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));

        expect(document.activeElement).toBe(treeItems[1]);
    });

    it('supports expanding and selecting nested folders from the keyboard', () => {
        const container = buildTree();
        const treeItems = container.querySelectorAll('.folder-tree-item[role="treeitem"]');
        const moviesItem = treeItems[1];

        moviesItem.focus();
        moviesItem.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
        moviesItem.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));

        const classicsItem = document.activeElement;
        expect(classicsItem).not.toBe(moviesItem);

        classicsItem.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

        expect(onSelect).toHaveBeenLastCalledWith({
            path: '/media/usb/Movies/Classics',
            relativePath: 'Movies/Classics',
            fullPath: '/media/usb/Movies/Classics'
        });
        expect(classicsItem.getAttribute('aria-selected')).toBe('true');
    });
});
