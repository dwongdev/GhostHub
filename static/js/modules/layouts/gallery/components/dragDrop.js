/**
 * Gallery Layout - Drag & Drop Component
 * Reuses shared uploadManager logic instead of duplicating code
 */

import { ensureFeatureAccess } from '../../../../utils/authManager.js';
import {
    uploadFiles as uploadFilesOptimized,
    resetUploadState,
    checkDuplicates,
    resetDuplicateState,
    getDuplicateState
} from '../../../../utils/uploadManager.js';
import { showDuplicateWarning, createDuplicateWarningBadge } from '../../../../utils/duplicateWarning.js';
import { renderFolderTree } from '../../../../utils/folderTree.js';
import { videoIcon, imageIcon } from '../../../../utils/icons.js';
import { getContainer } from '../state.js';
import { refreshAllLayouts } from '../../../../utils/liveVisibility.js';
import { createElement, attr, $, $$, append, clear, createIcon } from '../../../../libs/ragot.esm.min.js';
import { toast } from '../../../../utils/notificationManager.js';

/**
 * Setup drag-drop upload on gallery area (files AND folders)
 * Uses shared uploadManager logic to avoid code duplication
 */
export function setupGalleryDragDrop() {
    const container = getContainer();
    if (!container) return;

    const main = $('.gallery-main', container);
    const scrollArea = $('.gallery-scroll-area', container);
    if (!main || !scrollArea) return;

    // Create drop overlay INSIDE scroll-area (not main) to avoid blocking toolbar touches
    let dropOverlay = $('.gallery-drop-overlay', scrollArea);
    if (!dropOverlay) {
        dropOverlay = createElement('div', {
            className: 'gallery-drop-overlay',
            style: { pointerEvents: 'none' },
            innerHTML: `
            <div class="gallery-drop-content">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <p>Drop files or folders to upload</p>
            </div>
        ` });
        scrollArea.appendChild(dropOverlay);
    }

    let dragCounter = 0;

    attr(main, {
        onDragEnter: (e) => {
            e.preventDefault();
            dragCounter++;
            if (e.dataTransfer?.types?.includes('Files')) {
                dropOverlay.classList.add('active');
                dropOverlay.style.pointerEvents = 'auto';
            }
        },
        onDragLeave: (e) => {
            e.preventDefault();
            dragCounter--;
            if (dragCounter === 0) {
                dropOverlay.classList.remove('active');
                dropOverlay.style.pointerEvents = 'none';
            }
        },
        onDragOver: (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        },
        onDrop: async (e) => {
            e.preventDefault();
            dragCounter = 0;
            dropOverlay.classList.remove('active');
            dropOverlay.style.pointerEvents = 'none';

            const accessGranted = await ensureFeatureAccess();
            if (!accessGranted) return;

            const { files, folderName } = await getFilesFromDrop(e.dataTransfer);
            if (files.length === 0) {
                toast.error('No image or video files found.');
                return;
            }

            showDropFilesPreview(files, folderName);
        }
    });
}

/**
 * Get files from DataTransfer including folder contents
 */
async function getFilesFromDrop(dataTransfer) {
    const files = [];
    let folderName = null;
    const items = dataTransfer.items;

    if (items) {
        const entries = [];
        for (let i = 0; i < items.length; i++) {
            const entry = items[i].webkitGetAsEntry?.();
            if (entry) entries.push(entry);
        }

        if (entries.length === 1 && entries[0].isDirectory) {
            folderName = entries[0].name;
        }

        for (const entry of entries) {
            await traverseFileEntry(entry, '', files);
        }
    }

    if (files.length === 0) {
        for (const file of dataTransfer.files) {
            if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
                files.push({ file, relativePath: '' });
            }
        }
    }

    return { files, folderName };
}

async function traverseFileEntry(entry, path, files) {
    if (entry.isFile) {
        const file = await new Promise(resolve => entry.file(resolve));
        if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
            const relativePath = path ? `${path}/${file.name}` : file.name;
            files.push({ file, relativePath });
        }
    } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const entries = await new Promise((resolve) => {
            const allEntries = [];
            const readEntries = () => {
                reader.readEntries((results) => {
                    if (results.length) {
                        allEntries.push(...results);
                        readEntries();
                    } else {
                        resolve(allEntries);
                    }
                });
            };
            readEntries();
        });

        const newPath = path ? `${path}/${entry.name}` : entry.name;
        for (const e of entries) {
            await traverseFileEntry(e, newPath, files);
        }
    }
}

/**
 * Format bytes for display
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Show dropped files preview with drive selection and folder options
 */
async function showDropFilesPreview(files, folderName = null) {
    $('.gallery-drop-preview')?.remove();

    let filesToUpload = [...files];
    const isFolder = !!folderName;
    let selectedDrivePath = '';

    const popup = createElement('div', { className: 'gallery-drop-preview' });
    const overlay = createElement('div', { className: 'gallery-drop-preview-overlay' });
    const content = createElement('div', { className: 'gallery-drop-preview-content' });

    const header = createElement('div', { className: 'gallery-drop-preview-header' },
        createElement('h3', { textContent: isFolder ? `Folder: ${folderName}` : `Upload ${filesToUpload.length} file${filesToUpload.length !== 1 ? 's' : ''}` }),
        createElement('button', { className: 'gallery-drop-preview-close', textContent: '×' })
    );

    const driveSection = createElement('div', { className: 'gallery-drop-preview-drive' },
        createElement('label', { textContent: 'Drive:' }),
        createElement('select', { id: 'drop-drive-select' },
            createElement('option', { value: '', textContent: 'Loading drives...' })
        )
    );

    const categorySection = createElement('div', { className: 'gallery-drop-preview-category' },
        createElement('label', { textContent: isFolder ? 'Create as:' : 'Upload to:' }),
        createElement('div', { id: 'drop-folder-tree', className: 'folder-tree-container' },
            createElement('div', { className: 'folder-tree-placeholder', textContent: 'Select drive first...' })
        )
    );

    const filesContainer = createElement('div', { className: 'gallery-drop-preview-files' });

    const footer = createElement('div', { className: 'gallery-drop-preview-footer' });
    const totalSpan = createElement('span', { className: 'gallery-drop-preview-total' });
    const actions = createElement('div', { className: 'gallery-drop-preview-actions' });
    const cancelBtn = createElement('button', { className: 'gallery-drop-cancel', textContent: 'Cancel' });
    const uploadBtn = createElement('button', { className: 'gallery-drop-upload', disabled: true, textContent: 'Upload' });
    append(actions, [cancelBtn, uploadBtn]);
    append(footer, [totalSpan, actions]);

    append(content, [header, driveSection, categorySection, filesContainer, footer]);
    append(popup, [overlay, content]);

    append(document.body, popup);

    const driveSelect = $('#drop-drive-select', popup);
    const folderTreeContainer = $('#drop-folder-tree', popup);
    let selectedFolderPath = 'root';
    let selectedFolderRelative = '';
    const closeBtn = $('.gallery-drop-preview-close', popup);

    try {
        const response = await fetch('/api/storage/drives');
        const data = await response.json();
        clear(driveSelect);
        append(driveSelect, createElement('option', { value: '', textContent: 'Select drive...' }));
        (data.drives || []).forEach(drive => {
            append(driveSelect, createElement('option', { value: drive.path, textContent: `${drive.name} (${drive.free_formatted} free)` }));
        });
    } catch (e) {
        console.error('[GalleryLayout] Failed to load drives:', e);
        clear(driveSelect);
        append(driveSelect, createElement('option', { value: '', textContent: 'Failed to load drives' }));
    }

    let folderTreeApi = null;

    const checkForDuplicates = async () => {
        if (!selectedDrivePath || filesToUpload.length === 0) return;

        // Get subfolder based on selection
        let subfolder = '';
        if (selectedFolderPath.startsWith('new:')) {
            subfolder = selectedFolderPath.substring(4);
        } else if (selectedFolderPath !== 'root' && selectedFolderPath) {
            subfolder = selectedFolderRelative;
        }

        resetDuplicateState();
        await checkDuplicates(filesToUpload, selectedDrivePath, subfolder);
        updateDuplicateBadge();
    };

    const updateDuplicateBadge = () => {
        // Remove existing badge
        $('.duplicate-warning-badge', popup)?.remove();

        const duplicateState = getDuplicateState();
        if (duplicateState.duplicates && duplicateState.duplicates.length > 0) {
            const badge = createDuplicateWarningBadge();
            if (badge) {
                const footer = $('.gallery-drop-preview-footer', popup);
                footer.insertBefore(badge, footer.firstChild);

                attr(badge, {
                    onClick: () => {
                        showDuplicateWarning(
                            filesToUpload, // Pass files array for inline renaming
                            () => {
                                // User chose to skip duplicates
                                const state = getDuplicateState();
                                state.userChoice = 'skip';
                                uploadBtn.click();
                            },
                            () => {
                                // User chose to rename/upload anyway
                                const state = getDuplicateState();
                                state.userChoice = 'upload';
                                uploadBtn.click();
                            }
                        );
                    }
                });
            }
        }
    };

    const loadFolders = async (drivePath) => {
        selectedDrivePath = drivePath;
        folderTreeContainer.innerHTML = '<div class="folder-tree-placeholder">Loading...</div>';

        if (!drivePath) {
            folderTreeContainer.innerHTML = '<div class="folder-tree-placeholder">Select drive first...</div>';
            uploadBtn.disabled = true;
            return;
        }

        try {
            const response = await fetch(`/api/storage/folders?path=${encodeURIComponent(drivePath)}&include_subdirs=true`);
            const data = await response.json();

            folderTreeApi = renderFolderTree(folderTreeContainer, data.folders || [], {
                drivePath: drivePath,
                newFolderName: isFolder ? folderName : null,
                onSelect: async ({ path, relativePath }) => {
                    selectedFolderPath = path;
                    selectedFolderRelative = relativePath;
                    uploadBtn.disabled = filesToUpload.length === 0;
                    await checkForDuplicates();
                }
            });

            const initial = folderTreeApi.getSelected();
            selectedFolderPath = initial.path;
            selectedFolderRelative = initial.relativePath;

            uploadBtn.disabled = filesToUpload.length === 0;

            // Check for duplicates after folder is loaded
            await checkForDuplicates();
        } catch (e) {
            console.error('[GalleryLayout] Failed to load folders:', e);
            folderTreeContainer.innerHTML = '<div class="folder-tree-placeholder">Failed to load folders</div>';
        }
    };

    attr(driveSelect, {
        onChange: () => loadFolders(driveSelect.value)
    });

    const updateUI = async () => {
        const totalSize = filesToUpload.reduce((sum, f) => sum + f.file.size, 0);
        totalSpan.textContent = `${filesToUpload.length} file${filesToUpload.length !== 1 ? 's' : ''} (${formatBytes(totalSize)})`;

        $('.gallery-drop-preview-header h3', popup).textContent =
            `Upload ${filesToUpload.length} file${filesToUpload.length !== 1 ? 's' : ''}`;

        clear(filesContainer);
        filesToUpload.forEach((fileInfo, i) => {
            const displayName = fileInfo.relativePath || fileInfo.file.name;
            const fileEl = createElement('div', { className: 'gallery-drop-file', dataset: { index: String(i) } },
                createIcon(fileInfo.file.type.startsWith('video/') ? videoIcon(16) : imageIcon(16), 'gallery-drop-file-icon'),
                createElement('span', { className: 'gallery-drop-file-name', title: displayName, textContent: displayName }),
                createElement('span', { className: 'gallery-drop-file-size', textContent: formatBytes(fileInfo.file.size) }),
                createElement('button', { className: 'gallery-drop-file-remove', dataset: { index: String(i) }, textContent: 'Remove' })
            );
            append(filesContainer, fileEl);
        });

        $$('.gallery-drop-file-remove', filesContainer).forEach(btn => {
            attr(btn, {
                onClick: async () => {
                    filesToUpload.splice(parseInt(btn.dataset.index), 1);
                    if (filesToUpload.length === 0) {
                        popup.remove();
                    } else {
                        await updateUI();
                        await checkForDuplicates();
                    }
                }
            });
        });

        uploadBtn.disabled = filesToUpload.length === 0 || !selectedDrivePath;
    };

    updateUI();

    const closePopup = () => popup.remove();
    attr(closeBtn, { onClick: closePopup });
    attr(cancelBtn, { onClick: closePopup });
    attr(overlay, { onClick: closePopup });

    attr(uploadBtn, {
        onClick: async () => {
            if (filesToUpload.length === 0 || !selectedDrivePath) return;

            // Check if duplicates exist and user hasn't made a choice
            const duplicateState = getDuplicateState();
            if (duplicateState.duplicates.length > 0 && !duplicateState.userChoice) {
                // Show the duplicate warning modal with inline rename
                showDuplicateWarning(
                    filesToUpload, // Pass files array for inline renaming
                    () => {
                        // User chose to skip duplicates
                        duplicateState.userChoice = 'skip';
                        uploadBtn.click();
                    },
                    () => {
                        // User chose to rename/upload anyway
                        duplicateState.userChoice = 'upload';
                        uploadBtn.click();
                    }
                );
                return;
            }

            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';

            const footer = $('.gallery-drop-preview-footer', popup);
            let progressBar = $('.gallery-upload-progress-bar', footer);
            if (!progressBar) {
                progressBar = createElement('div', {
                    className: 'gallery-upload-progress-bar',
                    style: { width: '100%', height: '4px', background: 'var(--border-color, #333)', borderRadius: '2px', marginBottom: '8px', overflow: 'hidden' },
                    innerHTML: '<div class="gallery-upload-progress-fill" style="height:100%;width:0%;background:var(--accent-color,#4a9eff);transition:width 0.2s"></div>'
                });
                footer.insertBefore(progressBar, footer.firstChild);
            }
            const progressFill = $('.gallery-upload-progress-fill', progressBar);

            try {
                let subfolder = '';
                if (selectedFolderPath.startsWith('new:')) {
                    const newFolderName = selectedFolderPath.substring(4);
                    // Build parent path: if a folder is selected in the tree, create inside it
                    // Note: When "Create new folder" is selected, selectedFolderRelative is the new folder name
                    // We need to get the parent folder from the tree state
                    const parentPath = selectedDrivePath;
                    const createResponse = await fetch('/api/storage/folder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            drive_path: parentPath,
                            folder_name: newFolderName
                        })
                    });
                    if (!createResponse.ok) {
                        const err = await createResponse.json();
                        throw new Error(err.error || 'Failed to create folder');
                    }
                    subfolder = newFolderName;
                } else if (selectedFolderPath !== 'root' && selectedFolderPath) {
                    subfolder = selectedFolderRelative;
                }

                resetUploadState();

                const result = await uploadFilesOptimized(
                    filesToUpload,
                    selectedDrivePath,
                    subfolder,
                    (progress) => {
                        progressFill.style.width = `${progress}%`;
                        uploadBtn.textContent = `Uploading ${Math.round(progress)}%...`;
                    },
                    null, // onFileComplete
                    true  // skipDuplicateCheck (already checked)
                );

                // Reset duplicate state after upload
                resetDuplicateState();

                if (result.skippedAll) {
                    toast.success('All files were duplicates and were skipped.');
                } else if (result.failed > 0) {
                    toast.success(`Upload completed with ${result.failed} error(s). ${result.success} files uploaded successfully.`);
                }

                popup.remove();
                await refreshAllLayouts();
            } catch (error) {
                console.error('[GalleryLayout] Upload error:', error);
                toast.error('Upload failed: ' + error.message);
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload';
                if (progressFill) progressFill.style.width = '0%';
                resetDuplicateState();
            }
        }
    });
}
