# Third-Party Licenses

GhostHub includes and interoperates with open-source dependencies. This document is an attribution guide for the main runtime components; package-manager lockfiles and upstream project metadata remain the authoritative source for exact transitive dependency versions.

## Python Runtime

GhostHub depends on Python packages listed in `requirements.txt`, including Flask, Flask-SocketIO, gevent, requests, Pillow, python-dotenv, psutil, zeroconf, and related libraries. These projects are distributed under their respective upstream open-source licenses.

## JavaScript Runtime

Frontend dependencies are declared in `static/js/package.json`. Vendored browser libraries in `static/js/libs/` retain their upstream license terms and notices.

## System Tools

GhostHub can call system tools installed on Raspberry Pi OS, including FFmpeg, mpv, hostapd, dnsmasq, udisks2, Tailscale, Headscale, and cloudflared when optional features are enabled. These tools are not relicensed by GhostHub.

## RAGOT

GhostHub frontend code uses the vendored RAGOT runtime at `static/js/libs/ragot.esm.min.js`. Keep upstream RAGOT attribution and license metadata with any refreshed vendored copy.

## Release Artifacts

Public GhostHub releases attach the application ZIP and installer script. Generated artifacts may contain bundled or compiled forms of project files and third-party dependencies; the corresponding source remains available in the repository under the licenses documented here and upstream.
