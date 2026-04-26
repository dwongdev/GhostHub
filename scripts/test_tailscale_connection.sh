#!/bin/bash
# Test Tailscale Connection Script
# Run this on the Pi to debug remote access issues

echo "=== GhostHub Tailscale Connection Test ==="
echo ""

# 1. Check if Tailscale is running
echo "1. Checking Tailscale status..."
if systemctl is-active --quiet tailscaled; then
    echo "   ✓ Tailscale daemon is running"
else
    echo "   ✗ Tailscale daemon is NOT running"
    echo "   Run: sudo systemctl start tailscaled"
fi

# 2. Get Tailscale IP
echo ""
echo "2. Getting Tailscale IP address..."
TS_IP=$(tailscale ip -4 2>/dev/null)
if [ -n "$TS_IP" ]; then
    echo "   ✓ Tailscale IP: $TS_IP"
else
    echo "   ✗ No Tailscale IP assigned"
    echo "   Pi may not be connected to mesh"
fi

# 3. Check if GhostHub is listening on port 5000
echo ""
echo "3. Checking if GhostHub is listening on port 5000..."
if netstat -tuln 2>/dev/null | grep -q ":5000"; then
    LISTEN_ADDR=$(netstat -tuln 2>/dev/null | grep ":5000" | awk '{print $4}')
    echo "   ✓ GhostHub is listening on: $LISTEN_ADDR"
    if echo "$LISTEN_ADDR" | grep -q "0.0.0.0:5000"; then
        echo "   ✓ Binding to all interfaces (correct)"
    else
        echo "   ⚠ Not binding to all interfaces - may not be accessible via Tailscale"
    fi
else
    echo "   ✗ GhostHub is NOT listening on port 5000"
    echo "   Check if GhostHub is running"
fi

# 4. Check firewall rules
echo ""
echo "4. Checking firewall rules for Tailscale..."
if sudo iptables -L INPUT -n | grep -q "tailscale0.*dpt:5000"; then
    echo "   ✓ Firewall allows Tailscale traffic to port 5000"
else
    echo "   ✗ No firewall rule for Tailscale traffic"
    echo "   Run: sudo iptables -I INPUT 1 -i tailscale0 -p tcp --dport 5000 -j ACCEPT"
fi

# 5. Test local access
echo ""
echo "5. Testing local access to GhostHub..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 | grep -q "200\|302"; then
    echo "   ✓ GhostHub responds on localhost"
else
    echo "   ✗ GhostHub does NOT respond on localhost"
fi

# 6. Test Tailscale IP access
if [ -n "$TS_IP" ]; then
    echo ""
    echo "6. Testing access via Tailscale IP..."
    if curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://$TS_IP:5000 | grep -q "200\|302"; then
        echo "   ✓ GhostHub responds on Tailscale IP ($TS_IP)"
    else
        echo "   ✗ GhostHub does NOT respond on Tailscale IP"
        echo "   This is the problem - firewall or binding issue"
    fi
fi

# 7. Check Headscale status
echo ""
echo "7. Checking Headscale status..."
if systemctl is-active --quiet ghosthub-headscale; then
    echo "   ✓ Headscale is running"
else
    echo "   ✗ Headscale is NOT running"
fi

# 8. List connected nodes
echo ""
echo "8. Connected Tailscale nodes:"
tailscale status 2>/dev/null || echo "   Could not get Tailscale status"

echo ""
echo "=== Test Complete ==="
echo ""
echo "REMOTE ACCESS CHECKLIST:"
echo "1. Tailscale daemon running: $(systemctl is-active --quiet tailscaled && echo '✓' || echo '✗')"
echo "2. Pi has Tailscale IP: $([ -n "$TS_IP" ] && echo '✓' || echo '✗')"
echo "3. GhostHub listening on 0.0.0.0:5000: $(netstat -tuln 2>/dev/null | grep -q '0.0.0.0:5000' && echo '✓' || echo '✗')"
echo "4. Firewall allows Tailscale: $(sudo iptables -L INPUT -n | grep -q 'tailscale0.*dpt:5000' && echo '✓' || echo '✗')"
echo ""
echo "To access from remote device:"
echo "  - URL: http://ghosthub.mesh.local:5000"
echo "  - Or:  http://$TS_IP:5000"
