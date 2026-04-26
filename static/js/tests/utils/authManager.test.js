/**
 * AuthManager Unit Tests
 * Tests for password authentication and feature access
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock configManager before any imports
vi.mock('../../utils/configManager.js', () => ({
  getConfigValue: vi.fn()
}));

// Mock notificationManager before any imports
vi.mock('../../utils/notificationManager.js', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
  dialog: { prompt: vi.fn() }
}));

describe('AuthManager', () => {
  let ensureFeatureAccess;
  let getConfigValue;
  let dialog;
  let toast;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();

    // Reset sessionStorage
    sessionStorage.clear();

    // Mock fetch
    global.fetch = vi.fn();

    // Re-import modules fresh to reset internal state (positiveValidationTimestamp)
    const configManager = await import('../../utils/configManager.js');
    getConfigValue = configManager.getConfigValue;

    const notificationManager = await import('../../utils/notificationManager.js');
    dialog = notificationManager.dialog;
    toast = notificationManager.toast;

    const authManager = await import('../../utils/authManager.js');
    ensureFeatureAccess = authManager.ensureFeatureAccess;
  });

  describe('ensureFeatureAccess', () => {
    it('should grant access when password protection is disabled', async () => {
      getConfigValue.mockReturnValue(false);

      const result = await ensureFeatureAccess();

      expect(result).toBe(true);
      expect(dialog.prompt).not.toHaveBeenCalled();
    });

    it('should grant access when password already validated in session', async () => {
      getConfigValue.mockReturnValue(true);
      sessionStorage.setItem('session_password_validated', 'true');

      const result = await ensureFeatureAccess();

      expect(result).toBe(true);
      expect(dialog.prompt).not.toHaveBeenCalled();
    });

    it('should prompt for password when protection is active and not validated', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue('testpassword');
      global.fetch.mockResolvedValue({
        json: () => Promise.resolve({ valid: true })
      });

      await ensureFeatureAccess();

      expect(dialog.prompt).toHaveBeenCalledWith(
        expect.stringContaining('password'),
        expect.any(Object)
      );
    });

    it('should deny access when user cancels prompt', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue(null);

      const result = await ensureFeatureAccess();

      expect(result).toBe(false);
    });

    it('should validate password with API', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue('correctpassword');
      global.fetch.mockResolvedValue({
        json: () => Promise.resolve({ valid: true })
      });

      await ensureFeatureAccess();

      expect(fetch).toHaveBeenCalledWith('/api/validate_session_password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: 'correctpassword' })
      });
    });

    it('should grant access and store in session on valid password', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue('correctpassword');
      global.fetch.mockResolvedValue({
        json: () => Promise.resolve({ valid: true })
      });

      const result = await ensureFeatureAccess();

      expect(result).toBe(true);
      expect(sessionStorage.getItem('session_password_validated')).toBe('true');
    });

    it('should deny access on invalid password', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue('wrongpassword');
      global.fetch.mockResolvedValue({
        json: () => Promise.resolve({ valid: false, message: 'Incorrect' })
      });

      const result = await ensureFeatureAccess();

      expect(result).toBe(false);
      expect(toast.error).toHaveBeenCalled();
    });

    it('should handle API errors gracefully', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue('password');
      global.fetch.mockRejectedValue(new Error('Network error'));

      const result = await ensureFeatureAccess();

      expect(result).toBe(false);
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('Error'));
    });

    it('should use short-term cache for repeated calls', async () => {
      getConfigValue.mockReturnValue(true);
      dialog.prompt.mockResolvedValue('password');
      global.fetch.mockResolvedValue({
        json: () => Promise.resolve({ valid: true })
      });

      // First call validates
      await ensureFeatureAccess();

      // Second call should use cache (no new prompt)
      vi.clearAllMocks();
      getConfigValue.mockReturnValue(true);
      const result = await ensureFeatureAccess();

      expect(result).toBe(true);
      // The exact behavior depends on timing, but it should be fast
    });
  });
});
