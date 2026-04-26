/**
 * WiFi Settings Section
 * Admin-only section for configuring the WiFi access point on Raspberry Pi.
 */

import { setupCollapsibleSection } from './sectionUtils.js';
import { createElement, $ } from '../../../libs/ragot.esm.min.js';
import { toast, dialog } from '../../../utils/notificationManager.js';

// WiFi config cache (module-scoped)
let wifiConfig = null;
let wifiConfigModified = false;

/**
 * Fetches WiFi configuration from the server.
 * @returns {Promise<Object|null>}
 */
async function fetchWifiConfig() {
    try {
        const response = await fetch('/api/admin/wifi/config');
        if (!response.ok) {
            if (response.status === 403) return null;
            throw new Error('Failed to fetch WiFi config');
        }
        const data = await response.json();
        return data.config || null;
    } catch (error) {
        console.error('Error fetching WiFi config:', error);
        return null;
    }
}

/**
 * Saves WiFi configuration to the server.
 * @param {Object} config
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function saveWifiConfigToServer(config) {
    try {
        const response = await fetch('/api/admin/wifi/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await response.json();
        if (!response.ok) {
            return { success: false, message: data.error || 'Failed to save WiFi config' };
        }
        return { success: true, message: data.message || 'WiFi configuration saved' };
    } catch (error) {
        console.error('Error saving WiFi config:', error);
        return { success: false, message: error.message };
    }
}

/**
 * Handles saving WiFi configuration.
 */
async function handleSaveWifiConfig() {
    const ssidInput = $('#wifi-ssid');
    const passInput = $('#wifi-password');
    const channelSelect = $('#wifi-channel');
    const countryInput = $('#wifi-country');
    const saveBtn = $('#wifi-save-btn');

    if (!ssidInput || !channelSelect) return;

    const ssid = ssidInput.value.trim();
    const password = passInput.value;
    const channel = parseInt(channelSelect.value, 10);
    const country = countryInput.value.trim().toUpperCase();

    if (ssid && (ssid.length < 1 || ssid.length > 32)) {
        toast.error('SSID must be 1-32 characters');
        return;
    }
    if (password && (password.length < 8 || password.length > 63)) {
        toast.error('Password must be 8-63 characters');
        return;
    }
    if (country && country.length !== 2) {
        toast.error('Country code must be exactly 2 characters');
        return;
    }

    const config = {};
    if (ssid && ssid !== wifiConfig?.ssid) config.ssid = ssid;
    if (password) config.password = password;
    if (channel !== wifiConfig?.channel) config.channel = channel;
    if (country && country !== wifiConfig?.country_code) config.country_code = country;

    if (Object.keys(config).length === 0) {
        toast.error('No changes to save');
        return;
    }

    const confirmMsg = 'Apply WiFi changes?\n\nConnected devices will be disconnected and will need to reconnect' +
        (config.ssid || config.password ? ' with new credentials.' : '.');
    if (!await dialog.confirm(confirmMsg)) return;

    try {
        saveBtn.textContent = 'Applying...';
        saveBtn.disabled = true;

        const result = await saveWifiConfigToServer(config);

        if (result.success) {
            toast.success(result.message);
            wifiConfigModified = false;
            if (config.ssid) wifiConfig.ssid = config.ssid;
            if (config.password) wifiConfig.password = config.password;
            if (config.channel) wifiConfig.channel = config.channel;
            if (config.country_code) wifiConfig.country_code = config.country_code;
        } else {
            toast.error('Error: ' + result.message);
        }
    } catch (error) {
        toast.error('Error saving WiFi config: ' + error.message);
    } finally {
        saveBtn.textContent = 'Apply WiFi Changes';
        saveBtn.disabled = false;
    }
}

/**
 * Creates the WiFi Settings section.
 * @returns {DocumentFragment}
 */
export function createWifiSettingsSection() {
    const fragment = document.createDocumentFragment();

    // Initialize with defaults, fetch will update async
    wifiConfig = { ssid: 'GhostHub', password: '', channel: 7, country_code: 'US' };
    wifiConfigModified = false;

    const header = createElement('h3', { className: 'config-section-header collapsed', textContent: 'WiFi Access Point' });
    fragment.appendChild(header);

    const container = createElement('div', { className: 'config-section-settings collapsed', id: 'wifi-settings' });

    // Info message
    container.appendChild(createElement('div', {
        className: 'config-description',
        innerHTML: '<strong>Note:</strong> Changes apply immediately on Raspberry Pi. Connected devices will need to reconnect with new credentials.',
    }));

    // SSID Input
    const ssidGroup = createElement('div', { className: 'form-group' });
    ssidGroup.appendChild(createElement('label', { htmlFor: 'wifi-ssid', textContent: 'Network Name (SSID)' }));
    const ssidInput = createElement('input', {
        type: 'text',
        id: 'wifi-ssid',
        placeholder: 'GhostHub',
        maxLength: 32,
        value: wifiConfig?.ssid || '',
        onInput: () => { wifiConfigModified = true; }
    });
    ssidGroup.appendChild(ssidInput);
    ssidGroup.appendChild(createElement('div', { className: 'config-description', textContent: 'The name of the WiFi network (1-32 characters).' }));
    container.appendChild(ssidGroup);

    // Password Input
    const passGroup = createElement('div', { className: 'form-group' });
    passGroup.appendChild(createElement('label', { htmlFor: 'wifi-password', textContent: 'WiFi Password' }));
    const passWrapper = createElement('div', { className: 'input-wrapper password-wrapper' });
    const passInput = createElement('input', {
        type: 'password',
        id: 'wifi-password',
        placeholder: '••••••••',
        minLength: 8,
        maxLength: 63,
        value: wifiConfig?.password || '',
        onInput: () => { wifiConfigModified = true; }
    });
    const toggleBtn = createElement('button', {
        type: 'button',
        className: 'btn btn--secondary btn--sm',
        textContent: 'Show',
        onClick: () => {
            if (passInput.type === 'password') {
                passInput.type = 'text';
                toggleBtn.textContent = 'Hide';
            } else {
                passInput.type = 'password';
                toggleBtn.textContent = 'Show';
            }
        }
    });
    passWrapper.appendChild(passInput);
    passWrapper.appendChild(toggleBtn);
    passGroup.appendChild(passWrapper);
    passGroup.appendChild(createElement('div', { className: 'config-description', textContent: 'WPA2 password (8-63 characters). Click Show to view current password.' }));
    container.appendChild(passGroup);

    // Channel Select
    const channelGroup = createElement('div', { className: 'form-group' });
    channelGroup.appendChild(createElement('label', { htmlFor: 'wifi-channel', textContent: 'WiFi Channel' }));
    const channelSelect = createElement('select', {
        id: 'wifi-channel',
        className: 'config-input-select',
        onChange: () => { wifiConfigModified = true; }
    });
    for (let i = 1; i <= 11; i++) {
        const option = createElement('option', { value: i, textContent: `Channel ${i}` });
        if (i === (wifiConfig?.channel || 7)) option.selected = true;
        channelSelect.appendChild(option);
    }
    channelGroup.appendChild(channelSelect);
    channelGroup.appendChild(createElement('div', { className: 'config-description', textContent: 'WiFi channel (1-11). Try a different channel if you experience interference.' }));
    container.appendChild(channelGroup);

    // Country Code Input
    const countryGroup = createElement('div', { className: 'form-group' });
    countryGroup.appendChild(createElement('label', { htmlFor: 'wifi-country', textContent: 'Country Code' }));
    const countryInput = createElement('input', {
        type: 'text',
        id: 'wifi-country',
        className: 'wifi-country-input',
        placeholder: 'US',
        maxLength: 2,
        value: wifiConfig?.country_code || 'US',
        onInput: (e) => {
            e.target.value = e.target.value.toUpperCase();
            wifiConfigModified = true;
        }
    });
    countryGroup.appendChild(countryInput);
    countryGroup.appendChild(createElement('div', { className: 'config-description', textContent: 'Two-letter country code (e.g., US, GB, DE). Required for regulatory compliance.' }));
    container.appendChild(countryGroup);

    // Save WiFi Button
    const saveWifiBtn = createElement('button', {
        id: 'wifi-save-btn',
        className: 'btn btn--primary btn--sm config-section-action-btn',
        textContent: 'Apply WiFi Changes',
        onClick: handleSaveWifiConfig
    });
    container.appendChild(saveWifiBtn);

    fragment.appendChild(container);

    setupCollapsibleSection(header, container);

    // Fetch actual config in background and update fields
    fetchWifiConfig().then(config => {
        if (config) {
            wifiConfig = config;
            const ssidEl = $('#wifi-ssid');
            const passEl = $('#wifi-password');
            const channelEl = $('#wifi-channel');
            const countryEl = $('#wifi-country');
            if (ssidEl) ssidEl.value = config.ssid || '';
            if (passEl) passEl.value = config.password || '';
            if (channelEl) channelEl.value = config.channel || 7;
            if (countryEl) countryEl.value = config.country_code || 'US';
        }
    }).catch(err => console.warn('Could not fetch WiFi config:', err));

    return fragment;
}
