/**
 * Photo Viewer Component
 * Fullscreen image viewer with pinch-to-zoom, double-tap zoom, and pan.
 */

import { Component, createElement } from '../../libs/ragot.esm.min.js';
import { VIEWER_MODES, setViewerMode } from './viewerUiController.js';
import { createFocusTrap } from '../../utils/focusTrap.js';

const MAX_ZOOM = 3;
const MIN_ZOOM = 1;

export class PhotoViewer extends Component {
    constructor() {
        super({
            isOpen: false,
            imageUrl: '',
            imageName: '',
            scale: 1,
            panX: 0,
            panY: 0,
            loading: false
        });

        // Pinch/Pan state
        this.scale = 1;
        this.panX = 0;
        this.panY = 0;
        this.pinchDist = 0;
        this.startScale = 1;
        this.isPanning = false;
        this.panStart = { x: 0, y: 0 };
        this.panStartOffset = { x: 0, y: 0 };
        this.lastTap = 0;
        this._focusTrap = null;
        this._returnFocusTo = null;
        this._touchBound = false;
    }

    onStart() {
        this.on(window, 'keydown', (e) => {
            if (this.state.isOpen && e.key === 'Escape') this.close();
        });
    }

    open(url, name) {
        this._touchBound = false;
        this.scale = 1;
        this.panX = 0;
        this.panY = 0;
        this.setState({
            isOpen: true,
            imageUrl: url,
            imageName: name || 'Photo',
            scale: 1,
            panX: 0,
            panY: 0,
            loading: true
        });
        this._returnFocusTo = document.activeElement;
        document.body.style.overflow = 'hidden';
        setViewerMode(VIEWER_MODES.PHOTO_VIEWER);
        requestAnimationFrame(() => {
            this._bindTouchEvents();
            this._focusTrap?.deactivate({ restoreFocus: false });
            this._focusTrap = createFocusTrap(this.element, {
                initialFocus: () => this.element?.querySelector('.pv-close-btn'),
                returnFocusTo: this._returnFocusTo
            });
            this._focusTrap.activate();
        });
    }

    close() {
        this._focusTrap?.deactivate();
        this._focusTrap = null;
        this.setState({ isOpen: false });
        document.body.style.overflow = '';
        const controlsAttached = window.ragotModules?.videoControls?.isControlsAttached?.();
        setViewerMode(controlsAttached ? VIEWER_MODES.VIDEO_CONTROLS : VIEWER_MODES.MEDIA);
    }

    render() {
        const { isOpen, imageUrl, imageName, loading } = this.state;

        if (!isOpen) return createElement('div', { className: 'pv-hidden' });

        return createElement('div', {
            className: `pv-overlay ${loading ? 'pv-loading' : ''}`,
            role: 'dialog',
            'aria-modal': 'true',
            'aria-label': imageName || 'Photo viewer',
            dataset: { zoomed: String(this.scale > 1.05) },
            onClick: (e) => { if (e.target === e.currentTarget) this.close(); }
        },
            createElement('button', {
                className: 'pv-close-btn',
                onClick: (e) => { e.stopPropagation(); this.close(); },
                textContent: '×'
            }),
            createElement('div', {
                className: 'pv-image-container',
                onWheel: (e) => this._handleWheel(e),
                onDblClick: (e) => this._handleDblClick(e),
                onMouseDown: (e) => this._handleMouseDown(e),
                ref: this.ref('container')
            },
                createElement('img', {
                    className: 'pv-image',
                    src: imageUrl,
                    alt: imageName,
                    draggable: false,
                    style: { transform: `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})` },
                    onLoad: () => this.setState({ loading: false }),
                    onError: () => this.setState({ loading: false }),
                    ref: this.ref('img')
                }),
                createElement('div', { className: 'pv-spinner' })
            )
        );
    }

    /**
     * Bind touch events with { passive: false } so preventDefault() works.
     * RAGOT's createElement adds listeners as passive by default which breaks
     * pinch-to-zoom and pan gestures.
     */
    _bindTouchEvents() {
        const container = this.refs.container;
        if (!container || this._touchBound) return;
        this._touchBound = true;
        this.on(container, 'touchstart', (e) => this._handleTouchStart(e), { passive: false });
        this.on(container, 'touchmove', (e) => this._handleTouchMove(e), { passive: false });
        this.on(container, 'touchend', (e) => this._handleTouchEnd(e), { passive: false });
    }

    _handleTouchStart(e) {
        e.preventDefault();
        if (e.touches.length === 2) {
            this.pinchDist = this._getTouchDist(e.touches);
            this.startScale = this.scale;
            this.isPanning = false;
        } else if (e.touches.length === 1) {
            const now = Date.now();
            if (now - this.lastTap < 300) {
                // Double-tap: reset zoom if zoomed, close if at 1x
                if (this.scale > 1.05) {
                    this._updateView(1, 0, 0);
                } else {
                    this.close();
                }
                this.lastTap = 0;
                return;
            }
            this.lastTap = now;

            if (this.scale > 1.05) {
                this.isPanning = true;
                this.panStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                this.panStartOffset = { x: this.panX, y: this.panY };
            }
        }
    }

    _handleTouchMove(e) {
        e.preventDefault();
        if (e.touches.length === 2) {
            const dist = this._getTouchDist(e.touches);
            const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, this.startScale * (dist / this.pinchDist)));
            this._updateView(newScale, this.panX, this.panY);
        } else if (e.touches.length === 1 && this.isPanning) {
            const dx = e.touches[0].clientX - this.panStart.x;
            const dy = e.touches[0].clientY - this.panStart.y;
            this._updateView(this.scale, this.panStartOffset.x + dx, this.panStartOffset.y + dy);
        }
    }

    _handleTouchEnd(e) {
        if (e.touches.length === 0) {
            this.isPanning = false;
            if (this.scale <= 1.05) this._updateView(1, 0, 0);
        }
    }

    _handleWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.15 : 0.15;
        const oldScale = this.scale;
        const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, oldScale + delta));

        let panX = this.panX;
        let panY = this.panY;
        if (this.refs.img) {
            const rect = this.refs.img.getBoundingClientRect();
            const cx = e.clientX - rect.left - rect.width / 2;
            const cy = e.clientY - rect.top - rect.height / 2;
            const factor = newScale / oldScale;
            panX = panX * factor - cx * (factor - 1);
            panY = panY * factor - cy * (factor - 1);
        }

        this._updateView(newScale, panX, panY);
    }

    _handleDblClick(e) {
        e.preventDefault();
        if (this.scale > 1.05) {
            this._updateView(1, 0, 0);
        } else {
            this.close();
        }
    }

    _handleMouseDown(e) {
        if (this.scale <= 1.05) return;
        e.preventDefault();
        this.isPanning = true;
        this.panStart = { x: e.clientX, y: e.clientY };
        this.panStartOffset = { x: this.panX, y: this.panY };

        const onMove = (ev) => {
            if (!this.isPanning) return;
            const dx = ev.clientX - this.panStart.x;
            const dy = ev.clientY - this.panStart.y;
            this._updateView(this.scale, this.panStartOffset.x + dx, this.panStartOffset.y + dy);
        };

        const onEnd = () => {
            this.isPanning = false;
            this.off(document, 'mousemove', onMove);
            this.off(document, 'mouseup', onEnd);
        };

        this.on(document, 'mousemove', onMove);
        this.on(document, 'mouseup', onEnd);
    }

    _getTouchDist(touches) {
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    _updateView(scale, panX, panY) {
        const nextScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, scale));
        const clamped = this._clampPan(nextScale, panX, panY);
        this.scale = nextScale;
        this.panX = clamped.panX;
        this.panY = clamped.panY;

        if (this.refs.img) {
            this.refs.img.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
        }

        if (this.element?.dataset) {
            this.element.dataset.zoomed = String(this.scale > 1.05);
        }
    }

    _clampPan(scale, panX, panY) {
        if (scale <= 1) {
            return { panX: 0, panY: 0 };
        }
        if (!this.refs.img) return { panX, panY };
        const container = this.refs.img.parentElement;
        const cw = container.clientWidth, ch = container.clientHeight;
        const iw = this.refs.img.naturalWidth || cw, ih = this.refs.img.naturalHeight || ch;
        const imgAspect = iw / ih, contAspect = cw / ch;
        let dw, dh;
        if (imgAspect > contAspect) { dw = cw; dh = cw / imgAspect; }
        else { dh = ch; dw = ch * imgAspect; }
        const sw = dw * scale, sh = dh * scale;
        const mx = Math.max(0, (sw - cw) / 2), my = Math.max(0, (sh - ch) / 2);
        return {
            panX: Math.max(-mx, Math.min(mx, panX)),
            panY: Math.max(-my, Math.min(my, panY))
        };
    }
}

let activeInstance = null;

export function openPhotoViewer(url, name) {
    if (!activeInstance) {
        activeInstance = new PhotoViewer();
        activeInstance.mount(document.body);
    }
    activeInstance.open(url, name);
}

export function closePhotoViewer() {
    if (activeInstance) activeInstance.close();
}

export function isPhotoViewerOpen() { return activeInstance?.state.isOpen || false; }
export function isZoomed() { return activeInstance?.state.isOpen && activeInstance.scale > 1.05; }
export function isPanningPhoto() { return activeInstance?.state.isOpen && activeInstance.isPanning; }
