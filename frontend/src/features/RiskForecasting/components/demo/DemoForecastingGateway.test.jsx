import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DemoForecastingGateway } from './DemoForecastingGateway.jsx';
import * as authHookModule from '../../hooks/useDemoForecastingAuth.js';
import { AUTH_STATUS } from '../../context/DemoForecastingAuthContext.jsx';

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

describe('DemoForecastingGateway Component Unit Tests', () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    mockLogout.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mockAuthContext(overrides = {}) {
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

  // Test 1: Disabled state
  it('Requirement 1: Disabled status renders unavailable screen without login form', () => {
    mockAuthContext({ demoEnabled: false, status: AUTH_STATUS.DISABLED });
    render(<DemoForecastingGateway />);

    expect(screen.getByText('Disease Forecasting Demo Disabled')).toBeInTheDocument();
    expect(screen.queryByLabelText('Password')).toBeNull();
  });

  // Test 2: Checking state
  it('Requirement 2: Checking status renders role="status" and no protected feature', () => {
    mockAuthContext({ status: AUTH_STATUS.CHECKING, viewerContext: null });
    render(<DemoForecastingGateway />);

    const statusEl = screen.getByRole('status');
    expect(statusEl).toBeInTheDocument();
    expect(statusEl).toHaveTextContent('Verifying demo authentication session...');
    expect(screen.queryByText('Disease Forecasting Demo')).toBeNull();
  });

  // Test 3: Unauthenticated state
  it('Requirement 3: Unauthenticated status renders login form', () => {
    mockAuthContext({ status: AUTH_STATUS.UNAUTHENTICATED, viewerContext: null });
    render(<DemoForecastingGateway />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Disease Forecasting Demonstration');
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  // Test 17, 18, 19, 20: Authenticated state rendering, role header, synthetic notices, logout
  it('Requirement 17, 18, 19, 20: Authenticated status renders feature, displays human role (no userId/token), notices, and logout button', () => {
    mockAuthContext({ status: AUTH_STATUS.AUTHENTICATED, viewerContext: mockFarmerContext });
    render(<DemoForecastingGateway />);

    expect(screen.getByText('Disease Forecasting Demo')).toBeInTheDocument();
    expect(screen.getByText(/Farmer Demonstration \(Jaffna\)/i)).toBeInTheDocument();
    expect(screen.queryByText('user_farmer_123')).toBeNull();

    expect(screen.getByText(/Synthetic records are not permitted for model training or scientific analysis/i)).toBeInTheDocument();

    const logoutBtn = screen.getByRole('button', { name: /log out/i });
    expect(logoutBtn).toBeInTheDocument();

    fireEvent.click(logoutBtn);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  // Test 21 & 22: Error status and invalid ViewerContext fail closed
  it('Requirement 21 & 22: Error status and invalid ViewerContext fail closed without rendering feature', () => {
    mockAuthContext({ status: AUTH_STATUS.ERROR, error: 'Authentication service unavailable.' });
    render(<DemoForecastingGateway />);

    expect(screen.getByRole('alert')).toHaveTextContent('Authentication Service Unavailable');
    expect(screen.queryByText('Disease Forecasting Demo')).toBeNull();

    const returnBtn = screen.getByRole('button', { name: /return to login/i });
    fireEvent.click(returnBtn);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('Requirement 22: Authenticated status with null/invalid ViewerContext fails closed', () => {
    mockAuthContext({ status: AUTH_STATUS.AUTHENTICATED, viewerContext: { invalid: 'data' } });
    render(<DemoForecastingGateway />);

    expect(screen.getByRole('alert')).toHaveTextContent('Session Validation Failure');
    expect(screen.queryByText('Disease Forecasting Demo')).toBeNull();
  });
});
