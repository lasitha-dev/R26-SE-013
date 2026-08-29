import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import { DemoForecastingAuthProvider, AUTH_STATUS } from './DemoForecastingAuthContext.jsx';
import { useDemoForecastingAuth } from '../hooks/useDemoForecastingAuth.js';
import {
  DEMO_ACCESS_TOKEN_KEY,
  writeDemoAccessToken,
  readDemoAccessToken,
} from '../services/demoSessionStorage.js';

function TestAuthConsumer({ onRender }) {
  const auth = useDemoForecastingAuth();
  if (onRender) {
    onRender(auth);
  }

  return (
    <div>
      <span data-testid="demo-enabled">{String(auth.demoEnabled)}</span>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="role">{auth.viewerContext?.role || 'none'}</span>
      <span data-testid="error">{auth.error || 'none'}</span>
      <button data-testid="login-btn" onClick={() => auth.login('demo_farmer_jaffna', 'Pass123!').catch(() => {})}>
        Login
      </button>
      <button data-testid="logout-btn" onClick={() => auth.logout()}>
        Logout
      </button>
      <button data-testid="refresh-btn" onClick={() => auth.refreshViewerContext()}>
        Refresh
      </button>
    </div>
  );
}

const mockValidFarmerContext = {
  userId: 'farmer_jaffna_001',
  role: 'FARMER',
  authorization: {
    scopeLevel: 'FARM',
    registeredFarmDistrict: 'Jaffna',
    authorizedDistricts: ['Jaffna'],
    assignedFarmIds: [],
  },
  permissions: {
    viewDataQuality: false,
    viewModelTransparency: false,
    manageAlerts: false,
    recordResponse: false,
    viewReports: false,
  },
};

const mockValidVetContext = {
  userId: 'vet_north_001',
  role: 'VETERINARY_OFFICER',
  authorization: {
    scopeLevel: 'PROVINCE',
    registeredFarmDistrict: null,
    authorizedDistricts: ['Jaffna', 'Kilinochchi'],
    assignedFarmIds: ['FARM_001'],
  },
  permissions: {
    viewDataQuality: true,
    viewModelTransparency: true,
    manageAlerts: true,
    recordResponse: true,
    viewReports: true,
  },
};

describe('DemoForecastingAuthContext React Provider & Hook Tests', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // Test 2: Disabled mode makes zero network calls
  it('Requirement 2: Disabled mode sets status="disabled" and makes zero network calls', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'false');
    writeDemoAccessToken('stored.token.123');

    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer />
      </DemoForecastingAuthProvider>
    );

    expect(screen.getByTestId('demo-enabled').textContent).toBe('false');
    expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.DISABLED);
    expect(fetch).not.toHaveBeenCalled();
  });

  // Test 3: Missing token becomes unauthenticated
  it('Requirement 3: Enabled mode with missing token becomes status="unauthenticated"', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');

    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.UNAUTHENTICATED);
    });
    expect(screen.getByTestId('role').textContent).toBe('none');
    expect(fetch).not.toHaveBeenCalled();
  });

  // Test 4 & 9: Successful login calls login then /me and sets authenticated state
  it('Requirement 4 & 9: Successful login calls POST /login then GET /me, storing ViewerContext in memory', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');

    // Mock 1: Login POST
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        accessToken: 'new.bearer.access.token',
        tokenType: 'bearer',
        expiresIn: 1800,
      }),
    });

    // Mock 2: GET /me
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidFarmerContext,
    });

    let authRef = null;
    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer onRender={(auth) => (authRef = auth)} />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.UNAUTHENTICATED);
    });

    await act(async () => {
      await authRef.login('demo_farmer_jaffna', 'FarmerPass123!');
    });

    expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.AUTHENTICATED);
    expect(screen.getByTestId('role').textContent).toBe('FARMER');
    expect(readDemoAccessToken()).toBe('new.bearer.access.token');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  // Test 7: Password is never stored
  it('Requirement 7: Password is never stored in sessionStorage, localStorage, or React state', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    const secretPassword = 'SuperSecretPassword999!';

    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        accessToken: 'access.token.777',
        tokenType: 'bearer',
        expiresIn: 1800,
      }),
    });

    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidFarmerContext,
    });

    let authRef = null;
    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer onRender={(auth) => (authRef = auth)} />
      </DemoForecastingAuthProvider>
    );

    await act(async () => {
      await authRef.login('demo_farmer_jaffna', secretPassword);
    });

    expect(sessionStorage.getItem(DEMO_ACCESS_TOKEN_KEY)).not.toContain(secretPassword);
    expect(localStorage.getItem(DEMO_ACCESS_TOKEN_KEY)).toBeNull();
    expect(JSON.stringify(authRef.viewerContext)).not.toContain(secretPassword);
  });

  // Test 10: Invalid ViewerContext response fails closed and clears token
  it('Requirement 10: Invalid ViewerContext response fails closed and clears stored token', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    writeDemoAccessToken('existing.token');

    // Invalid ViewerContext (missing role)
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ invalidField: 'malformed_contract' }),
    });

    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.ERROR);
    });

    expect(readDemoAccessToken()).toBeNull();
    expect(screen.getByTestId('role').textContent).toBe('none');
  });

  // Test 12: Stored-token /me 401 clears session
  it('Requirement 12: Stored token /me 401 clears session and becomes unauthenticated', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    writeDemoAccessToken('expired.token.401');

    fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Token expired' }),
    });

    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.UNAUTHENTICATED);
    });

    expect(readDemoAccessToken()).toBeNull();
    expect(screen.getByTestId('error').textContent).toBe('Your demo session has expired.');
  });

  // Test 13: /me 503/network failure produces sanitized error state
  it('Requirement 13: /me 503 service failure produces sanitized error state', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    writeDemoAccessToken('valid.token.503');

    fetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Database unavailable' }),
    });

    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.ERROR);
    });

    expect(screen.getByTestId('error').textContent).toBe('Demo authentication is currently unavailable.');
  });

  // Test 14: Logout clears token and ViewerContext without API writes
  it('Requirement 14: Logout clears token and ViewerContext without sending backend write request', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    writeDemoAccessToken('active.token');

    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidFarmerContext,
    });

    let authRef = null;
    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer onRender={(auth) => (authRef = auth)} />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.AUTHENTICATED);
    });

    const initialFetchCalls = fetch.mock.calls.length;

    act(() => {
      authRef.logout();
    });

    expect(screen.getByTestId('status').textContent).toBe(AUTH_STATUS.UNAUTHENTICATED);
    expect(screen.getByTestId('role').textContent).toBe('none');
    expect(readDemoAccessToken()).toBeNull();
    // Verify no logout network request was sent
    expect(fetch).toHaveBeenCalledTimes(initialFetchCalls);
  });

  // Test 15 & 16: Refresh reloads the latest ViewerContext and replaces old context
  it('Requirement 15 & 16: Refresh reloads latest ViewerContext and replaces old in-memory context', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    writeDemoAccessToken('valid.token.refresh');

    // Initial mount: Farmer role
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidFarmerContext,
    });

    let authRef = null;
    render(
      <DemoForecastingAuthProvider>
        <TestAuthConsumer onRender={(auth) => (authRef = auth)} />
      </DemoForecastingAuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('role').textContent).toBe('FARMER');
    });

    // Mock 2 for refresh: Role updated server-side to VETERINARY_OFFICER
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockValidVetContext,
    });

    await act(async () => {
      await authRef.refreshViewerContext();
    });

    expect(screen.getByTestId('role').textContent).toBe('VETERINARY_OFFICER');
    expect(authRef.viewerContext.authorization.authorizedDistricts).toEqual(['Jaffna', 'Kilinochchi']);
  });
});
