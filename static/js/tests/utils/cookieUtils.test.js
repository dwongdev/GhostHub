/**
 * Cookie Utilities Tests
 * ----------------------
 * Session identity is built on cookies. If getCookieValue or ensureSessionId
 * break, every user loses their identity, progress, and admin status.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getCookieValue, setCookie, ensureSessionId } from '../../utils/cookieUtils.js';

beforeEach(() => {
    // Clear all cookies
    document.cookie.split(';').forEach(c => {
        const name = c.split('=')[0].trim();
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    });
    vi.clearAllMocks();
});

// ─── getCookieValue ──────────────────────────────────────────────────────────

describe('getCookieValue', () => {
    it('returns null when cookie does not exist', () => {
        expect(getCookieValue('nonexistent')).toBeNull();
    });

    it('returns the value when cookie exists', () => {
        document.cookie = 'session_id=abc123; path=/';
        expect(getCookieValue('session_id')).toBe('abc123');
    });

    it('returns the correct cookie when multiple cookies exist', () => {
        document.cookie = 'theme=dark; path=/';
        document.cookie = 'session_id=xyz789; path=/';
        document.cookie = 'layout=streaming; path=/';
        expect(getCookieValue('session_id')).toBe('xyz789');
        expect(getCookieValue('theme')).toBe('dark');
        expect(getCookieValue('layout')).toBe('streaming');
    });

    it('strips surrounding double quotes from values', () => {
        document.cookie = 'quoted_value="hello-world"; path=/';
        expect(getCookieValue('quoted_value')).toBe('hello-world');
    });

    it('does not strip quotes if only one end has them', () => {
        document.cookie = 'partial="noquote; path=/';
        const value = getCookieValue('partial');
        // Starts with quote but doesn't end with one — should keep as-is
        expect(value).toBe('"noquote');
    });

    it('returns null for empty cookie string', () => {
        // jsdom may have empty cookie string initially
        expect(getCookieValue('')).toBeNull();
    });

    it('does not confuse cookie names that are substrings of each other', () => {
        document.cookie = 'session_id_extra=wrong; path=/';
        document.cookie = 'session_id=correct; path=/';
        expect(getCookieValue('session_id')).toBe('correct');
    });
});

// ─── setCookie ───────────────────────────────────────────────────────────────

describe('setCookie', () => {
    it('sets a cookie that can be read back', () => {
        setCookie('mykey', 'myvalue');
        expect(getCookieValue('mykey')).toBe('myvalue');
    });

    it('overwrites an existing cookie', () => {
        setCookie('overwrite_me', 'first');
        setCookie('overwrite_me', 'second');
        expect(getCookieValue('overwrite_me')).toBe('second');
    });

    it('handles special characters in values', () => {
        setCookie('special', 'value=with=equals');
        // getCookieValue uses regex that stops at semicolons, equals in value should be fine
        // since the cookie format is name=value;
        const val = getCookieValue('special');
        expect(val).toBeTruthy();
    });
});

// ─── ensureSessionId ─────────────────────────────────────────────────────────

describe('ensureSessionId', () => {
    it('generates a session ID when none exists', () => {
        const id = ensureSessionId();
        expect(id).toBeTruthy();
        expect(typeof id).toBe('string');
        expect(id.length).toBeGreaterThan(10); // UUID-like length
    });

    it('returns the existing session ID if already set', () => {
        document.cookie = 'session_id=existing-uuid-1234; path=/';
        const id = ensureSessionId();
        expect(id).toBe('existing-uuid-1234');
    });

    it('persists the generated ID as a cookie', () => {
        const id = ensureSessionId();
        // Second call should return same ID
        const id2 = ensureSessionId();
        expect(id2).toBe(id);
    });

    it('generates unique IDs on separate calls (after clearing)', () => {
        const id1 = ensureSessionId();
        // Clear the cookie
        document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
        const id2 = ensureSessionId();
        expect(id1).not.toBe(id2);
    });

    it('works with crypto.randomUUID when available', () => {
        const mockUUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
        const originalRandomUUID = crypto.randomUUID;
        crypto.randomUUID = vi.fn(() => mockUUID);

        // Clear any existing session
        document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';

        const id = ensureSessionId();
        expect(id).toBe(mockUUID);

        crypto.randomUUID = originalRandomUUID;
    });
});
