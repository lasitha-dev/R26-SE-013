/**
 * Safe Browser Session Storage Helper for Demo Authentication.
 *
 * Rules:
 * - Stores ONLY the access token for the current browser tab/session.
 * - Key namespaced to: 'r26.riskForecasting.demoAccessToken'.
 * - Never stores passwords, ViewerContext objects, or database credentials.
 * - Protects against missing window / sessionStorage in SSR and test environments.
 * - Rejects and clears empty, whitespace-only, or non-string values.
 */

export const DEMO_ACCESS_TOKEN_KEY = 'r26.riskForecasting.demoAccessToken';

/**
 * Checks if browser sessionStorage is available and accessible.
 * @returns {boolean}
 */
function isSessionStorageAvailable() {
  try {
    return (
      typeof window !== 'undefined' &&
      typeof window.sessionStorage !== 'undefined' &&
      window.sessionStorage !== null
    );
  } catch (_) {
    return false;
  }
}

/**
 * Reads and validates the stored demo access token from sessionStorage.
 * Clears and rejects invalid, non-string, or whitespace-only tokens.
 *
 * @returns {string | null} Valid access token string or null
 */
export function readDemoAccessToken() {
  if (!isSessionStorageAvailable()) {
    return null;
  }

  try {
    const value = window.sessionStorage.getItem(DEMO_ACCESS_TOKEN_KEY);
    if (typeof value !== 'string' || value.trim() === '') {
      clearDemoAccessToken();
      return null;
    }
    return value.trim();
  } catch (_) {
    return null;
  }
}

/**
 * Writes a valid demo access token string to sessionStorage.
 * Clears stored token and returns false if token is invalid, non-string, or empty.
 *
 * @param {string} token
 * @returns {boolean} True if successfully written, false otherwise
 */
export function writeDemoAccessToken(token) {
  if (typeof token !== 'string' || token.trim() === '') {
    clearDemoAccessToken();
    return false;
  }

  if (!isSessionStorageAvailable()) {
    return false;
  }

  try {
    window.sessionStorage.setItem(DEMO_ACCESS_TOKEN_KEY, token.trim());
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Safely removes the stored demo access token from sessionStorage.
 */
export function clearDemoAccessToken() {
  if (!isSessionStorageAvailable()) {
    return;
  }

  try {
    window.sessionStorage.removeItem(DEMO_ACCESS_TOKEN_KEY);
  } catch (_) {
    // Ignore storage removal errors in restricted contexts
  }
}
