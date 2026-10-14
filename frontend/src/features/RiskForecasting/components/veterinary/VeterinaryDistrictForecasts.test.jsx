import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { VeterinaryDistrictForecasts } from './VeterinaryDistrictForecasts';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';

vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  createForecastRecord: vi.fn(),
  listForecastRecords: vi.fn(),
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

    it('renders the scientific boundaries section with health_and_safety and no biomedical identifier', () => {
      render(<VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} />);

      const boundariesHeading = screen.getByRole('heading', {
        name: /Scientific & Diagnostic Guardrails/i,
        level: 2,
      });
      const boundariesSection = boundariesHeading.closest('section');

      expect(within(boundariesSection).getByText('health_and_safety')).toBeInTheDocument();
      expect(within(boundariesSection).queryByText('biomedical')).not.toBeInTheDocument();
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
  describe('Connected mode shows the stored (official) forecasts only', () => {
    const rec = (disease, district, overrides) => ({
      forecast_id: `fdr_${disease}_${district}`, disease, district, target_year: 2025, target_month: 1,
      probability: 0.31, probability_pct: 31.0, risk_level: 'MEDIUM', predicted_severity: null,
      status: 'GENERATED', generated_at: '2026-10-13T00:00:00Z', model_version: 'fmd_v2.0', forecaster: 'O',
      deployment_status: 'back_tested', relative_risk: 2.4, probability_low: 0.18, probability_high: 0.47,
      interval_level: 0.8, data_quality: 'V2_MODEL', fallback_applied: false,
      ...overrides,
    });
    const authValue = {
      isDemoEnabled: true,
      isDemoAuthenticated: true,
      viewerContext: validDistrictVetContext,
      logout: vi.fn(),
    };
    const renderConnected = async (initialProps = {}) => {
      const { DemoForecastingAuthContext } = await import('../../context/DemoForecastingAuthContext.jsx');
      return render(
        <DemoForecastingAuthContext.Provider value={authValue}>
          <VeterinaryDistrictForecasts viewerContext={validDistrictVetContext} {...initialProps} />
        </DemoForecastingAuthContext.Provider>
      );
    };

    it('restricts the selector to authorized districts and reads the stored records of every authorized district for both diseases', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: [] });
      await renderConnected();

      const options = Array.from(screen.getByLabelText('Target district').querySelectorAll('option')).map((o) => o.value);
      expect(options).toEqual(['ALL', 'Vavuniya', 'Mannar']);

      await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalledTimes(4));
      const calls = workflowApi.listForecastRecords.mock.calls.map(([f]) => `${f.disease}:${f.district}`).sort();
      expect(calls).toEqual(['FMD:Mannar', 'FMD:Vavuniya', 'LSD:Mannar', 'LSD:Vavuniya']);
    });

    it('never runs a model on demand: no demo prediction API, no save-as-record action', async () => {
      const demoApi = await import('../../services/demoForecastingApi.js');
      const liveSpy = vi.spyOn(demoApi, 'fetchAuthorizedDiseaseForecasts');
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      workflowApi.listForecastRecords.mockImplementation(async ({ disease, district }) => ({ records: [rec(disease, district)] }));

      await renderConnected();
      await waitFor(() => expect(screen.getByText('Foot-and-Mouth Disease (FMD) District Forecasts')).toBeInTheDocument());

      expect(liveSpy).not.toHaveBeenCalled();
      expect(fetchSpy).not.toHaveBeenCalled();
      expect(workflowApi.createForecastRecord).not.toHaveBeenCalled();
      expect(screen.queryByRole('button', { name: /save as official forecast record/i })).not.toBeInTheDocument();
      expect(screen.getAllByText('MEDIUM RISK').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('80% range 18–47%').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('2.4× usual for this district and month').length).toBeGreaterThanOrEqual(1);
    });

    it('shows a baseline record as the usual level, never as an assessed LOW RISK', async () => {
      workflowApi.listForecastRecords.mockImplementation(async ({ disease, district }) => ({
        records: [rec(disease, district, { forecaster: 'climatology', deployment_status: 'baseline', risk_level: 'LOW', probability_pct: 12, relative_risk: 1.0, fallback_applied: true, data_quality: 'V2_BASELINE' })],
      }));
      await renderConnected();
      await waitFor(() => expect(screen.getAllByText('USUAL LEVEL').length).toBeGreaterThanOrEqual(1));
      expect(screen.queryByText('LOW RISK')).not.toBeInTheDocument();
    });

    it('says so when no forecast has been issued for a district, instead of inventing one', async () => {
      workflowApi.listForecastRecords.mockImplementation(async ({ disease, district }) => (
        district === 'Vavuniya' ? { records: [rec(disease, district)] } : { records: [] }
      ));
      await renderConnected();
      await waitFor(() => expect(screen.getByText(/No FMD forecast has been issued for/)).toBeInTheDocument());
      expect(screen.getByText(/No LSD forecast has been issued for/)).toBeInTheDocument();
    });

    it('ignores superseded records and prefers a v2 record', async () => {
      workflowApi.listForecastRecords.mockImplementation(async ({ disease, district }) => ({
        records: [
          rec(disease, district, { forecast_id: 'old_v2', status: 'SUPERSEDED', probability_pct: 99, risk_level: 'HIGH' }),
          rec(disease, district, { forecast_id: 'v1', model_version: undefined, forecaster: undefined, probability_pct: 77, risk_level: 'HIGH', generated_at: '2026-10-20T00:00:00Z' }),
          rec(disease, district, { forecast_id: 'v2', probability_pct: 31 }),
        ],
      }));
      await renderConnected();
      await waitFor(() => expect(screen.getAllByText('31.0%').length).toBeGreaterThanOrEqual(1));
      expect(screen.queryByText('99.0%')).not.toBeInTheDocument();
      expect(screen.queryByText('77.0%')).not.toBeInTheDocument();
    });

    it('re-reads only the chosen district when one is selected and the form is submitted', async () => {
      workflowApi.listForecastRecords.mockResolvedValue({ records: [] });
      await renderConnected();
      await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalledTimes(4));

      fireEvent.change(screen.getByLabelText('Target district'), { target: { value: 'Mannar' } });
      fireEvent.change(screen.getByLabelText('Forecast month'), { target: { value: 5 } });
      fireEvent.change(screen.getByLabelText('Forecast year'), { target: { value: 2025 } });
      expect(workflowApi.listForecastRecords).toHaveBeenCalledTimes(4); // dropdown changes call nothing

      fireEvent.click(screen.getByRole('button', { name: /update forecast/i }));
      await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalledTimes(6));
      const last = workflowApi.listForecastRecords.mock.calls.slice(-2).map(([f]) => f);
      expect(last.every((f) => f.district === 'Mannar' && f.target_year === 2025 && f.target_month === 5)).toBe(true);
    });

    it('reports a failed read without showing stale or invented data', async () => {
      workflowApi.listForecastRecords.mockRejectedValue(new Error('down'));
      await renderConnected();
      await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/could not be loaded/i));
      expect(screen.queryByText(/% range/)).not.toBeInTheDocument();
    });
  });
});
