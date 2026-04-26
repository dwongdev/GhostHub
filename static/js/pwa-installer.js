/**
 * Minimal PWA Installer
 * Handles the PWA installation prompt with a subtle floating button
 */

import { sparkleIcon } from './utils/icons.js';
import { Module, createElement, show, hide } from './libs/ragot.esm.min.js';

let deferredPrompt;
let installButton;
let pwaInstallerLifecycle = null;

function ensurePwaInstallerLifecycle() {
    if (!pwaInstallerLifecycle) {
        pwaInstallerLifecycle = new Module();
    }
    pwaInstallerLifecycle.start();
    return pwaInstallerLifecycle;
}

document.addEventListener('DOMContentLoaded', () => {
    const lifecycle = ensurePwaInstallerLifecycle();
    createInstallButton(lifecycle);
    lifecycle.on(window, 'beforeinstallprompt', handleBeforeInstallPrompt);
    registerServiceWorker();
});

function createInstallButton(lifecycle) {
    if (installButton) return;

    const button = createElement('button', {
        id: 'pwa-install-btn',
        innerHTML: `Install App ${sparkleIcon(14)}`,
        className: 'hidden',
        style: {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            background: '#222',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            padding: '10px 14px',
            fontSize: '14px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
            cursor: 'pointer',
            zIndex: '1000',
            transition: 'opacity 0.2s ease'
        }
    });
    lifecycle.on(button, 'click', installPWA);
    document.body.appendChild(button);
    installButton = button;
}

function handleBeforeInstallPrompt(e) {
    e.preventDefault();
    deferredPrompt = e;
    if (installButton) {
        show(installButton);
    }
}

async function installPWA() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const choiceResult = await deferredPrompt.userChoice;
    if (choiceResult.outcome === 'accepted') {
        console.log('PWA install accepted');
    }
    deferredPrompt = null;
    if (installButton) {
        hide(installButton);
    }
}

function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('Service Worker registered'))
            .catch(err => console.log('Service Worker registration failed:', err));
    }
}

export function cleanupPwaInstaller() {
    deferredPrompt = null;
    if (pwaInstallerLifecycle) {
        pwaInstallerLifecycle.stop();
        pwaInstallerLifecycle = null;
    }
    if (installButton) {
        installButton.remove();
        installButton = null;
    }
}
