/**
 * Tunnel Modal Module
 * Handles the tunnel management modal, its population, and related tunnel operations.
 */

import { saveConfig } from '../utils/configManager.js';

// DOM Elements for Tunnel Modal
const tunnelModal = document.getElementById('tunnel-modal');
const tunnelToggleBtn = document.getElementById('tunnel-toggle-btn'); // Will be used by uiController to trigger open
const tunnelModalCloseBtn = document.getElementById('tunnel-modal-close-btn');
const tunnelModalStartBtn = document.getElementById('tunnel-modal-start-btn');
const tunnelModalStopBtn = document.getElementById('tunnel-modal-stop-btn');
const tunnelModalSaveSettingsBtn = document.getElementById('tunnel-modal-save-settings-btn');
const tunnelProviderSelect = document.getElementById('tunnel-provider-select');
const pinggyTokenGroup = document.getElementById('pinggy-token-group');
const pinggyAccessTokenInput = document.getElementById('pinggy-access-token-input');
const tunnelLocalPortInput = document.getElementById('tunnel-local-port-input');
const tunnelStatusDisplay = document.getElementById('tunnel-status-display');

// Variable to track the tunnel status polling interval
let tunnelStatusPollingInterval = null;

/**
 * Updates the visibility of Pinggy token input based on provider selection.
 */
function updatePinggyTokenVisibility() {
    if (tunnelProviderSelect && pinggyTokenGroup) {
        pinggyTokenGroup.classList.toggle('hidden', tunnelProviderSelect.value !== 'pinggy');
    }
}

/**
 * Populates the tunnel modal with current settings from appConfig.
 */
function populateTunnelModal() {
    if (!window.appConfig || !window.appConfig.python_config) {
        if (tunnelStatusDisplay) tunnelStatusDisplay.textContent = 'Error: App configuration not loaded.';
        return;
    }
    const pythonConfig = window.appConfig.python_config;
    if (tunnelProviderSelect) tunnelProviderSelect.value = pythonConfig.TUNNEL_PROVIDER || 'none';
    if (pinggyAccessTokenInput) pinggyAccessTokenInput.value = pythonConfig.PINGGY_ACCESS_TOKEN || '';
    if (tunnelLocalPortInput) tunnelLocalPortInput.value = pythonConfig.TUNNEL_LOCAL_PORT || 5000;
    
    updatePinggyTokenVisibility();
    updateTunnelStatusDisplay(); // Fetch current status from backend
}

/**
 * Opens the tunnel management modal.
 */
function openTunnelModal() {
    populateTunnelModal();
    if (tunnelModal) tunnelModal.classList.remove('hidden');
    
    // Initialize tunnel status and start polling if not active
    updateTunnelStatusDisplay();
    
    // Start a polling interval for tunnel status updates when the modal is open
    if (!tunnelStatusPollingInterval) {
        tunnelStatusPollingInterval = setInterval(async () => {
            try {
                const statusResponse = await fetch('/api/tunnel/status');
                const statusData = await statusResponse.json();
                
                if (statusResponse.ok) {
                    await updateTunnelStatusDisplay();
                    
                    // If tunnel is running and has a URL, we can slow down polling or stop it
                    if (statusData.status === 'running' && statusData.url) {
                        console.log('Tunnel has URL, reducing polling frequency');
                        
                        // Just do one more poll after a delay, then stop
                        clearInterval(tunnelStatusPollingInterval);
                        tunnelStatusPollingInterval = null;
                        
                        // Do a final refresh after 3 seconds to ensure everything is up to date
                        setTimeout(async () => {
                            await updateTunnelStatusDisplay();
                            console.log('Final tunnel status check completed');
                        }, 3000);
                    }
                }
            } catch (error) {
                console.error('Error polling tunnel status:', error);
            }
        }, 3000); // Poll every 3 seconds while modal is open
        
        console.log('Started tunnel status polling on modal open');
    }
}

/**
 * Closes the tunnel management modal.
 */
function closeTunnelModal() {
    if (tunnelModal) tunnelModal.classList.add('hidden');
    
    // Clear any active polling interval when the modal is closed
    if (tunnelStatusPollingInterval) {
        clearInterval(tunnelStatusPollingInterval);
        tunnelStatusPollingInterval = null;
        console.log('Tunnel status polling stopped due to modal close');
    }
}

/**
 * Updates the tunnel status display by fetching from the backend.
 */
async function updateTunnelStatusDisplay() {
    if (!tunnelStatusDisplay) return;
    tunnelStatusDisplay.textContent = 'Status: Checking...';
    tunnelStatusDisplay.className = 'tunnel-status status-checking'; // Base class + checking

    try {
        const response = await fetch('/api/tunnel/status');
        const data = await response.json();

        if (response.ok) {
            if (data.status === 'running') {
                let displayText = `Status: Running (${data.provider || 'Unknown'}) on port ${data.local_port || 'N/A'}`;
                
                if (data.url) {
                    // For Cloudflare tunnels
                    if (data.provider === 'cloudflare' && data.url.includes('trycloudflare.com')) {
                        displayText += ` - URL: <a href="${data.url}" target="_blank" class="tunnel-url cloudflare-url">${data.url}</a>`;
                    } 
                    // For Pinggy tunnels
                    else if (data.provider === 'pinggy' && data.url.startsWith('https://')) {
                        displayText += ` - URL: <a href="${data.url}" target="_blank" class="tunnel-url pinggy-url">${data.url}</a>`;
                    } 
                    // For any other tunnels or URLs
                    else {
                        displayText += ` - URL: <a href="${data.url}" target="_blank" class="tunnel-url">${data.url}</a>`;
                    }
                } else {
                    displayText += ' - URL: Waiting for URL...';
                }
                
                tunnelStatusDisplay.innerHTML = displayText;
                tunnelStatusDisplay.className = 'tunnel-status status-running'; // Set class last
            } else {
                tunnelStatusDisplay.textContent = `Status: Stopped`;
                tunnelStatusDisplay.className = 'tunnel-status status-stopped';
            }
        } else {
            tunnelStatusDisplay.textContent = `Status: Error fetching - ${data.message || 'Unknown error'}`;
            tunnelStatusDisplay.className = 'tunnel-status status-stopped'; // Treat error as stopped
        }
    } catch (error) {
        console.error('Failed to fetch tunnel status:', error);
        tunnelStatusDisplay.textContent = 'Status: Error fetching status.';
        tunnelStatusDisplay.className = 'tunnel-status status-stopped';
    }
}

/**
 * Handles saving tunnel specific settings (provider, token, port).
 */
async function handleSaveTunnelSettings() {
    if (!window.appConfig) {
        alert('App configuration not loaded. Cannot save tunnel settings.');
        return;
    }

    const newPythonConfig = { ...window.appConfig.python_config }; // Create a copy to modify

    newPythonConfig.TUNNEL_PROVIDER = tunnelProviderSelect ? tunnelProviderSelect.value : 'none';
    newPythonConfig.PINGGY_ACCESS_TOKEN = pinggyAccessTokenInput ? pinggyAccessTokenInput.value : '';
    newPythonConfig.TUNNEL_LOCAL_PORT = tunnelLocalPortInput ? parseInt(tunnelLocalPortInput.value, 10) : 5000;

    const fullNewConfig = {
        ...window.appConfig,
        python_config: newPythonConfig
    };
    
    try {
        if(tunnelModalSaveSettingsBtn) {
            tunnelModalSaveSettingsBtn.textContent = 'Saving...';
            tunnelModalSaveSettingsBtn.disabled = true;
        }
        const result = await saveConfig(fullNewConfig); // Use the global saveConfig
        alert(result.message || 'Tunnel settings saved successfully! These will be used next time a tunnel is started.');
        window.appConfig.python_config = newPythonConfig; 
    } catch (error) {
        console.error('Failed to save tunnel settings:', error);
        alert(`Error saving tunnel settings: ${error.message || 'Unknown error'}`);
    } finally {
        if(tunnelModalSaveSettingsBtn) {
            tunnelModalSaveSettingsBtn.textContent = 'Save Settings';
            tunnelModalSaveSettingsBtn.disabled = false;
        }
    }
}

/**
 * Handles starting the tunnel.
 */
async function handleStartTunnel() {
    if(tunnelModalStartBtn) {
        tunnelModalStartBtn.textContent = 'Starting...';
        tunnelModalStartBtn.disabled = true;
    }
    if(tunnelStatusDisplay) {
        tunnelStatusDisplay.textContent = 'Status: Starting...';
        tunnelStatusDisplay.className = 'tunnel-status status-starting';
    }

    if (tunnelStatusPollingInterval) {
        clearInterval(tunnelStatusPollingInterval);
        tunnelStatusPollingInterval = null;
    }

    try {
        await handleSaveTunnelSettings(); 

        const provider = tunnelProviderSelect ? tunnelProviderSelect.value : 'none';
        const localPort = tunnelLocalPortInput ? parseInt(tunnelLocalPortInput.value, 10) : 5000;
        let pinggyToken = '';
        if (provider === 'pinggy') {
            pinggyToken = pinggyAccessTokenInput ? pinggyAccessTokenInput.value : '';
        }

        if (provider === 'none') {
            alert('Please select a tunnel provider.');
            if(tunnelModalStartBtn) {
                tunnelModalStartBtn.textContent = 'Start Tunnel';
                tunnelModalStartBtn.disabled = false;
            }
            if(tunnelStatusDisplay) tunnelStatusDisplay.textContent = 'Status: Not Active';
            return;
        }

        const body = {
            provider: provider,
            local_port: localPort
        };
        if (provider === 'pinggy') {
            body.pinggy_token = pinggyToken;
        }

        const response = await fetch('/api/tunnel/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });
        const data = await response.json();

        if (data.status === 'success') { 
            alert(data.message || 'Tunnel started successfully!');
            
            // Start polling for tunnel status
            console.log(`Starting tunnel status polling for ${provider} URL`);
            await updateTunnelStatusDisplay();
            let pollCount = 0;
            const maxPolls = 30;
            
            tunnelStatusPollingInterval = setInterval(async () => {
                pollCount++;
                console.log(`Polling tunnel status (${pollCount}/${maxPolls})`);
                
                try {
                    const statusResponse = await fetch('/api/tunnel/status');
                    const statusData = await statusResponse.json();
                    
                    if (statusResponse.ok) {
                        // If tunnel is running and has a URL - stop polling immediately
                        if (statusData.status === 'running' && statusData.url) {
                            console.log(`Tunnel URL found: ${statusData.url}, updating display and stopping polling`);
                            await updateTunnelStatusDisplay();
                            
                            // Stop polling immediately when URL is found
                            clearInterval(tunnelStatusPollingInterval);
                            tunnelStatusPollingInterval = null;
                            console.log('Tunnel URL polling stopped - URL found');
                        } 
                        // If tunnel is no longer running
                        else if (statusData.status !== 'running') {
                            console.log('Tunnel is no longer running, stopping polling');
                            clearInterval(tunnelStatusPollingInterval);
                            tunnelStatusPollingInterval = null;
                            await updateTunnelStatusDisplay();
                        }
                        // If tunnel is running but URL not yet available, continue polling
                        else {
                            console.log('Tunnel is running but URL not yet available, continuing to poll');
                            await updateTunnelStatusDisplay();
                        }
                    }
                } catch (error) {
                    console.error('Error polling tunnel status:', error);
                }
                
                if (pollCount >= maxPolls) {
                    console.log('Reached maximum polling attempts, stopping');
                    clearInterval(tunnelStatusPollingInterval);
                    tunnelStatusPollingInterval = null;
                    await updateTunnelStatusDisplay();
                }
            }, 2000); 
        } else {
            alert(`Error starting tunnel: ${data.message || 'Unknown error'}`);
            updateTunnelStatusDisplay();
        }
    } catch (error) {
        console.error('Failed to start tunnel:', error);
        alert(`Error starting tunnel: ${error.toString()}`);
        updateTunnelStatusDisplay();
    } finally {
        if(tunnelModalStartBtn) {
            tunnelModalStartBtn.textContent = 'Start Tunnel';
            tunnelModalStartBtn.disabled = false;
        }
    }
}

/**
 * Handles stopping the tunnel.
 */
async function handleStopTunnel() {
    if(tunnelModalStopBtn) {
        tunnelModalStopBtn.textContent = 'Stopping...';
        tunnelModalStopBtn.disabled = true;
    }
    if(tunnelStatusDisplay) {
        tunnelStatusDisplay.textContent = 'Status: Stopping...';
        tunnelStatusDisplay.className = 'tunnel-status status-starting';
    }
    
    // Always clear any existing polling interval before proceeding
    if (tunnelStatusPollingInterval) {
        clearInterval(tunnelStatusPollingInterval);
        tunnelStatusPollingInterval = null;
        console.log('Tunnel status polling stopped due to tunnel stop request');
    }
    
    try {
        const response = await fetch('/api/tunnel/stop', { method: 'POST' });
        const data = await response.json();

        if (response.ok && data.status === 'success') {
            alert(data.message || 'Tunnel stopped successfully!');
        } else {
            alert(`Error stopping tunnel: ${data.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Failed to stop tunnel:', error);
        alert(`Error stopping tunnel: ${error.toString()}`);
    } finally {
        if(tunnelModalStopBtn) {
            tunnelModalStopBtn.textContent = 'Stop Tunnel';
            tunnelModalStopBtn.disabled = false;
        }
        updateTunnelStatusDisplay(); // Refresh status
    }
}

/**
 * Initializes the tunnel modal event listeners.
 */
function initTunnelModal() {
    // Add inline styles for tunnel URLs if not already in CSS
    const style = document.createElement('style');
    style.textContent = `
        .tunnel-url {
            font-weight: bold;
            color: #0066cc;
            text-decoration: underline;
            transition: all 0.2s ease;
        }
        .tunnel-url:hover {
            color: #004080;
        }
        .cloudflare-url {
            color: #f48120;
        }
        .cloudflare-url:hover {
            color: #bf6012;
        }
        .pinggy-url {
            color: #2fac66;
        }
        .pinggy-url:hover {
            color: #238a4f;
        }
    `;
    document.head.appendChild(style);

    // tunnelToggleBtn is handled by uiController, which will call openTunnelModal
    if (tunnelModalCloseBtn) {
        tunnelModalCloseBtn.addEventListener('click', closeTunnelModal);
    }
    if (tunnelModalStartBtn) {
        tunnelModalStartBtn.addEventListener('click', handleStartTunnel);
    }
    if (tunnelModalStopBtn) {
        tunnelModalStopBtn.addEventListener('click', handleStopTunnel);
    }
    if (tunnelModalSaveSettingsBtn) {
        tunnelModalSaveSettingsBtn.addEventListener('click', handleSaveTunnelSettings);
    }
    if (tunnelProviderSelect) {
        tunnelProviderSelect.addEventListener('change', updatePinggyTokenVisibility);
    }

    // Close tunnel modal if clicking outside the content
    if (tunnelModal) {
        tunnelModal.addEventListener('click', (event) => {
            if (event.target === tunnelModal) {
                closeTunnelModal();
            }
        });
    }
    console.log('Tunnel Modal Initialized');
}

export { initTunnelModal, openTunnelModal }; 