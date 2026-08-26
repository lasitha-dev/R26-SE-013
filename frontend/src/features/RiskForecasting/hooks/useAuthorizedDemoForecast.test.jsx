import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAuthorizedDemoForecast } from './useAuthorizedDemoForecast.js';
import { DemoForecastingAuthContext } from '../context/DemoForecastingAuthContext.jsx';
import * as demoApi from '../services/demoForecastingApi.js';
import * as demoSessionStorage from '../services/demoSessionStorage.js';

vi.mock('../services/demoForecastingApi.js');

const mockFarmerContext = {
  userId: 'usr_farmer_001',
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

const mockVetContext = {
  userId: 'usr_vet_001',
  role: 'VETERINARY_OFFICER',
  authorization: {
    scopeLevel: 'DISTRICT',
    registeredFarmDistrict: null,
    authorizedDistricts: ['Jaffna', 'Kilinochchi'],
    assignedFarmIds: [],
  },
  permissions: {
    viewDataQuality: true,
    viewModelTransparency: false,
    manageAlerts: true,
    recordResponse: true,
    viewReports: true,
  },
};

describe('useAuthorizedDemoForecast Hook Lifecycle & Security Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue('mock_token');
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
    localStorage.clear();
  });

  // 1. Hook outside DemoForecastingAuthProvider
  it('renders safely outside DemoForecastingAuthProvider without throwing and remains unauthenticated', async () => {
    const { result } = renderHook(() => useAuthorizedDemoForecast());

    expect(result.current.status).toBe('idle');

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('unauthenticated');
    expect(result.current.error).toBe('Demo authentication required.');
    expect(demoApi.fetchAuthorizedDiseaseForecasts).not.toHaveBeenCalled();
  });

  // 2. Authenticated successful request
  it('produces success state and stores separate FMD and LSD results upon successful request', async () => {
    const fmdData = { disease: 'FMD', target_year: 2024, target_month: 1, districts: [{ district: 'Jaffna', probability_pct: 60 }] };
    const lsdData = { disease: 'LSD', target_year: 2024, target_month: 1, districts: [{ district: 'Jaffna', probability_pct: 40 }] };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: fmdData, error: null },
      lsd: { status: 'success', data: lsdData, error: null },
    });

    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('success');
    expect(result.current.fmdForecast).toEqual(fmdData);
    expect(result.current.lsdForecast).toEqual(lsdData);
    expect(result.current.error).toBeNull();
  });

  // 3. Frontend unauthorized district
  it('makes zero API calls and produces forbidden state when requesting unauthorized district', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Colombo' });
    });

    expect(demoApi.fetchAuthorizedDiseaseForecasts).not.toHaveBeenCalled();
    expect(result.current.status).toBe('forbidden');
    expect(result.current.error).toBe('Forecast access to the requested district is forbidden.');
    expect(result.current.fmdForecast).toBeNull();
    expect(result.current.lsdForecast).toBeNull();
  });

  // 4. Missing token / 401
  it('clears results, sets unauthenticated status, and calls logout on 401 error', async () => {
    const mockLogout = vi.fn();
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: mockLogout,
    };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockRejectedValue({
      status: 401,
      category: 'UNAUTHENTICATED',
      message: 'Your demo session has expired.',
    });

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('unauthenticated');
    expect(result.current.fmdForecast).toBeNull();
    expect(result.current.lsdForecast).toBeNull();
    expect(mockLogout).toHaveBeenCalledOnce();
  });

  // 5. 403 Forbidden
  it('clears results and sets forbidden status without calling logout on 403 error', async () => {
    const mockLogout = vi.fn();
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockVetContext,
      logout: mockLogout,
    };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockRejectedValue({
      status: 403,
      category: 'FORBIDDEN',
      message: 'Forecast access to the requested district is forbidden.',
    });

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('forbidden');
    expect(result.current.error).toBe('Forecast access to the requested district is forbidden.');
    expect(mockLogout).not.toHaveBeenCalled();
  });

  // 6. 503 / network error
  it('clears results and produces sanitized error state on 503/network error without exposing raw traces', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockRejectedValue(new Error('Fatal internal server crash traceback line 42'));

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe('Forecast service is currently unavailable.');
    expect(result.current.error).not.toContain('traceback');
  });

  // 7. Abort error
  it('ignores AbortError silently without rendering an error state', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    const abortError = new Error('Request aborted');
    abortError.name = 'AbortError';

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockRejectedValue(abortError);

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.error).toBeNull();
  });

  // 8. Stale-response protection
  it('prevents stale out-of-order request responses from overwriting newer request results', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockVetContext,
      logout: vi.fn(),
    };

    let resolveA;
    let resolveB;

    const promiseA = new Promise((res) => { resolveA = res; });
    const promiseB = new Promise((res) => { resolveB = res; });

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts)
      .mockImplementationOnce(() => promiseA)
      .mockImplementationOnce(() => promiseB);

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    // Request A
    act(() => {
      result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    // Request B (cancels A)
    act(() => {
      result.current.requestForecast({ year: 2024, targetMonth: 2, district: 'Kilinochchi' });
    });

    // Resolve B first
    await act(async () => {
      resolveB({
        overallStatus: 'success',
        fmd: { status: 'success', data: { district: 'Kilinochchi' }, error: null },
        lsd: { status: 'success', data: { district: 'Kilinochchi' }, error: null },
      });
    });

    expect(result.current.fmdForecast).toEqual({ district: 'Kilinochchi' });

    // Resolve A second (stale)
    await act(async () => {
      resolveA({
        overallStatus: 'success',
        fmd: { status: 'success', data: { district: 'Jaffna' }, error: null },
        lsd: { status: 'success', data: { district: 'Jaffna' }, error: null },
      });
    });

    // Result must remain B (Kilinochchi)
    expect(result.current.fmdForecast).toEqual({ district: 'Kilinochchi' });
  });

  // 9. ViewerContext change
  it('clears forecast state immediately when viewerContext changes', async () => {
    let contextValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: { district: 'Jaffna' }, error: null },
      lsd: { status: 'success', data: { district: 'Jaffna' }, error: null },
    });

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={contextValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result, rerender } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('success');
    expect(result.current.fmdForecast).toEqual({ district: 'Jaffna' });

    // Change context
    contextValue = {
      ...contextValue,
      viewerContext: mockVetContext,
    };

    rerender();

    expect(result.current.status).toBe('idle');
    expect(result.current.fmdForecast).toBeNull();
    expect(result.current.lsdForecast).toBeNull();
  });

  // 10. Unmount
  it('aborts active request upon unmount without state update warnings', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    let capturedSignal;
    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockImplementation(({ signal }) => {
      capturedSignal = signal;
      return new Promise(() => {}); // never resolves
    });

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result, unmount } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    act(() => {
      result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(capturedSignal.aborted).toBe(false);

    unmount();

    expect(capturedSignal.aborted).toBe(true);
  });

  // 11. clearForecast()
  it('resets results and status to idle when clearForecast is invoked', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: { district: 'Jaffna' }, error: null },
      lsd: { status: 'success', data: { district: 'Jaffna' }, error: null },
    });

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(result.current.status).toBe('success');

    act(() => {
      result.current.clearForecast();
    });

    expect(result.current.status).toBe('idle');
    expect(result.current.fmdForecast).toBeNull();
    expect(result.current.lsdForecast).toBeNull();
  });

  // 12. Forecast results are not written to storage
  it('verifies forecast results are never written to sessionStorage or localStorage', async () => {
    const mockAuthValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: mockFarmerContext,
      logout: vi.fn(),
    };

    vi.mocked(demoApi.fetchAuthorizedDiseaseForecasts).mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: { disease: 'FMD', secret_data: 123 }, error: null },
      lsd: { status: 'success', data: { disease: 'LSD', secret_data: 456 }, error: null },
    });

    const wrapper = ({ children }) => (
      <DemoForecastingAuthContext.Provider value={mockAuthValue}>
        {children}
      </DemoForecastingAuthContext.Provider>
    );

    const { result } = renderHook(() => useAuthorizedDemoForecast(), { wrapper });

    await act(async () => {
      await result.current.requestForecast({ year: 2024, targetMonth: 1, district: 'Jaffna' });
    });

    expect(sessionStorage.getItem('fmdForecast')).toBeNull();
    expect(sessionStorage.getItem('lsdForecast')).toBeNull();
    expect(localStorage.getItem('fmdForecast')).toBeNull();
    expect(localStorage.getItem('lsdForecast')).toBeNull();
  });
});
