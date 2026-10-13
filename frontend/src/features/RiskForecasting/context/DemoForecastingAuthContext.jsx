/**
 * Isolated React Auth Context and Provider for Disease Forecasting Demo Mode.
 *
 * Provides fail-closed, session-based authentication state management.
 */

import React, { createContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  isDemoModeEnabled,
  loginDemoUser,
  fetchDemoViewerContext,
  DemoAuthApiError,
} from '../services/demoAuthApi.js';
import {
  readDemoAccessToken,
  writeDemoAccessToken,
  clearDemoAccessToken,
} from '../services/demoSessionStorage.js';

export const DemoForecastingAuthContext = createContext({
  demoEnabled: false,
  status: 'disabled',
  viewerContext: null,
  error: null,
  login: async () => {},
  logout: () => {},
  refreshViewerContext: async () => {},
});

export const AUTH_STATUS = Object.freeze({
  DISABLED: 'disabled',
  CHECKING: 'checking',
  UNAUTHENTICATED: 'unauthenticated',
  AUTHENTICATED: 'authenticated',
  ERROR: 'error',
});

export function DemoForecastingAuthProvider({ children }) {
  const demoEnabled = isDemoModeEnabled();
  const [status, setStatus] = useState(demoEnabled ? AUTH_STATUS.CHECKING : AUTH_STATUS.DISABLED);
  const [viewerContext, setViewerContext] = useState(null);
  const [error, setError] = useState(null);
  const isPendingRef = useRef(false);

  /**
   * Initializes or verifies existing session token from sessionStorage.
   */
  const initializeSession = useCallback(async () => {
    if (!demoEnabled) {
      setStatus(AUTH_STATUS.DISABLED);
      setViewerContext(null);
      setError(null);
      return;
    }

    const token = readDemoAccessToken();

    if (!token) {
      setStatus(AUTH_STATUS.UNAUTHENTICATED);
      setViewerContext(null);
      setError(null);
      return;
    }

    setStatus(AUTH_STATUS.CHECKING);
    try {
      const context = await fetchDemoViewerContext(token);
      setViewerContext(context);
      setStatus(AUTH_STATUS.AUTHENTICATED);
      setError(null);
    } catch (err) {
      clearDemoAccessToken();
      setViewerContext(null);

      if (err instanceof DemoAuthApiError && err.status === 401) {
        setStatus(AUTH_STATUS.UNAUTHENTICATED);
        setError('Your demo session has expired.');
      } else {
        setStatus(AUTH_STATUS.ERROR);
        setError(err.message || 'Demo authentication is currently unavailable.');
      }
    }
  }, [demoEnabled]);

  useEffect(() => {
    initializeSession();
  }, [initializeSession]);

  /**
   * Logs in demo user, stores access token in sessionStorage, and fetches ViewerContext.
   */
  const login = useCallback(
    async (loginName, password) => {
      if (!demoEnabled) {
        throw new Error('Demo authentication is disabled.');
      }

      if (isPendingRef.current) {
        return;
      }

      isPendingRef.current = true;
      setStatus(AUTH_STATUS.CHECKING);
      setError(null);

      try {
        const authData = await loginDemoUser({ loginName, password });
        writeDemoAccessToken(authData.accessToken);

        const context = await fetchDemoViewerContext(authData.accessToken);
        setViewerContext(context);
        setStatus(AUTH_STATUS.AUTHENTICATED);
        setError(null);
        return context;
      } catch (err) {
        clearDemoAccessToken();
        setViewerContext(null);

        const is401 = err instanceof DemoAuthApiError && err.status === 401;
        setStatus(is401 ? AUTH_STATUS.UNAUTHENTICATED : AUTH_STATUS.ERROR);
        const safeError = err.message || 'Demo authentication is currently unavailable.';
        setError(safeError);
        throw new Error(safeError);
      } finally {
        isPendingRef.current = false;
      }
    },
    [demoEnabled]
  );

  /**
   * Clears session token and resets state to unauthenticated.
   */
  const logout = useCallback(() => {
    clearDemoAccessToken();
    setViewerContext(null);
    setError(null);
    setStatus(demoEnabled ? AUTH_STATUS.UNAUTHENTICATED : AUTH_STATUS.DISABLED);
  }, [demoEnabled]);

  /**
   * Reloads ViewerContext using stored session token.
   */
  const refreshViewerContext = useCallback(async () => {
    if (!demoEnabled) {
      return null;
    }

    const token = readDemoAccessToken();
    if (!token) {
      logout();
      return null;
    }

    try {
      const context = await fetchDemoViewerContext(token);
      setViewerContext(context);
      setStatus(AUTH_STATUS.AUTHENTICATED);
      setError(null);
      return context;
    } catch (err) {
      clearDemoAccessToken();
      setViewerContext(null);

      if (err instanceof DemoAuthApiError && err.status === 401) {
        setStatus(AUTH_STATUS.UNAUTHENTICATED);
        setError('Your demo session has expired.');
      } else {
        setStatus(AUTH_STATUS.ERROR);
        setError(err.message || 'Demo authentication is currently unavailable.');
      }
      return null;
    }
  }, [demoEnabled, logout]);

  const value = useMemo(
    () => ({
      demoEnabled,
      isDemoEnabled: Boolean(demoEnabled),
      status,
      isDemoAuthenticated: status === AUTH_STATUS.AUTHENTICATED,
      viewerContext,
      error,
      login,
      logout,
      refreshViewerContext,
    }),
    [demoEnabled, status, viewerContext, error, login, logout, refreshViewerContext]
  );

  return (
    <DemoForecastingAuthContext.Provider value={value}>
      {children}
    </DemoForecastingAuthContext.Provider>
  );
}

DemoForecastingAuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};
