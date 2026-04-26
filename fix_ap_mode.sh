#!/bin/bash
set -e

# ==== CONFIGURATION ====
SSID="GhostHub"
PASSPHRASE="ghost123"
IP_ADDRESS="192.168.4.1/24"
DHCP_RANGE="192.168.4.2,192.168.4.20,255.255.255.0,24h"
TARGET_HOSTNAME="ghosthub"
LOG_FILE="/var/log/ghosthub-ap-fix.log"

# ==== LOG ROTATION ====
MAX_LOG_SIZE=100000  # ~100KB
if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE") -gt $MAX_LOG_SIZE ]; then
    mv "$LOG_FILE" "$LOG_FILE.old"
    touch "$LOG_FILE"
fi

# ==== LOGGING FUNCTION ====
log() {
    echo "$1" | tee -a "$LOG_FILE"
}

log "===== GHOSTHUB ACCESS POINT FIX - $(date) ====="

# ==== ROOT CHECK ====
if [ "$(id -u)" -ne 0 ]; then
    log "[!] This script must be run as root."
    exit 1
fi

# ==== UNBLOCK WIFI ====
log "[*] Unblocking Wi-Fi and bringing up wlan0..."
systemctl stop wpa_supplicant || true
systemctl disable wpa_supplicant || true
rfkill unblock all
ip link set wlan0 down || true
sleep 1
ip link set wlan0 up || true
sleep 1

# ==== USB AUTO-MOUNT ====
log "[*] Setting up USB auto-mounting..."
mkdir -p /media/usb && chmod 777 /media/usb
apt-get install -y udevil udisks2 >> "$LOG_FILE" 2>&1 || true

# udev rules and mount script
cat > /usr/local/bin/ap-usb-mount.sh <<'EOF'
#!/bin/bash
ACTION=$1
DEVNAME=$2
if [ "$ACTION" = "add" ] && [ -n "$DEVNAME" ]; then
    LABEL=$(blkid -s LABEL -o value "/dev/$DEVNAME" 2>/dev/null)
    if [ -z "$LABEL" ]; then
        UUID=$(blkid -s UUID -o value "/dev/$DEVNAME" 2>/dev/null)
        if [ -n "$UUID" ]; then
            LABEL="USB-${UUID:0:4}"
        fi
    fi
    [ -z "$LABEL" ] && LABEL=$DEVNAME
    LABEL=$(echo "$LABEL" | tr ' ' '_' | tr -cd '[:alnum:]_-')
    [ -z "$LABEL" ] && LABEL=$DEVNAME
    mkdir -p "/media/usb/$LABEL"
    mount -o uid=pi,gid=pi "/dev/$DEVNAME" "/media/usb/$LABEL" || true
elif [ "$ACTION" = "remove" ]; then
    for dir in /media/usb/*; do
        [ -d "$dir" ] || continue
        if mountpoint -q "$dir"; then
            SRC=$(findmnt -n -o SOURCE --target "$dir" 2>/dev/null)
            if [ -n "$SRC" ] && [[ "$SRC" == /dev/* ]] && [ ! -e "$SRC" ]; then
                umount -l "$dir" 2>/dev/null && rmdir "$dir" 2>/dev/null
            fi
        else
            rmdir "$dir" 2>/dev/null
        fi
    done
fi
EOF
chmod +x /usr/local/bin/ap-usb-mount.sh

cat > /etc/udev/rules.d/99-usb-auto-mount.rules <<'EOF'
ACTION=="add", KERNEL=="sd*[0-9]*", RUN+="/usr/local/bin/ap-usb-mount.sh add %k"
ACTION=="remove", KERNEL=="sd*[0-9]*", RUN+="/usr/local/bin/ap-usb-mount.sh remove %k"
EOF
udevadm control --reload-rules && udevadm trigger

# mount existing
for dev in /dev/sd*[0-9]*; do
    [ -e "$dev" ] || continue
    log "[*] Mounting USB: $dev"
    
    LABEL=$(blkid -s LABEL -o value "$dev" 2>/dev/null)
    if [ -z "$LABEL" ]; then
        UUID=$(blkid -s UUID -o value "$dev" 2>/dev/null)
        if [ -n "$UUID" ]; then
            LABEL="USB-${UUID:0:4}"
        fi
    fi
    [ -z "$LABEL" ] && LABEL=$(basename "$dev")
    # Sanitize
    LABEL=$(echo "$LABEL" | tr ' ' '_' | tr -cd '[:alnum:]_-')
    [ -z "$LABEL" ] && LABEL=$(basename "$dev")
    
    mkdir -p "/media/usb/$LABEL"
    mount -o uid=pi,gid=pi "$dev" "/media/usb/$LABEL" || true
done

# ==== NETWORK CONFIG ====
log "[*] Repairing hostname for ghosthub.local..."
CURRENT_HOSTNAME="$(hostnamectl --static 2>/dev/null || hostname)"
if [ "$CURRENT_HOSTNAME" != "$TARGET_HOSTNAME" ]; then
    hostnamectl set-hostname "$TARGET_HOSTNAME" || true
fi
if grep -q '^127\.0\.1\.1' /etc/hosts 2>/dev/null; then
    sed -i "s/^127\\.0\\.1\\.1.*/127.0.1.1\t$TARGET_HOSTNAME/" /etc/hosts || true
else
    printf '127.0.1.1\t%s\n' "$TARGET_HOSTNAME" >> /etc/hosts
fi

log "[*] Configuring static IP for wlan0..."
DHCPCD_TMP="$(mktemp)"
if [ -f "/etc/dhcpcd.conf" ]; then
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
systemctl restart dhcpcd || true
ip addr flush dev wlan0
ip addr add $IP_ADDRESS dev wlan0 || true

# ==== DHCP CONFIG ====
log "[*] Configuring dnsmasq..."
cp /etc/dnsmasq.conf /etc/dnsmasq.conf.bak 2>/dev/null || true
cat > /etc/dnsmasq.conf <<EOF
interface=wlan0
dhcp-range=$DHCP_RANGE
domain=local
address=/ghosthub.local/192.168.4.1
EOF

# ==== HOSTAPD CONFIG ====
log "[*] Configuring hostapd..."
cp /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.bak 2>/dev/null || true
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
country_code=US
EOF
sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

# ==== NAT ====
log "[*] Enabling IP forwarding and NAT..."
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/routed-ap.conf
sysctl -p /etc/sysctl.d/routed-ap.conf
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE || true
netfilter-persistent save

# ==== SERVICE START ====
log "[*] Enabling and starting hostapd, dnsmasq, avahi..."
systemctl unmask hostapd
systemctl enable hostapd dnsmasq avahi-daemon
systemctl restart hostapd dnsmasq avahi-daemon

# ==== OPTIONAL: Port forward 80 to 5000 ====
iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 2>/dev/null || \
    iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 || true
netfilter-persistent save

# ==== AUTO-REPAIR TIMER ====
log "[*] Creating watchdog timer..."
cat > /etc/systemd/system/ghosthub-ap-repair.timer <<EOF
[Unit]
Description=Auto-heal AP Mode every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/ghosthub-ap-repair.service <<EOF
[Unit]
Description=GhostHub AP Mode Auto-Heal

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ghosthub-ap-fix.sh
EOF

chmod +x /usr/local/bin/ghosthub-ap-fix.sh
systemctl daemon-reload
systemctl enable ghosthub-ap-repair.timer
systemctl start ghosthub-ap-repair.timer

log ""
log "===== AP SETUP COMPLETE ====="
log "✅ SSID: $SSID"
log "🔑 Password: $PASSPHRASE"
log "🌐 http://192.168.4.1 or http://ghosthub.local"
log "📦 USB auto-mount ready"
log "🛠 Self-healing service enabled"
log "========================================="
