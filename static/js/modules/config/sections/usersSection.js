/**
 * Users Management Section
 * Admin-only section for viewing and managing connected users.
 */

import { setupCollapsibleSection } from './sectionUtils.js';
import { createElement } from '../../../libs/ragot.esm.min.js';
import { initUsersModule, fetchUsers } from '../../admin/users.js';

function getAppSocket() {
    return window.ragotModules?.appStore?.get?.('socket', null) || null;
}

/**
 * Creates the Users Management settings section (admin-only).
 * @returns {DocumentFragment}
 */
export function createUsersManagementSection() {
    const fragment = document.createDocumentFragment();

    const header = createElement('h3', { className: 'config-section-header collapsed', textContent: 'User Management' });
    fragment.appendChild(header);

    const container = createElement('div', { className: 'config-section-settings collapsed' });

    container.appendChild(createElement('p', {
        className: 'config-description',
        textContent: 'View and manage connected users. Kick users and block their IP addresses if needed.',
    }));

    container.appendChild(createElement('div', { id: 'users-list' }));

    const refreshBtn = createElement('button', {
        id: 'users-refresh-btn',
        className: 'btn btn--secondary btn--sm config-section-action-btn',
        textContent: 'Refresh',
        onClick: () => {
            initUsersModule(getAppSocket());
            fetchUsers();
        }
    });
    container.appendChild(refreshBtn);

    container.appendChild(createElement('div', {
        id: 'users-status-message',
        className: 'config-description',
    }));

    fragment.appendChild(container);

    setupCollapsibleSection(header, container, {
        onExpand() {
            initUsersModule(getAppSocket());
            fetchUsers();
        }
    });

    return fragment;
}
