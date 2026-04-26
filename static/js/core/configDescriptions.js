/**
 * Configuration Descriptions
 * Provides descriptive text for each configuration setting.
 *
 * Format: {
 *   description: "User-facing description text",
 *   level: "basic" | "advanced"  // Determines visibility in Basic/Advanced mode
 * }
 *
 * Basic: Settings that casual users need (UI, security, basic media)
 * Advanced: Technical settings (performance tuning, rate limits, reconnection logic)
 */

export const CONFIG_DESCRIPTIONS = {
    // Python Config - Advanced (Performance & Technical)
    "python_config.CACHE_EXPIRY": {
        description: "Automatic Refresher: How often the server updates its internal lists of your media. A shorter time shows new files faster, while a longer time saves resources. Default: 300 seconds.",
        level: "advanced"
    },
    "python_config.DEFAULT_PAGE_SIZE": {
        description: "Loading Speed: How many items are loaded at once when you browse. Smaller numbers load faster, while larger numbers show more items per page. Default: 10.",
        level: "advanced"
    },
    "python_config.SESSION_EXPIRY": {
        description: "Login Lifetime: How long you stay logged in before needing to re-authenticate. Default is effectively permanent (1 year).",
        level: "advanced"
    },

    // Python Config - Basic (Media & Playback)
    "python_config.SHUFFLE_MEDIA": {
        description: "Random Play: Automatically mix up the order of videos when you browse a category. Great for music or clip collections. Default: Off.",
        level: "basic"
    },
    "python_config.SAVE_VIDEO_PROGRESS": {
        description: "Remember My Place: Automatically save exactly where you left off in every video. Resume from any device and never lose your spot. Default: On.",
        level: "basic"
    },
    "python_config.SAVE_PROGRESS_FOR_HIDDEN_FILES": {
        description: "Hidden File Progress: Save watch progress for files marked as hidden. Turn this off if you don't want hidden content to appear in 'Continue Watching'. Default: On.",
        level: "basic"
    },
    "python_config.ENABLE_SUBTITLES": {
        description: "Subtitle Support: Automatically detect and show captions for your videos. Works with internal tracks and external .srt or .vtt files. Default: On.",
        level: "basic"
    },
    "python_config.ENABLE_TV_SORTING": {
        description: "TV Episode Sorting: Automatically detect seasons/episodes and keep TV shows (and anime) in the correct order. Default: On.",
        level: "basic"
    },
    "python_config.VIDEO_END_BEHAVIOR": {
        description: "End of Video Action: What should happen when a video finishes? Choose 'Stop', 'Loop' to repeat, or 'Play Next' to start the next one automatically.",
        level: "basic"
    },

    // Python Config - Basic (Security)
    "python_config.SESSION_PASSWORD": {
        description: "Privacy Mode: Set a password to protect your categories from unauthorized access. Leave blank if you want it open for everyone.",
        level: "basic"
    },
    "python_config.ADMIN_PASSWORD": {
        description: "Master Password: The admin password used to unlock restricted settings and take control of the server. Default: admin.",
        level: "basic"
    },

    // Python Config - Advanced (WebSocket & Performance)
    "python_config.WS_RECONNECT_ATTEMPTS": {
        description: "Connection Recovery: How many times the app tries to fix a dropped connection automatically. Default: 10.",
        level: "advanced"
    },
    "python_config.WS_RECONNECT_DELAY": {
        description: "Recovery Wait Time: How long to wait before trying to reconnect after a network glitch. Default: 1000ms.",
        level: "advanced"
    },
    "python_config.WS_RECONNECT_FACTOR": {
        description: "Recovery Spacing: How much longer to wait between each retry attempt. Default: 1.5x.",
        level: "advanced"
    },
    "python_config.MEMORY_CLEANUP_INTERVAL": {
        description: "System Maintenance: How often the server performs deep cleaning of its temporary memory. Default: 60000ms.",
        level: "advanced"
    },
    "python_config.MAX_CACHE_SIZE": {
        description: "Memory Limit: The maximum number of items stored in quick-access memory for faster browsing. Default: 75.",
        level: "advanced"
    },
    "python_config.MAX_CATEGORY_SCAN_DEPTH": {
        description: "Folder Search Depth: How deep GhostHub looks through your folders to find media. Supports better organization but may slow down initial scanning. Default: 6.",
        level: "advanced"
    },

    // Python Config - Advanced (Rate Limiting)
    "python_config.UPLOAD_RATE_LIMIT_PER_CLIENT": {
        description: "Upload Limit Per User: Maximum speed allowed for each person. Prevents one user from slowing down everyone else. Default: 50 Mbps.",
        level: "advanced"
    },
    "python_config.UPLOAD_RATE_LIMIT_GLOBAL": {
        description: "Total Upload Limit: Maximum combined speed for all users. Prevents overworking your network. Default: 100 Mbps.",
        level: "advanced"
    },
    "python_config.DOWNLOAD_RATE_LIMIT_PER_CLIENT": {
        description: "Download Limit Per User: Maximum data speed per user for non-streaming actions. Default: 50 Mbps.",
        level: "advanced"
    },
    "python_config.DOWNLOAD_RATE_LIMIT_GLOBAL": {
        description: "Total Download Limit: Maximum total speed allowed for the entire server to prevent performance issues. Default: 100 Mbps.",
        level: "advanced"
    },

    // Python Config - Advanced (Admin UI Settings Mode)
    "python_config.UI_SETTINGS_MODE": {
        description: "Settings View: Choose 'basic' for essential controls or 'advanced' for deep technical tuning. Default: basic.",
        level: "advanced"
    },
    "python_config.AUTO_OPTIMIZE_FOR_HARDWARE": {
        description: "Hardware Intelligence: Automatically tune performance based on whether you have a 2GB, 4GB, or 8GB Raspberry Pi. Recommended. Default: On.",
        level: "advanced"
    },

    // JavaScript Config - Advanced (Main - Reconnection)
    "javascript_config.main.socket_reconnectionAttempts": {
        description: "App Sync Retries: Max attempts for the main interface to stay synced with the server. Default: 5.",
        level: "advanced"
    },
    "javascript_config.main.socket_reconnectionDelay": {
        description: "App Sync Wait: Initial delay before trying to resync the interface. Default: 2000ms.",
        level: "advanced"
    },
    "javascript_config.main.phase2_init_delay": {
        description: "App Load Speed (P2): Delay before non-essential parts of the app start up. Default: 250ms.",
        level: "advanced"
    },
    "javascript_config.main.phase3_init_delay": {
        description: "App Load Speed (P3): Delay before background features like chat start up. Default: 500ms.",
        level: "advanced"
    },

    // JavaScript Config - Advanced (Core App - Performance)
    "javascript_config.core_app.media_per_page_desktop": {
        description: "Items Per Row (Desktop): How many media items are loaded when you scroll on desktop. Default: 5.",
        level: "advanced"
    },
    "javascript_config.core_app.media_per_page_mobile": {
        description: "Items Per Row (Mobile): How many media items are loaded when you scroll on mobile. Default: 3.",
        level: "advanced"
    },
    "javascript_config.core_app.load_more_threshold_desktop": {
        description: "Infinite Scroll Limit (Desktop): How early to load the next page of items on desktop. Default: 3.",
        level: "advanced"
    },
    "javascript_config.core_app.load_more_threshold_mobile": {
        description: "Infinite Scroll Limit (Mobile): How early to load the next page of items on mobile. Default: 2.",
        level: "advanced"
    },
    "javascript_config.core_app.render_window_size": {
        description: "Visibility Window: How many off-screen items are kept 'ready' to show. Higher uses more memory. Default: 0.",
        level: "advanced"
    },
    "javascript_config.core_app.mobile_cleanup_interval": {
        description: "Mobile Memory Wash: How often to clear out old data to keep the mobile app running smooth. Default: 60000ms.",
        level: "advanced"
    },
    "javascript_config.core_app.mobile_fetch_timeout": {
        description: "Mobile Network Timeout: How long to wait for data on mobile before giving up. Default: 15000ms.",
        level: "advanced"
    },
    "javascript_config.core_app.fullscreen_check_interval": {
        description: "Mobile UI Polish: How often the app ensures controls are perfectly sized for mobile screens. Default: 2000ms.",
        level: "advanced"
    },

    // JavaScript Config - Advanced (Sync Manager - Reconnection)
    "javascript_config.sync_manager.socket_reconnectionAttempts": {
        description: "Sync Mode Retries: Max attempts to keep your 'Watch Together' session active during drops. Default: 10.",
        level: "advanced"
    },
    "javascript_config.sync_manager.socket_reconnectionDelay": {
        description: "Sync Mode Recovery: Initial wait time to fix a sync issue. Default: 1000ms.",
        level: "advanced"
    },
    "javascript_config.sync_manager.manual_maxReconnectAttempts": {
        description: "Custom Sync Recovery: Extra attempts to fix sync when standard methods fail. Default: 10.",
        level: "advanced"
    },

    // JavaScript Config - User Preferences
    "javascript_config.ui.theme": {
        description: "Personal Style: Choose your favorite color theme. Note: This can be changed individually per device.",
        level: "basic"
    },
    "javascript_config.ui.layout": {
        description: "Interface Mode: Netflix-style horizontal rows (Streaming) or photo-grid style browsing (Gallery).",
        level: "basic"
    },
    "javascript_config.ui.features.chat": {
        description: "Community Chat: Show or hide the sidebar for live watch-together chat. Default: On.",
        level: "basic"
    },
    "javascript_config.ui.features.headerBranding": {
        description: "GhostHub Logo: Show the branding and app title in the top bar. Default: On.",
        level: "basic"
    },
    "javascript_config.ui.features.search": {
        description: "Search Bar: Show the search icon to let people find movies instantly. Default: On.",
        level: "basic"
    },

    // JavaScript Config - Basic (GhostStream Transcoding)
    "javascript_config.ghoststream.preferTranscode": {
        description: "Smart Streaming: Always optimize videos for your network instead of playing the large original file. Default: Off.",
        level: "advanced"
    },
    "javascript_config.ghoststream.preferredQuality": {
        description: "Favorite Picture Quality: Default resolution for optimized streaming (Original, 1080p, 720p, etc.). Default: Original.",
        level: "basic"
    },
    "javascript_config.ghoststream.autoTranscodeFormats": {
        description: "Universal Compatibility: Automatically fix videos that don't normally play in browsers (MKV, AVI, etc.). Default: On.",
        level: "basic"
    },
    "javascript_config.ghoststream.maxBitrate": {
        description: "Streaming Speed Limit: Cap the data usage for videos to save bandwidth. Default: Auto.",
        level: "advanced"
    },
    "javascript_config.ghoststream.autoTranscodeHighBitrate": {
        description: "High Quality Optimizer: Automatically smooth out very high-quality videos that might stutter. Default: On.",
        level: "advanced"
    },
    "javascript_config.ghoststream.enableABR": {
        description: "Adaptive Streaming: Automatically switch quality if your internet slows down, preventing buffering. Default: Off.",
        level: "advanced"
    }
};
