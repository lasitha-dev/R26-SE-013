import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { RiskForecastingDemoEntry } from '../../RiskForecastingDemoEntry.jsx';
import { VeterinaryDistrictForecasts } from '../veterinary/VeterinaryDistrictForecasts.jsx';
import { DaphDistrictForecasts } from '../daph/DaphDistrictForecasts.jsx';
import { DEMO_ACCESS_TOKEN_KEY } from '../../services/demoSessionStorage.js';
import * as workflowApi from '../../services/riskForecastingWorkflowApi.js';

vi.mock('../../services/riskForecastingWorkflowApi.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    listForecastRecords: vi.fn().mockResolvedValue({ records: [] }),
  };
});

const PERSISTED_DAPH_RECORDS = [
  {
    forecast_id: 'rec_integ_fmd_01',
    district: 'Colombo',
    disease: 'FMD',
    target_year: 2025,
    target_month: 1,
    probability: 0.82,
    probability_pct: 82,
    risk_level: 'HIGH',
    predicted_severity: 'SEVERE',
    status: 'GENERATED',
    data_quality: 'EXACT_MATCH',
    fallback_applied: true,
    generated_at: '2026-12-15T08:30:00Z',
  },
  {
    forecast_id: 'rec_integ_lsd_01',
    district: 'Colombo',
    disease: 'LSD',
    target_year: 2025,
    target_month: 1,
    probability: 0.15,
    probability_pct: 15,
    risk_level: 'LOW',
    predicted_severity: 'N/A',
    status: 'GENERATED',
    data_quality: 'EXACT_MATCH',
    fallback_applied: true,
    generated_at: '2026-12-15T08:35:00Z',
  },
];

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
    workflowApi.listForecastRecords.mockResolvedValue({ records: [] });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    sessionStorage.clear();
    localStorage.clear();
  });

  it('restores Vet session and verifies District Forecasts is hidden from demo navigation', async () => {
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
      return { ok: false, status: 404, json: async () => ({ detail: 'Not found' }) };
    });

    global.fetch = fetchSpy;

    render(<RiskForecastingDemoEntry />);

    // 1. Wait for session restore
    await waitFor(() => {
      expect(screen.getByText('Veterinary Officer Demonstration (PROVINCE Scope)')).toBeInTheDocument();
    });

    // 2. Confirm District Forecasts button is hidden
    expect(screen.queryByRole('button', { name: /District Forecasts/i })).not.toBeInTheDocument();
  });

  it('restores DAPH session, shows connected District Forecast controls without blocked fallback, and restricts to explicit national array', async () => {
    sessionStorage.setItem(DEMO_ACCESS_TOKEN_KEY, 'valid-daph-token');

    // Mock listForecastRecords to return persisted records for DAPH
    workflowApi.listForecastRecords.mockResolvedValue({ records: PERSISTED_DAPH_RECORDS });

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

    // Old blocked fallback text absent — component now consumes persisted records
    expect(screen.queryByText('District forecasts are awaiting secure DAPH access integration')).not.toBeInTheDocument();

    // DAPH production component renders its heading and district selector without blocked text
    expect(screen.getByText('January 2025 District Disease Risk Outlook')).toBeInTheDocument();
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

  it('renders Vet standalone outside provider with blocked fallback and DAPH standalone with persisted-record UI', async () => {
    // Vet standalone — still uses demo hooks internally, shows blocked state
    expect(() => {
      render(<VeterinaryDistrictForecasts viewerContext={RAW_VET_CONTEXT} />);
    }).not.toThrow();

    expect(screen.getByText('District forecasts are awaiting secure access integration')).toBeInTheDocument();

    // DAPH standalone — now consumes persisted records via listForecastRecords
    workflowApi.listForecastRecords.mockResolvedValue({ records: PERSISTED_DAPH_RECORDS });

    expect(() => {
      render(<DaphDistrictForecasts viewerContext={RAW_DAPH_CONTEXT} />);
    }).not.toThrow();

    // DAPH component renders its production heading (not blocked text)
    expect(screen.getByText('January 2025 District Disease Risk Outlook')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/Colombo District/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/FMD/i).length).toBeGreaterThan(0);
    });
  });
});
