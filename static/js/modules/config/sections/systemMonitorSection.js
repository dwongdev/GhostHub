/**
 * System Monitor Section
 * Admin-only section for real-time Raspberry Pi system stats.
 */

import { getColorClass, getTempColorClass, setupCollapsibleSection } from './sectionUtils.js';
import { Module, createElement, $ } from '../../../libs/ragot.esm.min.js';

// Auto-refresh interval handle
let systemStatsInterval = null;
let systemMonitorLifecycle = null;

// Debounce state for manual refresh
let lastManualRefreshTime = 0;
const MIN_REFRESH_INTERVAL_MS = 1000;

function ensureSystemMonitorLifecycle() {
    if (!systemMonitorLifecycle) {
        systemMonitorLifecycle = new Module();
    }
    systemMonitorLifecycle.start();
    return systemMonitorLifecycle;
}

/**
 * Fetches system stats from the server.
 * @returns {Promise<Object|null>}
 */
async function fetchSystemStats() {
    try {
        const response = await fetch('/api/admin/system/stats');
        if (!response.ok) {
            if (response.status === 403) return null;
            throw new Error('Failed to fetch system stats');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching system stats:', error);
        return null;
    }
}

/**
 * Updates the system stats display.
 * @param {Object} stats
 */
function updateSystemStatsDisplay(stats) {
    const container = $('#system-stats-content');
    if (!container || !stats) return;

    let html = '';

    // Platform info
    html += `<div class="system-stat-group">`;
    html += `<div class="system-stat-header">System</div>`;
    html += `<div class="system-stat-row">`;
    html += `<span class="system-stat-label">Host:</span>`;
    html += `<span class="system-stat-value">${stats.hostname || 'Unknown'}</span>`;
    html += `</div>`;
    if (stats.pi_model) {
        html += `<div class="system-stat-row">`;
        html += `<span class="system-stat-label">Model:</span>`;
        html += `<span class="system-stat-value">${stats.pi_model}</span>`;
        html += `</div>`;
    }
    if (stats.uptime) {
        html += `<div class="system-stat-row">`;
        html += `<span class="system-stat-label">Uptime:</span>`;
        html += `<span class="system-stat-value">${stats.uptime}</span>`;
        html += `</div>`;
    }
    html += `</div>`;

    // CPU stats
    if (stats.cpu) {
        const cpu = stats.cpu;
        html += `<div class="system-stat-group">`;
        html += `<div class="system-stat-header">CPU</div>`;

        if (cpu.usage_percent !== null) {
            const cpuColor = getColorClass(cpu.usage_percent);
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label">Usage:</span>`;
            html += `<span class="system-stat-value ${cpuColor}">${cpu.usage_percent}%</span>`;
            html += `</div>`;
            html += `<div class="system-stat-row full-width">`;
            html += `<div class="system-progress-bar"><div class="system-progress-fill ${cpuColor}" style="width: ${cpu.usage_percent}%"></div></div>`;
            html += `</div>`;
        }

        if (cpu.cores) {
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label">Cores:</span>`;
            html += `<span class="system-stat-value">${cpu.cores}</span>`;
            html += `</div>`;
        }

        if (cpu.frequency_mhz) {
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label">Frequency:</span>`;
            html += `<span class="system-stat-value">${cpu.frequency_mhz} MHz</span>`;
            html += `</div>`;
        }

        if (cpu.temperature_c !== null) {
            const tempColor = getTempColorClass(cpu.temperature_c);
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label">Temperature:</span>`;
            html += `<span class="system-stat-value ${tempColor}">${cpu.temperature_c}°C</span>`;
            html += `</div>`;
        }

        html += `</div>`;
    }

    // Memory stats
    if (stats.memory) {
        const mem = stats.memory;
        const memColor = getColorClass(mem.percent);
        html += `<div class="system-stat-group">`;
        html += `<div class="system-stat-header">Memory</div>`;
        html += `<div class="system-stat-row">`;
        html += `<span class="system-stat-label">Used:</span>`;
        html += `<span class="system-stat-value ${memColor}">${mem.used_mb} MB / ${mem.total_mb} MB (${mem.percent}%)</span>`;
        html += `</div>`;
        html += `<div class="system-stat-row full-width">`;
        html += `<div class="system-progress-bar"><div class="system-progress-fill ${memColor}" style="width: ${mem.percent}%"></div></div>`;
        html += `</div>`;
        html += `<div class="system-stat-row">`;
        html += `<span class="system-stat-label">Available:</span>`;
        html += `<span class="system-stat-value">${mem.available_mb} MB</span>`;
        html += `</div>`;
        if (stats.gpu_memory_mb) {
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label">GPU Memory:</span>`;
            html += `<span class="system-stat-value">${stats.gpu_memory_mb} MB</span>`;
            html += `</div>`;
        }
        html += `</div>`;
    }

    // Network stats
    if (stats.network && stats.network.length > 0) {
        html += `<div class="system-stat-group">`;
        html += `<div class="system-stat-header">Network</div>`;
        for (const iface of stats.network) {
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label">${iface.name}:</span>`;
            html += `<span class="system-stat-value">${iface.ip || 'No IP'}</span>`;
            html += `</div>`;
            html += `<div class="system-stat-row">`;
            html += `<span class="system-stat-label" style="padding-left: 1rem;">Traffic:</span>`;
            html += `<span class="system-stat-value">\u2193${iface.rx_mb} MB / \u2191${iface.tx_mb} MB</span>`;
            html += `</div>`;
        }
        html += `</div>`;
    }

    // Load average
    if (stats.load_average) {
        const load = stats.load_average;
        html += `<div class="system-stat-group">`;
        html += `<div class="system-stat-header">Load Average</div>`;
        html += `<div class="system-stat-row">`;
        html += `<span class="system-stat-label">1 / 5 / 15 min:</span>`;
        html += `<span class="system-stat-value">${load['1min']} / ${load['5min']} / ${load['15min']}</span>`;
        html += `</div>`;
        html += `</div>`;
    }

    // Throttle status (Pi specific)
    if (stats.throttle) {
        const t = stats.throttle;
        const hasIssues = t.under_voltage_now || t.throttled_now || t.arm_freq_capped_now || t.soft_temp_limit_now;
        const hadIssues = t.under_voltage_occurred || t.throttled_occurred || t.arm_freq_capped_occurred || t.soft_temp_limit_occurred;

        if (hasIssues || hadIssues) {
            html += `<div class="system-stat-group">`;
            html += `<div class="system-stat-header ${hasIssues ? 'red' : 'yellow'}">Throttle Status</div>`;

            if (t.under_voltage_now) {
                html += `<div class="system-stat-row"><span class="system-stat-value red">\u26A0 Under-voltage detected!</span></div>`;
            }
            if (t.throttled_now) {
                html += `<div class="system-stat-row"><span class="system-stat-value red">\u26A0 Currently throttled!</span></div>`;
            }
            if (t.arm_freq_capped_now) {
                html += `<div class="system-stat-row"><span class="system-stat-value yellow">\u26A0 Frequency capped</span></div>`;
            }
            if (t.soft_temp_limit_now) {
                html += `<div class="system-stat-row"><span class="system-stat-value yellow">\u26A0 Soft temp limit reached</span></div>`;
            }

            if (!hasIssues && hadIssues) {
                html += `<div class="system-stat-row"><span class="system-stat-value yellow">Past issues detected (since boot)</span></div>`;
            }

            html += `</div>`;
        }
    }

    container.innerHTML = html;
}

/**
 * Stops the system stats auto-refresh interval.
 * Exported so modal.js can call it when the modal closes.
 */
export function stopSystemStatsInterval() {
    if (systemStatsInterval) {
        if (systemMonitorLifecycle) {
            systemMonitorLifecycle.clearInterval(systemStatsInterval);
        } else {
            clearInterval(systemStatsInterval);
        }
        systemStatsInterval = null;
    }
}

export function cleanupSystemMonitorSection() {
    stopSystemStatsInterval();
    if (systemMonitorLifecycle) {
        systemMonitorLifecycle.stop();
        systemMonitorLifecycle = null;
    }
}

/**
 * Creates the System Monitor settings section.
 * @returns {DocumentFragment}
 */
export function createSystemMonitorSection() {
    cleanupSystemMonitorSection();
    const lifecycle = ensureSystemMonitorLifecycle();
    const fragment = document.createDocumentFragment();

    const header = createElement('h3', { className: 'config-section-header collapsed', textContent: 'System Monitor' });
    fragment.appendChild(header);

    const container = createElement('div', { className: 'config-section-settings collapsed', id: 'system-monitor-settings' });

    // Info message
    container.appendChild(createElement('div', {
        className: 'config-description',
        innerHTML: 'Hardware monitoring for your Raspberry Pi. Click the stats or use the Refresh button to update.'
    }));

    // Stats container (clickable to refresh)
    const statsContainer = createElement('div', {
        id: 'system-stats-content',
        className: 'system-stats-container',
        title: 'Click to refresh stats',
        innerHTML: '<div class="system-loading">Loading system stats...</div>'
    });

    lifecycle.on(statsContainer, 'click', async (e) => {
        if (e.target.closest('button')) return;

        const now = Date.now();
        if (now - lastManualRefreshTime < MIN_REFRESH_INTERVAL_MS) return;
        lastManualRefreshTime = now;

        statsContainer.style.opacity = '0.6';
        const stats = await fetchSystemStats();
        if (stats) updateSystemStatsDisplay(stats);
        statsContainer.style.opacity = '1';
    });

    container.appendChild(statsContainer);

    // Refresh button
    const refreshBtn = createElement('button', {
        className: 'btn btn--secondary btn--sm config-section-action-btn',
        textContent: 'Refresh Now',
    });
    lifecycle.on(refreshBtn, 'click', async () => {
        const now = Date.now();
        if (now - lastManualRefreshTime < MIN_REFRESH_INTERVAL_MS) return;
        lastManualRefreshTime = now;

        refreshBtn.textContent = 'Refreshing...';
        refreshBtn.disabled = true;
        const stats = await fetchSystemStats();
        if (stats) updateSystemStatsDisplay(stats);
        lifecycle.timeout(() => {
            refreshBtn.textContent = 'Refresh Now';
            refreshBtn.disabled = false;
        }, 500);
    });
    container.appendChild(refreshBtn);

    fragment.appendChild(container);

    setupCollapsibleSection(header, container, {
        async onExpand() {
            const stats = await fetchSystemStats();
            if (stats) {
                updateSystemStatsDisplay(stats);
            } else {
                const el = $('#system-stats-content');
                if (el) {
                    el.innerHTML = '<div class="system-error">Unable to fetch system stats. Admin access required.</div>';
                }
            }

            stopSystemStatsInterval();
            systemStatsInterval = lifecycle.interval(async () => {
                const stats = await fetchSystemStats();
                if (stats) updateSystemStatsDisplay(stats);
            }, 5000);
        },
        onCollapse() {
            stopSystemStatsInterval();
        }
    });

    return fragment;
}
