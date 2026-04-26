# Security Policy

GhostHub is self-hosted software that may handle private media libraries, local network details, and device configuration. Please be careful when reporting issues.

## Reporting Security Issues

Do not post secrets, credentials, private logs, media file listings, or network details in public issues.

For security-sensitive reports, contact the maintainer privately when possible. Include:

- GhostHub version
- Install method: base image, release installer, or source
- Raspberry Pi model and OS version
- A minimal reproduction
- Logs with secrets removed

## Public Issue Hygiene

Before opening a public issue, remove:

- Session passwords
- Tunnel tokens
- Wi-Fi credentials
- Tailscale or Headscale auth keys
- Private IP ranges if you do not want them public
- Filenames or paths that reveal sensitive media

## Supported Versions

The current public source tree and current GitHub Release are the supported targets for security fixes. Older public releases may remain available for historical reasons, but fixes should be based on the current tree unless a maintainer says otherwise.
