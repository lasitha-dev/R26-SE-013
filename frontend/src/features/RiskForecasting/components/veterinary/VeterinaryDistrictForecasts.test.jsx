import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VeterinaryDistrictForecasts } from './VeterinaryDistrictForecasts';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';

vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  createForecastRecord: vi.fn(),
}));

describe('VeterinaryDistrictForecasts Component', () => {
  const validDistrictVetContext = Object.freeze({
    userId: 'usr_vet_district_002',
    role: ROLES.VETERINARY_OFFICER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Vavuniya', 'Mannar']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: Object.freeze({
      viewDataQuality: true,
      viewModelTransparency: false,
      manageAlerts: true,
      recordResponse: true,
      viewReports: true,
    }),
  });

  const validProvinceVetContext = Object.freeze({
    userId: 'usr_vet_province_002',
    role: ROLES.VETERINARY_OFFICER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.PROVINCE,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Kurunegala', 'Puttalam']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: validDistrictVetContext.permissions,
  });

  const validFarmerContext = Object.freeze({
    userId: 'usr_farmer_001',
    role: ROLES.FARMER,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.FARM,
      registeredFarmDistrict: 'Vavuniya',
      authorizedDistricts: Object.freeze(['Vavuniya']),
      assignedFarmIds: Object.freeze(['FARM_001']),
    }),
    permissions: Object.freeze({
      viewModelTransparency: false,
    }),
  });

  const validDaphContext = Object.freeze({
    userId: 'usr_daph_001',
    role: ROLES.DAPH_OFFICIAL,
    authorization: Object.freeze({
      scopeLevel: SCOPE_LEVELS.NATIONAL,
      registeredFarmDistrict: null,
      authorizedDistricts: Object.freeze(['Vavuniya', 'Mannar', 'Colombo']),
      assignedFarmIds: Object.freeze([]),
    }),
    permissions: Object.freeze({
      viewDataQuality: true,
      viewModelTransparency: true,
    }),
  });

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. Invalid Access & Fail-Closed Guardrails
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
      render(<VeterinaryDistrictForecasts viewerContext={validFarmerContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects DAPH_OFFICIAL role', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDaphContext} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER with FARM scopeLevel', () => {
      const invalidVetScope = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.FARM,
        },
      };
      render(<VeterinaryDistrictForecasts viewerContext={invalidVetScope} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('rejects VETERINARY_OFFICER with NATIONAL scopeLevel', () => {
      const invalidVetScope = {
        ...validDistrictVetContext,
        authorization: {
          ...validDistrictVetContext.authorization,
          scopeLevel: SCOPE_LEVELS.NATIONAL,
        },
      };
      render(<VeterinaryDistrictForecasts viewerContext={invalidVetScope} />);
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

  // 3. Accessibility & Zero Network Calls
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

  // 4. Visual & Responsive Layout Contracts
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

  // 5. Interactive Demo Mode & Official Record Workflow Tests
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

      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.getByRole('button', { name: /update forecast/i })).not.toBeDisabled());

      const updateBtn = screen.getByRole('button', { name: /update forecast/i });
      fireEvent.click(updateBtn);

      await waitFor(() => expect(mockFetchCombined).toHaveBeenCalledTimes(2));

      const callArg = mockFetchCombined.mock.calls[0][0];
      expect(callArg.districts).toEqual(['Vavuniya', 'Mannar']);
      expect(callArg.district).toBeUndefined();
    });

    it('Clicking "Save as Official Forecast Record" submits authoritative params without client probability/risk', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: {
            disease: 'FMD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Vavuniya', probability_pct: 65.5, risk_level: 'HIGH' }],
          },
          error: null,
        },
        lsd: {
          status: 'success',
          data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] },
          error: null,
        },
      });

      workflowApi.createForecastRecord.mockResolvedValue({
        forecast_id: 'fdr_saved_001',
        disease: 'FMD',
        district: 'Vavuniya',
        target_year: 2024,
        target_month: 1,
        risk_level: 'HIGH',
        status: 'GENERATED',
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictVetContext,
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
        </DemoForecastingAuthContext.Provider>
      );

      const saveBtn = await screen.findByRole('button', { name: /Save as Official Forecast Record/i });
      fireEvent.click(saveBtn);

      expect(workflowApi.createForecastRecord).toHaveBeenCalledWith({
        disease: 'FMD',
        district: 'Vavuniya',
        year: 2024,
        month: 1,
        trigger_type: 'MANUAL',
        generated_by: 'usr_vet_district_002',
        idempotency_key: 'usr_vet_district_002_Vavuniya_FMD_2024_1_manual_save',
      });

      const callArgs = workflowApi.createForecastRecord.mock.calls[0][0];
      expect(callArgs.probability_pct).toBeUndefined();
      expect(callArgs.predicted_probability).toBeUndefined();
      expect(callArgs.risk_level).toBeUndefined();

      expect(await screen.findByText('Official Record Saved')).toBeInTheDocument();
      expect(screen.getByText('ID: fdr_saved_001')).toBeInTheDocument();
    });

    it('Clicking LSD "Save as Official Forecast Record" submits disease: "LSD" and the target card district', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: { disease: 'FMD', target_year: 2024, target_month: 1, districts: [] },
          error: null,
        },
        lsd: {
          status: 'success',
          data: {
            disease: 'LSD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Mannar', probability_pct: 35.0, risk_level: 'MEDIUM' }],
          },
          error: null,
        },
      });

      workflowApi.createForecastRecord.mockResolvedValue({
        forecast_id: 'fdr_lsd_saved_002',
        disease: 'LSD',
        district: 'Mannar',
        year: 2024,
        month: 1,
        risk_level: 'MEDIUM',
        status: 'GENERATED',
      });

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictVetContext,
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
        </DemoForecastingAuthContext.Provider>
      );

      const saveBtns = await screen.findAllByRole('button', { name: /Save as Official Forecast Record/i });
      fireEvent.click(saveBtns[0]); // First visible save button belongs to LSD section (since FMD districts array is empty)

      expect(workflowApi.createForecastRecord).toHaveBeenCalledWith({
        disease: 'LSD',
        district: 'Mannar',
        year: 2024,
        month: 1,
        trigger_type: 'MANUAL',
        generated_by: 'usr_vet_district_002',
        idempotency_key: 'usr_vet_district_002_Mannar_LSD_2024_1_manual_save',
      });

      expect(await screen.findByText('Official Record Saved')).toBeInTheDocument();
      expect(screen.getByText('ID: fdr_lsd_saved_002')).toBeInTheDocument();
    });

    it('Handles save errors and clears stale save confirmations when input parameters change', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: {
            disease: 'FMD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Vavuniya', probability_pct: 65.5, risk_level: 'HIGH' }],
          },
          error: null,
        },
        lsd: {
          status: 'success',
          data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] },
          error: null,
        },
      });

      workflowApi.createForecastRecord.mockRejectedValue(new Error('Record already exists'));

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictVetContext,
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
        </DemoForecastingAuthContext.Provider>
      );

      const saveBtn = await screen.findByRole('button', { name: /Save as Official Forecast Record/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(screen.getByText('Record already exists')).toBeInTheDocument();
      });

      // Change month selection -> clears error/saved state
      const monthSelect = screen.getByLabelText('Forecast month');
      fireEvent.change(monthSelect, { target: { value: '2' } });

      expect(screen.queryByText('Record already exists')).not.toBeInTheDocument();
    });

    it('Blocks duplicate save click while request is pending', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts').mockResolvedValue({
        overallStatus: 'success',
        fmd: {
          status: 'success',
          data: {
            disease: 'FMD',
            target_year: 2024,
            target_month: 1,
            districts: [{ district: 'Vavuniya', probability_pct: 65.5, risk_level: 'HIGH' }],
          },
          error: null,
        },
        lsd: {
          status: 'success',
          data: { disease: 'LSD', target_year: 2024, target_month: 1, districts: [] },
          error: null,
        },
      });

      let resolveSave;
      const pendingPromise = new Promise((resolve) => {
        resolveSave = resolve;
      });
      workflowApi.createForecastRecord.mockReturnValue(pendingPromise);

      const mockAuthValue = {
        isDemoEnabled: true,
        isDemoAuthenticated: true,
        viewerContext: validDistrictVetContext,
      };

      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');

      render(
        <DemoForecastingAuthContext.Provider value={mockAuthValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />
        </DemoForecastingAuthContext.Provider>
      );

      const saveBtn = await screen.findByRole('button', { name: /Save as Official Forecast Record/i });
      fireEvent.click(saveBtn);
      fireEvent.click(saveBtn);

      expect(workflowApi.createForecastRecord).toHaveBeenCalledTimes(1);

      resolveSave({
        forecast_id: 'fdr_saved_002',
        disease: 'FMD',
        district: 'Vavuniya',
        target_year: 2024,
        target_month: 1,
        risk_level: 'HIGH',
        status: 'GENERATED',
      });
    });
  });
});
