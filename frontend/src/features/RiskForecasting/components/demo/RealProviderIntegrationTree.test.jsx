import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { RiskForecastingDemoEntry } from '../../RiskForecastingDemoEntry.jsx';
import { VeterinaryDistrictForecasts } from '../veterinary/VeterinaryDistrictForecasts.jsx';
import { DaphDistrictForecasts } from '../daph/DaphDistrictForecasts.jsx';
import { DEMO_ACCESS_TOKEN_KEY } from '../../services/demoSessionStorage.js';

const RAW_VET_CONTEXT = {
  userId: 'vet-001',
  role: 'VETERINARY_OFFICER',
  authorization: {
    scopeLevel: 'PROVINCE',
    assignedProvince: 'NORTHERN',
    authorizedDistricts: ['Jaffna', 'Kilinochchi', 'Mannar', 'Mullaitivu', 'Vavuniya'],
    assignedFarmIds: ['FARM-JAF-001', 'FARM-KIL-002'],
  },
  permissions: {
    viewModelTransparency: true,
  },
};

const RAW_DAPH_CONTEXT = {
  userId: 'daph-001',
  role: 'DAPH_OFFICIAL',
  authorization: {
    scopeLevel: 'NATIONAL',
    authorizedDistricts: [
      'Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo', 'Galle',
      'Gampaha', 'Hambantota', 'Jaffna', 'Kalutara', 'Kandy', 'Kegalle',
      'Kilinochchi', 'Kurunegala', 'Mannar', 'Matale', 'Matara', 'Mullaitivu',
      'Nuwara Eliya', 'Polonnaruwa', 'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya',
    ],
    assignedFarmIds: [],
  },
  permissions: {
    viewDataQuality: true,
    viewModelTransparency: true,
  },
};

const RAW_FARMER_CONTEXT = {
  userId: 'farmer-001',
  role: 'FARMER',
  authorization: {
    scopeLevel: 'FARM',
    registeredFarmId: 'FARM-JAF-001',
    registeredFarmDistrict: 'Jaffna',
    authorizedDistricts: ['Jaffna'],
    assignedFarmIds: [],
  },
  permissions: {},
};

const FMD_FORECAST_RESPONSE = {
  status: 'success',
  disease: 'FMD',
  scope_level: 'PROVINCE',
  year: 2026,
  target_month: 8,
  districts: [
    { district: 'Jaffna', probability_pct: 25.6, risk_level: 'LOW', predicted_severity: 'MILD' },
  ],
  disclaimer: 'Operational demonstration decision support only.',
};

const LSD_FORECAST_RESPONSE = {
  status: 'success',
  disease: 'LSD',
  scope_level: 'PROVINCE',
  year: 2026,
  target_month: 8,
  districts: [
    { district: 'Jaffna', probability_pct: 4.2, risk_level: 'LOW', predicted_severity: 'MILD' },
  ],
  disclaimer: 'Operational demonstration decision support only.',
};

describe('Real-Provider Integration Tree Tests (No Context Mocking)', () => {
  let originalFetch;

  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    originalFetch = global.fetch;
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');
    vi.stubEnv('VITE_API_URL', 'http://127.0.0.1:8002');
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    sessionStorage.clear();
    localStorage.clear();
  });

  it('restores Vet session, shows connected District Forecast controls without blocked fallback, and queries protected endpoints', async () => {
    sessionStorage.setItem(DEMO_ACCESS_TOKEN_KEY, 'valid-vet-token');

    const fetchSpy = vi.fn(async (url) => {
      const urlStr = url.toString();
      if (urlStr.includes('/api/v1/demo-auth/me')) {
        return {
          ok: true,
          status: 200,
          json: async () => RAW_VET_CONTEXT,
        };
      }
      if (urlStr.includes('/api/v1/demo-operational/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: 'success', data: [] }),
        };
      }
      if (urlStr.includes('/api/v1/demo-forecasting/forecast/fmd')) {
        return {
          ok: true,
          status: 200,
          json: async () => FMD_FORECAST_RESPONSE,
        };
      }
      if (urlStr.includes('/api/v1/demo-forecasting/forecast/lsd')) {
        return {
          ok: true,
          status: 200,
          json: async () => LSD_FORECAST_RESPONSE,
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: 'Not found' }) };
    });

    global.fetch = fetchSpy;

    render(<RiskForecastingDemoEntry />);

    // 1. Wait for session restore
    await waitFor(() => {
      expect(screen.getByText('Veterinary Officer Demonstration (PROVINCE Scope)')).toBeInTheDocument();
    });

    // 2. Click District Forecasts subnav button
    const forecastBtn = screen.getByRole('button', { name: /District Forecasts/i });
    fireEvent.click(forecastBtn);

    // 3. Confirm connected controls appear
    await waitFor(() => {
      expect(screen.getByLabelText(/Target district/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Update forecast/i })).toBeInTheDocument();
    });

    // 4. Confirm blocked fallback text is ABSENT
    expect(screen.queryByText('District forecasts are awaiting secure access integration')).not.toBeInTheDocument();
    expect(screen.queryByText('Integration blocked')).not.toBeInTheDocument();

    // 5. Confirm Vet selector contains only five explicit districts
    const districtSelect = screen.getByLabelText(/Target district/i);
    const options = Array.from(districtSelect.querySelectorAll('option')).map((opt) => opt.value);
    expect(options).toEqual(['ALL', 'Jaffna', 'Kilinochchi', 'Mannar', 'Mullaitivu', 'Vavuniya']);

    // 6. Click Update Forecast and confirm protected endpoints called
    const updateBtn = screen.getByRole('button', { name: /Update forecast/i });
    fireEvent.click(updateBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/demo-forecasting/forecast/fmd'),
        expect.any(Object)
      );
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/demo-forecasting/forecast/lsd'),
        expect.any(Object)
      );
    });
  });

  it('restores DAPH session, shows connected District Forecast controls without blocked fallback, and restricts to explicit national array', async () => {
    sessionStorage.setItem(DEMO_ACCESS_TOKEN_KEY, 'valid-daph-token');

    const fetchSpy = vi.fn(async (url) => {
      const urlStr = url.toString();
      if (urlStr.includes('/api/v1/demo-auth/me')) {
        return {
          ok: true,
          status: 200,
          json: async () => RAW_DAPH_CONTEXT,
        };
      }
      if (urlStr.includes('/api/v1/demo-operational/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: 'success', data: [] }),
        };
      }
      if (urlStr.includes('/api/v1/demo-forecasting/forecast/fmd')) {
        return {
          ok: true,
          status: 200,
          json: async () => FMD_FORECAST_RESPONSE,
        };
      }
      if (urlStr.includes('/api/v1/demo-forecasting/forecast/lsd')) {
        return {
          ok: true,
          status: 200,
          json: async () => LSD_FORECAST_RESPONSE,
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: 'Not found' }) };
    });

    global.fetch = fetchSpy;

    render(<RiskForecastingDemoEntry />);

    // Wait for DAPH session restore
    await waitFor(() => {
      expect(screen.getByText('DAPH Official Demonstration (NATIONAL Scope)')).toBeInTheDocument();
    });

    // Click District Forecasts subnav button
    const forecastBtn = screen.getByRole('button', { name: /District Forecasts/i });
    fireEvent.click(forecastBtn);

    await waitFor(() => {
      expect(screen.getByLabelText(/Target district/i)).toBeInTheDocument();
    });

    // Blocked fallback text absent
    expect(screen.queryByText('District forecasts are awaiting secure DAPH access integration')).not.toBeInTheDocument();

    // Verify district options match explicit array + ALL
    const districtSelect = screen.getByLabelText(/Target district/i);
    const options = Array.from(districtSelect.querySelectorAll('option')).map((opt) => opt.value);
    expect(options.length).toBe(25); // 24 national districts + ALL
  });

  it('restores Farmer session, uses protected FMD/LSD endpoints, and restricts to registered farm district', async () => {
    sessionStorage.setItem(DEMO_ACCESS_TOKEN_KEY, 'valid-farmer-token');

    const fetchSpy = vi.fn(async (url) => {
      const urlStr = url.toString();
      if (urlStr.includes('/api/v1/demo-auth/me')) {
        return {
          ok: true,
          status: 200,
          json: async () => RAW_FARMER_CONTEXT,
        };
      }
      if (urlStr.includes('/api/v1/demo-operational/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: 'success', data: [] }),
        };
      }
      if (urlStr.includes('/api/v1/demo-forecasting/forecast/fmd')) {
        return {
          ok: true,
          status: 200,
          json: async () => FMD_FORECAST_RESPONSE,
        };
      }
      if (urlStr.includes('/api/v1/demo-forecasting/forecast/lsd')) {
        return {
          ok: true,
          status: 200,
          json: async () => LSD_FORECAST_RESPONSE,
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: 'Not found' }) };
    });

    global.fetch = fetchSpy;

    render(<RiskForecastingDemoEntry />);

    await waitFor(() => {
      expect(screen.getByText('Farmer Demonstration (Jaffna)')).toBeInTheDocument();
    });

    // Verify protected endpoints called for Farmer
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/demo-forecasting/forecast/fmd'),
        expect.any(Object)
      );
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/demo-forecasting/forecast/lsd'),
        expect.any(Object)
      );
    });
  });

  it('renders components standalone outside provider without crashing and preserving blocked/fallback behavior', () => {
    expect(() => {
      render(<VeterinaryDistrictForecasts viewerContext={RAW_VET_CONTEXT} />);
    }).not.toThrow();

    expect(screen.getByText('District forecasts are awaiting secure access integration')).toBeInTheDocument();

    expect(() => {
      render(<DaphDistrictForecasts viewerContext={RAW_DAPH_CONTEXT} />);
    }).not.toThrow();

    expect(screen.getByText('District forecasts are awaiting secure DAPH access integration')).toBeInTheDocument();
  });
});
