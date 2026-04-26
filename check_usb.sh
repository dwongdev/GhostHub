#!/bin/bash
# Basic USB detection and mounting script

echo "===== USB DETECTION SCRIPT ====="

# Check if USB devices are connected
echo "[*] Checking USB devices..."
lsusb
echo ""

# Check kernel messages for USB detection
echo "[*] Checking kernel messages for USB storage devices..."
dmesg | grep -i usb | tail -10
echo ""

# List all block devices
echo "[*] Available block devices:"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE
echo ""

# Check if any storage devices are detected but not mounted
echo "[*] Checking for unmounted storage devices..."
UNMOUNTED=$(lsblk -o NAME,MOUNTPOINT | grep -v "/" | grep "sd" | grep -v "MOUNTPOINT" | awk '{print $1}')

if [ -z "$UNMOUNTED" ]; then
    echo "[!] No unmounted storage devices found."
else
    echo "[*] Found unmounted devices: $UNMOUNTED"
    
    # Try to mount each device
    for DEVICE in $UNMOUNTED; do
        echo "[*] Attempting to mount /dev/$DEVICE..."
        
        # Create mount point
        LABEL=$(blkid -s LABEL -o value "/dev/$DEVICE" 2>/dev/null)
        if [ -z "$LABEL" ]; then
            UUID=$(blkid -s UUID -o value "/dev/$DEVICE" 2>/dev/null)
            if [ -n "$UUID" ]; then
                LABEL="USB-${UUID:0:4}"
            fi
        fi
        [ -z "$LABEL" ] && LABEL="$DEVICE"
        LABEL=$(echo "$LABEL" | tr ' ' '_' | tr -cd '[:alnum:]_-')
        [ -z "$LABEL" ] && LABEL="$DEVICE"
        
        MOUNT_POINT="/media/usb/$LABEL"
        sudo mkdir -p $MOUNT_POINT
        sudo chmod 777 $MOUNT_POINT
        
        # Try to mount
        sudo mount /dev/$DEVICE $MOUNT_POINT
        
        if [ $? -eq 0 ]; then
            echo "[✓] Successfully mounted /dev/$DEVICE to $MOUNT_POINT"
            echo "    Contents:"
            ls -la $MOUNT_POINT
        else
            echo "[!] Failed to auto-mount. Trying specific filesystems..."
            
            # Try with specific filesystem types
            for FS in vfat ntfs exfat ext4 ext3 ext2; do
                echo "[*] Trying to mount as $FS..."
                sudo mount -t $FS /dev/$DEVICE $MOUNT_POINT 2>/dev/null
                
                if [ $? -eq 0 ]; then
                    echo "[✓] Successfully mounted /dev/$DEVICE as $FS to $MOUNT_POINT"
                    echo "    Contents:"
                    ls -la $MOUNT_POINT
                    break
                fi
            done
        fi
    done
fi

echo ""
echo "[*] Currently mounted filesystems:"
mount | grep -E '/dev/sd|/media'
echo ""

echo "===== DONE ====="
echo "If your USB drive was mounted, restart GhostHub:"
echo "sudo systemctl restart ghosthub"
