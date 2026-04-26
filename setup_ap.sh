#!/bin/bash
# GhostHub Persistent AP Mode Setup
# This script automatically sets up a persistent Wi-Fi access point
# that survives reboots and handles country code settings automatically

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "[!] This script needs to be run as root. Please use sudo."
    exit 1
fi

echo "===== GHOSTHUB PERSISTENT AP MODE SETUP ====="

# Create log file
LOG_FILE="/var/log/ghosthub-ap-setup.log"
echo "===== SETUP STARTED AT $(date) =====" | tee -a "$LOG_FILE"

# Function to log messages
log() {
    echo "$1" | tee -a "$LOG_FILE"
}

# Configuration variables
SSID="GhostHub"
PASSPHRASE="ghost123"
IP_ADDRESS="192.168.4.1/24"
DHCP_RANGE="192.168.4.2,192.168.4.20,255.255.255.0,24h"
COUNTRY_CODE="US"  # Change this to your country code if needed

# Step 1: Set country code automatically
log "[*] Setting Wi-Fi country code to $COUNTRY_CODE..."

# Set country in wpa_supplicant.conf
if [ -f "/etc/wpa_supplicant/wpa_supplicant.conf" ]; then
    if ! grep -q "country=$COUNTRY_CODE" /etc/wpa_supplicant/wpa_supplicant.conf; then
        sed -i "/update_config=.*/a country=$COUNTRY_CODE" /etc/wpa_supplicant/wpa_supplicant.conf
    fi
else
    cat > /etc/wpa_supplicant/wpa_supplicant.conf <<EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=$COUNTRY_CODE
EOF
fi

# Set country in raspi-config noninteractively
if command -v raspi-config > /dev/null; then
    log "[*] Setting country in raspi-config..."
    raspi-config nonint do_wifi_country $COUNTRY_CODE
fi

# Step 2: Install required packages
log "[*] Installing required packages..."
apt-get update >> "$LOG_FILE" 2>&1
apt-get install -y hostapd dnsmasq netfilter-persistent iptables-persistent rfkill >> "$LOG_FILE" 2>&1

# Step 3: Aggressively unblock Wi-Fi
log "[*] Unblocking Wi-Fi..."
rfkill unblock wifi >> "$LOG_FILE" 2>&1
rfkill unblock wlan >> "$LOG_FILE" 2>&1
rfkill unblock all >> "$LOG_FILE" 2>&1
rfkill list >> "$LOG_FILE" 2>&1

# Step 4: Stop and disable services that might interfere
log "[*] Stopping and disabling conflicting services..."
systemctl stop hostapd >> "$LOG_FILE" 2>&1
systemctl stop dnsmasq >> "$LOG_FILE" 2>&1
systemctl stop wpa_supplicant >> "$LOG_FILE" 2>&1
systemctl disable wpa_supplicant >> "$LOG_FILE" 2>&1

# Step 5: Configure static IP
log "[*] Configuring static IP for wlan0..."
DHCPCD_TMP="$(mktemp)"
if [ -f /etc/dhcpcd.conf ]; then
    awk '
        BEGIN { skip = 0 }
        /^denyinterfaces[[:space:]]+wlan0([[:space:]]|$)/ { next }
        /^interface[[:space:]]+wlan0([[:space:]]|$)/ { skip = 1; next }
        skip && /^interface[[:space:]]+/ { skip = 0 }
        skip { next }
        { print }
        END {
            print ""
            print "interface wlan0"
            print "    static ip_address='"$IP_ADDRESS"'"
            print "    nohook wpa_supplicant"
            print "denyinterfaces wlan0"
        }
    ' /etc/dhcpcd.conf > "$DHCPCD_TMP"
else
    cat > "$DHCPCD_TMP" <<EOF
interface wlan0
    static ip_address=$IP_ADDRESS
    nohook wpa_supplicant
denyinterfaces wlan0
EOF
fi
install -m 644 "$DHCPCD_TMP" /etc/dhcpcd.conf
rm -f "$DHCPCD_TMP"

# Step 6: Reset wlan0 and set IP directly
log "[*] Setting up wlan0 interface..."
ip addr flush dev wlan0 >> "$LOG_FILE" 2>&1
ip link set wlan0 down >> "$LOG_FILE" 2>&1
sleep 2
ip link set wlan0 up >> "$LOG_FILE" 2>&1
sleep 2
ip addr add $IP_ADDRESS dev wlan0 >> "$LOG_FILE" 2>&1

# Step 7: Configure dnsmasq (DHCP server)
log "[*] Configuring DHCP server (dnsmasq)..."
cat > /etc/dnsmasq.conf <<EOF
interface=wlan0
dhcp-range=$DHCP_RANGE
domain=local
address=/ghosthub.local/192.168.4.1
EOF

# Step 8: Configure hostapd (Access Point)
log "[*] Configuring Access Point (hostapd)..."
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSPHRASE
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
country_code=$COUNTRY_CODE
EOF

# Make sure hostapd knows where to find the config file
log "[*] Updating hostapd defaults..."
sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

# Step 9: Enable IP forwarding for routing
log "[*] Enabling IP forwarding..."
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/routed-ap.conf
sysctl -p /etc/sysctl.d/routed-ap.conf >> "$LOG_FILE" 2>&1

# Step 10: Configure NAT
log "[*] Setting up NAT routing..."
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE >> "$LOG_FILE" 2>&1
# Port 80 -> 5000 redirect so http://ghosthub.local works without explicit :5000
iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 2>/dev/null || \
    iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 >> "$LOG_FILE" 2>&1
netfilter-persistent save >> "$LOG_FILE" 2>&1

# Step 11: Create persistent AP fix script
log "[*] Creating persistent AP fix script..."
cat > /usr/local/bin/fix-ap-mode.sh <<'EOF'
#!/bin/bash

# Log file
LOG_FILE="/var/log/ghosthub-ap-fix.log"
TARGET_HOSTNAME="ghosthub"
echo "===== AP MODE FIX RUNNING $(date) =====" >> "$LOG_FILE"

# Repair hostname for stable mDNS advertisement
CURRENT_HOSTNAME="$(hostnamectl --static 2>/dev/null || hostname)"
if [ "$CURRENT_HOSTNAME" != "$TARGET_HOSTNAME" ]; then
    hostnamectl set-hostname "$TARGET_HOSTNAME" >> "$LOG_FILE" 2>&1 || true
fi
if grep -q '^127\.0\.1\.1' /etc/hosts 2>/dev/null; then
    sed -i "s/^127\\.0\\.1\\.1.*/127.0.1.1\t$TARGET_HOSTNAME/" /etc/hosts >> "$LOG_FILE" 2>&1 || true
else
    printf '127.0.1.1\t%s\n' "$TARGET_HOSTNAME" >> /etc/hosts
fi

# Unblock Wi-Fi
rfkill unblock wifi >> "$LOG_FILE" 2>&1
rfkill unblock wlan >> "$LOG_FILE" 2>&1
rfkill unblock all >> "$LOG_FILE" 2>&1

# Reset wlan0
ip link set wlan0 down >> "$LOG_FILE" 2>&1
sleep 2
ip link set wlan0 up >> "$LOG_FILE" 2>&1
sleep 2

# Set IP address
ip addr flush dev wlan0 >> "$LOG_FILE" 2>&1
ip addr add 192.168.4.1/24 dev wlan0 >> "$LOG_FILE" 2>&1

# Restart services
# Check if dhcpcd exists before trying to restart it
if systemctl is-active --quiet dhcpcd 2>/dev/null || systemctl is-enabled --quiet dhcpcd 2>/dev/null; then
    systemctl restart dhcpcd
else
    echo "dhcpcd service not found, skipping restart"
fi >> "$LOG_FILE" 2>&1
systemctl restart hostapd >> "$LOG_FILE" 2>&1
systemctl restart dnsmasq >> "$LOG_FILE" 2>&1
systemctl restart avahi-daemon >> "$LOG_FILE" 2>&1

# Re-assert port 80 -> 5000 redirect so ghosthub.local works without :5000 even if
# /etc/iptables/rules.v4 was lost, flushed, or never saved on this boot.
if ! iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 2>/dev/null; then
    iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 >> "$LOG_FILE" 2>&1 || true
    netfilter-persistent save >> "$LOG_FILE" 2>&1 || true
fi

# Log diagnostics
echo "===== DIAGNOSTICS =====" >> "$LOG_FILE"
rfkill list >> "$LOG_FILE" 2>&1
ip addr show wlan0 >> "$LOG_FILE" 2>&1
systemctl status hostapd --no-pager >> "$LOG_FILE" 2>&1
systemctl status dnsmasq --no-pager >> "$LOG_FILE" 2>&1
echo "===== END DIAGNOSTICS =====" >> "$LOG_FILE"
EOF

chmod +x /usr/local/bin/fix-ap-mode.sh

# Step 12: Create THREE persistent services to ensure AP mode works on boot

# Service 1: Early boot service to unblock Wi-Fi
log "[*] Creating early boot service to unblock Wi-Fi..."
cat > /etc/systemd/system/unblock-wifi.service <<EOF
[Unit]
Description=Unblock Wi-Fi Early in Boot Process
DefaultDependencies=no
Before=basic.target network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock all
ExecStart=/usr/sbin/rfkill unblock wifi
ExecStart=/usr/sbin/rfkill unblock wlan
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
EOF

# Service 2: Main AP fix service
log "[*] Creating main AP fix service..."
cat > /etc/systemd/system/ghosthub-ap-fix.service <<EOF
[Unit]
Description=GhostHub AP Mode Fix
After=network.target unblock-wifi.service
Before=hostapd.service dnsmasq.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fix-ap-mode.sh

[Install]
WantedBy=multi-user.target
EOF

# Service 3: Persistent AP monitor service that runs every minute
log "[*] Creating persistent AP monitor service..."
cat > /etc/systemd/system/ghosthub-ap-monitor.service <<EOF
[Unit]
Description=GhostHub AP Mode Monitor
After=network.target

[Service]
Type=simple
ExecStart=/bin/bash -c '
fail_count=0
while true; do
  ap_ok=true
  hostnamectl --static 2>/dev/null | grep -qx "ghosthub" || hostname | grep -qx "ghosthub" || ap_ok=false
  systemctl is-active --quiet avahi-daemon || ap_ok=false
  ip addr show wlan0 | grep -q "192.168.4.1" || ap_ok=false
  systemctl is-active --quiet hostapd || ap_ok=false
  systemctl is-active --quiet dnsmasq || ap_ok=false

  if [ "$ap_ok" = false ]; then
    fail_count=$((fail_count + 1))
  else
    fail_count=0
  fi

  if [ "$fail_count" -ge 3 ]; then
    /usr/local/bin/fix-ap-mode.sh
    fail_count=0
    sleep 10
  fi

  sleep 20
done'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Step 13: Create boot service for AP fix
log "[*] Creating AP fix boot service..."
cat > /etc/systemd/system/ghosthub-ap-boot.service <<EOF
[Unit]
Description=GhostHub AP Boot Setup
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fix-ap-mode.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Step 14: Enable and start all services
log "[*] Enabling and starting all services..."
systemctl daemon-reload
systemctl enable unblock-wifi.service
systemctl enable ghosthub-ap-fix.service
systemctl enable ghosthub-ap-monitor.service
systemctl enable ghosthub-ap-fix.timer

systemctl start unblock-wifi.service
systemctl start ghosthub-ap-fix.service
systemctl start ghosthub-ap-monitor.service
systemctl start ghosthub-ap-fix.timer

# Step 15: Enable and start AP services
log "[*] Enabling and starting AP services..."
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq
# Check if dhcpcd exists before trying to restart it
if systemctl is-active --quiet dhcpcd 2>/dev/null || systemctl is-enabled --quiet dhcpcd 2>/dev/null; then
    systemctl restart dhcpcd
else
    echo "dhcpcd service not found, skipping restart"
fi
systemctl restart hostapd
systemctl restart dnsmasq

# Step 16: Final diagnostics
log "\n===== FINAL DIAGNOSTICS ====="
log "[*] RF Kill status:"
rfkill list | tee -a "$LOG_FILE"
log "[*] wlan0 status:"
ip addr show wlan0 | tee -a "$LOG_FILE"
log "[*] hostapd status:"
systemctl status hostapd --no-pager | tee -a "$LOG_FILE"
log "[*] dnsmasq status:"
systemctl status dnsmasq --no-pager | tee -a "$LOG_FILE"

log "\n===== SETUP COMPLETE ====="
log "✅ Your Raspberry Pi should now be broadcasting the Wi-Fi network:"
log "   SSID: $SSID"
log "   Password: $PASSPHRASE"
log "   IP Address: 192.168.4.1"
log "\nTo connect to GhostHub:"
log "1. Connect to the '$SSID' Wi-Fi network using the password"
log "2. Open http://192.168.4.1:5000 or http://ghosthub.local:5000 in your browser"
log "\nThis setup includes multiple persistent services that will:"
log "- Unblock Wi-Fi early in the boot process"
log "- Fix AP mode on boot"
log "- Monitor and repair AP mode every minute"
log "- Run a complete AP fix every 5 minutes"
log "\nLog files:"
log "- Setup log: $LOG_FILE"
log "- Runtime log: /var/log/ghosthub-ap-fix.log"

echo "\n***************************************************************"
echo "✅ Setup complete!"
echo "→ Wi-Fi SSID: $SSID (Password: $PASSPHRASE)"
echo "→ Visit http://192.168.4.1:5000 or http://ghosthub.local:5000"
echo "→ AP mode will be maintained automatically on boot"
echo "***************************************************************"
