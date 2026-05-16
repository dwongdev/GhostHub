/**
 * Admin Settings Section (Python Config)
 * Builds the App/Media Settings section including maintenance buttons and
 * clustered config groups for admin users.
 */

import { CONFIG_DESCRIPTIONS } from '../../../core/configDescriptions.js';
import {
    shieldCheckIcon, clapperIcon, clockIcon, gearIcon, refreshIcon
} from '../../../utils/icons.js';
import { refreshAllLayouts } from '../../../utils/liveVisibility.js';
import { setupCollapsibleSection, shouldShowSetting, createConfigInput } from './sectionUtils.js';
import { createElement, attr } from '../../../libs/ragot.esm.min.js';
import { toast, dialog } from '../../../utils/notificationManager.js';
import { createUserDataTransferSection } from './userDataTransferSection.js';

/**
 * Creates the settings mode toggle (Basic/Advanced) for admin settings.
 * @param {string} currentSettingsMode - Current mode ('basic' or 'advanced')
 * @param {Function} onModeChange - Called with the new mode when user toggles
 * @returns {HTMLElement}
 */
export function createSettingsModeToggle(currentSettingsMode, onModeChange) {
    const container = createElement('div', { className: 'config-mode-toggle' });

    const label = createElement('label', { textContent: 'Settings Mode:' });

    const radioGroup = createElement('div', { className: 'config-mode-radio-group' });

    const basicLabel = createElement('label');
    const basicRadio = createElement('input', {
        type: 'radio',
        name: 'settings-mode',
        value: 'basic',
        checked: currentSettingsMode === 'basic',
        onChange: () => {
            if (basicRadio.checked) onModeChange('basic');
        }
    });
    basicLabel.appendChild(basicRadio);
    basicLabel.appendChild(document.createTextNode(' Basic (Recommended)'));

    const advancedLabel = createElement('label');
    const advancedRadio = createElement('input', {
        type: 'radio',
        name: 'settings-mode',
        value: 'advanced',
        checked: currentSettingsMode === 'advanced',
        onChange: () => {
            if (advancedRadio.checked) onModeChange('advanced');
        }
    });
    advancedLabel.appendChild(advancedRadio);
    advancedLabel.appendChild(document.createTextNode(' Advanced (All Settings)'));

    radioGroup.appendChild(basicLabel);
    radioGroup.appendChild(advancedLabel);

    container.appendChild(label);
    container.appendChild(radioGroup);

    return container;
}

/**
 * Creates the Python/App config section with maintenance buttons and grouped settings.
 * @param {string} settingsMode - 'basic' or 'advanced'
 * @param {Function} closeConfigModal - Callback to close the modal
 * @returns {DocumentFragment}
 */
export function createAdminSettingsSection(settingsMode, closeConfigModal) {
    const fragment = document.createDocumentFragment();
    const runtimeConfig = window.ragotModules?.appStore?.get?.('config', {}) || {};

    const pythonHeader = createElement('h3', { className: 'config-section-header collapsed', textContent: 'App/Media Settings' });
    fragment.appendChild(pythonHeader);

    const pythonSettingsContainer = createElement('div', { className: 'config-section-settings collapsed' });

    const tunnelConfigKeys = ['TUNNEL_PROVIDER', 'PINGGY_ACCESS_TOKEN', 'TUNNEL_LOCAL_PORT'];
    const hiddenConfigKeys = ['DEBUG_MODE'];

    // --- Maintenance Sub-section ---
    const maintHeader = createElement('h4', { className: 'config-subsection-header' });

    const maintHeaderLabel = createElement('span', {
        innerHTML: `${refreshIcon(16)} Maintenance`,
    });
    maintHeader.appendChild(maintHeaderLabel);

    const versionBadge = createElement('span', {
        className: 'config-version-badge',
        textContent: 'v...',
    });
    maintHeader.appendChild(versionBadge);
    fetch('/api/system/version').then(r => r.json()).then(d => {
        if (d && d.version) versionBadge.textContent = `v${d.version}`;
    }).catch(() => { versionBadge.textContent = ''; });

    pythonSettingsContainer.appendChild(maintHeader);

    const maintButtons = createElement('div', { className: 'config-maint-buttons' });

    // Reindex Media button
    const reindexButton = createElement('button', {
        textContent: 'Reindex Media Library',
        className: 'btn btn--warning btn--sm config-reindex-btn',
        onClick: async () => {
            if (!await dialog.confirm('Are you sure you want to reindex the active drive media?\n\nThis will:\n- Refresh media indexes and metadata for active drives\n- Leave thumbnails and .ghosthub generated cache untouched\n\nNote: Disconnected drives will retain their existing media index data.\n\nThis may take several minutes.', { type: 'danger' })) return;
            try {
                reindexButton.textContent = 'Reindexing...';
                reindexButton.disabled = true;
                const response = await fetch('/api/admin/reindex-media', {
                    method: 'POST',
                    credentials: 'include'
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    let message = result.message;
                    if (result.warnings && result.warnings.length > 0) {
                        message += '\n\nWarnings:\n' + result.warnings.join('\n');
                    }
                    await dialog.alert(message);
                    await refreshAllLayouts(true);
                } else {
                    toast.error(`Error: ${result.error || 'Failed to reindex media.'}`);
                }
            } catch (error) {
                console.error('Error reindexing media:', error);
                toast.error('An error occurred while trying to reindex media.');
            } finally {
                reindexButton.textContent = 'Reindex Media Library';
                reindexButton.disabled = false;
            }
        }
    });
    maintButtons.appendChild(reindexButton);

    const regenerateThumbnailsButton = createElement('button', {
        textContent: 'Regenerate Thumbnails',
        className: 'btn btn--warning btn--sm config-regenerate-thumbnails-btn',
        onClick: async () => {
            if (!await dialog.confirm('Are you sure you want to regenerate thumbnails for the active drives?\n\nThis will:\n- Clear thumbnail cache only\n- Requeue thumbnail generation using the current media index\n- Leave media indexes and other generated cache data untouched\n\nThis may take several minutes.', { type: 'danger' })) return;
            try {
                regenerateThumbnailsButton.textContent = 'Regenerating...';
                regenerateThumbnailsButton.disabled = true;
                const response = await fetch('/api/admin/regenerate-thumbnails', {
                    method: 'POST',
                    credentials: 'include'
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    let message = result.message;
                    if (result.warnings && result.warnings.length > 0) {
                        message += '\n\nWarnings:\n' + result.warnings.join('\n');
                    }
                    await dialog.alert(message);
                    await refreshAllLayouts(true);
                } else {
                    toast.error(`Error: ${result.error || 'Failed to regenerate thumbnails.'}`);
                }
            } catch (error) {
                console.error('Error regenerating thumbnails:', error);
                toast.error('An error occurred while trying to regenerate thumbnails.');
            } finally {
                regenerateThumbnailsButton.textContent = 'Regenerate Thumbnails';
                regenerateThumbnailsButton.disabled = false;
            }
        }
    });
    maintButtons.appendChild(regenerateThumbnailsButton);

    if (settingsMode === 'advanced') {
        const clearGeneratedCacheButton = createElement('button', {
            textContent: 'Clear Full .ghosthub Cache',
            className: 'btn btn--danger btn--sm config-clear-generated-cache-btn',
            onClick: async () => {
                if (!await dialog.confirm('Are you sure you want to clear the full generated .ghosthub cache for active drives?\n\nThis will:\n- Remove thumbnail and other generated cache data inside .ghosthub\n- Leave media indexes untouched\n- Not start a reindex automatically\n\nUse this only when the broader generated cache needs a full reset.', { type: 'danger' })) return;
                try {
                    clearGeneratedCacheButton.textContent = 'Clearing Cache...';
                    clearGeneratedCacheButton.disabled = true;
                    const response = await fetch('/api/admin/clear-generated-cache', {
                        method: 'POST',
                        credentials: 'include'
                    });
                    const result = await response.json();
                    if (response.ok && result.success) {
                        let message = result.message;
                        if (result.warnings && result.warnings.length > 0) {
                            message += '\n\nWarnings:\n' + result.warnings.join('\n');
                        }
                        await dialog.alert(message);
                        await refreshAllLayouts(true);
                    } else {
                        toast.error(`Error: ${result.error || 'Failed to clear generated cache.'}`);
                    }
                } catch (error) {
                    console.error('Error clearing generated cache:', error);
                    toast.error('An error occurred while trying to clear generated cache.');
                } finally {
                    clearGeneratedCacheButton.textContent = 'Clear Full .ghosthub Cache';
                    clearGeneratedCacheButton.disabled = false;
                }
            }
        });
        maintButtons.appendChild(clearGeneratedCacheButton);
    }

    const clearDataButton = createElement('button', {
        textContent: 'Reset Shared Server Data',
        className: 'btn btn--danger btn--sm config-clear-data-btn',
        onClick: async () => {
            if (!await dialog.confirm('Are you sure you want to reset shared server data?\n\nThis clears:\n\u2022 Subtitle cache\n\u2022 Hidden categories\n\u2022 Hidden files\n\u2022 Media indexes across all drives\n\nProfile data (progress, preferences) is not affected.\n\nThis cannot be undone.', { type: 'danger' })) return;
            try {
                clearDataButton.textContent = 'Clearing...';
                clearDataButton.disabled = true;
                const response = await fetch('/api/admin/data/clear-all', { method: 'POST' });
                const result = await response.json();
                if (response.ok) {
                    toast.success(result.message || 'All saved data cleared successfully.');
                    await refreshAllLayouts(true);
                } else {
                    toast.error(`Error: ${result.error || 'Failed to clear data.'}`);
                }
            } catch (error) {
                console.error('Error clearing data:', error);
                toast.error('An error occurred while trying to clear data.');
            } finally {
                clearDataButton.textContent = 'Reset Shared Server Data';
                clearDataButton.disabled = false;
            }
        }
    });
    maintButtons.appendChild(clearDataButton);

    // Update GhostHub button
    const updateButton = createElement('button', {
        textContent: 'Update GhostHub',
        className: 'btn btn--primary btn--sm config-update-btn',
        onClick: async () => {
            updateButton.textContent = 'Checking for updates...';
            updateButton.disabled = true;

            let versionInfo = null;
            try {
                const checkResp = await fetch('/api/admin/system/version-check');
                versionInfo = await checkResp.json();
                console.log('[GhostHub] version-check response:', versionInfo);
            } catch (_err) {
                console.warn('[GhostHub] version-check network error:', _err);
                // Network error during check - fall through to simple confirm
            }

            if (versionInfo && versionInfo.local_mode) {
                if (!await dialog.confirm('Are you sure you want to update GhostHub from GitHub Releases?\n\nThis will:\n\u2022 Download the latest version\n\u2022 Restart the GhostHub service\n\u2022 May take 3-5 minutes\n\nDo not close this browser window.')) {
                    updateButton.textContent = 'Update GhostHub';
                    updateButton.disabled = false;
                    return;
                }
            } else if (versionInfo && versionInfo.update_available === false && versionInfo.latest_version) {
                toast.info(`GhostHub is up to date (v${versionInfo.current_version}).`);
                updateButton.textContent = 'Update GhostHub';
                updateButton.disabled = false;
                return;
            } else if (versionInfo && versionInfo.update_available) {
                if (!await dialog.confirm(`Update GhostHub v${versionInfo.current_version} \u2192 v${versionInfo.latest_version} from GitHub Releases?\n\nThis will:\n\u2022 Download the latest version\n\u2022 Restart the GhostHub service\n\u2022 May take 3-5 minutes\n\nDo not close this browser window.`)) {
                    updateButton.textContent = 'Update GhostHub';
                    updateButton.disabled = false;
                    return;
                }
            } else {
                // Check failed or version unknown - ask user if they want to proceed anyway
                const errMsg = versionInfo && versionInfo.error
                    ? `\n\nReason: ${versionInfo.error}`
                    : (!versionInfo ? '\n\n(Network error reaching server)' : '');
                if (!await dialog.confirm(`\u26a0 Could not determine available version.${errMsg}\n\nUpdate anyway?`)) {
                    updateButton.textContent = 'Update GhostHub';
                    updateButton.disabled = false;
                    return;
                }
            }

            try {
                updateButton.textContent = 'Scheduling update...';
                const response = await fetch('/api/admin/system/update', { method: 'POST' });
                const result = await response.json();
                if (response.ok) {
                    updateButton.textContent = 'Update scheduled!';
                    await dialog.alert(result.message || 'Update started successfully.\n\nThe system will restart in a few seconds.\n\nYou can refresh this page after 3-5 minutes.');
                    setTimeout(() => {
                        closeConfigModal();
                    }, 2000);
                } else {
                    toast.error(`Update failed:\n\n${result.error || 'Failed to start update.'}`);
                    updateButton.textContent = 'Update GhostHub';
                    updateButton.disabled = false;
                }
            } catch (error) {
                console.error('Error starting update:', error);
                toast.error('Network error:\n\nCould not reach the server. Check your connection.');
                updateButton.textContent = 'Update GhostHub';
                updateButton.disabled = false;
            }
        }
    });
    maintButtons.appendChild(updateButton);

    // Restart GhostHub button
    const restartButton = createElement('button', {
        textContent: 'Restart GhostHub',
        className: 'btn btn--secondary btn--sm config-restart-btn',
        title: 'Restarts the GhostHub service safely (no system reboot)',
        onClick: async () => {
            if (!await dialog.confirm('Are you sure you want to restart the GhostHub service?\n\nThis will disconnect all active users temporarily.', { type: 'danger' })) return;
            try {
                restartButton.textContent = 'Restarting...';
                restartButton.disabled = true;
                const response = await fetch('/api/admin/system/restart', { method: 'POST' });
                const result = await response.json();

                if (response.ok && result.success) {
                    toast.success(result.message || 'GhostHub is restarting. This page will refresh in 20 seconds.');
                    setTimeout(() => {
                        window.location.reload();
                    }, 20000);
                } else {
                    toast.error(`Restart failed:\n\n${result.error || 'Unknown error'}`);
                    restartButton.textContent = 'Restart GhostHub';
                    restartButton.disabled = false;
                }
            } catch (error) {
                console.error('Error starting restart:', error);
                toast.info('Note: The server connection was interrupted. This usually means the restart has started.\n\nYou can refresh this page in a few moments.');
                setTimeout(() => {
                    window.location.reload();
                }, 20000);
            }
        }
    });
    maintButtons.appendChild(restartButton);

    pythonSettingsContainer.appendChild(maintButtons);

    const userDataSection = createUserDataTransferSection();
    pythonSettingsContainer.appendChild(userDataSection);

    // Clustered Config Keys
    const configGroups = [
        { id: 'security', label: 'Security', icon: shieldCheckIcon, keys: ['SESSION_PASSWORD', 'ADMIN_PASSWORD'] },
        { id: 'playback', label: 'Playback Control', icon: clapperIcon, keys: ['SHUFFLE_MEDIA', 'VIDEO_END_BEHAVIOR', 'ENABLE_SUBTITLES'] },
        { id: 'progress', label: 'Progress Tracking', icon: clockIcon, keys: ['SAVE_VIDEO_PROGRESS', 'SAVE_PROGRESS_FOR_HIDDEN_FILES', 'PROGRESS_TRACKING_MODE'] },
        { id: 'technical', label: 'Technical & Performance', icon: gearIcon, keys: [] }
    ];

    const handledKeys = new Set();
    configGroups.forEach(group => {
        const groupContainer = createElement('div', {
            className: `config-group config-group-${group.id}`,
        });

        const groupLabel = createElement('h4', {
            className: 'config-group-label',
            innerHTML: `${group.icon ? group.icon(16) : ''} ${group.label}`,
        });
        groupContainer.appendChild(groupLabel);

        let groupHasContent = false;

        group.keys.forEach(key => {
            const fullKey = `python_config.${key}`;
            if (shouldShowSetting(fullKey, settingsMode)) {
                let value = runtimeConfig?.python_config?.[key];
                if (value === undefined) value = runtimeConfig?.[key];
                if (value === undefined && key === 'ADMIN_PASSWORD') value = 'admin';
                if (value === undefined && key === 'SESSION_PASSWORD') value = '';

                groupContainer.appendChild(createConfigInput(key, value, 'python_config.'));
                handledKeys.add(key);
                groupHasContent = true;
            }
        });

        if (group.id === 'technical') {
            for (const fullKey in CONFIG_DESCRIPTIONS) {
                if (fullKey.startsWith('python_config.')) {
                    const key = fullKey.substring('python_config.'.length);
                    if (!handledKeys.has(key) && !tunnelConfigKeys.includes(key) && !hiddenConfigKeys.includes(key)) {
                        if (shouldShowSetting(fullKey, settingsMode)) {
                            const value = (runtimeConfig && runtimeConfig.python_config && runtimeConfig.python_config.hasOwnProperty(key))
                                ? runtimeConfig.python_config[key]
                                : undefined;

                            if (value !== undefined) {
                                groupContainer.appendChild(createConfigInput(key, value, 'python_config.'));
                                groupHasContent = true;
                            }
                        }
                    }
                }
            }
        }

        if (groupHasContent) {
            pythonSettingsContainer.appendChild(groupContainer);
        }
    });

    fragment.appendChild(pythonSettingsContainer);

    setupCollapsibleSection(pythonHeader, pythonSettingsContainer);

    fragment.__cleanup = () => {
        if (typeof userDataSection.__cleanup === 'function') {
            userDataSection.__cleanup();
        }
    };

    return fragment;
}
