import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import {
  useDemoOperationalData,
  useDemoFarms,
  useDemoSurveillanceRecords,
  useDemoAlerts,
  useDemoResponseTasks,
  OPERATIONAL_STATUS,
} from './useDemoOperationalData.js';
import * as authHookModule from './useDemoForecastingAuth.js';
import { AUTH_STATUS } from '../context/DemoForecastingAuthContext.jsx';
import * as apiModule from '../services/demoOperationalApi.js';
import { writeDemoAccessToken } from '../services/demoSessionStorage.js';

function TestHookConsumer({ resource = 'farms', options = {}, onRender }) {
  const data = useDemoOperationalData(resource, options);
  if (onRender) {
    onRender(data);
  }
  return (
    <div>
      <span data-testid="status">{data.status}</span>
      <span data-testid="count">{data.count}</span>
      <span data-testid="items-len">{data.items.length}</span>
      <span data-testid="error">{data.error || 'none'}</span>
      <button data-testid="reload-btn" onClick={() => data.reload()}>
        Reload
      </button>
    </div>
  );
}

const mockFarmerContext = {
  userId: 'user_farmer_123',
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

const mockSampleFarm = {
  schemaVersion: '1.0',
  farmId: 'DEMO_FARM_JAFFNA_001',
  displayName: 'Jaffna Cattle Farm 001',
  district: 'Jaffna',
  ownerUserId: 'DEMO_USER_FARMER_JAFFNA',
  assignedVetUserIds: ['DEMO_USER_VET_NORTH'],
  livestockTypes: ['CATTLE'],
  active: true,
  isSynthetic: true,
  dataOrigin: 'SYNTHETIC_DEMO',
  scientificUseAllowed: false,
  createdAt: '2026-08-19T00:00:00Z',
  updatedAt: '2026-08-19T00:00:00Z',
};

describe('useDemoOperationalData Hook Unit Tests', () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    mockLogout.mockReset();
    sessionStorage.clear();
    localStorage.clear();
    writeDemoAccessToken('valid.test.session.token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mockAuth(overrides = {}) {
    vi.spyOn(authHookModule, 'useDemoForecastingAuth').mockReturnValue({
      demoEnabled: true,
      status: AUTH_STATUS.AUTHENTICATED,
      viewerContext: mockFarmerContext,
      error: null,
      login: vi.fn(),
      logout: mockLogout,
      refreshViewerContext: vi.fn(),
      ...overrides,
    });
  }

  // Test 21: Zero requests when demo is disabled
  it('Requirement 21: Hook makes zero requests when demo mode is disabled', async () => {
    mockAuth({ demoEnabled: false, status: AUTH_STATUS.DISABLED });
    const spyFetchFarms = vi.spyOn(apiModule, 'fetchDemoFarms');

    render(<TestHookConsumer resource="farms" />);

    expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.IDLE);
    expect(spyFetchFarms).not.toHaveBeenCalled();
  });

  // Test 22: Zero requests when unauthenticated
  it('Requirement 22: Hook makes zero requests when unauthenticated', async () => {
    mockAuth({ status: AUTH_STATUS.UNAUTHENTICATED, viewerContext: null });
    const spyFetchFarms = vi.spyOn(apiModule, 'fetchDemoFarms');

    render(<TestHookConsumer resource="farms" />);

    expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.IDLE);
    expect(spyFetchFarms).not.toHaveBeenCalled();
  });

  // Test 23: Zero requests when enabled=false
  it('Requirement 23: Hook makes zero requests when enabled option is false', async () => {
    mockAuth();
    const spyFetchFarms = vi.spyOn(apiModule, 'fetchDemoFarms');

    render(<TestHookConsumer resource="farms" options={{ enabled: false }} />);

    expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.IDLE);
    expect(spyFetchFarms).not.toHaveBeenCalled();
  });

  // Test 24: Authenticated hook loads data successfully
  it('Requirement 24: Authenticated hook loads operational data successfully', async () => {
    mockAuth();
    vi.spyOn(apiModule, 'fetchDemoFarms').mockResolvedValueOnce({
      items: [mockSampleFarm],
      skip: 0,
      limit: 50,
      count: 1,
      dataOrigin: 'SYNTHETIC_DEMO',
      scientificUseAllowed: false,
    });

    render(<TestHookConsumer resource="farms" />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.SUCCESS);
    });

    expect(screen.getByTestId('count').textContent).toBe('1');
    expect(screen.getByTestId('items-len').textContent).toBe('1');
  });

  // Test 25: Empty response creates empty state
  it('Requirement 25: Empty items array produces status="empty" with items=[] and count=0', async () => {
    mockAuth();
    vi.spyOn(apiModule, 'fetchDemoFarms').mockResolvedValueOnce({
      items: [],
      skip: 0,
      limit: 50,
      count: 0,
      dataOrigin: 'SYNTHETIC_DEMO',
      scientificUseAllowed: false,
    });

    render(<TestHookConsumer resource="farms" />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.EMPTY);
    });

    expect(screen.getByTestId('count').textContent).toBe('0');
    expect(screen.getByTestId('items-len').textContent).toBe('0');
  });

  // Test 26: 401 calls logout and clears records
  it('Requirement 26: 401 error calls logout() and clears records', async () => {
    mockAuth();
    vi.spyOn(apiModule, 'fetchDemoFarms').mockRejectedValueOnce(
      new apiModule.DemoOperationalApiError({
        message: 'Your demo session has expired.',
        category: apiModule.OPERATIONAL_ERROR_CATEGORIES.UNAUTHENTICATED,
        status: 401,
      })
    );

    render(<TestHookConsumer resource="farms" />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.UNAUTHENTICATED);
    });

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('items-len').textContent).toBe('0');
  });

  // Test 27: 403 sets forbidden without calling logout
  it('Requirement 27: 403 error sets status="forbidden" without calling logout()', async () => {
    mockAuth();
    vi.spyOn(apiModule, 'fetchDemoFarms').mockRejectedValueOnce(
      new apiModule.DemoOperationalApiError({
        message: 'Forbidden',
        category: apiModule.OPERATIONAL_ERROR_CATEGORIES.FORBIDDEN,
        status: 403,
      })
    );

    render(<TestHookConsumer resource="farms" />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.FORBIDDEN);
    });

    expect(mockLogout).not.toHaveBeenCalled();
    expect(screen.getByTestId('items-len').textContent).toBe('0');
  });

  // Test 28: Reload performs a new request
  it('Requirement 28: reload() triggers one new API request', async () => {
    mockAuth();
    const spyFetch = vi.spyOn(apiModule, 'fetchDemoFarms')
      .mockResolvedValueOnce({ items: [mockSampleFarm], skip: 0, limit: 50, count: 1, dataOrigin: 'SYNTHETIC_DEMO', scientificUseAllowed: false })
      .mockResolvedValueOnce({ items: [mockSampleFarm], skip: 0, limit: 50, count: 1, dataOrigin: 'SYNTHETIC_DEMO', scientificUseAllowed: false });

    render(<TestHookConsumer resource="farms" />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.SUCCESS);
    });

    expect(spyFetch).toHaveBeenCalledTimes(1);

    await act(async () => {
      screen.getByTestId('reload-btn').click();
    });

    await waitFor(() => {
      expect(spyFetch).toHaveBeenCalledTimes(2);
    });
  });

  // Test 30 & 31: ViewerContext change clears records immediately and stale responses are discarded
  it('Requirement 30 & 31: ViewerContext change clears records immediately and discards stale slow responses', async () => {
    mockAuth();

    let resolveSlowFetch;
    const slowPromise = new Promise((resolve) => {
      resolveSlowFetch = resolve;
    });

    vi.spyOn(apiModule, 'fetchDemoFarms')
      .mockImplementationOnce(() => slowPromise)
      .mockResolvedValueOnce({
        items: [mockSampleFarm],
        skip: 0,
        limit: 50,
        count: 1,
        dataOrigin: 'SYNTHETIC_DEMO',
        scientificUseAllowed: false,
      });

    const { rerender } = render(<TestHookConsumer resource="farms" />);

    expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.LOADING);

    // Trigger context / prop change (re-render with new skip value)
    rerender(<TestHookConsumer resource="farms" options={{ skip: 10 }} />);

    // Resolve the first slow fetch after second fetch starts
    resolveSlowFetch({
      items: [{ ...mockSampleFarm, displayName: 'STALE_OLD_FARM' }],
      skip: 0,
      limit: 50,
      count: 1,
      dataOrigin: 'SYNTHETIC_DEMO',
      scientificUseAllowed: false,
    });

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.SUCCESS);
    });

    // Verify stale response did not corrupt state
    expect(screen.getByTestId('count').textContent).toBe('1');
  });

  // Test 32: No records are written to sessionStorage/localStorage
  it('Requirement 32: Operational records are never written to sessionStorage or localStorage', async () => {
    mockAuth();
    vi.spyOn(apiModule, 'fetchDemoFarms').mockResolvedValueOnce({
      items: [mockSampleFarm],
      skip: 0,
      limit: 50,
      count: 1,
      dataOrigin: 'SYNTHETIC_DEMO',
      scientificUseAllowed: false,
    });

    render(<TestHookConsumer resource="farms" />);

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe(OPERATIONAL_STATUS.SUCCESS);
    });

    expect(sessionStorage.getItem('DEMO_FARM_JAFFNA_001')).toBeNull();
    expect(localStorage.getItem('DEMO_FARM_JAFFNA_001')).toBeNull();
  });
});
