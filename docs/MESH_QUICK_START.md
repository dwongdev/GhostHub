# Secure Mesh Quick Start Guide

GhostHub can use Headscale and Tailscale to create an optional secure mesh for remote access without exposing the app directly to the public internet.

## Expected Behavior

- Mesh setup usually takes 30-60 seconds on Raspberry Pi hardware.
- Preauth key generation may retry while Headscale finishes starting.
- GhostHub verifies the Pi receives a Tailscale IP before reporting the mesh as ready.

## How to Use Secure Mesh

### Step 1: Start Mesh (Admin Panel)
1. Open the GhostHub admin panel
2. Go to **Remote Access** section
3. Click **"Start Secure Mesh"**
4. Wait 30-60 seconds for setup to complete

### Step 2: Connect Client Device

The Remote Access modal shows device-specific instructions. Use those values first; the examples below show the shape of the commands.

#### Windows

1. Install Tailscale from `https://tailscale.com/download`.
2. Open PowerShell. If Tailscale asks for elevation, use an Administrator PowerShell.
3. Run the join command shown in GhostHub:

   ```powershell
   tailscale up --login-server http://YOUR_PI_IP:8080 --authkey YOUR_KEY --hostname my-windows-pc --accept-routes --accept-dns
   ```

4. Open `http://ghosthub.mesh.local:5000`.

#### macOS or Linux

1. Install Tailscale from `https://tailscale.com/download`.
2. Open Terminal.
3. Run the join command shown in GhostHub:

   ```bash
   tailscale up --login-server http://YOUR_PI_IP:8080 --authkey YOUR_KEY --hostname my-device --accept-routes --accept-dns
   ```

   On Linux, run the command with `sudo` if your Tailscale install requires it.

4. Open `http://ghosthub.mesh.local:5000`.

#### iPhone, iPad, or Android

1. Install the Tailscale app.
2. In the Tailscale app settings, add the custom server URL shown in GhostHub.
3. If the app shows a `nodekey:...` registration value, copy it.
4. Paste the node key into GhostHub Remote Access and choose Register Device.
5. Open `http://ghosthub.mesh.local:5000`.

### Step 3: Verify Connection
On Windows PowerShell:

```powershell
tailscale status
ping ghosthub.mesh.local
curl.exe http://ghosthub.mesh.local:5000
```

On macOS or Linux:

```bash
tailscale status
ping ghosthub.mesh.local
curl http://ghosthub.mesh.local:5000
```

## Troubleshooting Quick Fixes

### Pi Won't Join Mesh

Run these Linux commands on the Pi:

```bash
sudo tailscale logout
sudo systemctl restart ghosthub-headscale
```

### Client Can't Connect

On Windows PowerShell:

```powershell
tailscale logout
tailscale up --login-server http://YOUR_PI_IP:8080 --authkey NEW_KEY --force-reauth
```

On macOS or Linux:

```bash
tailscale logout
tailscale up --login-server http://YOUR_PI_IP:8080 --authkey NEW_KEY --force-reauth
```

On Linux, run the `tailscale` commands with `sudo` if your install requires it.

### ghosthub.mesh.local Not Resolving
DNS updates automatically every 30 seconds. Just wait a moment and try again. If still not working, restart mesh from admin panel.

## What to Expect in Logs

### Normal Startup Sequence
```
[INFO] Waiting for Headscale to start...
[INFO] Headscale started after 8s
[INFO] Waiting for Headscale to fully initialize...
[INFO] Creating default user...
[INFO] Attempting to join Pi to mesh network...
[INFO] Clearing Tailscale auth state before joining mesh
[INFO] Waiting for Headscale API to be ready...
[INFO] Headscale API ready after 3s
[INFO] Preauth key generated successfully on attempt 1
[INFO] Joining Pi to mesh at http://192.168.x.x:8080
[INFO] Tailscale up command succeeded
[INFO] Verifying mesh connectivity...
[INFO] Pi successfully joined mesh network with IP: 100.x.x.x
[INFO] DNS updated successfully - ghosthub.mesh.local is ready
```

### Warning Signs (But May Recover)
```
[WARNING] Preauth key generation attempt 1/5 failed, retrying in 1s...
[WARNING] Tailscale state is Running but no IP assigned
[WARNING] Headscale API not responding, attempting preauth key generation anyway...
```

### Actual Errors (Need Attention)
```
[ERROR] Failed to generate preauth key for Pi to join mesh after 5 attempts
[ERROR] Tailscale up succeeded but Pi did not receive an IP address
[ERROR] Failed to join mesh. Return code: 1
```

## Performance Tips

### On Raspberry Pi 4 (2GB RAM)
- First mesh start: 45-60 seconds
- Subsequent starts: 30-45 seconds
- Client connection: 10-20 seconds

### On Raspberry Pi 5
- First mesh start: 30-40 seconds
- Subsequent starts: 20-30 seconds
- Client connection: 5-10 seconds

## Common Questions

**Q: Why does it take so long to start?**  
A: Headscale needs to initialize database, generate keys, and establish DERP relay connections. This is normal on Pi hardware.

**Q: Why multiple preauth key retries?**  
A: The Headscale API needs time to be fully ready after service start. Retries with exponential backoff ensure success.

**Q: What if I see "NeedsLogin" state?**  
A: The new code automatically clears this by running `tailscale logout` before joining. If it persists, manually logout and restart mesh.

**Q: Can I use this over the internet?**  
A: Yes! Tailscale handles NAT traversal automatically via DERP relays. No port forwarding needed.

**Q: How many devices can connect?**  
A: Unlimited. Each device gets its own preauth key and joins the mesh independently.

**Q: Is it secure?**  
A: Yes. Uses WireGuard encryption, preauth keys expire after 24h, and only Tailscale IPs can access GhostHub.

## Admin Panel Features

### Mesh Status Panel
- **Server URL**: Headscale coordination server address
- **App URL**: Always `http://ghosthub.mesh.local:5000` (works on mesh)
- **Connected Devices**: Shows online devices with IPs
- **All Devices**: Shows all registered devices (including offline)

### Available Actions
- **Generate New Key**: Create preauth key for new device
- **Register Device**: Manually register device with node key
- **Update DNS**: Force DNS record update for ghosthub.mesh.local
- **Remove Device**: Disconnect and delete device from mesh
- **Stop Mesh**: Shutdown Headscale and disconnect all devices

## Next Steps

1. Start mesh from the admin panel and watch the status log.
2. Connect a device with the Tailscale app or manual registration.
3. Verify remote access at `http://ghosthub.mesh.local:5000`.
4. If issues occur, see `SECURE_MESH_TROUBLESHOOTING.md`.

## Need Help?

See detailed troubleshooting guide: `docs/SECURE_MESH_TROUBLESHOOTING.md`
