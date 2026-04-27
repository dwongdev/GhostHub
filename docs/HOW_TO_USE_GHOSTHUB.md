# How to Use GhostHub

GhostHub is an open-source, local-first media hub for photos and videos on a Raspberry Pi. Use this guide after GhostHub is already installed and running.

This is not an install or developer guide. For setup, see [Quick Start](QUICK_START.md).

## What You Need

- A running GhostHub device.
- A USB drive or configured media storage with photos and videos.
- A phone, tablet, laptop, desktop, or HDMI display.
- A modern browser. Chrome or Edge work best on desktop. Safari works well on iPhone and iPad.

## Open GhostHub

GhostHub runs in one of two network modes.

### Access Point Mode

In access point mode, the Pi creates its own Wi-Fi network.

1. Connect your device to the GhostHub Wi-Fi network.
2. Open `http://192.168.4.1` or `http://ghosthub.local`.

Default access point settings:

```text
SSID: GhostHub
Password: ghost123
```

### Home Network Mode

If the Pi is connected to your router by Ethernet, devices on that LAN can open one of these URLs. That includes phones and laptops connected to the router's Wi-Fi.

```text
http://ghosthub.local
http://<pi-ip-address>:5000
```

If `ghosthub.local` does not work, use the Pi IP address. Some networks and browsers handle `.local` names better than others.

### Device Notes

On Windows, Chrome and Edge give the smoothest browser and app-install experience. Downloads land in your Downloads folder unless your browser asks each time.

On macOS, Safari, Chrome, and Edge can browse GhostHub. Chrome and Edge provide the clearest "install app" prompt.

On Linux, Chrome, Chromium, Edge, and Firefox work for normal browsing. If `ghosthub.local` does not resolve, use the Pi IP address.

On iPhone, iPad, and Android, use the normal browser flow. Mobile is best for browsing, playback, chat, sync, and TV casting. Large folder uploads are easier from a desktop browser.

## First Launch

When GhostHub opens, you may see a "Who's watching?" screen.

- Select an existing profile.
- Create a profile with a name, color, and avatar.
- Continue without a profile when allowed.

Profiles keep personal preferences and video progress separate. A profile can only be active in one live session at a time, so a profile that is already being used may appear locked.

If the owner enabled a session password, GhostHub prompts for it before protected features such as profiles, uploads, downloads, and some commands.

## Add Media

Plug a USB drive into the Pi. GhostHub scans folders on the drive and turns them into browsable categories.

Large libraries may show indexing or thumbnail progress. You can usually start browsing while background work continues.

For best performance, keep media on USB storage instead of the Pi SD card.

## Layouts

GhostHub currently has two main layouts: Streaming and Gallery. Change layout from Settings, under My Preferences.

### Streaming

Streaming is the default couch-style interface.

- Hero area for featured or recently watched content.
- Continue Watching row for videos with saved progress.
- Recently added and category rows.
- Horizontal browsing through folders and media.
- Search from the header when the search feature is enabled.

Use Streaming when you mostly watch videos or browse folders like a media app.

### Gallery

Gallery is a photo-library style timeline.

- Media grouped by date.
- Year and month navigation.
- Filters for all media, photos, and videos.
- Zoom controls for grid density.
- Multi-select downloads.
- Drag-and-drop upload from desktop browsers.

Use Gallery when you mostly browse photos, mixed libraries, or date-based collections.

## Browsing Media

Open a card or thumbnail to enter the media viewer.

On touch devices:

- Swipe up or down to move between items.
- Swipe right to leave the viewer.
- Tap video controls to play, pause, seek, or adjust playback.
- Double-tap a video to enter fullscreen when the browser supports it.

On desktop:

- Use arrow keys to move between items.
- Click the back control to leave the viewer.
- Double-click a video for fullscreen when the browser supports it.

Videos use GhostHub's custom controls. The admin can choose what happens when a video ends: stop, loop, or play the next item.

## Profiles, Preferences, and Progress

Open Settings to manage your personal preferences.

Profiles can store:

- Theme.
- Layout.
- Motion preference.
- Header feature toggles such as chat, search, sync button, and branding.
- Video progress.

If you do not select a profile, some preferences and progress stay in the current browser instead.

Continue Watching uses saved video progress. Clearing video progress from My Preferences removes the selected profile's video progress, or the browser's local video progress when no profile is selected.

Gallery is mainly a timeline browser. Continue Watching is shown in Streaming.

## Themes

Built-in themes:

- Dark.
- Midnight.
- Nord.
- Monokai.
- Dracula.

Use Create Custom Theme in My Preferences to build and save a custom color palette with live preview.

## Uploading

Open Settings and use the content button near the top.

- Non-admin users see File Upload.
- Admin users see Content Management.

If a session password is active, non-admin upload requires the session password.

Upload flow:

1. Choose a storage drive.
2. Choose an existing folder or create a new one.
3. Drag files or folders into the upload area, or use the file/folder buttons.
4. Confirm duplicates when GhostHub finds matching target names.
5. Watch progress or cancel from the upload controls.

Large files use chunked uploads automatically. GhostHub negotiates chunk size based on the connection and Pi hardware. Single files over 16GB are rejected.

Gallery also supports desktop drag-and-drop upload. Drop files or folders into Gallery, choose a drive and folder, then start the upload.

## Downloading

Single file download:

1. Open a media item.
2. Use the download button in the viewer.

Gallery multi-select download:

1. Switch to Gallery.
2. Select one or more items.
3. Use Download in the selection toolbar.

Admin category download:

- Admin users can download a whole category from the viewer download menu.
- Large categories may be split into multiple ZIP parts or direct single-file downloads.

Downloads are protected by the session password when password protection is active.

## Managing Content

Admin users can open Settings, then Content Management.

Content Management can:

- Browse connected storage drives.
- Rename drives when GhostHub can identify the device.
- Create folders.
- Browse media files in folders.
- Rename media files.
- Delete media files.
- Hide or unhide files.
- Hide or unhide folders/categories.
- Temporarily reveal hidden content for the current admin session.

Hidden content is hidden from normal browsing and downloads. Admins can reveal hidden content for a limited time from Content Management or with chat commands.

## Admin Role

The admin role controls server-wide settings and sensitive actions.

When no one is admin, click the lock button to claim admin.

When someone else is already admin, clicking the lock button asks for the admin password so the role can be reclaimed. The default admin password is `admin` unless it was changed in Settings.

Admin users can:

- Change server settings.
- Change Wi-Fi access point settings.
- Manage content.
- Manage hidden content.
- View and kick connected users.
- Start remote access.
- Reindex media.
- Regenerate thumbnails.
- Reset shared server data.
- Restart or update GhostHub.

Click the admin button again to release the role.

## Server Settings

Admin settings are split into Basic and Advanced modes.

Common Basic settings:

- Session Password: protects access to shared features.
- Admin Password: used to reclaim admin.
- Shuffle Media: randomizes media order where supported.
- Video End Behavior: stop, loop, or play next.
- Enable Subtitles: detects embedded and external subtitles.
- Save Video Progress: enables video resume progress.
- Save Progress For Hidden Files: allows hidden videos to keep progress.

Maintenance actions:

- Reindex Media Library refreshes media indexes.
- Regenerate Thumbnails clears and rebuilds thumbnail cache.
- Reset Shared Server Data clears shared indexes, hidden lists, and subtitle cache without deleting profiles.
- Update GhostHub schedules an update from GitHub Releases.
- Restart GhostHub restarts the service and temporarily disconnects users.

## Wi-Fi Settings

Admin users can edit the GhostHub access point settings from Settings.

Available settings:

- Network name.
- Password.
- Channel.
- Country code.

These settings apply to GhostHub's access point mode. Saving them may briefly disconnect users while the network restarts.

## Chat and Commands

Open the chat panel to send messages. Type `/` to show command suggestions.

Common commands:

| Command | What it does |
| --- | --- |
| `/help` | Shows available commands. |
| `/myview` | Shares your current view in chat. |
| `/view <profile-or-session>` | Opens another user's shared view. |
| `/search <query>` | Searches media filenames. |
| `/find <query>` | Alias for `/search`. |
| `/random` | Jumps to random media. |
| `/play [seconds]` | Starts auto-play. Images advance after the chosen delay. |
| `/play stop` | Stops auto-play. |
| `/add` | Adds the current media item to the shared session playlist. |
| `/remove` | Removes the current media item from the shared session playlist. |
| `/hide` | Admin: hides the current category. |
| `/show [time]` | Admin: temporarily reveals hidden categories, such as `1h`, `30m`, or `90s`. |
| `/unhide` | Admin: permanently unhides hidden categories. |
| `/kick <user>` | Admin: kicks a connected user for the current server session. |

Search results open from chat and can include category and file matches.

## Session Playlist

The shared session playlist is a temporary virtual category.

Use `/add` while viewing media to add the current item. Use `/remove` to remove it. The playlist appears alongside normal categories when it contains items.

The playlist is shared by the current GhostHub server session.

## Sync Mode

Sync Mode lets one host guide everyone else through the same media.

Start Sync Mode:

1. Open the media you want to share.
2. Click the Sync button.
3. You become the host.

Guests automatically follow the host. Guest navigation is disabled while following, but guests can still chat and use local fullscreen.

The host can stop sync for everyone. Guests can leave sync without ending it for others.

Shuffle is disabled during sync so everyone sees the same order.

## TV Casting

GhostHub can cast media to an HDMI display connected to the Pi.

1. Connect a TV or monitor to the Pi by HDMI.
2. Open media in GhostHub.
3. Use the TV cast button.

GhostHub can start the TV kiosk when a cast begins. If the TV display is still booting, the browser shows a startup status.

Cast playback can start from the current or saved video position. Subtitles are sent to the TV when GhostHub finds a supported subtitle track.

If an admin starts a cast, non-admin users cannot control or stop that admin cast. Guest casts are treated as guest casts.

## GhostStream Transcoding

GhostStream is GhostHub's optional transcoding integration for videos that browsers may not play directly, such as some MKV, AVI, HEVC, AC3, or DTS files.

When a GhostStream server is connected, GhostHub can:

- Auto-transcode incompatible formats.
- Prefer a chosen quality.
- Optimize very high bitrate files.
- Use cached transcodes when available.
- Show live transcode status during playback.

Admin users manage GhostStream from Settings. If no GhostStream server is connected and a file requires transcoding, GhostHub shows a playback message instead of trying to play an unsupported format.

## Subtitles

When subtitles are enabled, GhostHub detects:

- Embedded subtitle tracks.
- External `.srt` files.
- External `.vtt` files.

External subtitle files should usually share the video filename. Browser playback uses GhostHub's player controls, and TV casting sends a supported subtitle track when one is available.

## Remote Access

Admin users can open Remote Access from the header.

Available providers depend on what is installed and configured on the Pi:

- Secure Mesh using Headscale and Tailscale.
- Cloudflare Tunnel.
- Pinggy.

Remote access requires the Pi to have internet access. It will not work from access point mode alone unless the Pi also has upstream connectivity.

Secure Mesh shows device-specific instructions in the app. Desktop clients get a Tailscale command. Mobile clients get app-based instructions and a device registration flow.

## Users

Admin users can view connected users from Settings.

The user list shows active sessions, profile names when available, IP addresses, and admin status. Admins can kick a user; the kicked user's IP is blocked for the current server session.

## Troubleshooting

### GhostHub Will Not Open

- Make sure your device is on the GhostHub access-point Wi-Fi network, on the same Ethernet network as the Pi, or connected directly to the Pi by Ethernet.
- Try `http://192.168.4.1` in access point mode.
- Try `http://<pi-ip-address>:5000` on a home network.
- Refresh the browser after reconnecting Wi-Fi.

### Media Is Missing

- Make sure the USB drive is connected.
- Wait for indexing to finish on large folders.
- Ask an admin whether the category or file is hidden.
- Ask an admin to use Reindex Media Library if the drive changed a lot.

### Thumbnails Are Missing

- Wait for thumbnail generation.
- Refresh the page.
- Ask an admin to use Regenerate Thumbnails if thumbnails look stale.

### A Video Will Not Play

- Try Chrome or Edge.
- Check whether the file format needs GhostStream.
- Try a browser-friendly format such as MP4 with H.264/AAC.
- If GhostStream is configured, ask an admin to check GhostStream server status.

### Uploads Fail

- Check free space on the target drive.
- Use a stable connection during large uploads. Ethernet is best; GhostHub access-point Wi-Fi can be slower.
- Try fewer files at once.
- Confirm the session password if prompted.
- Large files over 16GB are not accepted.

### Downloads Fail

- Confirm the session password if prompted.
- For large category downloads, download each part shown in the download dialog.
- Try a desktop browser for large ZIP downloads.

### Progress Is Not Saving

- Select a profile when you want progress to follow you between devices.
- Ask an admin whether Save Video Progress is enabled.
- If you are not using a profile, progress is tied to the current browser.

### Sync Mode Is Stuck

- Refresh the host and guest browsers.
- Make sure everyone can reach the same GhostHub URL.
- Have the host stop sync and start again.

### TV Casting Does Not Start

- Make sure the HDMI display is connected and powered on.
- Wait for the kiosk startup status.
- Refresh GhostHub and try casting again.
- Ask an admin to check HDMI status from Settings if the display is not detected.

## Tips

- Use Streaming for video watching and Continue Watching.
- Use Gallery for date-based photo browsing and multi-select downloads.
- Use profiles for separate watch progress and preferences.
- Keep large libraries on USB storage.
- Use MP4 H.264/AAC for the broadest browser compatibility.
- Use GhostStream when your library includes formats browsers cannot play directly.
