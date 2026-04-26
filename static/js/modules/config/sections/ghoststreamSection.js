/**
 * GhostStream Transcoding Section
 * Admin section for GhostStream transcoding server management.
 */

import { setupCollapsibleSection } from './sectionUtils.js';
import { getShowHiddenHeaders } from '../../../utils/showHiddenManager.js';
import { saveConfig } from '../../../utils/configManager.js';
import { createElement, attr, $, $$ } from '../../../libs/ragot.esm.min.js';
import { toast, dialog } from '../../../utils/notificationManager.js';

function getRuntimeConfig() {
    return window.ragotModules?.appStore?.get?.('config', {}) || {};
}

function isAdvancedMode(settingsMode) {
    return settingsMode === 'advanced';
}

/**
 * Triggers GhostStream discovery on the backend.
 */
async function triggerGhostStreamDiscovery() {
    try {
        await fetch('/api/ghoststream/discovery/start', { method: 'POST' });
    } catch (e) {
        // Silently fail - discovery may already be running
    }
}

/**
 * Refreshes GhostStream status in settings.
 */
async function refreshGhostStreamStatus() {
    const dot = $('#gs-settings-dot');
    const statusText = $('#gs-settings-status-text');
    const serverList = $('#gs-server-list');

    if (dot) dot.className = 'gs-dot checking';
    if (statusText) statusText.textContent = 'Scanning...';

    try {
        await fetch('/api/ghoststream/discovery/start', { method: 'POST' });
    } catch (e) {
        console.warn('[GhostStream] Discovery start failed:', e);
    }

    await new Promise(r => setTimeout(r, 1000));

    try {
        const response = await fetch('/api/ghoststream/status');
        const data = await response.json();

        if (dot && statusText) {
            if (data.available) {
                dot.className = 'gs-dot online';
                statusText.textContent = `Connected`;
            } else {
                dot.className = 'gs-dot offline';
                statusText.textContent = 'No servers found';
            }
        }

        const lbInfo = $('#gs-load-balancer-info');
        if (lbInfo) {
            lbInfo.style.display = (data.servers && data.servers.length >= 2) ? 'block' : 'none';
        }

        if (serverList) {
            if (data.servers && data.servers.length > 0) {
                const lbStats = data.load_balancer_stats || {};

                serverList.innerHTML = data.servers.map(s => {
                    const stats = lbStats[s.name];
                    const activeJobs = stats?.active_jobs || 0;
                    const isHealthy = stats?.is_healthy !== false;

                    return `
                    <div class="gs-server-item ${!isHealthy ? 'gs-server-unhealthy' : ''}" data-server-name="${s.name}">
                        <div class="gs-server-info">
                            <span class="gs-server-icon">\u{1F5A5}\uFE0F</span>
                            <span class="gs-server-addr">${s.host}:${s.port}</span>
                            ${s.has_hw_accel ? '<span class="gs-server-badge">GPU</span>' : ''}
                            ${data.servers.length >= 2 && activeJobs > 0 ? `<span class="gs-server-jobs">${activeJobs} job${activeJobs !== 1 ? 's' : ''}</span>` : ''}
                        </div>
                        <button class="gs-server-delete" title="Remove server" data-name="${s.name}">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M18 6L6 18M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                    `;
                }).join('');

                $$('.gs-server-delete', serverList).forEach(btn => {
                    attr(btn, {
                        onClick: async (e) => {
                            e.stopPropagation();
                            const serverName = btn.dataset.name;
                            if (!await dialog.confirm('Remove server ' + serverName + '?', { type: 'danger' })) return;
                            try {
                                const resp = await fetch(`/api/ghoststream/servers/${encodeURIComponent(serverName)}`, {
                                    method: 'DELETE'
                                });
                                if (resp.ok) {
                                    await refreshGhostStreamStatus();
                                }
                            } catch (err) {
                                console.error('Failed to remove server:', err);
                            }
                        }
                    });
                });
            } else {
                serverList.innerHTML = `<span class="gs-no-servers">No servers found. Start GhostStream on another device or add one manually below.</span>`;
            }
        }
    } catch (e) {
        if (dot) dot.className = 'gs-dot offline';
        if (statusText) statusText.textContent = 'Connection error';
        if (serverList) serverList.innerHTML = `<span class="gs-no-servers gs-error">Could not connect to GhostHub API</span>`;
    }
}

/**
 * Reload GhostStream preferences from config and update UI.
 */
export function reloadGhostStreamPreferences() {
    const prefs = getRuntimeConfig()?.javascript_config?.ghoststream || {};

    const savedQuality = prefs.preferredQuality || 'original';
    const radios = $$('input[name="gs-quality"]');
    radios.forEach(r => {
        r.checked = (r.value === savedQuality);
    });

    const bitrate = $('#gs-settings-bitrate');
    const abr = $('#gs-settings-abr');
    const debug = $('#gs-settings-debug');

    if (bitrate) bitrate.checked = prefs.autoTranscodeHighBitrate !== false;
    if (abr) abr.checked = prefs.enableABR || false;
    if (debug) debug.checked = prefs.debug || false;

}

/**
 * Setup event handlers for GhostStream settings.
 */
function setupGhostStreamSettingsHandlers() {
    const addBtn = $('#gs-settings-add-btn');
    const input = $('#gs-settings-server-input');
    const resultDiv = $('#gs-settings-add-result');
    const refreshBtn = $('#gs-refresh-btn');
    const qualityRadios = $$('input[name="gs-quality"]');
    const bitrateCheckbox = $('#gs-settings-bitrate');

    function loadPreferences() {
        const prefs = getRuntimeConfig()?.javascript_config?.ghoststream || {};
        console.log('[GhostStream] Loading preferences:', prefs);

        const savedQuality = prefs.preferredQuality || 'original';
        const radios = $$('input[name="gs-quality"]');
        radios.forEach(r => {
            r.checked = (r.value === savedQuality);
        });
        console.log('[GhostStream] Set quality to:', savedQuality);

        const bitrate = $('#gs-settings-bitrate');
        const abr = $('#gs-settings-abr');
        if (bitrate) bitrate.checked = prefs.autoTranscodeHighBitrate !== false;
        if (abr) abr.checked = prefs.enableABR || false;
    }

    function waitForConfigAndLoad() {
        if (getRuntimeConfig()?.javascript_config) {
            loadPreferences();
        } else {
            setTimeout(waitForConfigAndLoad, 200);
        }
    }

    setTimeout(() => {
        waitForConfigAndLoad();
        refreshGhostStreamStatus();
    }, 100);

    if (refreshBtn) {
        attr(refreshBtn, {
            onClick: async () => {
                refreshBtn.classList.add('spinning');
                await refreshGhostStreamStatus();
                setTimeout(() => refreshBtn.classList.remove('spinning'), 500);
            }
        });
    }

    if (addBtn && input) {
        attr(addBtn, {
            onClick: async () => {
            const address = input.value.trim();
            if (!address) {
                if (resultDiv) {
                    resultDiv.textContent = 'Enter server address';
                    resultDiv.className = 'gs-result error';
                }
                return;
            }

            const fullAddress = address.includes(':') ? address : `${address}:8765`;
            addBtn.disabled = true;
            addBtn.innerHTML = '<span class="gs-spinner"></span> Adding...';
            if (resultDiv) {
                resultDiv.textContent = '';
                resultDiv.className = 'gs-result';
            }

            try {
                const response = await fetch('/api/ghoststream/servers/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ address: fullAddress })
                });

                if (response.ok) {
                    if (resultDiv) {
                        resultDiv.textContent = '\u2713 Server added successfully';
                        resultDiv.className = 'gs-result success';
                    }
                    input.value = '';
                    await refreshGhostStreamStatus();
                } else {
                    const data = await response.json();
                    if (resultDiv) {
                        resultDiv.textContent = data.error || 'Failed to add server';
                        resultDiv.className = 'gs-result error';
                    }
                }
            } catch (e) {
                if (resultDiv) {
                    resultDiv.textContent = 'Connection error - check address';
                    resultDiv.className = 'gs-result error';
                }
            }

                addBtn.disabled = false;
                addBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg> Add`;
            }
        });

        attr(input, {
            onKeypress: (e) => {
                if (e.key === 'Enter') addBtn.click();
            }
        });
    }

    async function saveGhostStreamPrefs(updates) {
        try {
            const currentConfig = getRuntimeConfig();
            if (!currentConfig || Object.keys(currentConfig).length === 0) {
                console.warn('[GhostStream] Config not loaded yet');
                return;
            }
            const nextConfig = JSON.parse(JSON.stringify(currentConfig));
            if (!nextConfig.javascript_config) nextConfig.javascript_config = {};
            if (!nextConfig.javascript_config.ghoststream) nextConfig.javascript_config.ghoststream = {};
            Object.assign(nextConfig.javascript_config.ghoststream, updates);
            await saveConfig(nextConfig);
            console.log('[GhostStream] Settings saved:', updates);

            import('../../ghoststream/manager.js').then(gsm => {
                if (gsm.reloadPreferences) gsm.reloadPreferences();
            }).catch(() => { });
        } catch (e) {
            console.error('[GhostStream] Failed to save settings:', e);
        }
    }

    qualityRadios.forEach(radio => {
        attr(radio, {
            onChange: () => {
                saveGhostStreamPrefs({ preferredQuality: radio.value });
            }
        });
    });

    if (bitrateCheckbox) {
        attr(bitrateCheckbox, {
            onChange: () => {
                saveGhostStreamPrefs({ autoTranscodeHighBitrate: bitrateCheckbox.checked });
            }
        });
    }

    const abrCheckbox = $('#gs-settings-abr');
    if (abrCheckbox) {
        attr(abrCheckbox, {
            onChange: () => {
                saveGhostStreamPrefs({ enableABR: abrCheckbox.checked });
            }
        });
    }

    const debugCheckbox = $('#gs-settings-debug');
    if (debugCheckbox) {
        const savedDebug = getRuntimeConfig()?.javascript_config?.ghoststream?.debug || false;
        debugCheckbox.checked = savedDebug;

        attr(debugCheckbox, {
            onChange: () => {
                saveGhostStreamPrefs({ debug: debugCheckbox.checked });
                console.log(`[GhostStream] Debug mode ${debugCheckbox.checked ? 'ENABLED' : 'DISABLED'}`);
            }
        });
    }

    const categorySelect = $('#gs-batch-category');
    if (categorySelect) {
        fetch('/api/categories', {
            headers: getShowHiddenHeaders()
        })
            .then(r => r.json())
            .then(data => {
                const categories = Array.isArray(data) ? data : (data.categories || []);
                categorySelect.innerHTML = '<option value="">Select category to transcode...</option>';
                categories.forEach(cat => {
                    categorySelect.appendChild(createElement('option', { value: cat.id, textContent: cat.name }));
                });
            })
            .catch(e => console.error('Failed to load categories:', e));
    }

    const batchStartBtn = $('#gs-batch-start');
    if (batchStartBtn) {
        attr(batchStartBtn, {
            onClick: async () => {
                const categoryId = $('#gs-batch-category')?.value;
            if (!categoryId) {
                toast.error('Please select a category first');
                return;
            }

            const filters = {
                mkv: $('#gs-batch-mkv')?.checked,
                avi: $('#gs-batch-avi')?.checked,
                hevc: $('#gs-batch-hevc')?.checked,
                hdr: $('#gs-batch-hdr')?.checked
            };

            const extensions = [];
            if (filters.mkv) extensions.push('.mkv');
            if (filters.avi) extensions.push('.avi', '.wmv');

            batchStartBtn.disabled = true;
            batchStartBtn.textContent = 'Starting...';

            const statusDiv = $('#gs-batch-status');
            const progressText = $('#gs-batch-progress-text');
            const progressBar = $('#gs-batch-progress-bar');
            if (statusDiv) statusDiv.style.display = 'block';

            try {
                const response = await fetch('/api/ghoststream/cache/batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        category_id: categoryId,
                        resolution: $('input[name="gs-quality"]:checked')?.value || 'original',
                        video_codec: 'h264',
                        filters: filters
                    })
                });

                const result = await response.json();
                if (result.error) {
                    toast.error('Batch transcode error: ' + result.error);
                } else {
                    const completed = result.completed || result.successful || 0;
                    if (progressText) progressText.textContent = `Completed: ${completed}/${result.total || 0} files`;
                    toast.success('Batch transcode complete! Completed: ' + completed + ', Failed: ' + (result.failed || 0) + ', Skipped: ' + (result.skipped || 0));
                }
            } catch (e) {
                console.error('Batch transcode failed:', e);
                toast.error('Batch transcode failed: ' + e.message);
                } finally {
                    batchStartBtn.disabled = false;
                    batchStartBtn.textContent = '\u25B6 Start Batch Transcode';
                }
            }
        });
    }

    const cancelAllBtn = $('#gs-batch-cancel-all');
    if (cancelAllBtn) {
        attr(cancelAllBtn, {
            onClick: async () => {
            if (!await dialog.confirm('Cancel ALL active transcoding jobs?', { type: 'danger' })) return;

            cancelAllBtn.disabled = true;
            cancelAllBtn.textContent = 'Cancelling...';

            try {
                const response = await fetch('/api/ghoststream/jobs/cancel-all', {
                    method: 'POST'
                });

                const result = await response.json();
                toast.success('Cancelled ' + (result.cancelled || 0) + ' jobs');
            } catch (e) {
                console.error('Cancel all failed:', e);
                toast.error('Failed to cancel jobs: ' + e.message);
                } finally {
                    cancelAllBtn.disabled = false;
                    cancelAllBtn.textContent = '\u2715 Cancel All Jobs';
                }
            }
        });
    }
}

/**
 * Creates the GhostStream Transcoding settings section.
 * @param {string} settingsMode
 * @returns {DocumentFragment}
 */
export function createGhostStreamSection(settingsMode = 'basic') {
    const fragment = document.createDocumentFragment();
    const showAdvanced = isAdvancedMode(settingsMode);

    const header = createElement('h3', { className: 'config-section-header collapsed', innerHTML: 'Transcoding (GhostStream)' });
    fragment.appendChild(header);

    const container = createElement('div', { className: 'config-section-settings collapsed', id: 'ghoststream-settings' });

    container.innerHTML = `
        <div class="gs-section">
            <!-- Status Card -->
            <div class="gs-status-card">
                <div class="gs-status-header">
                    <div class="gs-status-indicator">
                        <span id="gs-settings-dot" class="gs-dot offline"></span>
                        <span id="gs-settings-status-text" class="gs-status-label">Checking...</span>
                    </div>
                    <button type="button" id="gs-refresh-btn" class="gs-icon-btn" title="Refresh">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 12a9 9 0 11-2.636-6.364M21 3v6h-6"/>
                        </svg>
                    </button>
                </div>
                <div id="gs-server-list" class="gs-server-list">
                    <span class="gs-no-servers">Searching for servers...</span>
                </div>
                <div id="gs-load-balancer-info" class="gs-load-balancer-info" style="display:none;">
                    <div class="gs-lb-label">Load Balancing: <strong>Active</strong></div>
                    <div class="gs-lb-desc">Jobs are automatically distributed across servers</div>
                </div>
            </div>

            <!-- Add Server -->
            <div class="gs-add-server">
                <label class="gs-label">Add Server Manually</label>
                <div class="gs-input-row">
                    <input type="text" id="gs-settings-server-input" class="gs-input" placeholder="192.168.1.100:8765">
                    <button type="button" id="gs-settings-add-btn" class="gs-btn-add">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 5v14M5 12h14"/>
                        </svg>
                        Add
                    </button>
                </div>
                <div id="gs-settings-add-result" class="gs-result"></div>
            </div>

            <!-- Playback Settings -->
            <div class="gs-settings-group">
                <label class="gs-label">Playback Quality</label>
                <p class="gs-desc">Choose the default quality GhostHub should target when it needs to optimize playback.</p>
                <div class="gs-quality-grid">
                    <label class="gs-quality-option">
                        <input type="radio" name="gs-quality" value="original" checked>
                        <span class="gs-quality-card">
                            <span class="gs-quality-name">Original</span>
                            <span class="gs-quality-desc">Direct stream</span>
                        </span>
                    </label>
                    <label class="gs-quality-option">
                        <input type="radio" name="gs-quality" value="1080p">
                        <span class="gs-quality-card">
                            <span class="gs-quality-name">1080p</span>
                            <span class="gs-quality-desc">Full HD</span>
                        </span>
                    </label>
                    <label class="gs-quality-option">
                        <input type="radio" name="gs-quality" value="720p">
                        <span class="gs-quality-card">
                            <span class="gs-quality-name">720p</span>
                            <span class="gs-quality-desc">HD</span>
                        </span>
                    </label>
                    <label class="gs-quality-option">
                        <input type="radio" name="gs-quality" value="480p">
                        <span class="gs-quality-card">
                            <span class="gs-quality-name">480p</span>
                            <span class="gs-quality-desc">SD</span>
                        </span>
                    </label>
                </div>
                <p class="gs-desc">Unsupported formats and browser-incompatible codecs are converted automatically when needed.</p>
            </div>

            ${showAdvanced ? `
            <div class="gs-settings-group">
                <label class="gs-label">Advanced Playback</label>
                <p class="gs-desc">These options are mainly helpful for remote or unstable connections.</p>
                <div class="gs-toggle-list">
                    <label class="gs-toggle-item">
                        <span class="gs-toggle-info">
                            <span class="gs-toggle-title">Auto-transcode high bitrate</span>
                            <span class="gs-toggle-desc">Smooth out very large files on slower networks by transcoding videos above 25 Mbps.</span>
                        </span>
                        <input type="checkbox" id="gs-settings-bitrate" class="gs-toggle" checked>
                    </label>
                    <label class="gs-toggle-item">
                        <span class="gs-toggle-info">
                            <span class="gs-toggle-title">Adaptive bitrate streaming</span>
                            <span class="gs-toggle-desc">Let GhostStream switch quality while streaming if the connection changes.</span>
                        </span>
                        <input type="checkbox" id="gs-settings-abr" class="gs-toggle">
                    </label>
                </div>
            </div>

            <div class="gs-settings-group">
                <label class="gs-label">Batch Transcoding</label>
                <p class="gs-desc">Pre-transcode videos to cache for instant playback</p>

                <div class="gs-batch-filters">
                    <label class="gs-filter-item">
                        <input type="checkbox" id="gs-batch-mkv" checked> MKV files
                    </label>
                    <label class="gs-filter-item">
                        <input type="checkbox" id="gs-batch-avi" checked> AVI files
                    </label>
                    <label class="gs-filter-item">
                        <input type="checkbox" id="gs-batch-hevc" checked> HEVC/H.265
                    </label>
                    <label class="gs-filter-item">
                        <input type="checkbox" id="gs-batch-hdr" checked> HDR content
                    </label>
                </div>

                <select id="gs-batch-category" class="gs-select" style="width:100%;margin:10px 0;">
                    <option value="">Select category to transcode...</option>
                </select>

                <div class="gs-batch-buttons">
                    <button type="button" id="gs-batch-start" class="gs-btn gs-btn-primary">
                        \u25B6 Start Batch Transcode
                    </button>
                    <button type="button" id="gs-batch-cancel-all" class="gs-btn gs-btn-danger">
                        \u2715 Cancel All Jobs
                    </button>
                </div>

                <div id="gs-batch-status" class="gs-batch-status" style="display:none;">
                    <div class="gs-batch-progress">
                        <span id="gs-batch-progress-text">0/0 files</span>
                        <progress id="gs-batch-progress-bar" value="0" max="100"></progress>
                    </div>
                </div>
            </div>

            <div class="gs-settings-group">
                <label class="gs-toggle-item">
                    <span class="gs-toggle-info">
                        <span class="gs-toggle-title">Debug Mode</span>
                        <span class="gs-toggle-desc">Show detailed logs in browser console (F12)</span>
                    </span>
                    <input type="checkbox" id="gs-settings-debug" class="gs-toggle">
                </label>
            </div>
            ` : `
            <div class="gs-settings-group">
                <p class="gs-desc">Advanced mode adds bitrate tuning, adaptive streaming, batch transcoding, and debug tools.</p>
            </div>
            `}
        </div>
    `;

    fragment.appendChild(container);

    setupCollapsibleSection(header, container, {
        onExpand() {
            triggerGhostStreamDiscovery();
            refreshGhostStreamStatus();
            reloadGhostStreamPreferences();
        }
    });

    // Setup immediately
    setTimeout(() => {
        setupGhostStreamSettingsHandlers();
    }, 0);

    return fragment;
}
