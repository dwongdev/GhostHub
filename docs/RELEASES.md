# Release Process

GhostHub releases are published through GitHub Releases on `BleedingXiko/GhostHub`.

## Versioning

Canonical version locations:

- `app/version.py`
- `install_ghosthub.sh`

Both must contain the same version before release.

Public app install snippets should not hardcode the current app release tag. They
resolve the newest `vX.Y.Z` app release from GitHub Releases so separate image
tags such as `B5` do not affect the app install lane. Ready-to-flash image docs
should keep exact "built on vX.Y.Z" provenance for each image tag.

Use:

- Patch for bug fixes and documentation-only release polish
- Minor for new features or new user-facing workflows
- Major for breaking changes or large migration changes

## Release Assets

Public releases should include:

- `Ghosthub_pi_github.zip`
- `install_ghosthub.sh`

The ready-to-flash GhostHub SD card image is prepared and uploaded separately by the maintainer. It is not produced by `scripts/ghostpack.py` and is not attached by the GitHub release workflow. B5 and newer image releases use separate `arm64` and `armhf` image ZIPs with clear architecture labels.

DIY users should download the clean supported 2022-01-28 Bullseye Lite OS image from Raspberry Pi's official archive:

```text
Recommended: 2022-01-28-raspios-bullseye-arm64-lite
https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2022-01-28/2022-01-28-raspios-bullseye-arm64-lite.zip

32-bit fallback: 2022-01-28-raspios-bullseye-armhf-lite
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-01-28/2022-01-28-raspios-bullseye-armhf-lite.zip
```

The ZIP and installer support updates and install-on-supported-OS flows.

## GitHub Actions

The release workflow runs when a `v*.*.*` tag is pushed. It:

1. Checks out the repository without submodules.
2. Sets up Python 3.9.
3. Sets up Node 20.
4. Installs Python and JavaScript dependencies.
5. Runs `python scripts/run_all_tests.py`.
6. Builds `dist/Ghosthub_pi_github.zip`.
7. Publishes `dist/Ghosthub_pi_github.zip` and `install_ghosthub.sh`.

## Manual Release Checklist

1. Confirm `app/version.py` and `install_ghosthub.sh` match.
2. Run focused tests for the changed surfaces.
3. Run the full suite.

   On macOS or Linux:

   ```bash
   ./venv/bin/python scripts/run_all_tests.py
   ```

   On Windows PowerShell:

   ```powershell
   .\venv\Scripts\python.exe scripts\run_all_tests.py
   ```

4. Package the app.

   On macOS or Linux:

   ```bash
   ./venv/bin/python scripts/ghostpack.py --zip
   ```

   On Windows PowerShell:

   ```powershell
   .\venv\Scripts\python.exe scripts\ghostpack.py --zip
   ```

5. Publish a `vX.Y.Z` tag.
6. Confirm the GitHub release contains the ZIP and installer.
7. Upload or publish the ready-to-flash GhostHub SD card image ZIPs through the separate maintainer-controlled download path.
8. Flash each published GhostHub SD card image variant on a fresh card and perform the first-boot smoke test.
9. Test an update from the previous public release through the admin UI.

## First-Boot Smoke Test

After flashing the image:

1. Boot the Pi.
2. Connect to the `GhostHub` Wi-Fi network.
3. Open `http://ghosthub.local` or `http://192.168.4.1`.
4. Plug in a USB drive and confirm categories appear.
5. Play a video and view an image.
6. Claim admin and open Settings.
7. Confirm update check reaches GitHub Releases.

## Update Smoke Test

On a previously installed GhostHub:

1. Preserve a small test library and existing `instance/` state.
2. Start update from the admin UI.
3. Confirm the service restarts.
4. Confirm media, settings, progress, and admin controls still work.
