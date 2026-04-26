# Secure Mesh Troubleshooting Guide

## Overview
This guide helps diagnose and fix issues with GhostHub's Secure Mesh (Headscale + Tailscale) remote access feature.

## Runtime Expectations

- Headscale startup wait: up to 60 seconds
- API readiness check: short polling window before preauth key generation
- Preauth retries: exponential backoff across multiple attempts
- IP verification: up to 30 seconds for Tailscale IP assignment
- Tailscale join timeout: long enough for Raspberry Pi hardware and slow networks

## Common Issues & Solutions

### Issue 1: Pi Fails to Join Mesh
**Symptoms:**
- Headscale starts successfully
- Pi shows "Failed to join mesh network" in logs
- Remote access doesn't work

**Diagnosis:**
```bash
# Check Headscale status
sudo systemctl status ghosthub-headscale

# Check Tailscale status on Pi
sudo tailscale status

# Check for Tailscale IP
tailscale ip -4

# View Headscale logs
tail -f ~/ghosthub/instance/headscale/headscale.log
```

**Solutions:**
1. **Stale Tailscale state**: Manually logout and retry
   ```bash
   sudo tailscale logout
   sudo systemctl restart ghosthub-headscale
   ```

2. **Firewall blocking**: Ensure iptables rules are set
   ```bash
   sudo iptables -L INPUT -n | grep tailscale
   sudo iptables -L INPUT -n | grep 100.64.0.0
   ```

3. **Headscale not ready**: Check if API is responding
   ```bash
   ~/ghosthub/headscale users list --config ~/ghosthub/instance/headscale/config.yaml
   ```

### Issue 2: "NeedsLogin" State
**Symptoms:**
- Tailscale shows "NeedsLogin" state
- Pi can't get Tailscale IP

**Solution:**
The new code always runs `tailscale logout` before joining. If still stuck:
```bash
# Force logout and clear state
sudo tailscale logout
sudo rm -rf /var/lib/tailscale/*
sudo systemctl restart ghosthub-headscale
```

### Issue 3: Preauth Key Generation Fails
**Symptoms:**
- Logs show "Failed to generate preauth key after 5 attempts"
- Headscale is running but API not responding

**Diagnosis:**
```bash
# Test Headscale API manually
~/ghosthub/headscale users list --config ~/ghosthub/instance/headscale/config.yaml

# Check socket permissions
ls -la /var/run/headscale/headscale.sock

# Check database
ls -la /var/lib/headscale/db.sqlite
```

**Solutions:**
1. **Socket permission issue**:
   ```bash
   sudo chown -R ghost:ghost /var/run/headscale
   sudo chmod 755 /var/run/headscale
   ```

2. **Database corruption**:
   ```bash
   sudo systemctl stop ghosthub-headscale
   sudo rm /var/lib/headscale/db.sqlite*
   sudo systemctl start ghosthub-headscale
   ```

### Issue 4: Pi Gets No Tailscale IP
**Symptoms:**
- `tailscale up` succeeds (return code 0)
- But `tailscale ip -4` returns nothing
- Verification loop times out

**Diagnosis:**
```bash
# Check Tailscale backend state
sudo tailscale status --json | grep BackendState

# Check for DERP connectivity
sudo tailscale netcheck

# View Tailscale logs
sudo journalctl -u tailscaled -n 50
```

**Solutions:**
1. **DERP relay issues**: Restart Tailscale daemon
   ```bash
   sudo systemctl restart tailscaled
   sudo tailscale up --login-server http://YOUR_PI_IP:8080 --authkey YOUR_KEY --hostname ghosthub --force-reauth
   ```

2. **Network interface issues**: Check if tailscale0 exists
   ```bash
   ip addr show tailscale0
   ```

### Issue 5: DNS Not Resolving ghosthub.mesh.local
**Symptoms:**
- Pi is connected to mesh with IP
- But `ghosthub.mesh.local` doesn't resolve on client devices

**Diagnosis:**
```bash
# Check DNS records in Headscale config
grep -A 5 "extra_records" ~/ghosthub/instance/headscale/config.yaml

# Check Pi's Tailscale IP
tailscale ip -4

# Test DNS from client
nslookup ghosthub.mesh.local
```

**Solutions:**
1. **Wait for automatic update**: DNS updates every 30 seconds automatically when mesh is active

2. **Verify DNS config**:
   ```yaml
   dns_config:
     magic_dns: true
     base_domain: "tail.local"
     extra_records:
       - name: "ghosthub.mesh.local"
         type: "A"
         value: "100.x.x.x"  # Should match Pi's Tailscale IP
   ```

## Verification Steps

### 1. Verify Headscale is Running
```bash
# Should show "active (running)"
sudo systemctl status ghosthub-headscale

# Should return port 8080 open
nc -zv 127.0.0.1 8080
```

### 2. Verify Pi Joined Mesh
```bash
# Should show "Running" state
sudo tailscale status

# Should return 100.x.x.x IP
tailscale ip -4

# Should list ghosthub node
~/ghosthub/headscale nodes list --config ~/ghosthub/instance/headscale/config.yaml
```

### 3. Verify Client Can Connect
```bash
# On client device with Tailscale installed:
tailscale logout
tailscale up --login-server http://YOUR_PI_IP:8080 --authkey NEW_KEY --force-reauth

# Should show ghosthub node
tailscale status

# Should resolve to Pi's Tailscale IP
ping ghosthub.mesh.local

# Should access GhostHub
curl http://ghosthub.mesh.local:5000
```

## Log Locations

- **Headscale logs**: `~/ghosthub/instance/headscale/headscale.log`
- **Systemd logs**: `sudo journalctl -u ghosthub-headscale -n 100`
- **Tailscale logs**: `sudo journalctl -u tailscaled -n 100`
- **GhostHub logs**: Check Flask app logs

## Performance Expectations

### Startup Times (on Raspberry Pi 4)
- Headscale service start: 5-15 seconds
- API readiness: 5-10 seconds
- Preauth key generation: 1-5 seconds
- Tailscale up: 10-20 seconds
- IP assignment: 5-15 seconds
- **Total mesh setup time**: 30-60 seconds

### What's Normal
- Multiple preauth key retry attempts (1-2 retries is normal)
- 10-20 second wait for Tailscale IP
- 5-10 second API readiness wait

### What's Not Normal
- Headscale failing to start after 60s
- All 5 preauth key attempts failing
- No Tailscale IP after 30s verification loop
- Constant "NeedsLogin" state after logout

## Advanced Debugging

### Enable Verbose Logging
```bash
# Edit systemd service to add debug flag
sudo systemctl edit ghosthub-headscale

# Add:
[Service]
ExecStart=
ExecStart=/path/to/headscale serve --config /path/to/config.yaml --debug

sudo systemctl daemon-reload
sudo systemctl restart ghosthub-headscale
```

### Monitor Real-time Logs
```bash
# Terminal 1: Headscale logs
tail -f ~/ghosthub/instance/headscale/headscale.log

# Terminal 2: Tailscale logs
sudo journalctl -u tailscaled -f

# Terminal 3: GhostHub logs
# (depends on your deployment)
```

### Network Diagnostics
```bash
# Check if Headscale port is accessible
curl http://YOUR_PI_IP:8080/health

# Check DERP connectivity
sudo tailscale netcheck

# Check firewall rules
sudo iptables -L -n -v | grep -E "tailscale|100.64"

# Check routing
ip route show table 52
```

## Getting Help

If issues persist after trying these solutions:

1. **Collect logs**:
   ```bash
   # Create debug bundle
   sudo journalctl -u ghosthub-headscale -n 200 > headscale.log
   sudo journalctl -u tailscaled -n 200 > tailscale.log
   sudo tailscale status --json > tailscale-status.json
   ~/ghosthub/headscale nodes list --config ~/ghosthub/instance/headscale/config.yaml > nodes.txt
   ```

2. **Check configuration**:
   ```bash
   cat ~/ghosthub/instance/headscale/config.yaml
   ```

3. **Verify versions**:
   ```bash
   ~/ghosthub/headscale version
   tailscale version
   ```

## Quick Reset (Nuclear Option)

If everything is broken and you want to start fresh:

```bash
# Stop services
sudo systemctl stop ghosthub-headscale
sudo tailscale logout

# Clear all state
sudo rm -rf ~/ghosthub/instance/headscale/*
sudo rm -rf /var/lib/headscale/*
sudo rm -rf /var/run/headscale/*
sudo rm -rf /var/lib/tailscale/*

# Restart GhostHub (will regenerate everything)
sudo systemctl restart ghosthub

# Or manually start mesh from admin panel
```

## Security Notes

- **Preauth keys**: Expire after 24 hours (configurable)
- **Reusable keys**: Enabled for easier device onboarding
- **Firewall**: Only Tailscale interface (100.64.0.0/10) has access
- **DNS**: MagicDNS enabled for automatic hostname resolution
- **DERP relays**: Uses Tailscale's public DERP servers for NAT traversal

## Related Files

- `app/services/system/headscale/runtime_service.py` - Headscale bootstrap, process control, DNS sync, and Tailscale connectivity
- `app/services/system/headscale/config_service.py` - Headscale config generation, path setup, and systemd setup
- `app/services/system/headscale/connectivity_service.py` - Mesh join flow, DNS update, and Tailscale connectivity checks
- `app/services/system/headscale/bootstrap_service.py` - Database reset validation and instance writeability prep
- `app/services/system/headscale/network_service.py` - Firewall rule setup for GhostHub over Tailscale
- `app/services/system/headscale/process_service.py` - systemctl lifecycle, readiness wait, log-tail, and default-user setup
- `app/services/system/headscale/access_service.py` - Headscale node, preauth, registration, and QR behavior
- `app/services/system/tunnel/mesh_service.py` - Mesh lifecycle and recovery orchestration
- `app/services/system/tunnel/provider_service.py` - Cloudflare/Pinggy tunnel process management
- `app/controllers/system/` and `app/controllers/admin/` - API endpoints
- `static/js/modules/config/tunnelModal.js` - Frontend UI
