/**
 * Reusable React Hook Foundation for Protected Synthetic Operational Data.
 *
 * Provides automated lifecycle management, stale request cancelling, and fail-closed state
 * for farms, surveillance-records, alerts, and response-tasks.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useDemoForecastingAuth } from './useDemoForecastingAuth.js';
import { AUTH_STATUS } from '../context/DemoForecastingAuthContext.jsx';
import {
  fetchDemoFarms,
  fetchDemoSurveillanceRecords,
  fetchDemoAlerts,
  fetchDemoResponseTasks,
  DemoOperationalApiError,
  OPERATIONAL_ERROR_CATEGORIES,
} from '../services/demoOperationalApi.js';

export const OPERATIONAL_STATUS = Object.freeze({
  IDLE: 'idle',
  LOADING: 'loading',
  SUCCESS: 'success',
  EMPTY: 'empty',
  FORBIDDEN: 'forbidden',
  UNAUTHENTICATED: 'unauthenticated',
  ERROR: 'error',
});

const RESOURCE_FETCHERS = Object.freeze({
  farms: (opts) => fetchDemoFarms(opts),
  'surveillance-records': (opts) => fetchDemoSurveillanceRecords(opts),
  alerts: (opts) => fetchDemoAlerts(opts),
  'response-tasks': (opts) => fetchDemoResponseTasks(opts),
});

/**
 * Shared core hook for authenticated synthetic operational data fetching.
 *
 * @param {string} resource - "farms" | "surveillance-records" | "alerts" | "response-tasks"
 * @param {Object} [options]
 * @param {number} [options.skip=0]
 * @param {number} [options.limit=50]
 * @param {boolean} [options.enabled=true]
 */
export function useDemoOperationalData(resource, options = {}) {
  const { skip = 0, limit = 50, enabled = true } = options;

  const { demoEnabled, status: authStatus, viewerContext, logout } = useDemoForecastingAuth();

  const [status, setStatus] = useState(OPERATIONAL_STATUS.IDLE);
  const [items, setItems] = useState([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState(null);

  const requestIdRef = useRef(0);
  const activeControllerRef = useRef(null);

  const fetcher = RESOURCE_FETCHERS[resource];

  const loadData = useCallback(async () => {
    // 1. Gate execution: Require demo mode, authenticated status, valid context, valid fetcher, and enabled != false
    if (!demoEnabled || authStatus !== AUTH_STATUS.AUTHENTICATED || !viewerContext || !fetcher || enabled === false) {
      setStatus(OPERATIONAL_STATUS.IDLE);
      setItems([]);
      setCount(0);
      setError(null);
      return;
    }

    // Abort previous in-flight request if active
    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
    }

    const controller = new AbortController();
    activeControllerRef.current = controller;

    const currentRequestId = ++requestIdRef.current;

    setStatus(OPERATIONAL_STATUS.LOADING);
    setError(null);

    try {
      const data = await fetcher({ skip, limit, signal: controller.signal });

      // Stale response guard: Ignore if a newer request was dispatched or component changed
      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      if (!data.items || data.items.length === 0) {
        setItems([]);
        setCount(0);
        setStatus(OPERATIONAL_STATUS.EMPTY);
      } else {
        setItems(data.items);
        setCount(data.count);
        setStatus(OPERATIONAL_STATUS.SUCCESS);
      }
      setError(null);
    } catch (err) {
      // Ignore cancelled request errors
      if (err instanceof DemoOperationalApiError && err.category === OPERATIONAL_ERROR_CATEGORIES.ABORTED) {
        return;
      }

      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      setItems([]);
      setCount(0);

      if (err instanceof DemoOperationalApiError) {
        if (err.category === OPERATIONAL_ERROR_CATEGORIES.UNAUTHENTICATED) {
          setStatus(OPERATIONAL_STATUS.UNAUTHENTICATED);
          setError(err.message);
          logout();
          return;
        }

        if (err.category === OPERATIONAL_ERROR_CATEGORIES.FORBIDDEN) {
          setStatus(OPERATIONAL_STATUS.FORBIDDEN);
          setError(err.message);
          return;
        }
      }

      setStatus(OPERATIONAL_STATUS.ERROR);
      setError(err.message || 'Operational data service is currently unavailable.');
    } finally {
      if (activeControllerRef.current === controller) {
        activeControllerRef.current = null;
      }
    }
  }, [demoEnabled, authStatus, viewerContext, fetcher, enabled, skip, limit, logout]);

  // Trigger loadData when dependencies or ViewerContext change
  useEffect(() => {
    // Clear old operational records immediately when context or dependencies change
    setItems([]);
    setCount(0);

    loadData();

    return () => {
      if (activeControllerRef.current) {
        activeControllerRef.current.abort();
        activeControllerRef.current = null;
      }
    };
  }, [loadData]);

  const reload = useCallback(async () => {
    await loadData();
  }, [loadData]);

  return {
    status,
    items,
    count,
    error,
    reload,
    skip,
    limit,
  };
}

/** Convenience Hook Wrapper for Demo Farms */
export function useDemoFarms(options) {
  return useDemoOperationalData('farms', options);
}

/** Convenience Hook Wrapper for Demo Surveillance Records */
export function useDemoSurveillanceRecords(options) {
  return useDemoOperationalData('surveillance-records', options);
}

/** Convenience Hook Wrapper for Demo Alerts */
export function useDemoAlerts(options) {
  return useDemoOperationalData('alerts', options);
}

/** Convenience Hook Wrapper for Demo Response Tasks */
export function useDemoResponseTasks(options) {
  return useDemoOperationalData('response-tasks', options);
}
