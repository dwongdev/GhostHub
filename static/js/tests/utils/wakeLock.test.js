/**
 * Wake Lock Tests
 * ---------------
 * The wake lock prevents the screen from sleeping during video playback.
 * On mobile devices and Raspberry Pi kiosk mode, a broken wake lock means
 * the screen goes dark mid-movie. Multiple components (viewer, PiP, TV cast)
 * can independently request wake locks — ref counting must be correct.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the ragot Module class before importing wakeLock
vi.mock('../libs/ragot.esm.min.js', () => ({
    Module: class {
        constructor() { }
        start() { }
        on() { }
        addCleanup() { }
    }
}));

let requestWakeLock, releaseWakeLock, isWakeLockActive, forceReleaseWakeLock;

beforeEach(async () => {
    vi.resetModules();

    // Re-mock ragot for each test
    vi.mock('../libs/ragot.esm.min.js', () => ({
        Module: class {
            constructor() { }
            start() { }
            on() { }
            addCleanup() { }
        }
    }));

    // Mock the Wake Lock API
    const mockWakeLock = {
        release: vi.fn().mockResolvedValue(undefined),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
    };

    Object.defineProperty(navigator, 'wakeLock', {
        value: {
            request: vi.fn().mockResolvedValue(mockWakeLock),
        },
        configurable: true,
        writable: true,
    });

    const mod = await import('../../utils/wakeLock.js');
    requestWakeLock = mod.requestWakeLock;
    releaseWakeLock = mod.releaseWakeLock;
    isWakeLockActive = mod.isWakeLockActive;
    forceReleaseWakeLock = mod.forceReleaseWakeLock;
});

// ─── requestWakeLock ─────────────────────────────────────────────────────────

describe('requestWakeLock', () => {
    it('returns true when wake lock is acquired', async () => {
        const result = await requestWakeLock();
        expect(result).toBe(true);
    });

    it('calls navigator.wakeLock.request with screen type', async () => {
        await requestWakeLock();
        expect(navigator.wakeLock.request).toHaveBeenCalledWith('screen');
    });

    it('returns true without re-requesting when already active', async () => {
        await requestWakeLock();
        navigator.wakeLock.request.mockClear();

        const result = await requestWakeLock();
        expect(result).toBe(true);
        // Should NOT call request again - use existing lock
        expect(navigator.wakeLock.request).not.toHaveBeenCalled();
    });

    it('returns false when Wake Lock API is not supported', async () => {
        delete navigator.wakeLock;
        const result = await requestWakeLock();
        expect(result).toBe(false);
    });

    it('returns false when request throws', async () => {
        navigator.wakeLock.request.mockRejectedValue(
            new DOMException('Not allowed', 'NotAllowedError')
        );
        const result = await requestWakeLock();
        expect(result).toBe(false);
    });
});

// ─── releaseWakeLock ─────────────────────────────────────────────────────────

describe('releaseWakeLock', () => {
    it('does not release when other components still need it', async () => {
        // Two components request wake lock
        await requestWakeLock();
        await requestWakeLock();

        // One releases — lock should stay
        releaseWakeLock();
        expect(isWakeLockActive()).toBe(true);
    });

    it('releases when last component releases', async () => {
        await requestWakeLock();
        releaseWakeLock();
        expect(isWakeLockActive()).toBe(false);
    });

    it('is safe to call when no wake lock is active', () => {
        // Should not throw
        releaseWakeLock();
        expect(isWakeLockActive()).toBe(false);
    });
});

// ─── forceReleaseWakeLock ────────────────────────────────────────────────────

describe('forceReleaseWakeLock', () => {
    it('releases regardless of request count', async () => {
        await requestWakeLock();
        await requestWakeLock();
        await requestWakeLock();

        forceReleaseWakeLock();
        expect(isWakeLockActive()).toBe(false);
    });

    it('is safe to call when no wake lock exists', () => {
        forceReleaseWakeLock();
        expect(isWakeLockActive()).toBe(false);
    });
});

// ─── isWakeLockActive ────────────────────────────────────────────────────────

describe('isWakeLockActive', () => {
    it('returns false initially', () => {
        expect(isWakeLockActive()).toBe(false);
    });

    it('returns true after successful request', async () => {
        await requestWakeLock();
        expect(isWakeLockActive()).toBe(true);
    });
});
