/**
 * App-level event names for RAGOT bus communication.
 * Keep this file constants-only.
 */

export const APP_EVENTS = Object.freeze({
    CONFIG_LOADED: 'app:config_loaded',
    THEME_CHANGED: 'ui:theme_changed',
    LAYOUT_CHANGED: 'ui:layout_changed',
    FEATURES_CHANGED: 'ui:features_changed',
    SHOW_HIDDEN_TOGGLED: 'ui:show_hidden_toggled',
    VIEWER_SET_MODE: 'media:viewer:set_mode',
    VIEWER_SYNC_UI: 'media:viewer:sync_ui',
    VIEWER_MODE_CHANGED: 'media:viewer_mode_changed',
    FILE_RENAMED_UPDATED: 'media:file_renamed_updated',
    LOCAL_PROGRESS_UPDATE: 'media:local_progress_update'
});
