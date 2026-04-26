/**
 * JavaScript Config Sections
 * Builds collapsible sections for JS config keys (main, core_app, sync_manager).
 */

import { setupCollapsibleSection, shouldShowSetting, createConfigInput } from './sectionUtils.js';
import { createElement } from '../../../libs/ragot.esm.min.js';

/**
 * Creates all JavaScript config sections.
 * @param {string} settingsMode - 'basic' or 'advanced'
 * @returns {DocumentFragment}
 */
export function createJsConfigSections(settingsMode) {
    const fragment = document.createDocumentFragment();
    const runtimeConfig = window.ragotModules?.appStore?.get?.('config', {}) || {};

    if (!runtimeConfig?.javascript_config) return fragment;

    const sectionDisplayNames = {
        'main': 'Main',
        'core_app': 'Core App',
        'sync_manager': 'Sync Manager'
    };

    const orderedSections = Object.keys(sectionDisplayNames);

    for (const sectionKey of orderedSections) {
        const sectionValue = runtimeConfig.javascript_config[sectionKey];
        if (!sectionValue) continue;

        const visibleSettings = [];
        if (typeof sectionValue === 'object' && sectionValue !== null) {
            const sortedKeys = Object.keys(sectionValue).sort();

            for (const key of sortedKeys) {
                const fullKey = `javascript_config.${sectionKey}.${key}`;
                if (shouldShowSetting(fullKey, settingsMode)) {
                    visibleSettings.push({ key, value: sectionValue[key] });
                }
            }
        }

        if (visibleSettings.length === 0) {
            console.log(`Skipping section ${sectionKey} (no visible settings in ${settingsMode} mode)`);
            continue;
        }

        const sectionHeader = createElement('h3', { className: 'config-section-header collapsed', textContent: `${sectionDisplayNames[sectionKey]} Settings` });
        fragment.appendChild(sectionHeader);

        const jsSettingsContainer = createElement('div', { className: 'config-section-settings collapsed', id: `js-settings-${sectionKey}` });

        for (const { key, value } of visibleSettings) {
            jsSettingsContainer.appendChild(createConfigInput(key, value, `javascript_config.${sectionKey}.`));
        }

        fragment.appendChild(jsSettingsContainer);

        setupCollapsibleSection(sectionHeader, jsSettingsContainer);
    }

    for (const sectionKey in runtimeConfig.javascript_config) {
        if (!orderedSections.includes(sectionKey)) {
            console.log(`Skipping legacy section: ${sectionKey}`);
        }
    }

    return fragment;
}
