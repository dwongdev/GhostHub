/**
 * notificationManager.js
 * Unified toast and dialog subsystem for GhostHub.
 *
 * Replaces native alert(), confirm(), and prompt() calls with:
 *   toast.success/error/info/warning(message)
 *   await dialog.alert(message, opts)
 *   await dialog.confirm(message, opts)
 *   await dialog.prompt(message, opts)
 */

import { Component, createElement } from '../libs/ragot.esm.min.js';
import { createFocusTrap } from './focusTrap.js';

const TOAST_DURATION = 3500;
const TOAST_FADE_MS = 220;
const TOAST_MAX = 5;
const DIALOG_FADE_MS = 180;

const TOAST_ICONS = {
    success: 'OK',
    error: 'X',
    warning: '!',
    info: 'i',
};

let _toastContainer = null;
let _overlayEl = null;
let _activeDialog = null;
const _activeToasts = [];

function _hasDomRoot() {
    return typeof document !== 'undefined' && !!document.body;
}

function _activateTransition(element, className) {
    if (!element) return;
    // Force the initial hidden style to commit so the visible class animates immediately.
    void element.offsetWidth;
    element.classList.add(className);
}

function _getToastContainer() {
    if (!_hasDomRoot()) return null;
    if (!_toastContainer || !_toastContainer.isConnected) {
        _toastContainer = createElement('div', { id: 'toast-container' });
        document.body.appendChild(_toastContainer);
    }
    return _toastContainer;
}

function _getOverlay() {
    if (!_hasDomRoot()) return null;
    if (!_overlayEl || !_overlayEl.isConnected) {
        _overlayEl = createElement('div', { id: 'dialog-overlay' });
        document.body.appendChild(_overlayEl);
    }
    return _overlayEl;
}

export function initNotificationManager() {
    if (!_hasDomRoot()) return false;
    _getToastContainer();
    _getOverlay();
    return true;
}

function _removeActiveToast(toastComponent) {
    const idx = _activeToasts.indexOf(toastComponent);
    if (idx !== -1) {
        _activeToasts.splice(idx, 1);
    }
}

function _getDialogDismissValue(type) {
    if (type === 'prompt') return null;
    if (type === 'alert') return undefined;
    return false;
}

class ToastComponent extends Component {
    constructor({ message, type, isHtml = false, persist = false }) {
        super({});
        this.message = message;
        this.type = type;
        this.isHtml = isHtml;
        this.persist = persist;
        this._dismissed = false;
        this._autoDismissTimer = null;
    }

    render() {
        const messageNode = this.isHtml
            ? createElement('span', {
                className: 'gh-toast__message gh-toast__message--html',
                innerHTML: this.message
            })
            : createElement('span', {
                className: 'gh-toast__message',
                textContent: this.message
            });

        return createElement('div', { className: `gh-toast gh-toast--${this.type}` },
            createElement('span', {
                className: 'gh-toast__icon',
                textContent: TOAST_ICONS[this.type] || TOAST_ICONS.info
            }),
            messageNode,
            createElement('button', {
                className: 'gh-toast__close',
                'aria-label': 'Dismiss',
                textContent: 'x',
                ref: this.ref('closeBtn'),
            })
        );
    }

    onStart() {
        this.on(this.refs.closeBtn, 'click', () => this.dismiss());
        _activateTransition(this.element, 'gh-toast--visible');
        if (!this.persist) {
            this._autoDismissTimer = this.timeout(() => this.dismiss(), TOAST_DURATION);
        }
    }

    onStop() {
        _removeActiveToast(this);
    }

    dismiss() {
        if (this._dismissed) return;

        this._dismissed = true;
        _removeActiveToast(this);

        if (this._autoDismissTimer) {
            this.clearTimeout(this._autoDismissTimer);
            this._autoDismissTimer = null;
        }

        this.element?.classList.add('gh-toast--leaving');
        this.timeout(() => this.unmount(), TOAST_FADE_MS);
    }
}

function _showToast(message, type, options = {}) {
    const container = _getToastContainer();
    if (!container) return null;

    if (_activeToasts.length >= TOAST_MAX) {
        _activeToasts[0]?.dismiss();
    }

    const toastComponent = new ToastComponent({
        message: options.isHtml ? String(message ?? '') : String(message),
        type,
        isHtml: Boolean(options.isHtml),
        persist: Boolean(options.persist),
    });

    _activeToasts.push(toastComponent);
    toastComponent.mount(container);
    return toastComponent;
}

export const toast = {
    show(message, type = 'info', options = {}) {
        return _showToast(message, type, options);
    },
    success(message, options = {}) {
        return _showToast(message, 'success', options);
    },
    error(message, options = {}) {
        return _showToast(message, 'error', options);
    },
    info(message, options = {}) {
        return _showToast(message, 'info', options);
    },
    warning(message, options = {}) {
        return _showToast(message, 'warning', options);
    },
};

class DialogComponent extends Component {
    constructor(props) {
        super({});
        this.props = props;
        this._resolved = false;
        this._focusTrap = null;
    }

    render() {
        const {
            type,
            message,
            title,
            confirmText,
            cancelText,
            btnType = 'primary',
        } = this.props;

        const isPrompt = type === 'prompt';
        const isAlert = type === 'alert';
        const showCancel = !isAlert;
        const children = [];

        if (title) {
            children.push(createElement('h3', {
                className: 'gh-dialog__title',
                textContent: title,
            }));
        }

        children.push(createElement('p', {
            className: 'gh-dialog__message',
            textContent: message,
        }));

        if (isPrompt) {
            children.push(createElement('input', {
                className: 'gh-dialog__input',
                type: 'text',
                placeholder: this.props.placeholder || '',
                value: this.props.defaultValue || '',
                ref: this.ref('input'),
            }));
        }

        const actions = [];

        if (showCancel) {
            actions.push(createElement('button', {
                className: 'btn btn--secondary gh-dialog__btn gh-dialog__btn--cancel',
                textContent: cancelText || 'Cancel',
                ref: this.ref('cancelBtn'),
            }));
        }

        actions.push(createElement('button', {
            className: `btn btn--${btnType} gh-dialog__btn gh-dialog__btn--${btnType}`,
            textContent: confirmText || (isAlert ? 'OK' : 'Confirm'),
            ref: this.ref('confirmBtn'),
        }));

        children.push(createElement('div', { className: 'gh-dialog__actions' }, ...actions));

        return createElement('div', {
            className: 'gh-dialog',
            role: 'dialog',
            'aria-modal': 'true',
        }, ...children);
    }

    onStart() {
        const { type } = this.props;
        const confirmBtn = this.refs.confirmBtn;
        const cancelBtn = this.refs.cancelBtn;
        const inputEl = this.refs.input;

        this._focusTrap = createFocusTrap(this.element, {
            initialFocus: () => inputEl || confirmBtn,
            returnFocusTo: this.props.returnFocusTo
        });
        this._focusTrap.activate();
        this.addCleanup(() => this._focusTrap?.deactivate({ restoreFocus: false }));

        const resolveConfirm = () => {
            if (type === 'prompt') {
                this._settle(inputEl ? inputEl.value : '');
            } else if (type === 'alert') {
                this._settle(undefined);
            } else {
                this._settle(true);
            }
        };

        const resolveCancel = () => {
            this._settle(_getDialogDismissValue(type));
        };

        this.on(confirmBtn, 'click', resolveConfirm);

        if (cancelBtn) {
            this.on(cancelBtn, 'click', resolveCancel);
        }

        this.on(document, 'keydown', (event) => {
            if (event.isComposing) return;

            if (event.key === 'Enter') {
                event.preventDefault();
                resolveConfirm();
            } else if (event.key === 'Escape' && type !== 'alert') {
                event.preventDefault();
                resolveCancel();
            }
        });

        if (type !== 'alert') {
            const overlay = _getOverlay();
            this.on(overlay, 'click', (event) => {
                if (event.target === overlay) {
                    resolveCancel();
                }
            });
        }

        _activateTransition(_getOverlay(), 'gh-dialog-overlay--visible');

        if (inputEl) {
            inputEl.focus();
            inputEl.select();
        } else if (confirmBtn) {
            confirmBtn.focus();
        }
    }

    forceResolve(value = _getDialogDismissValue(this.props.type)) {
        this._settle(value, { immediate: true });
    }

    _settle(value, options = {}) {
        if (this._resolved) return;

        this._resolved = true;
        const { immediate = false } = options;
        const overlay = _getOverlay();
        overlay.classList.remove('gh-dialog-overlay--visible');
        this._focusTrap?.deactivate();
        this._focusTrap = null;

        const finish = () => {
            this.unmount();
            if (_activeDialog === this) {
                _activeDialog = null;
            }
            this.props.resolve(value);
        };

        if (immediate) {
            finish();
            return;
        }

        this.timeout(finish, DIALOG_FADE_MS);
    }
}

function _openDialog(type, message, opts = {}) {
    return new Promise((resolve) => {
        const overlay = _getOverlay();
        if (!overlay) {
            resolve(_getDialogDismissValue(type));
            return;
        }

        if (_activeDialog) {
            _activeDialog.forceResolve();
        }

        const {
            title,
            confirmText,
            cancelText,
            type: btnStyleType = 'primary',
            placeholder,
            defaultValue,
        } = opts;

        const btnType = btnStyleType === 'danger' ? 'danger' : 'primary';

        const component = new DialogComponent({
            type,
            message: String(message),
            title,
            confirmText,
            cancelText,
            btnType,
            placeholder,
            defaultValue,
            returnFocusTo: document.activeElement,
            resolve,
        });

        _activeDialog = component;
        component.mount(overlay);
    });
}

export const dialog = {
    alert(message, opts) {
        return _openDialog('alert', message, opts);
    },

    confirm(message, opts) {
        return _openDialog('confirm', message, opts);
    },

    prompt(message, opts) {
        return _openDialog('prompt', message, opts);
    },
};
