import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import App, { isDemoPath, isDemoEnabled } from './App.jsx';
import * as demoAuthApi from './features/RiskForecasting/services/demoAuthApi.js';
import * as demoOperationalApi from './features/RiskForecasting/services/demoOperationalApi.js';
import * as demoForecastingApi from './features/RiskForecasting/services/demoForecastingApi.js';
import * as demoSessionStorage from './features/RiskForecasting/services/demoSessionStorage.js';
import * as legacyApi from './features/RiskForecasting/services/api.js';

vi.mock('./features/HealthAnomaly/HealthAnomalyRoutes.jsx', () => ({
  default: () => <div data-testid="mock-health-anomaly-routes">Health Anomaly Module</div>
}));

describe('Guarded App Entry & Routing Tests (App.jsx)', () => {
  const originalLocation = window.location;
  const originalEnv = import.meta.env.VITE_FORECASTING_DEMO_ENABLED;

  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    vi.spyOn(legacyApi, 'fetchDistricts').mockResolvedValue(['Jaffna', 'Colombo']);
  });

  afterEach(() => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = originalEnv;
    Object.defineProperty(window, 'location', {
      writable: true,
      value: originalLocation,
    });
  });

  const setWindowLocation = (pathname, search = '') => {
    delete window.location;
    window.location = new URL(`http://localhost:3000${pathname}${search}`);
  };

  const renderWithRouter = (ui, { route = '/' } = {}) => {
    return render(
      <MemoryRouter initialEntries={[route]}>
        {ui}
      </MemoryRouter>
    );
  };

  it('1. helper function isDemoPath correctly identifies /risk-forecasting-demo', () => {
    expect(isDemoPath('/risk-forecasting-demo')).toBe(true);
    expect(isDemoPath('/risk-forecasting-demo/sub')).toBe(true);
    expect(isDemoPath('/')).toBe(false);
    expect(isDemoPath('/forecasting')).toBe(false);
  });

  it('2. helper function isDemoEnabled returns true ONLY for exact "true" string', () => {
    expect(isDemoEnabled('true')).toBe(true);
    expect(isDemoEnabled('false')).toBe(false);
    expect(isDemoEnabled(undefined)).toBe(false);
    expect(isDemoEnabled('TRUE')).toBe(false);
    expect(isDemoEnabled('1')).toBe(false);
    expect(isDemoEnabled('yes')).toBe(false);
  });

  it('3. renders RiskForecastingDemoEntry login UI when flag is "true" and path is /risk-forecasting-demo', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    setWindowLocation('/risk-forecasting-demo');
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue(null);

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    await waitFor(() => {
      expect(screen.getByText('Disease Forecasting Demonstration')).toBeInTheDocument();
    });
    expect(screen.getByText(/Farmer demonstration/i)).toBeInTheDocument();
    expect(screen.getByText(/Veterinary Officer demonstration/i)).toBeInTheDocument();
    expect(screen.getByText(/DAPH Official demonstration/i)).toBeInTheDocument();
  });

  it('4. fails closed with safe disabled message when flag is false', () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'false';
    setWindowLocation('/risk-forecasting-demo');

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    expect(screen.getByText('Disease Forecasting Demo Disabled')).toBeInTheDocument();
    expect(screen.queryByText('Disease Forecasting Demonstration')).not.toBeInTheDocument();
  });

  it('5. fails closed when flag is missing/undefined', () => {
    delete import.meta.env.VITE_FORECASTING_DEMO_ENABLED;
    setWindowLocation('/risk-forecasting-demo');

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    expect(screen.getByText('Disease Forecasting Demo Disabled')).toBeInTheDocument();
    expect(screen.queryByText('Disease Forecasting Demonstration')).not.toBeInTheDocument();
  });

  it('6. disabled demo makes zero auth, operational, or forecasting API requests', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'false';
    setWindowLocation('/risk-forecasting-demo');

    const authSpy = vi.spyOn(demoAuthApi, 'fetchDemoViewerContext');
    const opSpy = vi.spyOn(demoOperationalApi, 'fetchDemoFarms');
    const fcSpy = vi.spyOn(demoForecastingApi, 'fetchAuthorizedDiseaseForecasts');

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    expect(screen.getByText('Disease Forecasting Demo Disabled')).toBeInTheDocument();
    expect(authSpy).not.toHaveBeenCalled();
    expect(opSpy).not.toHaveBeenCalled();
    expect(fcSpy).not.toHaveBeenCalled();
  });

  it('7. other flag values ("TRUE", "1", "yes") remain disabled and fail closed', () => {
    const invalidFlags = ['TRUE', '1', 'yes', 'true ', 'ENABLED'];
    for (const flagVal of invalidFlags) {
      import.meta.env.VITE_FORECASTING_DEMO_ENABLED = flagVal;
      setWindowLocation('/risk-forecasting-demo');

      const { unmount } = renderWithRouter(<App />, { route: '/risk-forecasting-demo' });
      expect(screen.getAllByText('Disease Forecasting Demo Disabled').length).toBeGreaterThanOrEqual(1);
      unmount();
    }
  });

  it('8. default app path (/) isolates demo and follows Main root routing to health anomaly', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    
    renderWithRouter(<App />, { route: '/' });

    await waitFor(() => {
      expect(screen.getByTestId('mock-health-anomaly-routes')).toBeInTheDocument();
    });
    expect(screen.getByText('Health Anomaly Module')).toBeInTheDocument();
    expect(screen.queryByText('Disease Forecasting Demonstration')).not.toBeInTheDocument();
  });

  it('9. URL query parameters (role, district, permissions, ViewerContext, token, password) cannot override demo security', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    setWindowLocation(
      '/risk-forecasting-demo',
      '?role=VETERINARY_OFFICER&district=Colombo&permissions=all&token=fake_token&password=admin'
    );
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue(null);

    renderWithRouter(<App />, { route: '/risk-forecasting-demo?role=VETERINARY_OFFICER&district=Colombo&permissions=all&token=fake_token&password=admin' });

    await waitFor(() => {
      expect(screen.getByText('Disease Forecasting Demonstration')).toBeInTheDocument();
    });

    expect(screen.queryByText(/Veterinary Officer Demonstration \(PROVINCE Scope\)/i)).not.toBeInTheDocument();
  });

  it('10. login UI appears through DemoForecastingAuthProvider and receives context from /me upon login', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    setWindowLocation('/risk-forecasting-demo');
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue(null);

    const loginSpy = vi.spyOn(demoAuthApi, 'loginDemoUser').mockResolvedValue({
      accessToken: 'test_token_123',
      tokenType: 'bearer',
      expiresIn: 3600,
    });

    vi.spyOn(demoAuthApi, 'fetchDemoViewerContext').mockResolvedValue({
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
    });

    vi.spyOn(demoForecastingApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [] } },
      lsd: { status: 'success', data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] } },
    });

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    await waitFor(() => {
      expect(screen.getByText('Disease Forecasting Demonstration')).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: 'demo123' } });

    const submitBtn = screen.getByRole('button', { name: /sign in to demo/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith({ loginName: 'demo_farmer_jaffna', password: 'demo123' });
    });
  });

  it('11. verifies no sensitive tokens or raw passwords are rendered in the DOM', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    setWindowLocation('/risk-forecasting-demo');
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue('super_secret_bearer_token');

    vi.spyOn(demoAuthApi, 'fetchDemoViewerContext').mockResolvedValue({
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
    });

    vi.spyOn(demoForecastingApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [] } },
      lsd: { status: 'success', data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] } },
    });

    const { container } = renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    await waitFor(() => {
      expect(screen.getByText(/Farmer Demonstration \(Jaffna\)/i)).toBeInTheDocument();
    });

    expect(container.innerHTML).not.toContain('super_secret_bearer_token');
    expect(container.innerHTML).not.toContain('FORECASTING_DEMO');
  });

  it('12. logout returns cleanly to login view', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    setWindowLocation('/risk-forecasting-demo');
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue('active_token');

    vi.spyOn(demoAuthApi, 'fetchDemoViewerContext').mockResolvedValue({
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
    });

    vi.spyOn(demoForecastingApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
      overallStatus: 'success',
      fmd: { status: 'success', data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [] } },
      lsd: { status: 'success', data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] } },
    });

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
    });

    const logoutBtn = screen.getByRole('button', { name: /log out/i });
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(screen.getByText('Disease Forecasting Demonstration')).toBeInTheDocument();
    });
  });

  it('13. demo route login screen renders page-level h1 and no duplicate h1 in shared shell', async () => {
    import.meta.env.VITE_FORECASTING_DEMO_ENABLED = 'true';
    setWindowLocation('/risk-forecasting-demo');
    vi.spyOn(demoSessionStorage, 'readDemoAccessToken').mockReturnValue(null);

    renderWithRouter(<App />, { route: '/risk-forecasting-demo' });

    await waitFor(() => {
      expect(screen.getByText('Disease Forecasting Demonstration')).toBeInTheDocument();
    });

    const h1Elements = screen.getAllByRole('heading', { level: 1 });
    expect(h1Elements).toHaveLength(1);
    expect(h1Elements[0]).toHaveTextContent('Disease Forecasting Demonstration');
  });
});
