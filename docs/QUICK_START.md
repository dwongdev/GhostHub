# Quick Start

This is the fastest path to a working GhostHub.

## Supported Hardware And OS

GhostHub's Pi install path targets:

```text
Hardware: Raspberry Pi 4
Recommended OS image: 2022-01-28-raspios-bullseye-arm64-lite
32-bit fallback: 2022-01-28-raspios-bullseye-armhf-lite
```

It is not currently documented as compatible with arbitrary Raspberry Pi OS images.

## Option 1: Flash The GhostHub Image

Use this if you have a fresh microSD card and want GhostHub ready immediately.

1. Download the ready-to-flash GhostHub image from the project download page or announcement post. For B5 and newer image releases, use `arm64` for the recommended Pi 4 image or `armhf` if you need the 32-bit build.
2. Flash it with Raspberry Pi Imager or balenaEtcher.
3. Insert the card into the Pi and boot.
4. Connect to the `GhostHub` Wi-Fi network.
5. Open `http://ghosthub.local` or `http://192.168.4.1`.

Default access-point settings:

```text
SSID: GhostHub
Password: ghost123
```

Prebuilt GhostHub images ship with SSH disabled. Use the DIY install path if you need SSH enabled during setup.

Plug in a USB drive with photos or videos. GhostHub discovers folders as categories and starts thumbnail/index work in the background.

Full guide: [Flash The GhostHub Image](FLASH_GHOSTHUB_IMAGE.md).

## Option 2: Install From GitHub Releases

Download the clean supported OS image from Raspberry Pi's official archive:

```text
Recommended: 2022-01-28-raspios-bullseye-arm64-lite
https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2022-01-28/2022-01-28-raspios-bullseye-arm64-lite.zip

32-bit fallback: 2022-01-28-raspios-bullseye-armhf-lite
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip
```

Optional checksum file:

```text
https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2022-01-28/2022-01-28-raspios-bullseye-arm64-lite.zip.sha256
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip.sha256
```

Flash with Raspberry Pi Imager v1.8.5. Before writing the card, open advanced options and set:

```text
Hostname: ghosthub
Username: ghost
Enable SSH: yes
Password: choose your own
```

For the DIY installer, give the Pi network access over Ethernet. Plug it into your router, or connect it directly to your computer if you are sharing network access from that computer. Then boot the Pi and SSH in.

On macOS, Linux, or Windows PowerShell:

```bash
ssh ghost@ghosthub.local
```

If mDNS is not resolving yet, use the Pi's IP address:

```bash
ssh ghost@<pi-ip-address>
```

If SSH refuses to connect with a host key warning, your computer may have an old key cached for `ghosthub.local` or that IP. Refresh it from your computer:

```bash
ssh-keygen -R ghosthub.local
ssh-keygen -R <pi-ip-address>
```

After you are logged into the Pi, run these commands on the Pi:

```bash
APP_TAG="$(curl -fsSL https://api.github.com/repos/BleedingXiko/GhostHub/releases \
  | sed -n 's/.*"tag_name": "\(v[0-9][0-9.]*\)".*/\1/p' \
  | head -n 1)"
curl -L -o install_ghosthub.sh \
  "https://github.com/BleedingXiko/GhostHub/releases/download/${APP_TAG}/install_ghosthub.sh"
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

Do not SSH into the Pi for this path. Run the CLI from the repository root on your computer.

On macOS or Linux:

```bash
./scripts/deploy_to_pi.sh
```

On Windows PowerShell:

```powershell
.\scripts\deploy_to_pi.ps1
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

Full DIY guide: [DIY Install](DIY_INSTALL.md).

Open one of these URLs after installation:

```text
http://ghosthub.local
http://192.168.4.1
http://<pi-ip-address>:5000
```

## Option 3: Run From Source

Use this for development on a normal workstation.

On macOS or Linux:

```bash
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd static/js
npm install
cd ../..
python ghosthub.py
```

On Windows PowerShell:

```powershell
py -3.9 -m venv venv
.\venv\Scripts\Activate.ps1
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
3. Switch between Streaming and Gallery layouts.
4. Try Gallery upload from a desktop browser.
5. Connect HDMI and cast media to the attached display.

## Updating

From the admin panel, use the system update controls. GhostHub checks GitHub Releases, downloads the release installer, and preserves runtime state during the update.

For manual pinned installs:

Run this on the Pi after SSH:

```bash
sudo ./install_ghosthub.sh --version vX.Y.Z
```
