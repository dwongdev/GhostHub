# GhostHub

**A private Raspberry Pi 4 media hub that feels like a polished streaming app, runs from your own storage, and works without a cloud account.**

GhostHub turns a Raspberry Pi 4 into a local-first photo and video system for USB drives, phones, tablets, laptops, and an HDMI screen. It gives you a cinematic browser UI, profiles, uploads, resume progress, TV casting, admin controls, offline access-point mode, and GitHub Releases updates in a package you can inspect and modify.

<p>
  <a href="https://github.com/BleedingXiko/GhostHub/releases/latest"><strong>Latest Release</strong></a>
  · <a href="docs/QUICK_START.md"><strong>Quick Start</strong></a>
  · <a href="docs/FLASH_GHOSTHUB_IMAGE.md"><strong>Flash Image</strong></a>
  · <a href="docs/DIY_INSTALL.md"><strong>DIY Install</strong></a>
  · <a href="CONTRIBUTING.md"><strong>Contributing</strong></a>
  · <a href="SECURITY.md"><strong>Security</strong></a>
</p>

<p>
  <img src="StreamingLayout.PNG" alt="GhostHub streaming layout on mobile" width="31%">
  <img src="WhosWatching.PNG" alt="GhostHub profile picker on mobile" width="31%">
  <img src="Settings.PNG" alt="GhostHub system settings on mobile" width="31%">
</p>

> **Compatibility:** GhostHub's Pi install path is built for Raspberry Pi 4 on `2022-01-28-raspios-bullseye-armhf-lite`. It is not a generic "any Raspberry Pi OS image" installer.

## Why GhostHub

- **Your media stays yours.** Browse local USB storage from any browser on your network.
- **Built for the couch and the pocket.** Mobile-first UI, HDMI kiosk mode, and TV casting are first-class.
- **Useful offline.** The Pi can create its own `GhostHub` Wi-Fi network for portable setups.
- **Not just a demo.** Uploads, downloads, profiles, progress, themes, admin tools, logs, updates, and hardware status are included.
- **Open source and hackable.** Python 3.9 backend, modular ES frontend, SPECTER services/controllers, and vendored RAGOT runtime.

## 30-Second Setup

### Fastest: Flash The Ready-To-Use Image

1. Download the ready-to-flash GhostHub image from the project download page or announcement post.
2. Flash it to a microSD card with Raspberry Pi Imager or balenaEtcher.
3. Boot the Pi, connect to the `GhostHub` Wi-Fi network, and open `http://ghosthub.local` or `http://192.168.4.1`.

That path is meant for a fresh Raspberry Pi 4 and gets you to a working GhostHub without cloning the repo.

### DIY: Install On The Supported Raspberry Pi OS Image

Use the exact supported base OS:

```text
2022-01-28-raspios-bullseye-armhf-lite
```

Download the trusted clean OS image from Raspberry Pi:

```text
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip
```

Use Raspberry Pi Imager v1.8.5 and open advanced options before flashing:

```text
Hostname: ghosthub
Username: ghost
Enable SSH: yes
Password: choose your own
Wi-Fi: optional, only needed if you are not using Ethernet
```

For the release installer path, SSH into the Pi from your computer.

On macOS, Linux, or Windows PowerShell:

```bash
ssh ghost@ghosthub.local
```

After you are logged into the Pi, run these commands on the Pi:

```bash
curl -L -o install_ghosthub.sh \
  https://github.com/BleedingXiko/GhostHub/releases/latest/download/install_ghosthub.sh
chmod +x install_ghosthub.sh
sudo ./install_ghosthub.sh
```

The installer downloads `Ghosthub_pi_github.zip` from GitHub Releases, installs system dependencies, configures the service, prepares USB/AP/HDMI support, and starts GhostHub.

If you cloned this repository and want to deploy local source instead, do not SSH into the Pi. Run the deploy CLI from your computer.

On macOS or Linux:

```bash
./scripts/deploy_to_pi.sh
```

On Windows PowerShell:

```powershell
.\scripts\deploy_to_pi.ps1
```

The CLI offers Standard, Update, and Image Prep modes. It creates `venv/`, installs Python and JavaScript dependencies, builds the local `ghostpack` ZIP, uploads it from your computer, and never downloads app ZIPs from GitHub Releases.

## What You Get

- Browser-based photo and video browsing from USB drives or configured media folders.
- Mobile, tablet, desktop, and HDMI kiosk experiences.
- Upload, download, rename, delete, move, and organize media.
- Streaming and Gallery browsing layouts.
- Category discovery, hidden folders, playlists, sorting, search, and progress tracking.
- Video playback with subtitles, thumbnails, resume progress, and browser-native controls.
- TV casting to an HDMI display connected to the Pi.
- Raspberry Pi access-point mode for offline use.
- Optional remote access experiments with tunnels or secure mesh.
- Admin tools for updates, storage, Wi-Fi, cache, restart, logs, and system status.

## How GhostHub Runs

GhostHub is a Python 3.9 + Flask/SPECTER backend with a modular ES frontend. It is packaged for Raspberry Pi but stays hackable as a normal source tree.

```text
Raspberry Pi 4 + USB storage
        |
        v
GhostHub service on port 5000
        |
        +-- phone/tablet/desktop browser
        +-- HDMI kiosk / TV display
        +-- optional mesh or tunnel access
```

## Install Options

### Base Image

Use this when you want the fastest path from blank SD card to working GhostHub.

See [Flash The GhostHub Image](docs/FLASH_GHOSTHUB_IMAGE.md).

### Release Installer

Use this when the exact supported Raspberry Pi OS image is already installed:

```text
2022-01-28-raspios-bullseye-armhf-lite
```

```bash
sudo ./install_ghosthub.sh --version v5.0.1
```

Install from a local release ZIP:

```bash
sudo ./install_ghosthub.sh --local-zip /path/to/Ghosthub_pi_github.zip
```

Compatibility local deploy mode still reads `/tmp/ghosthub_deploy.zip`:

```bash
sudo ./install_ghosthub.sh --local-only
```

See [Quick Start](docs/QUICK_START.md).

## Updates

GhostHub updates are published through [GitHub Releases](https://github.com/BleedingXiko/GhostHub/releases). The admin UI checks the latest `vX.Y.Z` tag, downloads the release installer, validates it, and schedules the update through `systemd-run`.

Runtime state is preserved during updates:

- `instance/`
- `venv/`
- `headscale`
- `cloudflared`

Public release assets are:

- `Ghosthub_pi_github.zip`
- `install_ghosthub.sh`

The ready-to-flash GhostHub SD card image is published separately by the maintainer. It is not produced by `scripts/ghostpack.py` and is not attached by the GitHub release workflow.

See [Release Process](docs/RELEASES.md).

## Development

GhostHub targets Python 3.9. Use a Python 3.9 virtual environment so local tests match Raspberry Pi deployments.

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

Run validation.

On macOS or Linux:

```bash
./venv/bin/python scripts/run_all_tests.py
```

On Windows PowerShell:

```powershell
.\venv\Scripts\python.exe scripts\run_all_tests.py
```

Run focused backend/frontend tests.

On macOS or Linux:

```bash
./venv/bin/python -m pytest tests/test_admin_routes.py -v
cd static/js
npm test
cd ../..
```

On Windows PowerShell:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_admin_routes.py -v
cd static\js
npm test
cd ..\..
```

## Architecture

- Backend routes and services use the `specter-runtime` package.
- Frontend modules use the vendored RAGOT runtime at `static/js/libs/ragot.esm.min.js`.
- SQLite stores app state in `instance/`.
- Raspberry Pi service setup is handled by `install_ghosthub.sh`.
- Release ZIPs are built with `scripts/ghostpack.py --zip`.

Start with [Architecture](docs/ARCHITECTURE.md) if you are changing internals.

## Documentation

- [Quick Start](docs/QUICK_START.md)
- [Docs Index](docs/README.md)
- [Flash The GhostHub Image](docs/FLASH_GHOSTHUB_IMAGE.md)
- [DIY Install](docs/DIY_INSTALL.md)
- [User Guide](docs/HOW_TO_USE_GHOSTHUB.md)
- [Contributing](CONTRIBUTING.md)
- [Release Process](docs/RELEASES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Manual QA](docs/MANUAL_QA_CHECKLIST.md)
- [Secure Mesh Quick Start](docs/MESH_QUICK_START.md)
- [Secure Mesh Troubleshooting](docs/SECURE_MESH_TROUBLESHOOTING.md)
- [Design Language](docs/DESIGN_LANGUAGE.md)
- [Third-Party Licenses](docs/THIRD_PARTY_LICENSES.md)
- [Security Policy](SECURITY.md)

## Contributing

Issues, fixes, docs, tests, Raspberry Pi validation, and release-readiness improvements are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening larger changes.

For backend work, follow the existing SPECTER controller/service patterns. For frontend work, use the existing ES module structure and RAGOT runtime.

## Security

Please do not post credentials, private media libraries, device logs with secrets, or private network details in public issues. See [SECURITY.md](SECURITY.md).

## License

New GhostHub source code is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).

Older public GhostHub releases may remain available under the MIT License; this repository's current source tree is AGPL-3.0.

## Donations

If GhostHub is useful to you, donations and sponsorships help support Raspberry Pi test hardware, maintenance time, and release infrastructure.
