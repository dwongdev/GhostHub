# Quick Start

This is the fastest path to a working GhostHub.

## Supported Hardware And OS

GhostHub's Pi install path targets:

```text
Hardware: Raspberry Pi 4
OS image: 2022-01-28-raspios-bullseye-armhf-lite
```

It is not currently documented as compatible with arbitrary Raspberry Pi OS images.

## Option 1: Flash The GhostHub Image

Use this if you have a fresh microSD card and want GhostHub ready immediately.

1. Download the ready-to-flash GhostHub image from the project download page or announcement post.
2. Flash it with Raspberry Pi Imager or balenaEtcher.
3. Insert the card into the Pi and boot.
4. Connect to the `GhostHub` Wi-Fi network.
5. Open `http://ghosthub.local` or `http://192.168.4.1`.

Default access-point settings:

```text
SSID: GhostHub
Password: ghost123
```

Plug in a USB drive with photos or videos. GhostHub discovers folders as categories and starts thumbnail/index work in the background.

Full guide: [Flash The GhostHub Image](FLASH_GHOSTHUB_IMAGE.md).

## Option 2: Install From GitHub Releases

Download the clean supported OS image from Raspberry Pi's official archive:

```text
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip
```

Optional checksum file:

```text
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip.sha256
```

Flash with Raspberry Pi Imager v1.8.5. Before writing the card, open advanced options and set:

```text
Hostname: ghosthub
Username: ghost
Enable SSH: yes
Password: choose your own
Wi-Fi: optional, only needed if you are not using Ethernet
```

Boot the Pi, wait for it to join the network, then SSH in. This path runs the release installer directly on the Pi:

```bash
ssh ghost@ghosthub.local
```

If mDNS is not resolving yet, use the Pi's IP address:

```bash
ssh ghost@<pi-ip-address>
```

If SSH refuses to connect with a host key warning, your computer may have an old key cached for `ghosthub.local` or that IP. Refresh it:

```bash
ssh-keygen -R ghosthub.local
ssh-keygen -R <pi-ip-address>
```

Then run:

```bash
curl -L -o install_ghosthub.sh \
  https://github.com/BleedingXiko/GhostHub/releases/latest/download/install_ghosthub.sh
chmod +x install_ghosthub.sh
sudo ./install_ghosthub.sh
```

Full DIY guide: [DIY Install](DIY_INSTALL.md).

## Option 2B: Deploy Local Source With The CLI

Use this if you cloned the repository on your computer and want the deploy CLI to build, upload, SSH, and install for you.

First flash the supported OS exactly as described above with:

```text
Hostname: ghosthub
Username: ghost
Enable SSH: yes
```

On your computer, install these local build prerequisites:

```text
Python 3.9
Node.js/npm
```

The deploy CLI creates `venv/`, installs Python requirements, installs `static/js` dependencies, builds the release ZIP, uploads it, and runs the Pi installer.

Do not SSH into the Pi for this path. Run the CLI from the repository root on your computer:

```bash
./scripts/deploy_to_pi.sh
```

The script walks you through the deployment mode and asks for the Pi password if needed.

Deployment modes:

- `Standard`: fresh local install from this repo.
- `Update`: local update from this repo, preserving runtime state.
- `Image Prep`: fresh local install, clear runtime state, then power off for SD image capture.

If the deploy CLI cannot connect over SSH after reflashing the Pi, clear the old host key and try again:

```bash
ssh-keygen -R ghosthub.local
ssh-keygen -R <pi-ip-address>
```

On Windows PowerShell:

```powershell
.\scripts\deploy_to_pi.ps1
```

Full DIY guide: [DIY Install](DIY_INSTALL.md).

Open one of these URLs after installation:

```text
http://ghosthub.local
http://192.168.4.1
http://<pi-ip-address>:5000
```

## Option 3: Run From Source

Use this for development on a normal workstation.

```bash
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd static/js
npm install
cd ../..
python ghosthub.py
```

Then open `http://localhost:5000`.

## First Things To Try

1. Plug in a USB drive with media folders.
2. Open Settings and claim admin.
3. Switch between Default, Streaming, and Gallery layouts.
4. Try Gallery upload from a desktop browser.
5. Connect HDMI and cast media to the attached display.

## Updating

From the admin panel, use the system update controls. GhostHub checks GitHub Releases, downloads the release installer, and preserves runtime state during the update.

For manual pinned installs:

```bash
sudo ./install_ghosthub.sh --version v5.0.1
```
