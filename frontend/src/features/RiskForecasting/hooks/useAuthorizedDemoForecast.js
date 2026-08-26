import { useState, useCallback, useEffect, useRef, useContext } from 'react';
import { DemoForecastingAuthContext } from '../context/DemoForecastingAuthContext.jsx';
import {
  fetchAuthorizedDiseaseForecasts,
  DEMO_FORECASTING_ERROR_CATEGORIES,
} from '../services/demoForecastingApi.js';
import {
  ROLES,
  getRegisteredFarmDistrict,
  getAuthorizedDistricts,
} from '../contracts/viewerContext.js';

/**
 * useAuthorizedDemoForecast
 *
 * Reusable React Hook managing protected role-scoped disease forecasting lifecycle.
 * Enforces frontend pre-validation against ViewerContext and handles secure cancellation,
 * stale-request prevention, 401 automatic logout, and sanitized error states.
 */
export function useAuthorizedDemoForecast() {
  const authContext = useContext(DemoForecastingAuthContext);
  const isDemoEnabled = Boolean(authContext?.isDemoEnabled || authContext?.demoEnabled);
  const isDemoAuthenticated = Boolean(
    authContext?.isDemoAuthenticated || authContext?.status === 'authenticated'
  );
  const viewerContext = authContext?.viewerContext || null;
  const logout = authContext?.logout || (() => {});

  const [status, setStatus] = useState('idle'); // 'idle' | 'loading' | 'success' | 'forbidden' | 'unauthenticated' | 'error'
  const [fmdForecast, setFmdForecast] = useState(null);
  const [lsdForecast, setLsdForecast] = useState(null);
  const [error, setError] = useState(null);

  const abortControllerRef = useRef(null);
  const requestIdRef = useRef(0);
  const isMountedRef = useRef(true);

  // Clear states helper
  const clearForecast = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setFmdForecast(null);
    setLsdForecast(null);
    setError(null);
    setStatus('idle');
  }, []);

  // Track component mount state and context changes
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Automatically reset results when ViewerContext or auth status changes
  useEffect(() => {
    clearForecast();
  }, [viewerContext, isDemoAuthenticated, clearForecast]);

  /**
   * Triggers a new protected role-scoped forecast request.
   */
  const requestForecast = useCallback(
    async ({ year, targetMonth, district, districts } = {}) => {
      if (!isDemoEnabled || !isDemoAuthenticated || !viewerContext) {
        setStatus('unauthenticated');
        setError('Demo authentication required.');
        return;
      }

      // Frontend Safety Validation against ViewerContext
      const role = viewerContext?.role;
      let isAllowed = true;

      if (role === ROLES.FARMER) {
        const regDistrict = getRegisteredFarmDistrict(viewerContext);
        if (district && district.trim().toLowerCase() !== (regDistrict || '').trim().toLowerCase()) {
          isAllowed = false;
        }
      } else if (role === ROLES.VETERINARY_OFFICER || role === ROLES.DAPH_OFFICIAL) {
        const authorized = getAuthorizedDistricts(viewerContext);
        if (district && !authorized.some(a => a.trim().toLowerCase() === district.trim().toLowerCase())) {
          isAllowed = false;
        }
        if (districts && Array.isArray(districts)) {
          for (const d of districts) {
            if (!authorized.some(a => a.trim().toLowerCase() === d.trim().toLowerCase())) {
              isAllowed = false;
              break;
            }
          }
        }
      } else {
        isAllowed = false;
      }

      if (!isAllowed) {
        setFmdForecast(null);
        setLsdForecast(null);
        setError('Forecast access to the requested district is forbidden.');
        setStatus('forbidden');
        return;
      }

      // Abort previous in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;
      const currentRequestId = ++requestIdRef.current;

      setStatus('loading');
      setError(null);

      try {
        const result = await fetchAuthorizedDiseaseForecasts({
          year,
          targetMonth,
          district,
          districts,
          signal: controller.signal,
        });

        if (!isMountedRef.current || currentRequestId !== requestIdRef.current) {
          return;
        }

        setFmdForecast(result.fmd?.data || null);
        setLsdForecast(result.lsd?.data || null);
        setStatus('success');
      } catch (err) {
        if (!isMountedRef.current || currentRequestId !== requestIdRef.current || err?.name === 'AbortError' || err?.category === DEMO_FORECASTING_ERROR_CATEGORIES.ABORTED) {
          return;
        }

        setFmdForecast(null);
        setLsdForecast(null);

        if (err?.category === DEMO_FORECASTING_ERROR_CATEGORIES.UNAUTHENTICATED || err?.status === 401) {
          setError('Your demo session has expired.');
          setStatus('unauthenticated');
          logout();
        } else if (err?.category === DEMO_FORECASTING_ERROR_CATEGORIES.FORBIDDEN || err?.status === 403) {
          setError('Forecast access to the requested district is forbidden.');
          setStatus('forbidden');
        } else {
          setError('Forecast service is currently unavailable.');
          setStatus('error');
        }
      }
    },
    [isDemoEnabled, isDemoAuthenticated, viewerContext, logout]
  );

  return {
    status,
    fmdForecast,
    lsdForecast,
    error,
    requestForecast,
    clearForecast,
  };
}
