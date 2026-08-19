import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VeterinaryDistrictForecasts } from './VeterinaryDistrictForecasts';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

describe('VeterinaryDistrictForecasts Component', () => {
  const validDistrictVetContext = {
    userId: 'usr_vet_district_002',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Vavuniya', 'Mannar'],
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

  const validProvinceVetContext = {
    userId: 'usr_vet_province_002',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: ['Kurunegala', 'Puttalam'],
      assignedFarmIds: [],
    },
    permissions: validDistrictVetContext.permissions,
  };

  // 1. Access & Fail-Closed Gating Tests
  describe('Access & Fail-Closed Gating', () => {
    it('fails closed when viewerContext is missing (null)', () => {
      render(<VeterinaryDistrictForecasts viewerContext={null} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('fails closed when viewerContext is invalid', () => {
      render(<VeterinaryDistrictForecasts viewerContext={{ invalid: true }} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects FARMER role', () => {
      const farmerContext = {
        userId: 'usr_farmer_002',
        role: ROLES.FARMER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.FARM,
          registeredFarmDistrict: 'Vavuniya',
          authorizedDistricts: ['Vavuniya'],
          assignedFarmIds: ['FARM_VAV_01'],
        },
        permissions: {},
      };
      render(<VeterinaryDistrictForecasts viewerContext={farmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects DAPH_OFFICIAL role', () => {
      const daphContext = {
        userId: 'usr_daph_002',
        role: ROLES.DAPH_OFFICIAL,
        authorization: {
          scopeLevel: SCOPE_LEVELS.NATIONAL,
          registeredFarmDistrict: null,
          authorizedDistricts: [],
          assignedFarmIds: [],
        },
        permissions: {},
      };
      render(<VeterinaryDistrictForecasts viewerContext={daphContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER with FARM scopeLevel', () => {
      const farmScopeVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.FARM,
        },
      };
      render(<VeterinaryDistrictForecasts viewerContext={farmScopeVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER with NATIONAL scopeLevel', () => {
      const nationalScopeVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.NATIONAL,
        },
      };
      render(<VeterinaryDistrictForecasts viewerContext={nationalScopeVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is missing or null', () => {
      const noDistrictsVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          authorizedDistricts: null,
        },
      };
      render(<VeterinaryDistrictForecasts viewerContext={noDistrictsVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('fails closed when authorizedDistricts is an empty array', () => {
      const emptyDistrictsVet = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          authorizedDistricts: [],
        },
      };
      render(<VeterinaryDistrictForecasts viewerContext={emptyDistrictsVet} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // 2. Authorized Scope & Workspace Display
  describe('Authorized Scope & Workspace Display', () => {
    it('accepts valid DISTRICT-scoped veterinary officer', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);
      expect(screen.getByText('District Risk Forecasts')).toBeInTheDocument();
      expect(screen.getByText('DISTRICT')).toBeInTheDocument();
    });

    it('accepts valid PROVINCE-scoped veterinary officer', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validProvinceVetContext} />);
      expect(screen.getByText('District Risk Forecasts')).toBeInTheDocument();
      expect(screen.getByText('PROVINCE')).toBeInTheDocument();
    });

    it('displays only explicitly authorized districts from viewerContext without national expansion', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);
      expect(screen.getByText('Vavuniya District')).toBeInTheDocument();
      expect(screen.getByText('Mannar District')).toBeInTheDocument();

      // Unauthorized districts must NOT appear
      expect(screen.queryByText('Colombo District')).not.toBeInTheDocument();
      expect(screen.queryByText('Gampaha District')).not.toBeInTheDocument();
    });

    it('does NOT render an editable district selector or role selector', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select district/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/select role/i)).not.toBeInTheDocument();
    });
  });

  // 3. UI_READY_API_BLOCKED Notice & Workspace Cards
  describe('UI_READY_API_BLOCKED Integration Notice & Workspace Cards', () => {
    it('renders secure-access integration notice distinguishing available forecasting service from missing backend authorization', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      expect(
        screen.getByText('District forecasts are awaiting secure access integration')
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /The forecasting service is available, but veterinary district authorization is not yet enforced by the backend/i
        )
      ).toBeInTheDocument();
    });

    it('renders all 4 blocked workspace cards (Period, FMD, LSD, Comparative View)', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      expect(screen.getByText('Forecast Period')).toBeInTheDocument();
      expect(screen.getByText('Foot-and-Mouth Disease (FMD)')).toBeInTheDocument();
      expect(screen.getByText('Lumpy Skin Disease (LSD)')).toBeInTheDocument();
      expect(screen.getByText('Comparative District View')).toBeInTheDocument();

      expect(screen.getByText('Integration blocked')).toBeInTheDocument();
      expect(screen.getAllByText('Forecast loading blocked')).toHaveLength(2);
      expect(screen.getByText('Not connected')).toBeInTheDocument();
    });

    it('does NOT contain month/year selection controls, non-functional buttons, or placeholders like --%', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/month/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/year/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/--%/)).not.toBeInTheDocument();
    });

    it('does NOT render probabilities, risk badges, charts, rankings, or sample forecasts', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
      expect(screen.queryByText(/HIGH RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/MEDIUM RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/LOW RISK/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Rank/i)).not.toBeInTheDocument();
    });

    it('distinguishes forecasts from confirmed alerts and individual farm diagnosis', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      expect(
        screen.getByText(
          /Disease risk forecasts are district-level early-warning estimates/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /They do not confirm disease on an individual farm, nor do they constitute a confirmed outbreak alert/i
        )
      ).toBeInTheDocument();
    });

    it('does NOT render farm-level risk language, AI Diagnosis CTAs, or technical Stage 2 outputs', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      expect(screen.queryByText(/farm-level/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Stage 2/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/\bECE\b/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/log_odds/i)).not.toBeInTheDocument();
    });
  });

  // 4. Accessibility & Zero Network Calls
  describe('Accessibility & Zero Network Calls', () => {
    it('uses role="status" and aria-live="polite" for the secure-integration notice, and not role="alert"', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toBeInTheDocument();
      expect(statusRegion).toHaveAttribute('aria-live', 'polite');
      expect(statusRegion).toHaveAttribute(
        'aria-labelledby',
        'vet-forecast-integration-heading'
      );

      // Valid access must NOT render authorization role="alert"
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('hides decorative Material symbols from assistive technology', () => {
      const { container } = render(
        <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
      );
      const icons = container.querySelectorAll('.material-symbols-outlined');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });

    it('does not mutate input viewerContext prop (deeply frozen object test)', () => {
      const frozenContext = {
        userId: 'usr_vet_frozen_002',
        role: ROLES.VETERINARY_OFFICER,
        authorization: {
          scopeLevel: SCOPE_LEVELS.DISTRICT,
          registeredFarmDistrict: null,
          authorizedDistricts: Object.freeze(['Vavuniya', 'Mullaitivu']),
          assignedFarmIds: Object.freeze([]),
        },
        permissions: Object.freeze({
          viewDataQuality: true,
          viewModelTransparency: false,
          manageAlerts: true,
          recordResponse: true,
          viewReports: true,
        }),
      };
      Object.freeze(frozenContext.authorization);
      Object.freeze(frozenContext);

      expect(() => {
        render(<VeterinaryDistrictForecasts viewerContext={frozenContext} />);
      }).not.toThrow();

      expect(frozenContext.role).toBe(ROLES.VETERINARY_OFFICER);
      expect(frozenContext.authorization.authorizedDistricts).toEqual(['Vavuniya', 'Mullaitivu']);
    });

    it('makes zero network or API fetch calls', () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });

  // 5. Visual & Responsive Token Contracts
  describe('Visual & Responsive Layout Contracts', () => {
    it('uses max-w-6xl outer container with flex-wrap district scope badges', () => {
      const { container } = render(
        <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
      );

      const outerContainer = container.firstElementChild;
      expect(outerContainer.className).toContain('max-w-6xl');
      expect(outerContainer.className).toContain('text-on-surface');

      const scopeHeading = screen.getByText('Authorized forecast areas');
      const badgeContainer = scopeHeading.closest('section').querySelector('.flex-wrap');
      expect(badgeContainer).toBeInTheDocument();
    });
  });

  describe('Veterinary Authenticated Demo Mode Direct UI Tests', () => {
    it('renders protected forecast controls and restricts selector to authorizedDistricts in demo mode', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const mockFetchCombined = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: {
            disease: 'FMD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Vavuniya', probability_pct: 65, risk_level: 'HIGH' }],
          },
          error: null,
        },
        lsd: {
          status: 'success',
          data: {
            disease: 'LSD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Vavuniya', probability_pct: 25, risk_level: 'LOW' }],
          },
          error: null,
        },
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictVetContext,
        logout: vi.fn(),
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
        </DemoForecastingAuthContext.Provider>
      );

      // Verify controls render
      const districtSelect = screen.getByLabelText('Target district');
      expect(districtSelect).toBeInTheDocument();

      // Options must include "ALL" plus Vavuniya & Mannar, but NO Colombo
      const options = Array.from(districtSelect.querySelectorAll('option')).map((o) => o.value);
      expect(options).toEqual(['ALL', 'Vavuniya', 'Mannar']);
      expect(options).not.toContain('Colombo');

      const { waitFor } = await import('@testing-library/react');
      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.getByText('Foot-and-Mouth Disease (FMD) District Forecasts')).toBeInTheDocument());

      // Verify FMD and LSD sections render separately
      expect(screen.getByText('Lumpy Skin Disease (LSD) District Forecasts')).toBeInTheDocument();

      // Verify non-diagnostic disclaimer
      expect(screen.getByText(/Disease risk forecasts are district-level early-warning estimates/i)).toBeInTheDocument();

      // Verify no model variant selector exists
      expect(screen.queryByLabelText(/model variant/i)).not.toBeInTheDocument();
    });

    it('submits exact explicit array when "All authorized districts" is selected', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const mockFetchCombined = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: { status: 'success', data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [] }, error: null },
        lsd: { status: 'success', data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] }, error: null },
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictVetContext,
        logout: vi.fn(),
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
        </DemoForecastingAuthContext.Provider>
      );

      const { waitFor, fireEvent } = await import('@testing-library/react');
      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.getByRole('button', { name: /update forecast/i })).not.toBeDisabled());

      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      fireEvent.click(updateBtn);

      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(2));

      const callArg = mockFetchCombined.mock.calls[0][0];
      expect(callArg.districts).toEqual(['Vavuniya', 'Mannar']);
      expect(callArg.district).toBeUndefined();
    });
  });
});
