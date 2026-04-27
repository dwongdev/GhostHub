# DIY Install

Use this path if you want to start from Raspberry Pi's official OS image and install GhostHub yourself.

GhostHub's Pi install path targets:

```text
Hardware: Raspberry Pi 4
OS image: 2022-01-28-raspios-bullseye-armhf-lite
```

Do not assume newer Raspberry Pi OS images are compatible unless a release explicitly says they have been tested.

## Download The Supported OS

Download the exact matching Raspberry Pi OS Lite image from Raspberry Pi's official archive:

```text
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip
```

Optional checksum file:

```text
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip.sha256
```

## Flash With Raspberry Pi Imager

Use Raspberry Pi Imager v1.8.5. Before writing the card, open advanced options and set:

```text
Hostname: ghosthub
Username: ghost
Enable SSH: yes
Password: choose your own
Wi-Fi: optional, only needed if you are not using Ethernet
```

Boot the Pi and wait for it to join the network.

## Option A: Install From GitHub Releases

Use this to install the published GhostHub release assets directly on the Pi.

SSH into the Pi from your computer.

On macOS, Linux, or Windows PowerShell:

```bash
ssh ghost@ghosthub.local
```

If `ghosthub.local` does not resolve, use the Pi's IP address:

```bash
ssh ghost@<pi-ip-address>
```

If SSH refuses to connect with a host key warning, your computer may have an old key cached for `ghosthub.local` or that IP. Refresh it from your computer:

```bash
ssh-keygen -R ghosthub.local
ssh-keygen -R <pi-ip-address>
```

After you are logged into the Pi, run the GhostHub release installer on the Pi:

```bash
curl -L -o install_ghosthub.sh \
  https://github.com/BleedingXiko/GhostHub/releases/download/v5.0.1/install_ghosthub.sh
chmod +x install_ghosthub.sh
sudo ./install_ghosthub.sh
```

## Option B: Deploy Local Source With The CLI

Use this when you cloned the repository on your computer and want the deploy CLI to build, upload, SSH, and install for you.

On your computer, install:

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

Deployment modes:

- `Standard`: fresh local install from this repo.
- `Update`: local update from this repo, preserving runtime state.
- `Image Prep`: fresh local install, clear runtime state, then power off for SD image capture.

If the deploy CLI cannot connect over SSH after reflashing the Pi, clear the old host key and try again:

```bash
ssh-keygen -R ghosthub.local
ssh-keygen -R <pi-ip-address>
```

## Open GhostHub

After installation, open one of:

```text
http://ghosthub.local
http://192.168.4.1
http://<pi-ip-address>:5000
```

Plug in a USB drive with photos or videos. GhostHub discovers folders as categories and starts thumbnail/index work in the background.
