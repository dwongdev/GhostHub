/**
 * Playback Module Index
 * Re-exports all playback control functionality.
 * 
 * @module playback
 */

// Auto-Play
export {
    initAutoPlayManager,
    toggleAutoPlay,
    handleAutoPlay,
    isAutoPlayActive,
    getAutoPlayInterval,
    updateAutoPlayIndicator
} from './autoPlay.js';
