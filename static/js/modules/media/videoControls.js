/**
 * Video Controls Overlay Component
 * Netflix-style custom controls for video playback.
 */

import { createDownloadButton } from './download.js';
import { setScrubPreviewActive } from './scrubPreviewState.js';
import {
    gearIcon,
    subtitleIcon,
    pipIcon,
    fullscreenIcon,
    muteIcon,
    unmuteIcon,
    rotateIcon
} from '../../utils/icons.js';
import { Component, createElement, show, hide, $ } from '../../libs/ragot.esm.min.js';
import { VIEWER_MODES, setViewerMode } from './viewerUiController.js';

const HIDE_DELAY = 3000;
const SKIP_SECONDS = 15;
const CONTROLS_VISIBLE_CLASS = 'viewer-controls-visible';
const CONTROLS_HIDDEN_CLASS = 'viewer-controls-hidden';
const SCRUB_NO_SELECT_CLASS = 'vc-scrub-no-select';
const SCRUB_SEEK_PREVIEW_INTERVAL_MS = 80;

function setControlsVisibilityState(isVisible) {
    const mediaViewer = $('#media-viewer');
    if (mediaViewer) {
        mediaViewer.setAttribute('data-controls-visible', isVisible ? 'true' : 'false');
    }

    if (typeof document !== 'undefined' && document.body) {
        document.body.classList.toggle(CONTROLS_VISIBLE_CLASS, isVisible);
        document.body.classList.toggle(CONTROLS_HIDDEN_CLASS, !isVisible);
    }
}

function clearControlsVisibilityState() {
    const mediaViewer = $('#media-viewer');
    if (mediaViewer) {
        mediaViewer.removeAttribute('data-controls-visible');
    }

    if (typeof document !== 'undefined' && document.body) {
        document.body.classList.remove(CONTROLS_VISIBLE_CLASS, CONTROLS_HIDDEN_CLASS);
    }
}

function formatTime(seconds) {
    if (!seconds || !isFinite(seconds)) return '0:00';
    const s = Math.floor(seconds);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) {
        return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    }
    return `${m}:${String(sec).padStart(2, '0')}`;
}

export class VideoControls extends Component {
    constructor(videoElement, fileInfo) {
        super({
            visible: true,
            currentTime: videoElement.currentTime,
            duration: videoElement.duration || 0,
            buffered: 0,
            isPlaying: !videoElement.paused,
            isMuted: videoElement.muted || videoElement.volume === 0,
            hasSubtitles: false,
            subtitlesActive: false,
            qualityLevels: [],
            currentQuality: -1,
            name: fileInfo?.name || '',
            rotated: false
        });
        this.video = videoElement;
        this.hideTimer = null;
        this.wasPlayingBeforeScrub = false;
        // Scrubbing is pure DOM — no state involved
        this._isDragging = false;
        this._dragTime = 0;
        this._lastPreviewSeekAt = 0;
        this._boundScrubMove = this._onScrubMove.bind(this);
        this._boundScrubEnd = this._onScrubEnd.bind(this);
    }

    onStart() {
        if (!this.video) return;

        this.on(this.video, 'timeupdate', () => {
            if (this._isDragging) return;
            this.setState({ currentTime: this.video.currentTime });
        });
        this.on(this.video, 'play', () => {
            this.setState({ isPlaying: true });
            this._scheduleHide();
        });
        this.on(this.video, 'pause', () => this.setState({ isPlaying: false }));
        this.on(this.video, 'progress', () => this._updateBuffered());
        this.on(this.video, 'loadedmetadata', () => this._syncDurationState());
        this.on(this.video, 'durationchange', () => this._syncDurationState());
        this.on(this.video, 'volumechange', () => this.setState({ isMuted: this.video.muted || this.video.volume === 0 }));
        this.on(this.video, 'loadedmetadata', () => {
            const tracks = this.video.textTracks;
            if (!tracks || tracks.length === 0) return;
            updateSubtitleState(true, tracks);
        });

        this._scheduleHide();

        this.on(document, 'mousemove', this._boundScrubMove);
        this.on(document, 'touchmove', this._boundScrubMove, { passive: false });
        this.on(document, 'mouseup', this._boundScrubEnd);
        this.on(document, 'touchend', this._boundScrubEnd);
        this.on(document, 'touchcancel', this._boundScrubEnd);
        this.on(window, 'blur', this._boundScrubEnd);
        this.on(document, 'selectstart', (e) => {
            if (this._isDragging && e.cancelable) e.preventDefault();
        });
        this.on(document, 'dragstart', (e) => {
            if (this._isDragging && e.cancelable) e.preventDefault();
        });

        setViewerMode(VIEWER_MODES.VIDEO_CONTROLS);
    }

    onStop() {
        if (this.hideTimer) {
            this.clearTimeout(this.hideTimer);
            this.hideTimer = null;
        }
        this._isDragging = false;
        this._setScrubSelectionLock(false);
        clearControlsVisibilityState();
        if (this.video) this.video.classList.remove('vc-rotated');
        if (screen.orientation?.unlock) screen.orientation.unlock();

        const isPhotoViewerOpen = window.ragotModules?.photoViewer?.isPhotoViewerOpen?.();
        setViewerMode(isPhotoViewerOpen ? VIEWER_MODES.PHOTO_VIEWER : VIEWER_MODES.MEDIA);
    }

    render() {
        const { visible, currentTime, duration, buffered, isPlaying, isMuted, hasSubtitles, subtitlesActive, name, qualityLevels, currentQuality, rotated } = this.state;
        const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0;
        const effectiveTime = this._isDragging ? this._dragTime : currentTime;
        const clampedCurrentTime = safeDuration > 0 ? Math.max(0, Math.min(effectiveTime, safeDuration)) : 0;
        const clampedBuffered = safeDuration > 0 ? Math.max(0, Math.min(buffered, safeDuration)) : 0;
        const progressPct = safeDuration > 0 ? (clampedCurrentTime / safeDuration) * 100 : 0;
        const bufferedPct = safeDuration > 0 ? (clampedBuffered / safeDuration) * 100 : 0;

        return createElement('div', {
            className: 'vc-overlay',
            dataset: { visible: String(visible) },
            onMouseMove: () => this._showControls(),
            onTouchStart: () => this._showControls()
        },
            createElement('div', {
                className: 'vc-tap-zone',
                onClick: (e) => {
                    e.stopPropagation();
                    if (visible) { this._hideControls(); return; }
                    this._showControls();
                }
            }),

            createElement('button', {
                className: 'vc-skip vc-skip-back',
                onClick: (e) => { e.stopPropagation(); this._skip(-SKIP_SECONDS); },
                innerHTML: '<svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5V1L7 6l5 5V7a6 6 0 11-1.18 11.82"/></svg><span>15</span>'
            }),
            createElement('button', {
                className: 'vc-center-play',
                onClick: (e) => { e.stopPropagation(); this._togglePlay(); },
                children: [
                    createElement('svg', {
                        className: 'vc-icon-play',
                        style: { display: isPlaying ? 'none' : '' },
                        viewBox: '0 0 24 24', width: '48', height: '48', fill: 'currentColor',
                        innerHTML: '<polygon points="5,3 19,12 5,21"/>'
                    }),
                    createElement('svg', {
                        className: 'vc-icon-pause',
                        style: { display: isPlaying ? '' : 'none' },
                        viewBox: '0 0 24 24', width: '48', height: '48', fill: 'currentColor',
                        innerHTML: '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>'
                    })
                ]
            }),
            createElement('button', {
                className: 'vc-skip vc-skip-fwd',
                onClick: (e) => { e.stopPropagation(); this._skip(SKIP_SECONDS); },
                innerHTML: '<svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5V1l5 5-5 5V7a6 6 0 101.18 11.82"/></svg><span>15</span>'
            }),

            createElement('div', { className: 'vc-filename-label', textContent: name }),

            createElement('div', { className: 'vc-bottom' },
                createElement('div', {
                    className: 'vc-progress-bar',
                    onMouseDown: (e) => this._onScrubStart(e),
                    onTouchStart: (e) => this._onScrubStart(e),
                    ref: this.ref('progressBar')
                },
                    createElement('div', { className: 'vc-progress-buffered', style: { width: `${bufferedPct}%` } }),
                    createElement('div', { className: 'vc-progress-played', style: { width: `${progressPct}%` }, ref: this.ref('progressPlayed') }),
                    createElement('div', { className: 'vc-progress-handle', style: { left: `${progressPct}%` }, ref: this.ref('progressHandle') }),
                    createElement('div', {
                        className: 'vc-time-tooltip hidden',
                        ref: this.ref('timeTooltip')
                    })
                ),
                createElement('div', { className: 'vc-controls-row' },
                    createElement('div', { className: 'vc-time', textContent: `${formatTime(currentTime)} / ${formatTime(safeDuration)}`, ref: this.ref('timeDisplay') }),
                    createElement('div', { className: 'vc-right-controls' },
                        qualityLevels.length > 1 ? createElement('button', {
                            className: 'vc-quality-btn',
                            onClick: (e) => { e.stopPropagation(); this._toggleQualityMenu(); },
                            innerHTML: gearIcon(20)
                        }) : null,
                        createElement('button', {
                            className: `vc-subtitle-btn ${subtitlesActive ? 'vc-subtitle-active' : ''}`,
                            style: { display: hasSubtitles ? '' : 'none' },
                            onClick: (e) => { e.stopPropagation(); this._cycleSubtitles(); },
                            innerHTML: subtitleIcon(20)
                        }),
                        createElement('button', {
                            className: 'vc-pip-btn',
                            onClick: (e) => { e.stopPropagation(); this._togglePip(); },
                            innerHTML: pipIcon(20)
                        }),
                        createElement('button', {
                            className: `vc-rotate-btn ${rotated ? 'vc-rotate-active' : ''}`,
                            onClick: (e) => { e.stopPropagation(); this._toggleRotate(); },
                            innerHTML: rotateIcon(20),
                            title: rotated ? 'Exit landscape' : 'Rotate to landscape'
                        }),
                        createElement('button', {
                            className: `vc-mute-btn ${isMuted ? 'vc-muted' : ''}`,
                            onClick: (e) => { e.stopPropagation(); this._toggleMute(); },
                            children: [
                                createElement('span', { className: 'vc-icon-unmuted', style: { display: isMuted ? 'none' : '' }, innerHTML: unmuteIcon(20) }),
                                createElement('span', { className: 'vc-icon-muted', style: { display: isMuted ? '' : 'none' }, innerHTML: muteIcon(20) })
                            ]
                        }),
                        createElement('div', { className: 'vc-download-wrapper' }, createDownloadButton()),
                        createElement('button', {
                            className: 'vc-fullscreen-btn',
                            onClick: (e) => { e.stopPropagation(); this._toggleFullscreen(); },
                            innerHTML: fullscreenIcon(20)
                        })
                    )
                ),
                this._renderQualityMenu()
            )
        );
    }

    _renderQualityMenu() {
        const { qualityLevels, currentQuality } = this.state;
        if (qualityLevels.length < 2) return null;

        return createElement('div', { className: 'vc-quality-menu' },
            createElement('div', {
                className: `vc-quality-option ${currentQuality === -1 ? 'active' : ''}`,
                onClick: (e) => this._setQuality(-1, e),
                innerHTML: '<span>Auto</span><span class="vc-quality-sub">Adaptive</span>'
            }),
            qualityLevels.map((level, idx) => createElement('div', {
                className: `vc-quality-option ${currentQuality === idx ? 'active' : ''}`,
                onClick: (e) => this._setQuality(idx, e),
                innerHTML: `<span>${level.height}p</span><span class="vc-quality-sub">${Math.round(level.bitrate / 1000)} kbps</span>`
            }))
        );
    }

    _toggleQualityMenu() {
        const menu = $('.vc-quality-menu', this.element);
        if (menu) menu.classList.toggle('vc-quality-menu-visible');
    }

    _setQuality(idx, e) {
        e.stopPropagation();
        if (this.hls) {
            this.hls.currentLevel = idx;
            this.setState({ currentQuality: idx });
            const menu = $('.vc-quality-menu', this.element);
            if (menu) menu.classList.remove('vc-quality-menu-visible');
        }
    }

    _updateBuffered() {
        if (!this.video || this.video.buffered.length === 0) return;
        const buffered = this.video.buffered.end(this.video.buffered.length - 1);
        this.setState({ buffered });
        if (!(this.state.duration > 0)) {
            this._syncDurationState();
        }
    }

    _showControls() {
        if (!this.state.visible) {
            this.setState({ visible: true });
        }
        this._scheduleHide();
    }

    _hideControls() {
        if (this.hideTimer) {
            this.clearTimeout(this.hideTimer);
            this.hideTimer = null;
        }
        this.setState({ visible: false });
        setControlsVisibilityState(false);
    }

    _scheduleHide() {
        if (this.hideTimer) this.clearTimeout(this.hideTimer);
        this.hideTimer = this.timeout(() => {
            if (!this._isDragging && this.state.isPlaying) {
                this.setState({ visible: false });
                setControlsVisibilityState(false);
            }
        }, HIDE_DELAY);

        setControlsVisibilityState(true);
    }

    _togglePlay() {
        if (this.video.paused) this.video.play().catch(() => { });
        else this.video.pause();
    }

    _skip(seconds) {
        this.video.currentTime = Math.max(0, Math.min(this.video.currentTime + seconds, this.video.duration || Infinity));
        this.setState({ visible: true });
        this._scheduleHide();
    }

    _toggleMute() {
        this.video.muted = !this.video.muted;
        if (!this.video.muted && this.video.volume === 0) this.video.volume = 1;
    }

    _togglePip() {
        if (document.pictureInPictureElement === this.video) document.exitPictureInPicture().catch(() => { });
        else if (document.pictureInPictureEnabled) this.video.requestPictureInPicture().catch(() => { });
    }

    _toggleFullscreen() {
        if (typeof this.video.webkitEnterFullscreen === 'function') {
            this.video.removeAttribute('playsinline');
            this.video.webkitEnterFullscreen();
        } else if (this.video.requestFullscreen) {
            this.video.requestFullscreen().catch(() => { });
        }
    }

    _toggleRotate() {
        const rotated = !this.state.rotated;
        this.setState({ rotated });
        if (this.video) this.video.classList.toggle('vc-rotated', rotated);

        if (rotated && screen.orientation?.lock) {
            screen.orientation.lock('landscape').catch(() => { });
        } else if (!rotated && screen.orientation?.unlock) {
            screen.orientation.unlock();
        }
    }

    _cycleSubtitles() {
        const tracks = this.video.textTracks;
        if (!tracks || tracks.length === 0) return;
        let activeIdx = -1;
        for (let i = 0; i < tracks.length; i++) {
            if (tracks[i].mode === 'showing') { activeIdx = i; break; }
        }
        if (activeIdx >= 0) tracks[activeIdx].mode = 'hidden';
        const nextIdx = activeIdx + 1;
        if (nextIdx < tracks.length) tracks[nextIdx].mode = 'showing';

        let isActive = false;
        for (let i = 0; i < tracks.length; i++) {
            if (tracks[i].mode === 'showing') { isActive = true; break; }
        }
        this.setState({ subtitlesActive: isActive });
    }

    _syncDurationState() {
        const duration = this.video?.duration;
        this.setState({ duration: Number.isFinite(duration) && duration > 0 ? duration : 0 });
    }

    // --- Scrubbing: pure DOM, no setState ---

    _clientXFromEvent(e) {
        if (e.touches && e.touches.length > 0) return e.touches[0].clientX;
        if (e.changedTouches && e.changedTouches.length > 0) return e.changedTouches[0].clientX;
        return e.clientX;
    }

    _scrubToClientX(clientX) {
        const bar = this.refs.progressBar;
        if (!bar) return;
        const duration = this.video?.duration;
        if (!Number.isFinite(duration) || duration <= 0) return;

        const rect = bar.getBoundingClientRect();
        const pct = Math.max(0, Math.min((clientX - rect.left) / rect.width, 1));
        this._dragTime = pct * duration;

        if (this.refs.progressPlayed) this.refs.progressPlayed.style.width = `${pct * 100}%`;
        if (this.refs.progressHandle) this.refs.progressHandle.style.left = `${pct * 100}%`;
        if (this.refs.timeTooltip) {
            this.refs.timeTooltip.textContent = formatTime(this._dragTime);
            this.refs.timeTooltip.style.left = `${pct * 100}%`;
            show(this.refs.timeTooltip);
        }
        if (this.refs.timeDisplay) {
            this.refs.timeDisplay.textContent = `${formatTime(this._dragTime)} / ${formatTime(duration)}`;
        }

        this._previewDragTime();
    }

    _previewDragTime(force = false) {
        if (!this.video || !this._isDragging) return;
        const now = Date.now();
        if (!force && (now - this._lastPreviewSeekAt) < SCRUB_SEEK_PREVIEW_INTERVAL_MS) return;
        this._lastPreviewSeekAt = now;
        this.video.currentTime = this._dragTime;
    }

    _onScrubStart(e) {
        const duration = this.video?.duration;
        if (!Number.isFinite(duration) || duration <= 0) return;

        e.preventDefault();
        e.stopPropagation();

        this._isDragging = true;
        this._dragTime = this.video.currentTime;
        this._lastPreviewSeekAt = 0;
        this._setScrubSelectionLock(true);
        setScrubPreviewActive(this.video, true);

        if (this.refs.progressBar) this.refs.progressBar.classList.add('scrubbing');
        if (this.refs.timeTooltip) show(this.refs.timeTooltip);

        this.wasPlayingBeforeScrub = !this.video.paused;
        this.video.pause();

        this._scrubToClientX(this._clientXFromEvent(e));
    }

    _onScrubMove(e) {
        if (!this._isDragging) return;
        e.preventDefault();
        e.stopPropagation();
        this._scrubToClientX(this._clientXFromEvent(e));
    }

    _onScrubEnd(e) {
        if (!this._isDragging) return;
        if (e) e.stopPropagation?.();

        this._isDragging = false;
        this._setScrubSelectionLock(false);

        if (this.refs.progressBar) this.refs.progressBar.classList.remove('scrubbing');
        if (this.refs.timeTooltip) hide(this.refs.timeTooltip);

        this._previewDragTime(true);

        // Commit the seek
        this.video.currentTime = this._dragTime;
        // Sync state so next render reflects committed position
        this.setState({ currentTime: this._dragTime });

        if (this.wasPlayingBeforeScrub) this.video.play().catch(() => { });
        this.timeout(() => setScrubPreviewActive(this.video, false), 120);
        this._scheduleHide();
    }

    _setScrubSelectionLock(locked) {
        if (typeof document === 'undefined' || !document.body) return;
        document.body.classList.toggle(SCRUB_NO_SELECT_CLASS, !!locked);
    }
}

let activeInstance = null;

export function attachControls(videoElement, fileInfo) {
    if (!videoElement) return;

    if (activeInstance && activeInstance.video === videoElement) {
        if (fileInfo && fileInfo.name !== activeInstance.state.name) {
            activeInstance.setState({ name: fileInfo.name || '' });
        }
        return;
    }

    detachControls();
    activeInstance = new VideoControls(videoElement, fileInfo);

    const tryMount = () => {
        const parent = videoElement.parentElement;
        if (parent) {
            const existing = $('.vc-overlay', parent);
            if (existing) existing.remove();
            activeInstance.mount(parent);
            return true;
        }
        return false;
    };

    if (!tryMount()) {
        const poll = activeInstance.interval(() => {
            if (tryMount() || !activeInstance) activeInstance?.clearInterval(poll);
        }, 50);
        activeInstance.timeout(() => activeInstance?.clearInterval(poll), 2000);
    }
}

export function detachControls() {
    if (activeInstance) {
        activeInstance.unmount();
        activeInstance = null;
    }

    clearControlsVisibilityState();

    const isPhotoViewerOpen = window.ragotModules?.photoViewer?.isPhotoViewerOpen?.();
    setViewerMode(isPhotoViewerOpen ? VIEWER_MODES.PHOTO_VIEWER : VIEWER_MODES.MEDIA);
}

export function updateSubtitleState(hasSubtitles, tracks) {
    if (activeInstance) {
        let isActive = false;
        if (tracks) {
            for (let i = 0; i < tracks.length; i++) {
                if (tracks[i].mode === 'showing') { isActive = true; break; }
            }
        }
        activeInstance.setState({ hasSubtitles, subtitlesActive: isActive });
    }
}

export function updateQualityState(hls, levels) {
    if (activeInstance) {
        activeInstance.hls = hls;
        activeInstance.setState({ qualityLevels: levels, currentQuality: hls.currentLevel });
    }
}

export function getPlaybackState() {
    if (!activeInstance || !activeInstance.video) return null;
    return {
        is_playing: !activeInstance.video.paused,
        current_time: activeInstance.video.currentTime
    };
}

export function isControlsAttached() {
    return !!activeInstance;
}
