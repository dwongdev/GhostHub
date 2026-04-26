import { describe, it, expect } from 'vitest';
import { getSyncPlayMode } from '../../../modules/sync/manager.js';

describe('Sync Play Policy', () => {
    it('uses muted-only mode when there is no user activation', () => {
        expect(getSyncPlayMode({ hasUserActivation: false, prefersUnmuted: true })).toBe('muted-only');
    });

    it('uses muted-only mode when user preference is muted', () => {
        expect(getSyncPlayMode({ hasUserActivation: true, prefersUnmuted: false })).toBe('muted-only');
    });

    it('uses unmuted-first mode when activated and unmuted preferred', () => {
        expect(getSyncPlayMode({ hasUserActivation: true, prefersUnmuted: true })).toBe('unmuted-first');
    });
});
