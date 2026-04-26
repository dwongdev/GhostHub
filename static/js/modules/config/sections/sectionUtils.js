/**
 * Shared utilities for config modal sections.
 * Contains form input builders, scroll helpers, and progress bar helpers.
 */

import { CONFIG_DESCRIPTIONS } from '../../../core/configDescriptions.js';
import { createElement, attr } from '../../../libs/ragot.esm.min.js';

/**
 * Smoothly scrolls a section content into view when expanded.
 * @param {HTMLElement} header - The section header element
 * @param {HTMLElement} [contentContainer] - The content container element (optional)
 */
export function scrollSectionIntoView(header, contentContainer) {
    setTimeout(() => {
        const scrollTarget = contentContainer || header;
        scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

/**
 * Wires up a collapsible section header/container pair.
 * @param {HTMLElement} header - The section header element
 * @param {HTMLElement} container - The collapsible content element
 * @param {Object} [options]
 * @param {Function} [options.onExpand] - Called when the section is expanded
 * @param {Function} [options.onCollapse] - Called when the section is collapsed
 */
export function setupCollapsibleSection(header, container, options = {}) {
    const expandSection = ({ animate = true } = {}) => {
        header.classList.remove('collapsed');
        container.classList.remove('collapsed');

        const targetHeight = container.scrollHeight;

        if (!animate) {
            container.style.maxHeight = 'none';
            return;
        }

        container.style.maxHeight = '0px';
        requestAnimationFrame(() => {
            container.style.maxHeight = `${targetHeight}px`;
        });

        const handleExpandEnd = (event) => {
            if (event.target !== container || event.propertyName !== 'max-height') return;
            container.style.maxHeight = 'none';
            container.removeEventListener('transitionend', handleExpandEnd);
        };

        container.addEventListener('transitionend', handleExpandEnd);
    };

    const collapseSection = ({ animate = true } = {}) => {
        const startHeight = container.scrollHeight;

        header.classList.add('collapsed');
        container.classList.add('collapsed');

        if (!animate) {
            container.style.maxHeight = '0px';
            return;
        }

        container.style.maxHeight = `${startHeight}px`;
        requestAnimationFrame(() => {
            container.style.maxHeight = '0px';
        });
    };

    attr(header, {
        onClick: () => {
            const wasCollapsed = header.classList.contains('collapsed');

            if (wasCollapsed) {
                expandSection();
                scrollSectionIntoView(header, container);
                if (options.onExpand) options.onExpand();
            } else {
                collapseSection();
                if (options.onCollapse) options.onCollapse();
            }
        }
    });

    if (header.classList.contains('collapsed') || container.classList.contains('collapsed')) {
        collapseSection({ animate: false });
    } else {
        expandSection({ animate: false });
    }
}

/**
 * Creates a progress bar element.
 * @param {number} percent - Percentage value (0-100)
 * @param {string} color - Color class (green, yellow, red)
 * @returns {HTMLElement}
 */
export function createProgressBar(percent, color = 'green') {
    const fill = createElement('div', {
        className: `system-progress-fill ${color}`,
        style: { width: `${Math.min(100, Math.max(0, percent))}%` }
    });
    const container = createElement('div', { className: 'system-progress-bar' });
    container.appendChild(fill);
    return container;
}

/**
 * Gets color class based on percentage thresholds.
 * @param {number} percent
 * @param {boolean} inverse - If true, high is good (like free space)
 * @returns {string}
 */
export function getColorClass(percent, inverse = false) {
    if (inverse) {
        if (percent >= 50) return 'green';
        if (percent >= 20) return 'yellow';
        return 'red';
    }
    if (percent >= 90) return 'red';
    if (percent >= 70) return 'yellow';
    return 'green';
}

/**
 * Gets temperature color class.
 * @param {number} temp - Temperature in Celsius
 * @returns {string}
 */
export function getTempColorClass(temp) {
    if (temp >= 80) return 'red';
    if (temp >= 70) return 'yellow';
    return 'green';
}

/**
 * Checks if a setting should be shown in the given mode (basic/advanced).
 * @param {string} fullKey - Full config key (e.g., "python_config.CACHE_EXPIRY")
 * @param {string} settingsMode - 'basic' or 'advanced'
 * @returns {boolean}
 */
export function shouldShowSetting(fullKey, settingsMode) {
    const descObj = CONFIG_DESCRIPTIONS[fullKey];
    const settingLevel = descObj?.level || 'advanced';
    if (settingsMode === 'advanced') return true;
    return settingLevel === 'basic';
}

/**
 * Creates a form input element for a configuration setting.
 * @param {string} key - The configuration key
 * @param {*} value - The current value of the configuration
 * @param {string} pathPrefix - The path prefix for nested objects (e.g., "python_config.")
 * @returns {HTMLElement} The created form group element
 */
export function createConfigInput(key, value, pathPrefix = '') {
    const formGroup = createElement('div', { className: 'form-group' });
    const labelText = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const label = createElement('label', { htmlFor: `config-${pathPrefix}${key}`, textContent: labelText });

    const helpIcon = createElement('span', { className: 'config-help-icon', textContent: '?', title: 'Click for details' });

    const descriptionDiv = createElement('div', { className: 'config-description hidden' });
    const fullPath = `${pathPrefix}${key}`;

    const descObj = CONFIG_DESCRIPTIONS[fullPath];
    const description = (typeof descObj === 'object' && descObj?.description)
        ? descObj.description
        : (typeof descObj === 'string' ? descObj : `${labelText} configuration setting. No detailed description available.`);

    if (value === undefined) {
        console.warn(`Config value for ${fullPath} is undefined, using default value`);
        if (key.includes('TIMEOUT') || key.includes('DELAY') || key.includes('ATTEMPTS')) {
            value = 30;
        } else if (key.includes('ENABLED') || key.includes('AUTO') || key.startsWith('IS_')) {
            value = false;
        } else {
            value = '';
        }
    }
    descriptionDiv.textContent = description;

    attr(helpIcon, {
        onClick: (e) => {
            e.stopPropagation();
            descriptionDiv.classList.toggle('hidden');
        }
    });

    label.appendChild(helpIcon);

    let input;
    const inputWrapper = createElement('div', { className: 'input-wrapper' });
    const fullPathKey = `${pathPrefix}${key}`;

    const selectOptions = {
        'python_config.PROGRESS_TRACKING_MODE': [
            { value: 'category', label: 'Per Category (resume where you left off in folder)' },
            { value: 'video', label: 'Per Video (resume each video independently)' }
        ],
        'python_config.VIDEO_END_BEHAVIOR': [
            { value: 'stop', label: 'Stop (video stops at end)' },
            { value: 'loop', label: 'Loop (video repeats continuously)' },
            { value: 'play_next', label: 'Play Next (auto-advance if available)' }
        ]
    };

    if (selectOptions[fullPathKey]) {
        input = createElement('select', { className: 'config-input-select' });

        selectOptions[fullPathKey].forEach(opt => {
            const option = createElement('option', { value: opt.value, textContent: opt.label });
            if (opt.value === value) option.selected = true;
            input.appendChild(option);
        });

        inputWrapper.appendChild(input);
        inputWrapper.appendChild(descriptionDiv);
        formGroup.appendChild(label);
        formGroup.appendChild(inputWrapper);
    } else if (typeof value === 'boolean') {
        input = createElement('input', { type: 'checkbox', checked: value, className: 'config-input-checkbox' });
        const checkboxLabel = createElement('span', { className: 'checkbox-label-text', textContent: ` ${labelText}` });

        label.textContent = '';
        label.appendChild(helpIcon);

        inputWrapper.appendChild(input);
        inputWrapper.appendChild(checkboxLabel);
        inputWrapper.appendChild(descriptionDiv);
        formGroup.appendChild(label);
        formGroup.appendChild(inputWrapper);
    } else {
        input = createElement('input');

        if (key.endsWith('_PASSWORD')) {
            input.type = 'password';
            input.value = value || '';
            input.placeholder = '••••••••';

            const toggleBtn = createElement('button', {
                type: 'button',
                className: 'btn btn--secondary btn--sm',
                textContent: 'Show'
            });
            attr(toggleBtn, {
                onClick: () => {
                    if (input.type === 'password') {
                    input.type = 'text';
                    toggleBtn.textContent = 'Hide';
                    } else {
                        input.type = 'password';
                        toggleBtn.textContent = 'Show';
                    }
                }
            });

            inputWrapper.classList.add('password-wrapper');

            inputWrapper.appendChild(input);
            inputWrapper.appendChild(toggleBtn);
            inputWrapper.appendChild(descriptionDiv);
            formGroup.appendChild(label);
            formGroup.appendChild(inputWrapper);
        } else if (typeof value === 'number') {
            input.type = 'number';
            input.value = value;
            if (key.includes('FACTOR')) {
                input.step = '0.1';
            }

            inputWrapper.appendChild(input);
            inputWrapper.appendChild(descriptionDiv);
            formGroup.appendChild(label);
            formGroup.appendChild(inputWrapper);
        } else {
            input.type = 'text';
            input.value = value;

            inputWrapper.appendChild(input);
            inputWrapper.appendChild(descriptionDiv);
            formGroup.appendChild(label);
            formGroup.appendChild(inputWrapper);
        }
    }

    if (input) {
        input.id = `config-${fullPathKey.replace(/\./g, '-')}`;
        input.dataset.path = fullPathKey;
    }

    return formGroup;
}
