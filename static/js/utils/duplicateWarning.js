/**
 * Duplicate Warning Modal
 * Shows a warning when duplicate files are detected before upload
 * Mobile-friendly and desktop-compatible with inline rename functionality
 */

import { getDuplicateState, resetDuplicateState } from './uploadManager.js';
import { Component, createElement, $, $$ } from '../libs/ragot.esm.min.js';
import { toast } from './notificationManager.js';

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

class DuplicateWarningComponent extends Component {
    constructor(files, onSkip, onRename) {
        super();
        this.files = files;
        this.onSkip = onSkip;
        this.onRename = onRename;
        this.duplicateFiles = [];
        this.activeOutsideClickRemovers = new Map();
        this.escapeHandler = this.handleEscape.bind(this);
        this.resetStateOnUnmount = true;

        const state = getDuplicateState();
        const duplicateSet = new Set(state.duplicates || []);
        this.duplicateFiles = (files || []).filter(f => {
            const displayPath = f.relativePath || f.file?.name;
            return duplicateSet.has(displayPath);
        });
    }

    render() {
        return createElement('div', {
            className: 'duplicate-warning-modal',
            innerHTML: `
                <div class="duplicate-warning-overlay"></div>
                <div class="duplicate-warning-content">
                    <div class="duplicate-warning-header">
                        <div class="duplicate-warning-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/>
                                <line x1="12" y1="17" x2="12.01" y2="17"/>
                            </svg>
                        </div>
                        <div class="duplicate-warning-title">
                            <h3>${this.duplicateFiles.length} Duplicate File${this.duplicateFiles.length !== 1 ? 's' : ''} Detected</h3>
                            <p>Click filename to rename, or skip/upload with auto-numbering:</p>
                        </div>
                        <button class="duplicate-warning-close" title="Close">x</button>
                    </div>
                    <div class="duplicate-warning-list">
                        ${this.duplicateFiles.slice(0, 10).map((fileInfo, index) => {
        const filename = fileInfo.file.name;
        const lastDot = filename.lastIndexOf('.');
        const baseName = lastDot !== -1 ? filename.substring(0, lastDot) : filename;
        const ext = lastDot !== -1 ? filename.substring(lastDot) : '';

        return `
                                <div class="duplicate-warning-item" data-index="${index}">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                                        <polyline points="13 2 13 9 20 9"/>
                                    </svg>
                                    <div class="duplicate-file-name-container" data-index="${index}">
                                        <span class="duplicate-file-name-static" title="Click to rename">${escapeHtml(filename)}</span>
                                        <div class="duplicate-rename-container hidden">
                                            <input type="text"
                                                   class="duplicate-rename-input"
                                                   value="${escapeHtml(baseName)}"
                                                   placeholder="New name..."
                                                   data-index="${index}">
                                            <span class="duplicate-file-ext">${escapeHtml(ext)}</span>
                                            <button class="duplicate-rename-confirm-btn" data-index="${index}" title="Confirm">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                    <polyline points="20 6 9 17 4 12"/>
                                                </svg>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            `;
    }).join('')}
                        ${this.duplicateFiles.length > 10 ? `
                            <div class="duplicate-warning-more">
                                +${this.duplicateFiles.length - 10} more file${this.duplicateFiles.length - 10 !== 1 ? 's' : ''} (click first 10 to rename)
                            </div>
                        ` : ''}
                    </div>
                    <div class="duplicate-warning-footer">
                        <p class="duplicate-warning-note">
                            <strong>Skip:</strong> Don't upload duplicates  <strong>Rename:</strong> Upload with new names  <strong>Upload:</strong> Auto-number (file_1.jpg)
                        </p>
                        <div class="duplicate-warning-actions">
                            <button class="duplicate-warning-btn duplicate-warning-skip">Skip Duplicates</button>
                            <button class="duplicate-warning-btn duplicate-warning-rename">Rename & Upload</button>
                            <button class="duplicate-warning-btn duplicate-warning-upload">Upload Anyway</button>
                        </div>
                    </div>
                </div>
            `
        });
    }

    onStart() {
        this.on($('.duplicate-warning-close', this.element), 'click', this.closeModal);
        this.on($('.duplicate-warning-overlay', this.element), 'click', this.closeModal);
        this.on($('.duplicate-warning-skip', this.element), 'click', this.handleSkip);
        this.on($('.duplicate-warning-rename', this.element), 'click', this.handleRename);
        this.on($('.duplicate-warning-upload', this.element), 'click', this.handleUpload);
        this.on(document, 'keydown', this.escapeHandler);

        $$('.duplicate-file-name-static', this.element).forEach(span => {
            this.on(span, 'click', () => {
                const index = Number.parseInt(span.parentElement.dataset.index, 10);
                this.toggleRenameMode(index, true);
            });
        });

        $$('.duplicate-rename-confirm-btn', this.element).forEach(btn => {
            this.on(btn, 'click', (e) => {
                e.stopPropagation();
                const index = Number.parseInt(btn.dataset.index, 10);
                this.confirmRename(index);
            });
        });

        $$('.duplicate-rename-input', this.element).forEach(input => {
            this.on(input, 'keydown', (e) => {
                const index = Number.parseInt(e.target.dataset.index, 10);
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.confirmRename(index);
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    this.toggleRenameMode(index, false);
                }
            });
        });
    }

    onStop() {
        for (const removeListener of this.activeOutsideClickRemovers.values()) {
            removeListener();
        }
        this.activeOutsideClickRemovers.clear();
        if (this.resetStateOnUnmount) {
            resetDuplicateState();
        }
        if (activeModal === this) {
            activeModal = null;
        }
    }

    closeModal = () => {
        this.unmount();
    };

    handleEscape(e) {
        if (e.key === 'Escape') {
            this.closeModal();
        }
    }

    handleSkip = () => {
        this.resetStateOnUnmount = false;
        this.unmount();
        if (this.onSkip) this.onSkip();
    };

    handleRename = () => {
        this.resetStateOnUnmount = false;
        this.unmount();
        if (this.onRename) this.onRename();
    };

    handleUpload = () => {
        this.resetStateOnUnmount = false;
        this.unmount();
        if (this.onRename) this.onRename();
    };

    toggleRenameMode(index, isEditing) {
        const container = $(`.duplicate-file-name-container[data-index="${index}"]`, this.element);
        if (!container) return;

        const staticName = $('.duplicate-file-name-static', container);
        const renameBox = $('.duplicate-rename-container', container);
        const input = $('.duplicate-rename-input', container);

        if (isEditing) {
            staticName.classList.add('hidden');
            renameBox.classList.remove('hidden');
            input.focus();
            input.select();

            const previous = this.activeOutsideClickRemovers.get(index);
            if (previous) previous();

            const outsideClick = (e) => {
                if (!container.contains(e.target)) {
                    this.toggleRenameMode(index, false);
                }
            };

            const timeoutId = setTimeout(() => {
                this.on(document, 'click', outsideClick);
                this.activeOutsideClickRemovers.set(index, () => this.off(document, 'click', outsideClick));
            }, 10);

            this.activeOutsideClickRemovers.set(index, () => clearTimeout(timeoutId));
        } else {
            staticName.classList.remove('hidden');
            renameBox.classList.add('hidden');
            const removeListener = this.activeOutsideClickRemovers.get(index);
            if (removeListener) removeListener();
            this.activeOutsideClickRemovers.delete(index);
        }
    }

    confirmRename(index) {
        const input = $(`.duplicate-rename-input[data-index="${index}"]`, this.element);
        const newBaseName = input.value.trim();

        if (!newBaseName) {
            toast.error('Filename cannot be empty');
            return;
        }

        this.duplicateFiles[index].customFilename = newBaseName;

        const container = $(`.duplicate-file-name-container[data-index="${index}"]`, this.element);
        const staticName = $('.duplicate-file-name-static', container);
        const filename = this.duplicateFiles[index].file.name;
        const lastDot = filename.lastIndexOf('.');
        const ext = lastDot !== -1 ? filename.substring(lastDot) : '';
        staticName.textContent = newBaseName + ext;

        this.toggleRenameMode(index, false);
    }
}

let activeModal = null;

/**
 * Show duplicate warning modal with inline rename capability
 * @param {Array} files - Array of file objects to potentially rename
 * @param {Function} onSkip - Callback when user chooses to skip duplicates
 * @param {Function} onRename - Callback when user renames and uploads
 */
export function showDuplicateWarning(files, onSkip, onRename) {
    const state = getDuplicateState();

    if (!state.duplicates || state.duplicates.length === 0) {
        return;
    }

    if (activeModal) {
        activeModal.unmount();
        activeModal = null;
    }

    activeModal = new DuplicateWarningComponent(files, onSkip, onRename);
    activeModal.mount(document.body);
}

/**
 * Create duplicate warning icon badge
 * Shows a red warning badge that can be clicked to show the duplicate modal
 * @returns {HTMLElement}
 */
export function createDuplicateWarningBadge() {
    const state = getDuplicateState();

    if (!state.duplicates || state.duplicates.length === 0) {
        return null;
    }

    return createElement('div', {
        className: 'duplicate-warning-badge',
        title: `${state.duplicates.length} duplicate file${state.duplicates.length !== 1 ? 's' : ''} detected - Click to review`,
        innerHTML: `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span>${state.duplicates.length}</span>
    `
    });
}
