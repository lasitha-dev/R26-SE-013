/**
 * Narrowly scoped frontend API client module for Demo Authentication.
 *
 * Features:
 * - loginDemoUser: POST /api/v1/demo-auth/login
 * - fetchDemoViewerContext: GET /api/v1/demo-auth/me
 *
 * Rules:
 * - Feature flag VITE_FORECASTING_DEMO_ENABLED requires exact string "true".
 * - Validates response structures using validateViewerContext contract.
 * - Does NOT decode JWTs in frontend code.
 * - Sanitizes all error messages to protect credentials, tokens, and backend details.
 * - Contains NO registration, password reset, refresh-token, seed, or admin methods.
 */

import { validateViewerContext } from '../contracts/viewerContext.js';

const API_BASE = import.meta.env?.VITE_API_URL || '';

/**
 * Custom error class for Demo Authentication API failures.
 * Guarantees message is sanitized and user-facing.
 */
export class DemoAuthApiError extends Error {
  constructor({ message, status = null, code = null }) {
    super(message);
    this.name = 'DemoAuthApiError';
    this.status = status;
    this.code = code;
  }
}

/**
 * Checks whether Disease Forecasting Demo Mode is explicitly enabled.
 * Requires exact string equality with "true".
 *
 * @returns {boolean}
 */
export function isDemoModeEnabled() {
  const flag = import.meta.env?.VITE_FORECASTING_DEMO_ENABLED;
  return flag === 'true';
}

/**
 * Sanitizes backend HTTP error status into safe, user-facing error message.
 *
 * @param {number | null} status
 * @param {string} fallbackMsg
 * @returns {string}
 */
function sanitizeAuthErrorMessage(status, fallbackMsg = 'Demo authentication is currently unavailable.') {
  if (status === 401) {
    return 'Invalid login name or password.';
  }
  return fallbackMsg;
}

/**
 * Internal single-pass JSON fetch wrapper for demo-auth endpoints.
 */
async function requestDemoAuthApi(url, options = {}) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    throw new DemoAuthApiError({
      message: 'Demo authentication is currently unavailable.',
      status: null,
      code: 'NETWORK_ERROR',
    });
  }

  if (!res.ok) {
    if (res.status === 401) {
      throw new DemoAuthApiError({
        message: 'Invalid login name or password.',
        status: 401,
        code: 'UNAUTHORIZED',
      });
    }
    throw new DemoAuthApiError({
      message: sanitizeAuthErrorMessage(res.status),
      status: res.status,
      code: 'HTTP_ERROR',
    });
  }

  try {
    return await res.json();
  } catch (_) {
    throw new DemoAuthApiError({
      message: 'Demo authentication is currently unavailable.',
      status: res.status,
      code: 'PARSE_ERROR',
    });
  }
}

/**
 * Authenticates a demo user via login credentials.
 * Calls POST /api/v1/demo-auth/login.
 *
 * @param {Object} credentials - { loginName, password }
 * @returns {Promise<{ accessToken: string, tokenType: "bearer", expiresIn: number }>}
 */
export async function loginDemoUser({ loginName, password } = {}) {
  if (!isDemoModeEnabled()) {
    throw new DemoAuthApiError({
      message: 'Demo authentication is disabled.',
      status: null,
      code: 'DEMO_DISABLED',
    });
  }

  if (typeof loginName !== 'string' || loginName.trim() === '' || typeof password !== 'string' || password === '') {
    throw new DemoAuthApiError({
      message: 'Invalid login name or password.',
      status: 400,
      code: 'BAD_REQUEST',
    });
  }

  const endpoint = `${API_BASE}/api/v1/demo-auth/login`;
  const data = await requestDemoAuthApi(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ loginName: loginName.trim(), password }),
  });

  const { accessToken, tokenType, expiresIn } = data || {};

  if (
    typeof accessToken !== 'string' ||
    accessToken.trim() === '' ||
    tokenType !== 'bearer' ||
    typeof expiresIn !== 'number' ||
    expiresIn <= 0
  ) {
    throw new DemoAuthApiError({
      message: 'Demo authentication is currently unavailable.',
      status: 500,
      code: 'INVALID_RESPONSE',
    });
  }

  return {
    accessToken: accessToken.trim(),
    tokenType: 'bearer',
    expiresIn,
  };
}

/**
 * Fetches and validates the trusted ViewerContext for an authenticated session token.
 * Calls GET /api/v1/demo-auth/me.
 * Must NOT decode the JWT token.
 *
 * @param {string} accessToken
 * @returns {Promise<Object>} Validated and normalized ViewerContext
 */
export async function fetchDemoViewerContext(accessToken) {
  if (!isDemoModeEnabled()) {
    throw new DemoAuthApiError({
      message: 'Demo authentication is disabled.',
      status: null,
      code: 'DEMO_DISABLED',
    });
  }

  if (typeof accessToken !== 'string' || accessToken.trim() === '') {
    throw new DemoAuthApiError({
      message: 'Your demo session has expired.',
      status: 401,
      code: 'UNAUTHORIZED',
    });
  }

  const endpoint = `${API_BASE}/api/v1/demo-auth/me`;
  let data;
  try {
    data = await requestDemoAuthApi(endpoint, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken.trim()}`,
      },
    });
  } catch (err) {
    if (err.status === 401) {
      throw new DemoAuthApiError({
        message: 'Your demo session has expired.',
        status: 401,
        code: 'SESSION_EXPIRED',
      });
    }
    throw err;
  }

  const { valid, reason, normalizedContext } = validateViewerContext(data);

  if (!valid || !normalizedContext) {
    throw new DemoAuthApiError({
      message: 'Demo authentication is currently unavailable.',
      status: 422,
      code: 'CONTRACT_VIOLATION',
    });
  }

  return normalizedContext;
}
