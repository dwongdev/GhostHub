/**
 * Profile socket event bridge.
 * Re-broadcasts socket events as window events so UI modules can stay decoupled.
 */

import { Module } from '../../libs/ragot.esm.min.js';
import { SOCKET_EVENTS } from '../../core/socketEvents.js';

const PROFILE_SELECTED_EVENT = 'ghosthub:profile-selected';
const PROFILES_CHANGED_EVENT = 'ghosthub:profiles-changed';

class ProfileEventsLifecycle extends Module {
    constructor(socket) {
        super();
        this.socket = socket;
    }

    onStart() {
        if (!this.socket) return;

        this.onSocket(this.socket, SOCKET_EVENTS.PROFILE_SELECTED, (payload) => {
            window.dispatchEvent(new CustomEvent(PROFILE_SELECTED_EVENT, { detail: payload }));
        });

        this.onSocket(this.socket, SOCKET_EVENTS.PROFILES_CHANGED, (payload) => {
            window.dispatchEvent(new CustomEvent(PROFILES_CHANGED_EVENT, { detail: payload }));
        });
    }
}

let lifecycle = null;

export function registerProfileSocketHandlers(socket, selector = null) {
    if (lifecycle) {
        lifecycle.stop();
        lifecycle = null;
    }

    void selector;
    lifecycle = new ProfileEventsLifecycle(socket);
    lifecycle.start();
}

export function cleanupProfileSocketHandlers() {
    if (lifecycle) {
        lifecycle.stop();
        lifecycle = null;
    }
}

export {
    PROFILE_SELECTED_EVENT,
    PROFILES_CHANGED_EVENT,
};
