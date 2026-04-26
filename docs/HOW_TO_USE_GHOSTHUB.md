# How to Use GhostHub

A friendly guide for regular users who have a GhostHub Pi device set up and ready to go.

---

## Overview

GhostHub is your personal media hub that lets you browse photos and videos stored on a USB drive, all from your phone or computer's web browser. Think of it like a local media library for your own content.

**What GhostHub does:**
- Displays your photos and videos in multiple layout styles (Default, Streaming, Gallery)
- Remembers where you left off (Continue Watching)
- Lets multiple people watch together in sync (Sync Mode)
- Casts media to a TV display (Admin only)
- Upload/download files to connected USB drives (File Manager)
- Remote access via secure tunnels (Cloudflare/Pinggy)
- Works entirely offline — no internet required

**What you need:**
- A GhostHub device (Raspberry Pi with GhostHub installed)
- A USB drive with your media files
- Any phone, tablet, or computer with WiFi and a web browser

---

## Getting Started

### Connecting to GhostHub

GhostHub creates its own WiFi network. To connect:

1. **Connect to the GhostHub WiFi network** from your phone or tablet
   - Network name: **GhostHub**
   - Password: **ghost123** (default)

2. **Open your browser** and go to `http://192.168.4.1` or `http://ghosthub.local`

3. **Browse categories**: You'll see a grid of "categories" — each category is a folder from your USB drive. Tap or click one to start viewing.

4. **Navigate media**: Swipe up/down on mobile or use arrow keys on desktop to move through items.

### TV Display Mode

If your GhostHub Pi is connected to a TV or monitor via HDMI, it automatically displays a fullscreen media viewer (kiosk mode). The kiosk starts and stops automatically based on HDMI connection — unplug the TV and it saves resources, plug it back in and it resumes. You can cast media from your phone to this TV display (see Casting to TV section).

### Install as an App (PWA)

GhostHub can be installed as an app on your phone or computer:

1. Open GhostHub in your browser
2. Look for the **"Install App"** button (appears at bottom-right on supported browsers)
3. Tap to install — GhostHub will appear on your home screen like a native app

This gives you a fullscreen experience without browser controls.

### Network Modes

GhostHub can run in two network modes:

1. **Access Point Mode** (default): GhostHub creates its own "GhostHub" WiFi network. Perfect for offline use — no internet required.

2. **Connected Mode**: You can connect your Pi to your home WiFi network. This allows remote access via tunnels but still works locally.

---

## UI Layouts

GhostHub offers three different ways to browse your media. Switch between them in Settings > Themes & Layout.

### Default Layout
The standard category-based interface:
- Grid of category cards (folders from your USB)
- Filter by All, Videos, or Photos
- Pagination for large collections
- TikTok-style vertical swiping inside categories

### Streaming Layout
A Netflix/HBO Max-style horizontal browsing experience:
- **Hero Section**: Featured content (your most recent video with progress)
- **Continue Watching Row**: Videos with saved progress
- **What's New Row**: Recently added media across all categories
- **Category Rows**: Horizontal scrolling media cards per category
- Infinite scroll pagination as you browse right
- Click any card to open the media viewer

### Gallery Layout
A Google Photos/Immich-style timeline interface:
- Media grouped by date with month/year sidebar navigation
- Filter by All, Photos, or Videos
- Adjustable grid size (zoom in/out)
- Grid of thumbnails with date headers
- Drag-and-drop upload on desktop (password protected)
- Download and selection mode for batch operations

---

## Themes & Customization

GhostHub supports multiple color themes. Access via Settings (⚙️) > Themes & Layout.

**Available Themes:**
- **Dark** (default): Classic dark theme with red accents
- **Midnight**: Deep purple-blue with pink accents
- **Nord**: Arctic, bluish color palette
- **Monokai**: Classic code editor theme
- **Dracula**: Popular dark theme with purple accents

**Feature Toggles:**
- **Chat Sidebar**: Show/hide the chat panel
- **Sync Status Display**: Show/hide sync status in header
- **Swipe Navigation Indicators**: Show/hide up/down arrows
- **Header Branding**: Show/hide GhostHub logo in header

### Theme Builder (Custom Themes)

Create your own custom color themes:

1. Open **Settings** (⚙️) > **Themes & Layout**
2. Click **"Open Theme Builder"**
3. Choose from preset palettes (Dark, Midnight, Nord, Monokai, Dracula, Ocean, Forest, Sunset, Cyberpunk, Coffee) or customize individual colors:
   - **Primary**: Main brand color for headers
   - **Secondary**: Supporting color for gradients
   - **Accent**: Highlight color for buttons
   - **Background**: Main page background
   - **Surface**: Card and panel backgrounds
   - **Text**: Primary text color
4. Use **Random** to generate random palettes, or **Invert** to flip light/dark
5. Preview your theme in real-time across different layout tabs
6. Click **Save Theme** to keep it (appears in theme dropdown with ✨)

---

## Browsing & Navigation

### Category View (Home Screen)

When you first open GhostHub, you see your media organized into **categories** — these are folders from your USB drive.

**What you'll see on each category card:**
- **Thumbnail**: A preview image of the folder's contents
- **Media count badge**: Shows total items (e.g., "42") or your position if Continue Watching is on (e.g., "15/42")
- **Type icon**: 🎬 for video folders, 🖼️ for image-only folders
- **Progress bar**: A small red bar at the bottom showing how far into a video you were (if Continue Watching is enabled)

**Filtering categories**: Use the filter buttons (All, Videos, Photos) at the top. For large collections, use the Load More button or pagination.

### Inside a Category (Media View)

Once you tap a category, you enter the full-screen media viewer.

**On mobile (touch screens):**
- **Swipe up**: Next item
- **Swipe down**: Previous item
- **Swipe right**: Go back to categories
- **Tap**: Play/pause videos
- **Double-tap**: Enter fullscreen mode for videos

**On desktop (keyboard):**
- **Arrow Down**: Next item
- **Arrow Up**: Previous item
- **Click the back arrow** (top-left): Return to categories

**What the arrows mean:**
- ⬆️ appears when there are previous items
- ⬇️ appears when there are more items to see

### Videos vs Images

- **Videos**: Tap the thumbnail to start playing. Videos loop by default. Tap to pause, tap again to play.
- **Images**: Display instantly. Just swipe to move on.

### Going Fullscreen

**Double-tap** (or double-click on desktop) is the primary way to enter fullscreen on all devices.

---

## Continue Watching

GhostHub can remember where you left off in each category, so you can pick up right where you stopped — like Netflix.

### How it works

When **Save Current Index** is enabled (by the admin):
- The app remembers which item you were on in each category
- For videos, it also remembers your exact playback position
- When you return to a category, you'll automatically jump to where you left off

### What you'll see

- **Category badges** show your position: "15/42" means you're on item 15 of 42
- **Progress bars** on category cards show how far into the current video you were
- **Thumbnails** update to show the last item you viewed
- **Continue Watching row** (Streaming layout) shows all videos with progress

### Two tracking modes

The admin can set progress tracking to work in one of two ways:

1. **Per-Category mode** (default): Your position in each category is saved. Good for watching through folders sequentially.

2. **Per-Video mode**: Progress is saved for each video individually. Good if you're jumping around and want to resume specific videos.

### Session Progress (for guests)

If you're not the admin, your progress can be saved locally in your browser (if the admin enabled "Session Progress"). This means:
- Your progress stays on your device only (stored in IndexedDB)
- You won't overwrite the admin's progress
- Different family members can each have their own place

---

## Session Playlist

Create a temporary playlist of media items to share with others in your session.

### How to use

1. While viewing any media item, type `/add` in chat to add it to the playlist
2. The **Session Playlist** appears as a virtual category at the top of your category list
3. Anyone can view and play from this shared playlist
4. Use `/remove` while viewing an item to remove it from the playlist
5. Admin can clear the entire playlist from settings

The session playlist is temporary and resets when the server restarts.

---

## Subtitles

If the admin has enabled subtitles and your video files have subtitle tracks (embedded in MP4s or as separate .srt/.vtt files), they'll appear automatically.

**Supported formats:**
- Embedded subtitles in video files
- External `.srt` files (same name as the video)
- External `.vtt` files (same name as the video)

Subtitles use your browser's built-in subtitle controls — look for the CC button in the video player.

---

## Sync Mode

Sync Mode lets everyone see the same thing at the same time — great for watching together remotely or controlling a viewing party.

### How Sync Mode works

1. **One person becomes the Host**: The first person to enable Sync Mode controls what everyone sees.
2. **Others join as Guests**: Guests automatically follow along with whatever the Host is viewing.
3. **Navigation is locked for Guests**: Guests can't swipe to change items — they just watch.

### Starting Sync Mode (becoming Host)

1. Navigate to the media you want to share
2. Click the **"Sync"** button (in the header)
3. You're now the Host — everyone connected will see "Sync Mode: ON"

### Joining as a Guest

If someone else already started Sync Mode:
- You'll automatically join as a guest
- The header will show "Sync Mode: ON"
- You'll be taken to whatever the Host is viewing
- Your swipe controls are disabled — just watch and enjoy

### Stopping Sync Mode

- **Host**: Click **"Stop Host"** to end the sync session for everyone
- **Guest**: Click **"Leave Sync"** to stop following (only you leave — sync continues for others)

### What Guests CAN do

- **Use the chat** to communicate
- **Go fullscreen** on videos

### What Guests CANNOT do

- Swipe to change items
- Use keyboard arrows to navigate
- Control video playback (play/pause/seek) — the Host controls this for everyone

### Important: Shuffle is disabled

When Sync Mode is on, media shuffle is automatically disabled. This ensures everyone sees items in the same order.

---

## Casting to TV

GhostHub can send media to the TV/monitor connected to the Pi's HDMI port — like Chromecast, but completely local.

### How it works

When your GhostHub Pi is connected to a TV via HDMI, it automatically runs in kiosk mode displaying a fullscreen media viewer. You control what appears on the TV from your phone.

### Requirements

- GhostHub Pi connected to a TV/monitor via HDMI
- You must be the **Admin** to cast

### How to cast

1. Make sure your Pi is connected to a TV via HDMI (it will show a black screen until you cast something)
2. On your phone, claim admin (if not already)
3. Browse to any media item
4. Click the **Cast button** (📺 icon in the header)
5. The media will appear on the TV

### Controlling TV playback

Once casting:
- **Play/pause** on your device — TV follows
- **Seek** in videos — TV syncs position
- **Cast button turns red** when actively casting
- Click the cast button again to **stop casting**

### Resume from where you left off

If you cast a video, the TV will start from your saved progress position (if Continue Watching is enabled).

### Who can cast?

Only the Admin can cast and control the TV. Non-admins won't see the cast button.

---

## Uploading Files

GhostHub lets you upload files to your connected USB drives.

### Gallery Drag-and-Drop (Password Protected, Desktop Only)

On desktop, you can drag and drop files directly onto the Gallery layout:
1. Drag files onto the gallery area
2. Select the target drive and folder in the popup
3. Files upload with progress tracking

This is the only upload method available to non-admins (requires session password if set).

### File Manager / Upload Button (Admin Only)

The **Upload** button in Gallery and the File Manager in Settings both open the same admin-only interface:
1. Click the Settings gear (⚙️) → **"File Manager"** button
2. Or click **Upload** in Gallery toolbar (same modal)

### Features

- **Drive Selection**: See all connected USB drives with free space info
- **Folder Browser**: Navigate existing folders or create new ones
- **File Upload**: Upload single files or entire folders
- **Chunked Uploads**: Large files (>10MB) are automatically uploaded in 5MB chunks for reliability
- **Folder Structure**: When uploading folders, the directory structure is preserved
- **Progress Tracking**: See per-file and overall upload progress
- **Cancel Uploads**: Stop in-progress uploads at any time

### Supported file types

GhostHub accepts any file for upload, but only these formats display natively:
- **Images**: JPG, JPEG, PNG, GIF, WebP, SVG, BMP, ICO
- **Videos**: MP4, WebM, OGV, OGG, MOV

---

## Downloading Media

Download media files from GhostHub to your device. Downloads are password-protected (if a session password is set), but **not** admin-only.

### Single file download

While viewing any media item, use the download button (⬇️) to save that file directly.

### Gallery multi-select download

1. Switch to **Gallery layout** in Settings
2. Tap/click files to select multiple items
3. Click the **Download** button in the selection toolbar
4. Single files download directly; multiple files are bundled as a ZIP

### Category download (Admin Only)

Admins can download entire categories as ZIP files using the download dropdown in the media viewer.

---

## Remote Access (Tunnels)

Access GhostHub from anywhere on the internet using secure tunnels — no port forwarding required.

### When to use tunnels

Tunnels are useful when:
- Your GhostHub Pi is connected to your home WiFi (not just in AP mode)
- You want to access GhostHub from outside your home network
- You want to share access with friends/family remotely

**Note**: Tunnels require your Pi to have internet access. They won't work if the Pi is only running in Access Point mode (creating its own "GhostHub" WiFi network).

### Accessing Tunnel Settings

Click the **Tunnel button** (🔗) in the header (Admin only).

### Supported Providers

1. **Cloudflare Tunnel**: Supported when `cloudflared` is installed and configured
2. **Pinggy**: Easy setup, requires an access token from pinggy.io

### How to use

1. Connect your Pi to your home WiFi (or Ethernet)
2. Open Tunnel settings
3. Select your tunnel provider
4. Enter any required credentials (Pinggy token if using Pinggy)
5. Click **Start Tunnel**
6. Share the generated URL with others — they can access GhostHub from anywhere

---

## WiFi Settings (Admin Only)

If running GhostHub on Raspberry Pi in Access Point mode, you can configure the WiFi network settings.

### Accessing WiFi Settings

Open **Settings** (⚙️) and expand the **WiFi Settings** section.

### What you can change

| Setting | Description |
|---------|-------------|
| **Network Name (SSID)** | The name that appears when connecting (1-32 characters) |
| **Password** | WiFi password (must be 8-63 characters) |
| **Channel** | WiFi channel 1-11 (default: 7) |
| **Country Code** | Two-letter country code for regulatory compliance (default: US) |

### Applying changes

Click **Save WiFi Settings** to apply. Changes require restarting the WiFi service, which will briefly disconnect all connected devices. They'll need to reconnect to the new network.

**Note**: WiFi settings only apply when the Pi is in Access Point mode. If connected to your home router, these settings don't apply.

---

## USB Hotplug (Automatic Detection)

GhostHub automatically detects when you plug in or unplug USB drives.

### What happens when you plug in a USB

1. GhostHub scans the drive for media folders
2. New categories appear automatically
3. Thumbnails are generated in the background (you'll see a loading indicator)

### What happens when you remove a USB

- Categories from that drive become unavailable
- Your progress for those categories is kept (it'll be there when you plug it back in)

### Where USB drives mount

GhostHub automatically mounts USB drives to `/media/pi/DRIVENAME` where DRIVENAME is the label of your USB drive. Just plug in your USB drive and GhostHub handles the rest.

### Thumbnail generation

When GhostHub finds new media, it creates preview thumbnails. For large folders:
- You'll see a spinning indicator on the category card
- A progress bar shows how far along thumbnail generation is
- You can still browse the category while thumbnails are being created

---

## Chat & Commands

GhostHub includes a simple real-time chat. Click the chat panel on the right side to expand it.

### Command Autocomplete

Type `/` in the chat input to see a popup of all available commands. Start typing to filter, use arrow keys to navigate, and press Enter or tap to select. The popup can be dragged by its header if it's in the way.

### Slash Commands

Type these in the chat to perform actions:

| Command | What it does |
|---------|--------------|
| `/help` | Shows all available commands |
| `/myview` | Shares your current view as a clickable link |
| `/view <session_id>` | Jump to what another user is viewing |
| `/search <query>` | Search for files by name across all categories |
| `/find <query>` | Same as /search |
| `/play [seconds]` | Start auto-play mode (images show for X seconds, videos play fully) |
| `/play stop` | Stop auto-play |
| `/random` | Jump to a random item |
| `/add` | Add current item to session playlist |
| `/remove` | Remove current item from session playlist |
| `/kick <user>` | (Admin) Kick a user from the session |

### Auto-Play Mode

Use `/play` to automatically advance through media:
- Images display for the specified time (default: 10 seconds)
- Videos play to the end, then advance
- A green ▶ indicator appears in the corner when active
- Use `/play stop` to turn it off

---

## Admin Features

### Claiming Admin

The first person to click the Admin button (🔒) claims the admin role for the session. Admin can:
- Access Settings
- Access File Manager
- Access Tunnel settings
- Cast to TV
- Kick users
- Clear saved data
- Update GhostHub

### Kicking Users

Admins can kick troublesome users using the `/kick <user_id>` command in chat:
1. The kicked user is disconnected immediately
2. Their IP address is blocked for the current server session
3. User IDs are visible in chat messages (first 8 characters of session ID)

### Releasing Admin

Click the Admin button again to release the admin role, allowing someone else to claim it.

---

## Performance Notes (Raspberry Pi)

GhostHub is optimized to run smoothly on Raspberry Pi:

### What helps performance

- **USB drives**: Store your media on USB, not the SD card — much faster
- **Lazy loading**: Thumbnails load as you scroll, not all at once
- **Background processing**: Thumbnail generation happens without blocking you
- **SQLite database**: Progress and categories stored efficiently

### Large folders

If a category has thousands of files:
- Initial loading takes longer
- You'll see an "Indexing" progress indicator
- Once indexed, browsing is fast
- The index is cached, so it's fast next time

### Memory management

GhostHub automatically cleans up memory:
- Old media elements are removed as you scroll away
- Video resources are released when not visible
- The app uses conservative caching on mobile devices

---

## Limitations

### What GhostHub doesn't do

- **No full user-account system**: Admin is claimed first-come, first-served.
- **No file editing**: You can upload but not edit/delete files from the UI
- **No transcoding**: Videos play in their original format. If your browser can't play a format, it won't work.
- **No offline caching**: Media streams from the device; nothing is saved to your phone.

### Browser compatibility

GhostHub works best in modern browsers:
- Chrome/Edge (recommended)
- Safari (iOS)
- Firefox

### Video format support

Depends on your browser. Generally supported:
- MP4 (H.264)
- WebM

May have issues:
- MKV (some browsers)
- AVI (most browsers)
- MOV (varies)

### Large files

Very large video files (several GB) may be slow to start or buffer. This depends on your network speed to the GhostHub device. GhostHub supports uploads up to 16GB.

---

## Quick Fixes / Troubleshooting

### Media isn't showing up

- **Check the USB**: Make sure it's plugged in properly
- **Refresh the page**: Pull down on mobile or press F5 on desktop
- **Give it time**: Large folders take time to index

### Videos won't play

- **Try a different browser**: Some video formats only work in certain browsers
- **Check the format**: MKV and AVI may not play; try MP4 or WebM

### Thumbnails are missing

- **Wait for generation**: Thumbnails are created in the background
- **Check the progress indicator**: A spinning icon means it's working

### Sync Mode isn't working

- **Check your connection**: Both devices need to reach the GhostHub server
- **Someone might already be Host**: Only one person can be Host at a time
- **Try refreshing**: Sometimes the connection drops — refresh both devices

### Progress isn't being saved

- **Check if it's enabled**: The admin needs to turn on "Save Current Index" in settings
- **Are you the admin?**: Non-admin progress is saved locally in your browser (if session progress is enabled)
- **Try refreshing**: Progress saves periodically; make sure you've given it time

### Cast button doesn't appear

- **Are you admin?**: Only the admin can cast
- **Is the TV connected?**: Make sure your Pi is connected to a TV/monitor via HDMI
- **Check HDMI detection**: The Pi needs to detect a display is connected

### Everything is slow

- **Using SD card for media?**: Move your files to a USB drive
- **Too many large files?**: GhostHub works better with reasonable file sizes
- **Network issues?**: Check your WiFi signal to the Pi

### "Password Required" prompt

If the admin set a session password, you'll need to enter it to:
- View categories
- Use Sync Mode
- Use most commands

Ask whoever set up GhostHub for the password.

### Uploads failing

- **Check disk space**: The File Manager shows free space per drive
- **Large files**: Very large files use chunked upload automatically
- **Network issues**: Poor WiFi can cause chunk upload failures

---

## UI Indicators Reference

| Indicator | Meaning |
|-----------|---------|
| 🎬 on category | Contains videos |
| 🖼️ on category | Images only |
| 📁 placeholder | No thumbnail yet |
| 🔄 spinning | Generating thumbnails |
| Red progress bar | Video playback progress |
| "15/42" badge | Your position when Continue Watching is on |
| ⬆️ arrow | Previous items available |
| ⬇️ arrow | More items available |
| Green ▶ (top-right) | Auto-play is active |
| 📺 button (red) | Currently casting to TV |
| "Sync Mode: HOST" | You're controlling the sync session |
| "Sync Mode: ON" | You're following someone else |
| 🔒 (filled) | You are the admin |
| 🔓 (open) | Admin role available |

---

## Settings (Admin Only)

The admin can configure GhostHub by clicking the ⚙️ gear icon.

### Themes & Layout

| Setting | What it does |
|---------|--------------|
| **Color Theme** | Choose from 5 built-in themes or custom themes |
| **Theme Builder** | Create and save custom color themes |
| **UI Layout** | Default, Streaming, or Gallery layout |
| **Feature Toggles** | Show/hide chat, sync status, indicators, branding |

### WiFi Settings (Pi Only)

| Setting | What it does |
|---------|--------------|
| **Network Name (SSID)** | Name of the GhostHub WiFi network |
| **Password** | WiFi password (8-63 characters) |
| **Channel** | WiFi channel (1-11) |
| **Country Code** | Regulatory country code |

### Server Settings

| Setting | What it does |
|---------|--------------|
| **Session Password** | Password-protects access to GhostHub |
| **Save Current Index** | Enables Continue Watching (remembers your place) |
| **Progress Tracking Mode** | Per-category or per-video progress |
| **Enable Session Progress** | Lets non-admins save their own progress locally |
| **Shuffle Media** | Randomizes order (disabled automatically in Sync Mode) |
| **Enable Subtitles** | Turns on subtitle detection |
| **Debug Mode** | Enables verbose logging (for troubleshooting) |
| **Cache Expiry** | How long to cache category data |
| **Memory Cleanup Interval** | How often to clean up unused resources |

### Admin Actions

| Button | What it does |
|--------|--------------|
| **File Manager** | Opens the file upload/download interface |
| **Clear All Saved Data** | Deletes all progress and cached subtitles |
| **Update GhostHub** | Triggers an update from GitHub (Pi only) |

---

## Final Tips

- **Try different layouts**: Streaming layout is great for movies, Gallery for photos
- **USB is your friend**: Keep media on USB drives for best performance
- **Share with /myview**: The easiest way to show someone a specific item
- **Build playlists**: Use `/add` to create viewing queues for watch parties
- **Don't fight Sync Mode**: If you're a guest, just enjoy the ride
- **Refresh if stuck**: Most issues are solved by a simple page refresh

Happy browsing.
