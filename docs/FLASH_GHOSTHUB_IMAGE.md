# Flash The GhostHub Image

Use this path when you want the fastest setup: flash the maintainer-provided GhostHub SD card image, boot the Pi, and start using GhostHub.

This image is prepared and uploaded separately by the maintainer. It is not produced by `scripts/ghostpack.py` and is not attached by the GitHub release workflow.

## Requirements

- Raspberry Pi 4
- microSD card
- Raspberry Pi Imager or balenaEtcher
- USB drive with photos/videos
- Optional HDMI display for TV/kiosk mode

## Flash

1. Download the ready-to-flash GhostHub image from the project download page or announcement post.
2. Open Raspberry Pi Imager or balenaEtcher.
3. Select the downloaded GhostHub image.
4. Select the microSD card.
5. Flash and eject the card.
6. Insert the card into the Pi and boot.

## First Boot

On first boot, GhostHub starts its local service and access point.

```text
SSID: GhostHub
Password: ghost123
URL: http://ghosthub.local
Fallback URL: http://192.168.4.1
```

If the Pi is connected to Ethernet or another configured network, you can also open:

```text
http://<pi-ip-address>:5000
```

## Add Media

Plug in a USB drive. Folders become GhostHub categories. Large libraries may take a few minutes to index and generate thumbnails, but browsing can begin while background work continues.

## Updates

Use the admin update controls in GhostHub. Updates come from GitHub Releases and preserve local runtime state such as `instance/`, the virtual environment, Headscale data, and Cloudflared data.

## Customizing The Image

If you want to build from source or prepare your own SD card image, use [DIY Install](DIY_INSTALL.md).
