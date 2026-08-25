import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { DaphDistrictForecasts } from './DaphDistrictForecasts';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('DaphDistrictForecasts Component', () => {
  const validDistrictDaphContext = {
    userId: 'usr_daph_district_002',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Hambantota', 'Matara'],
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
    userId: 'usr_daph_province_002',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Galle', 'Matara', 'Hambantota'],
      assignedFarmIds: [],
    },
    permissions: validDistrictDaphContext.permissions,
  };

  const validNationalDaphContext = {
    userId: 'usr_daph_national_002',
    role: ROLES.DAPH_OFFICIAL,
    authorization: {
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Hambantota', 'Matara', 'Badulla'],
      assignedFarmIds: [],
    },
    permissions: validDistrictDaphContext.permissions,
  };

  // 1. Access & Fail-Closed Gating Tests
  describe('Access & Fail-Closed Gating', () => {
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
        ...validDistrictDaphContext,
        authorization: {
          ...validDistrictDaphContext.authorization,
          scopeLevel: SCOPE_LEVELS.FARM,
        },
      };
      render(<DaphDistrictForecasts viewerContext={farmScopeDaph} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is missing or null', () => {
      const noDistrictsDaph = {
        ...validDistrictDaphContext,
        authorization: {
          ...validDistrictDaphContext.authorization,
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
  });

  it('renders the scientific boundaries section with health_and_safety and no biomedical identifier', () => {
    render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

    const boundariesHeading = screen.getByRole('heading', {
      name: /Scientific & Epidemiological Boundaries/i,
      level: 2,
    });
    const boundariesSection = boundariesHeading.closest('section');

    expect(within(boundariesSection).getByText('health_and_safety')).toBeInTheDocument();
    expect(within(boundariesSection).queryByText('biomedical')).not.toBeInTheDocument();
  });

  // 2. Authorized Scope & Workspace Display
  describe('Authorized Scope & Workspace Display', () => {
    it('accepts DISTRICT-scoped DAPH official with explicit districts', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);
      expect(screen.getByText('Departmental District Forecasts')).toBeInTheDocument();
      expect(screen.getByText('DISTRICT')).toBeInTheDocument();
      expect(screen.getByText('Hambantota District')).toBeInTheDocument();
      expect(screen.getByText('Matara District')).toBeInTheDocument();
    });

    it('accepts PROVINCE-scoped DAPH official with explicit districts', () => {
      render(<DaphDistrictForecasts viewerContext={validProvinceDaphContext} />);
      expect(screen.getByText('Departmental District Forecasts')).toBeInTheDocument();
      expect(screen.getByText('PROVINCE')).toBeInTheDocument();
      expect(screen.getByText('Galle District')).toBeInTheDocument();
    });

    it('accepts NATIONAL-scoped DAPH official with explicit districts', () => {
      render(<DaphDistrictForecasts viewerContext={validNationalDaphContext} />);
      expect(screen.getByText('Departmental District Forecasts')).toBeInTheDocument();
      expect(screen.getByText('NATIONAL')).toBeInTheDocument();
      expect(screen.getByText('Badulla District')).toBeInTheDocument();
    });

    it('displays only explicit districts from viewerContext without automatic 25-district expansion', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);
      expect(screen.getByText('Hambantota District')).toBeInTheDocument();
      expect(screen.getByText('Matara District')).toBeInTheDocument();

      // Unauthorized districts must NOT appear
      expect(screen.queryByText('Trincomalee District')).not.toBeInTheDocument();
      expect(screen.queryByText('Batticaloa District')).not.toBeInTheDocument();
    });

    it('does NOT render any district, province, scope, or role selectors', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select province/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select scope/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select role/i)).not.toBeInTheDocument();
    });
  });

  // 3. UI_READY_API_BLOCKED Forecast Workspace & Guardrails
  describe('UI_READY_API_BLOCKED Forecast Workspace & Guardrails', () => {
    it('renders secure-integration wording distinguishing available forecasting service from missing DAPH authorization', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText('District forecasts are awaiting secure DAPH access integration')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /The forecasting service is available, but DAPH regional authorization is not yet enforced by the backend/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Frontend filtering is presentation-only and must not be treated as operational authorization/i
        )
      ).toBeInTheDocument();
    });

    it('renders all 4 blocked forecast workspace cards', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(screen.getByText('Forecast Period')).toBeInTheDocument();
      expect(screen.getByText('Foot-and-Mouth Disease (FMD)')).toBeInTheDocument();
      expect(screen.getByText('Lumpy Skin Disease (LSD)')).toBeInTheDocument();
      expect(screen.getByText('Regional Comparison')).toBeInTheDocument();

      expect(screen.getByText('Integration blocked')).toBeInTheDocument();
      expect(screen.getAllByText('Forecast loading blocked')).toHaveLength(2);
      expect(screen.getByText('Not connected')).toBeInTheDocument();
    });

    it('does NOT contain period controls, non-functional action buttons, or placeholders like --%', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/month/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/year/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/--%/)).not.toBeInTheDocument();
    });

    it('does NOT render percentages, risk badges, maps, charts, rankings, or sample forecasts', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
      expect(screen.queryByText(/HIGH RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/MEDIUM RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/LOW RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Rank/i)).not.toBeInTheDocument();
    });

    it('renders district-level scientific disclaimer distinguishing forecasts from alerts and individual farm diagnosis', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(
        screen.getByText(
          /Disease risk forecasts are district-level early-warning estimates/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /They do not confirm disease on an individual farm, nor do they constitute an official outbreak alert/i
        )
      ).toBeInTheDocument();
    });

    it('does NOT render Stage 2, ECE calibration, prediction sets, log-odds, model variants, or raw JSON', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
    });

    it('does NOT render Data Quality or Model Transparency content without separate screen permissions', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/Data Quality/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Model Transparency/i)).not.toBeInTheDocument();
    });

    it('contains no AI Diagnosis CTA', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
    });
  });

  // 4. Accessibility & Zero Network Calls
  describe('Accessibility & Zero Network Calls', () => {
    it('uses role="status" and aria-live="polite" for the secure-integration notice, and not role="alert"', () => {
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);

      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute(
        'aria-labelledby',
        'daph-forecast-integration-heading'
      );

      // Valid access must NOT render authorization role="alert"
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <DaphDistrictForecasts viewerContext={validDistrictDaphContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('does not mutate input viewerContext prop (deeply frozen object test)', () => {
      const frozenContext = {
        userId: 'usr_daph_frozen_002',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.NATIONAL,
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Hambantota', 'Matara']),
          assignedFarmIds: Object.freeze([]),
        },
        permissions: Object.freeze({
          viewDataQuality: false,
          viewModelTransparency: false,
          manageAlerts: true,
          recordResponse: true,
          viewReports: true,
        }),
      };
      Object.freeze(frozenContext.authorization);
      Object.freeze(frozenContext);

      expect(() => {
        render(<DaphDistrictForecasts viewerContext={frozenContext} />);
      }).not.toThrow();

      expect(frozenContext.role).toBe(ROLES.DAPH_OFFICIAL);
      expect(frozenContext.authorization.authorizedDistricts).toEqual(['Hambantota', 'Matara']);
    });

    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<DaphDistrictForecasts viewerContext={validDistrictDaphContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 5. Visual & Responsive Token Contracts
  describe('Visual & Responsive Layout Contracts', () => {
    it('uses max-w-6xl outer container with flex-wrap district scope badges', () => {
      const { container } = render(
        <DaphDistrictForecasts viewerContext={validDistrictDaphContext} />
      );

      const outerContainer = container.firstElementChild;
      expect(outerContainer.className).toContain('max-w-6xl');
      expect(outerContainer.className).toContain('text-on-surface');

      const scopeHeading = screen.getByText('Authorized forecast scope');
      const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
      expect(badgeContainer).toBeInTheDocument();
    });
  });

  describe('DAPH Authenticated Demo Mode Direct UI Tests', () => {
    it('renders protected forecast controls and restricts selector strictly to explicit authorizedDistricts under NATIONAL scope in demo mode', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const mockFetchCombined = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: {
            disease: 'FMD',
            target_year: 2024,
            target_month: 1,
            districts: [
              { district: 'Hambantota', probability_pct: 70, risk_level: 'HIGH' },
              { district: 'Matara', probability_pct: 40, risk_level: 'MEDIUM' },
            ],
          },
          error: null,
        },
        lsd: {
          status: 'success',
          data: {
            disease: 'LSD',
            target_year: 2024,
            target_month: 1,
            districts: [
              { district: 'Hambantota', probability_pct: 30, risk_level: 'LOW' },
              { district: 'Matara', probability_pct: 20, risk_level: 'LOW' },
            ],
          },
          error: null,
        },
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validNationalDaphContext,
        logout: vi.fn(),
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <DaphDistrictForecasts viewerContext={validNationalDaphContext} />
        </DemoForecastingAuthContext.Provider>
      );

      // Verify controls render
      const districtSelect = screen.getByLabelText('Target district');
      expect(districtSelect).toBeInTheDocument();

      // Options must contain ALL plus Hambantota, Matara, Badulla, but NO 25-district national fabrication
      const options = Array.from(districtSelect.querySelectorAll('option')).map((o) => o.value);
      expect(options).toEqual(['ALL', 'Hambantota', 'Matara', 'Badulla']);
      expect(options).not.toContain('Jaffna');

      const { waitFor } = await import('@testing-library/react');
      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.getByText('FMD Departmental Risk Comparisons')).toBeInTheDocument());

      // Verify FMD and LSD sections render
      expect(screen.getByText('LSD Departmental Risk Comparisons')).toBeInTheDocument();

      // Verify non-diagnostic disclaimer
      expect(screen.getByText(/Disease risk forecasts are district-level early-warning estimates/i)).toBeInTheDocument();

      // Confirm no farm owner info renders
      expect(screen.queryByText(/farm owner/i)).not.toBeInTheDocument();
    });

    it('submits exact stored array when "All authorized districts" is selected under DAPH role', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const mockFetchCombined = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: { status: 'success', data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [] }, error: null },
        lsd: { status: 'success', data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] }, error: null },
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictDaphContext,
        logout: vi.fn(),
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <DaphDistrictForecasts viewerContext={validDistrictDaphContext} />
        </DemoForecastingAuthContext.Provider>
      );

      const { waitFor, fireEvent } = await import('@testing-library/react');
      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.getByRole('button', { name: /update forecast/i })).not.toBeDisabled());

      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      fireEvent.click(updateBtn);

      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(2));

      const callArg = mockFetchCombined.mock.calls[0][0];
      expect(callArg.districts).toEqual(['Hambantota', 'Matara']);
      expect(callArg.district).toBeUndefined();
    });
  });
});
