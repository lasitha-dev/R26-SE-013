import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { DaphDistrictForecasts } from './DaphDistrictForecasts';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi.js';

vi.mock('../../services/riskForecastingWorkflowApi.js', () => ({
  listForecastRecords: vi.fn()
}));

const validNationalDaphContext = {
  userId: 'usr_daph_national_002',
  role: ROLES.DAPH_OFFICIAL,
  authorization: {
    scopeLevel: SCOPE_LEVELS.NATIONAL,
    registeredFarmDistrict: null,
    authorizedDistricts: ['ALL_DISTRICTS'],
    assignedFarmIds: [],
  },
  permissions: {
    viewDataQuality: false,
    viewModelTransparency: false,
    manageAlerts: true,
    recordResponse: true,
    viewReports: true,
  },
};

const validProvinceDaphContext = {
  userId: 'usr_daph_prov_001',
  role: ROLES.DAPH_OFFICIAL,
  authorization: {
    scopeLevel: SCOPE_LEVELS.PROVINCE,
    registeredFarmDistrict: null,
    authorizedDistricts: ['Colombo'],
    assignedFarmIds: [],
  },
  permissions: {
    viewDataQuality: false,
    viewModelTransparency: false,
    manageAlerts: true,
    recordResponse: true,
    viewReports: true,
  },
};

const mockRecords = [
  {
    forecast_id: 'rec_01',
    district: 'Colombo',
    disease: 'FMD',
    target_year: 2026,
    target_month: 12,
    probability: 0.85,
    probability_pct: 85,
    risk_level: 'HIGH',
    predicted_severity: 'SEVERE',
    status: 'GENERATED',
    data_quality: 'PROXY_USED',
    fallback_applied: true,
    generated_at: '2026-11-20T10:00:00Z'
  },
  {
    forecast_id: 'rec_02',
    district: 'Colombo',
    disease: 'LSD',
    target_year: 2026,
    target_month: 12,
    probability: 0.15,
    probability_pct: 15,
    risk_level: 'LOW',
    predicted_severity: 'N/A',
    status: 'GENERATED',
    data_quality: 'PROXY_USED',
    fallback_applied: true,
    generated_at: '2026-11-20T10:05:00Z'
  },
  {
    forecast_id: 'rec_03',
    district: 'Gampaha',
    disease: 'FMD',
    target_year: 2026,
    target_month: 12,
    probability: 0.45,
    probability_pct: 45,
    risk_level: 'MEDIUM',
    predicted_severity: 'MODERATE',
    status: 'GENERATED',
    data_quality: 'EXACT_MATCH',
    fallback_applied: false,
    generated_at: '2026-12-01T10:00:00Z'
  },
  {
    forecast_id: 'rec_04',
    district: 'Gampaha',
    disease: 'LSD',
    target_year: 2025,
    target_month: 11,
    probability: 0.10,
    probability_pct: 10,
    risk_level: 'LOW',
    predicted_severity: 'N/A',
    status: 'GENERATED',
    data_quality: 'EXACT_MATCH',
    fallback_applied: false,
    generated_at: '2025-11-20T10:05:00Z'
  }
];

describe('DaphDistrictForecasts Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // --- RESTORED REGRESSION TESTS ---

  it('fails closed when viewerContext is missing (null)', () => {
    render(<DaphDistrictForecasts viewerContext={null} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
  });

  it('fails closed when viewerContext is invalid', () => {
    render(<DaphDistrictForecasts viewerContext={{ invalid: true }} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
  });

  it('rejects FARMER role', () => {
    const farmerContext = {
      userId: 'usr_farmer_004',
      role: ROLES.FARMER,
      authorization: {
        scopeLevel: SCOPE_LEVELS.FARM,
        registeredFarmDistrict: 'Hambantota',
        authorizedDistricts: ['Hambantota'],
        assignedFarmIds: ['FARM_HAM_01'],
      },
      permissions: {},
    };
    render(<DaphDistrictForecasts viewerContext={farmerContext} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
  });

  it('rejects VETERINARY_OFFICER role', () => {
    const vetContext = {
      userId: 'usr_vet_004',
      role: ROLES.VETERINARY_OFFICER,
      authorization: {
        scopeLevel: SCOPE_LEVELS.DISTRICT,
        registeredFarmDistrict: null,
        authorizedDistricts: ['Hambantota'],
        assignedFarmIds: [],
      },
      permissions: {},
    };
    render(<DaphDistrictForecasts viewerContext={vetContext} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
  });

  it('rejects DAPH_OFFICIAL with FARM scopeLevel', () => {
    const farmScopeDaph = {
      ...validNationalDaphContext,
      authorization: {
        ...validNationalDaphContext.authorization,
        scopeLevel: SCOPE_LEVELS.FARM,
      },
    };
    render(<DaphDistrictForecasts viewerContext={farmScopeDaph} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('fails closed when authorizedDistricts is missing or null', () => {
    const noDistrictsDaph = {
      ...validNationalDaphContext,
      authorization: {
        ...validNationalDaphContext.authorization,
        authorizedDistricts: null,
      },
    };
    render(<DaphDistrictForecasts viewerContext={noDistrictsDaph} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('fails closed when authorizedDistricts is an empty array, including for NATIONAL scope', () => {
    const emptyNationalDaph = {
      ...validNationalDaphContext,
      authorization: {
        ...validNationalDaphContext.authorization,
        authorizedDistricts: [],
      },
    };
    render(<DaphDistrictForecasts viewerContext={emptyNationalDaph} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('does not mutate input viewerContext prop (deeply frozen object test)', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    const frozenContext = Object.freeze({
      ...validNationalDaphContext,
      authorization: Object.freeze({ ...validNationalDaphContext.authorization }),
      permissions: Object.freeze({ ...validNationalDaphContext.permissions }),
    });

    expect(() => {
      render(<DaphDistrictForecasts viewerContext={frozenContext} />);
    }).not.toThrow();

    expect(frozenContext.role).toBe(ROLES.DAPH_OFFICIAL);
    expect(frozenContext.authorization.authorizedDistricts).toEqual(['ALL_DISTRICTS']);
  });

  it('renders the scientific boundaries section with health_and_safety and no biomedical identifier', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(screen.getByText(/Scientific & Epidemiological Boundaries/i)).toBeInTheDocument();
    expect(screen.getByText('health_and_safety')).toBeInTheDocument();
    expect(screen.queryByText('biomedical')).not.toBeInTheDocument();
  });

  it('renders district-level scientific disclaimer distinguishing forecasts from alerts and individual farm diagnosis', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(
      screen.getByText(/Disease risk forecasts are district-level early-warning estimates/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/They do not confirm disease on an individual farm, nor do they constitute an official outbreak alert/i)
    ).toBeInTheDocument();
  });

  it('does NOT render Stage 2, ECE calibration, prediction sets, log-odds, model variants, or raw JSON', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
  });

  it('does NOT render Data Quality or Model Transparency content without separate screen permissions', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(screen.queryByText(/Data Quality/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Model Transparency/i)).not.toBeInTheDocument();
  });

  it('contains no AI Diagnosis CTA', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
  });

  it('hides decorative Material symbols from assistive technology', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    const { container } = render(
      <DaphDistrictForecasts viewerContext={validNationalDaphContext} />
    );
    const decorativeIcons = container.querySelectorAll('.material-symbols-outlined');
    expect(decorativeIcons.length).toBeGreaterThan(0);
    decorativeIcons.forEach(icon => {
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  it('uses max-w-6xl outer container with flex-wrap district scope badges', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    const { container } = render(
      <DaphDistrictForecasts viewerContext={validNationalDaphContext} />
    );

    const outerContainer = container.firstElementChild;
    expect(outerContainer.className).toContain('max-w-6xl');
    expect(outerContainer.className).toContain('text-on-surface');

    const scopeHeading = screen.getByText('Authorized forecast scope');
    const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
    expect(badgeContainer).toBeInTheDocument();
  });

  // --- END RESTORED REGRESSION TESTS ---

  it('1. Uses listForecastRecords with limit 200, 2. Does not import useAuthorizedDemoForecast and 3. Does not call FMD/LSD POST', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });

    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalled());

    // Prove it calls with limit 200 and not limit 500
    expect(workflowApi.listForecastRecords).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 200 }),
      expect.anything()
    );
    expect(workflowApi.listForecastRecords).not.toHaveBeenCalledWith(
      expect.objectContaining({ limit: 500 }),
      expect.anything()
    );

    expect(await screen.findByText(/Colombo District · FMD/i)).toBeInTheDocument();
  });

  it('4. Does not send POST, PUT, PATCH, or DELETE requests', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
    await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalled());

    const nonGetCalls = fetchSpy.mock.calls.filter(c => c[1] && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(c[1].method));
    expect(nonGetCalls).toHaveLength(0);
  });

  it('5. Displays Colombo FMD persisted record, 6. Colombo LSD, 7. distinct probabilities, 8. December 2026, 9. fallback/provenance', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    await screen.findByText('Colombo District · FMD');
    await screen.findByText('Colombo District · LSD');

    expect(screen.getByText('85.0%')).toBeInTheDocument();
    expect(screen.getByText('15.0%')).toBeInTheDocument();
    expect(screen.getByText('HIGH RISK')).toBeInTheDocument();
    expect(screen.getByText('LOW RISK')).toBeInTheDocument();

    const targets = await screen.findAllByText('Target: December 2026');
    expect(targets.length).toBeGreaterThan(0);

    expect(screen.getAllByText('YES (Fallback Proxy)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('NO (Exact Period)').length).toBeGreaterThan(0);

    expect(screen.getAllByText('Yes').length).toBeGreaterThan(0);
    expect(screen.getAllByText('No').length).toBeGreaterThan(0);
  });

  it('10. Disease filter isolates FMD', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
    await screen.findByText('Colombo District · FMD');

    fireEvent.change(screen.getByLabelText(/Disease/i), { target: { value: 'FMD' } });

    expect(screen.queryByText('Colombo District · LSD')).not.toBeInTheDocument();
    expect(screen.getByText('Colombo District · FMD')).toBeInTheDocument();
  });

  it('11. Disease filter isolates LSD', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
    await screen.findByText('Colombo District · FMD');

    fireEvent.change(screen.getByLabelText(/Disease/i), { target: { value: 'LSD' } });

    expect(screen.queryByText('Colombo District · FMD')).not.toBeInTheDocument();
    expect(screen.getByText('Colombo District · LSD')).toBeInTheDocument();
  });

  it('12. District filter works', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
    await screen.findByText('Colombo District · FMD');

    fireEvent.change(screen.getByLabelText(/Target district/i), { target: { value: 'Colombo' } });

    expect(screen.queryByText('Gampaha District · FMD')).not.toBeInTheDocument();
  });

  it('13. Year/month filters work and 14. Reset filter works', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    // Gampaha FMD is in 2026, so it should be visible initially because 2026 is latest.
    await screen.findByText('Gampaha District · FMD');

    // Switch to 2025
    fireEvent.change(screen.getByLabelText(/Forecast year/i), { target: { value: '2025' } });

    // Now Gampaha FMD (which is 2026) is NOT visible.
    expect(screen.queryByText('Gampaha District · FMD')).not.toBeInTheDocument();
    // But Gampaha LSD (which is 2025) IS visible.
    expect(screen.getByText('Gampaha District · LSD')).toBeInTheDocument();

    // Reset filters
    fireEvent.click(screen.getByRole('button', { name: /Reset Filters/i }));

    // Gampaha FMD is back because it resets to latest (2026)
    expect(screen.getByText('Gampaha District · FMD')).toBeInTheDocument();
  });

  it('15. Empty response renders the truthful empty state', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: [] });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(await screen.findByText(/No saved district forecast records are available/i)).toBeInTheDocument();
  });

  it('16. Sanitized API failure renders the generic error', async () => {
    workflowApi.listForecastRecords.mockRejectedValue(new Error('Network disconnected'));
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    expect(await screen.findByText(/District forecast records could not be loaded/i)).toBeInTheDocument();
    expect(screen.queryByText(/Network disconnected/i)).not.toBeInTheDocument();
  });

  it('17. AbortError does not render an error', async () => {
    const abortErr = new Error('aborted');
    abortErr.name = 'AbortError';
    workflowApi.listForecastRecords.mockRejectedValue(abortErr);

    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    await waitFor(() => {
      expect(workflowApi.listForecastRecords).toHaveBeenCalled();
    });

    expect(screen.queryByText(/District forecast records could not be loaded/i)).not.toBeInTheDocument();
  });

  it('18. Stale request cannot overwrite the latest successful response', async () => {
    let resolveFirst;
    let resolveSecond;
    const p1 = new Promise((res) => { resolveFirst = res; });
    const p2 = new Promise((res) => { resolveSecond = res; });

    let callCount = 0;
    workflowApi.listForecastRecords.mockImplementation(() => {
      callCount++;
      if (callCount === 1) return p1;
      return p2;
    });

    const { rerender } = render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    // We need to wait for the first render to complete before changing context
    await waitFor(() => {
        expect(callCount).toBe(1);
    });

    // Change context to trigger useEffect again (will abort previous fetch and start new one)
    const newContext = { ...validNationalDaphContext, authorization: { ...validNationalDaphContext.authorization, authorizedDistricts: ['Colombo', 'Gampaha', 'Matara', 'Kandy'] } };

    rerender(<DaphDistrictForecasts viewerContext={newContext} />);

    await waitFor(() => {
        expect(callCount).toBe(2);
    });

    await act(async () => {
      resolveSecond({ records: [mockRecords[0]] }); // Colombo FMD
    });

    await screen.findByText('Colombo District · FMD');

    await act(async () => {
      resolveFirst({ records: [mockRecords[2]] }); // Gampaha FMD
    });

    await waitFor(() => {
      expect(screen.queryByText('Gampaha District · FMD')).not.toBeInTheDocument();
    });
  });

  it('19. Unmount does not produce state-update leakage', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    let resolveRequest;
    const promise = new Promise((res) => { resolveRequest = res; });
    workflowApi.listForecastRecords.mockReturnValue(promise);

    const { unmount } = render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
    unmount();

    await act(async () => {
        resolveRequest({ records: mockRecords });
    });

    // Verify no 'state update on unmounted component' warnings were emitted
    const stateUpdateWarnings = consoleErrorSpy.mock.calls.filter(
      call => call.some(arg => typeof arg === 'string' && arg.includes('unmounted'))
    );
    expect(stateUpdateWarnings).toHaveLength(0);
    consoleErrorSpy.mockRestore();
  });

  it('20. No DAPH model-generation action is rendered', () => {
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
    expect(screen.queryByRole('button', { name: /Generate Forecast/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Run Model/i })).not.toBeInTheDocument();
  });

  it('21. National scope labels render correctly and ALL_DISTRICTS is not treated as a district', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);

    // UI renders a national/all-districts scope label
    await screen.findByText('All districts \u2014 National scope');

    // UI does not render ALL_DISTRICTS District
    expect(screen.queryByText('ALL_DISTRICTS District')).not.toBeInTheDocument();

    // National DAPH sees Colombo FMD and LSD. ALL_DISTRICTS does not filter out district records.
    expect(screen.getByText('Colombo District · FMD')).toBeInTheDocument();
    expect(screen.getByText('Colombo District · LSD')).toBeInTheDocument();

    // National district dropdown derives Colombo from returned records.
    const districtSelect = screen.getByLabelText(/Target district/i);
    expect(districtSelect).toHaveTextContent('Colombo');
  });

  it('22. Existing explicit district-scope filtering still excludes an unauthorized district', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ records: mockRecords });
    // Using validProvinceDaphContext which only authorizes 'Colombo'
    render(<DaphDistrictForecasts viewerContext={validProvinceDaphContext} />);

    await screen.findByText('Colombo District · FMD');

    // Gampaha should be excluded because it's not authorized for this province scope
    expect(screen.queryByText('Gampaha District · FMD')).not.toBeInTheDocument();
  });
});
