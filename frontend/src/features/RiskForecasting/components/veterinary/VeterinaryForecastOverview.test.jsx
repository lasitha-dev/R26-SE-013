import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { VeterinaryForecastOverview } from './VeterinaryForecastOverview';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  listForecastRecords: vi.fn(),
}));

describe('VeterinaryForecastOverview Component Unit Tests', () => {
  const validVetContext = {
    userId: 'vet_officer_01',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: ['farm_1'],
    },
    permissions: {
      viewDataQuality: true,
      viewModelTransparency: true,
    },
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });



  it('Requests records only for assigned district from viewerContext and never for unauthorized districts', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => {
      expect(workflowApi.listForecastRecords).toHaveBeenCalledWith(
        expect.objectContaining({ district: 'Anuradhapura' })
      );
    });

    const calledDistricts = workflowApi.listForecastRecords.mock.calls.map((call) => call[0].district);
    expect(calledDistricts.every((d) => d === 'Anuradhapura')).toBe(true);
    expect(calledDistricts).not.toContain('Colombo');
  });

  it('Displays latest FMD and LSD records with LOW/MEDIUM/HIGH risk badges, fallback warnings, and disclaimers', async () => {
    const fmdRecordFixture = {
      forecast_id: 'fdr_fmd_100',
      disease: 'FMD',
      district: 'Anuradhapura',
      target_year: 2025,
      target_month: 1,
      risk_level: 'HIGH',
      probability_pct: 78.4,
      predicted_severity: 'MODERATE_OUTBREAK',
      status: 'GENERATED',
      generated_at: '2024-12-22T10:00:00Z',
      model_variant: 'Standard_FMD_v1',
      data_quality: 'PROXY',
      fallback_applied: true,
      source_year: 2024,
      source_month: 12,
      data_age_months: 12,
    };

    const lsdRecordFixture = {
      forecast_id: 'fdr_lsd_200',
      disease: 'LSD',
      district: 'Anuradhapura',
      target_year: 2025,
      target_month: 1,
      risk_level: 'LOW',
      probability_pct: 12.1,
      predicted_severity: null,
      status: 'APPROVED',
      generated_at: '2024-12-22T10:05:00Z',
      model_variant: 'Standard_LSD_v1',
      data_quality: 'EXACT',
      fallback_applied: false,
      source_year: 2025,
      source_month: 1,
      data_age_months: 0,
    };

    workflowApi.listForecastRecords.mockImplementation(({ disease }) => {
      if (disease === 'FMD') return Promise.resolve({ total_count: 1, limit: 50, offset: 0, records: [fmdRecordFixture] });
      if (disease === 'LSD') return Promise.resolve({ total_count: 1, limit: 50, offset: 0, records: [lsdRecordFixture] });
      return Promise.resolve({ total_count: 0, limit: 50, offset: 0, records: [] });
    });

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => {
      expect(screen.getByText('78.4%')).toBeInTheDocument();
    });

    expect(screen.getByText(/HIGH RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/LOW RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/Forecast decision records are immutable statistical early-warning estimates/i)).toBeInTheDocument();

    // Input age comes from the persisted data_age_months field; un-evaluated severity is labelled honestly
    expect(screen.getByText('12 months')).toBeInTheDocument();
    expect(screen.getByText('0 months')).toBeInTheDocument();
    expect(screen.getByText('Not evaluated')).toBeInTheDocument();
    expect(screen.queryByText(/SHAP/)).not.toBeInTheDocument();
  });

  it('renders the overview disclaimer section with health_and_safety and no biomedical identifier', async () => {
    workflowApi.listForecastRecords.mockImplementation(({ disease }) => {
      if (disease === 'FMD') return Promise.resolve({ total_count: 0, limit: 50, offset: 0, records: [] });
      return Promise.resolve({ total_count: 0, limit: 50, offset: 0, records: [] });
    });

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const disclaimerHeading = await screen.findByRole('heading', {
      name: /Epidemiological & Diagnostic Guardrails/i,
      level: 2,
    });
    const disclaimerSection = disclaimerHeading.closest('section');

    expect(within(disclaimerSection).getByText('health_and_safety')).toBeInTheDocument();
    expect(within(disclaimerSection).queryByText('biomedical')).not.toBeInTheDocument();
  });

  it('Empty state shows clear message and does not display 0%, LOW, or invented scientific values', async () => {
    workflowApi.listForecastRecords.mockImplementation(({ disease }) => {
      if (disease === 'FMD') return Promise.resolve({ total_count: 0, limit: 50, offset: 0, records: [] });
      return Promise.resolve({
        total_count: 1,
        limit: 50,
        offset: 0,
        records: [
          {
            forecast_id: 'fdr_lsd_999',
            disease: 'LSD',
            district: 'Anuradhapura',
            target_year: 2025,
            target_month: 1,
            risk_level: 'MEDIUM',
            probability_pct: 45.0,
          },
        ],
      });
    });

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => {
      expect(screen.getByText('No official stored forecast decision record exists for FMD in Anuradhapura District.')).toBeInTheDocument();
    });

    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    expect(screen.getByText('45.0%')).toBeInTheDocument();
  });



  it('Fails closed when viewer context has no authorized district or invalid context', () => {
    const invalidContext = {
      userId: 'vet_01',
      role: ROLES.VETERINARY_OFFICER,
      authorization: {
        scopeLevel: SCOPE_LEVELS.DISTRICT,
        authorizedDistricts: [],
        assignedFarmIds: [],
      },
      permissions: {},
    };

    render(<VeterinaryForecastOverview viewerContext={invalidContext} />);
    expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
  });

  it('Does NOT render any trends, charts, Advisory Centre, History, or outbox UI', () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    expect(screen.queryByText(/Trend/i)).toBeNull();
    expect(screen.queryByText(/Outbox/i)).toBeNull();
    expect(screen.queryByText(/Advisory Centre/i)).toBeNull();
    expect(screen.queryByText(/History/i)).toBeNull();
  });

  it('shows v2 relative risk, observed previous month and stored contributions without a live call', async () => {
    const v2Fmd = {
      forecast_id: 'fdr_v2_fmd', disease: 'FMD', district: 'Anuradhapura', target_year: 2025, target_month: 1,
      risk_level: 'MEDIUM', probability: 0.31, probability_pct: 31.0, predicted_severity: null, status: 'GENERATED',
      generated_at: '2026-10-13T00:00:00Z', model_variant: 'fmd_v2.0:A', model_version: 'fmd_v2.0', forecaster: 'A',
      deployment_status: 'back_tested', relative_risk: 2.4, data_quality: 'V2_MODEL', fallback_applied: false,
      source_year: 2024, source_month: 12, data_age_months: 1,
      previous_month_observation: { period: '2024-12', status: 'CONFIRMED_OUTBREAK', verified_cases: 4, deaths: 0, observed_severity: 'LOW' },
      contributions: [
        { feature: 'own_t1', value: 1, contribution_log_odds: 0.62 },
        { feature: 'rain_t1', value: 80, contribution_log_odds: -0.21 },
      ],
    };
    workflowApi.listForecastRecords.mockImplementation(({ disease }) => Promise.resolve({
      total_count: disease === 'FMD' ? 1 : 0, limit: 50, offset: 0, records: disease === 'FMD' ? [v2Fmd] : [],
    }));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('31.0%')).toBeInTheDocument());
    expect(screen.getByText('2.4× usual for this district and month')).toBeInTheDocument();
    expect(screen.getByText('Dec 2024: 4 verified cases, 0 deaths · LOW')).toBeInTheDocument();
    expect(screen.getByText('Back-tested candidate')).toBeInTheDocument();
    expect(screen.queryByText('Validated model')).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /EXPLAIN FORECAST/i })[0]);

    await waitFor(() => {
      expect(screen.getByText('Outbreak in this district last month')).toBeInTheDocument();
      expect(screen.getByText('Rainfall last month')).toBeInTheDocument();
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('shows a climatology record as a seasonal baseline, never as an assessed LOW RISK tier', async () => {
    const baseline = {
      forecast_id: 'fdr_v2_base', disease: 'FMD', district: 'Kandy', target_year: 2025, target_month: 1,
      risk_level: 'LOW', probability: 0.12, probability_pct: 12.0, predicted_severity: null, status: 'GENERATED',
      generated_at: '2026-10-13T00:00:00Z', model_variant: 'fmd_v2.0:climatology', model_version: 'fmd_v2.0',
      forecaster: 'climatology', deployment_status: 'baseline', relative_risk: 1.0, data_quality: 'V2_BASELINE',
      fallback_applied: true, source_year: 2024, source_month: 12, data_age_months: 1,
    };
    workflowApi.listForecastRecords.mockImplementation(({ disease }) => Promise.resolve({
      total_count: disease === 'FMD' ? 1 : 0, limit: 50, offset: 0, records: disease === 'FMD' ? [baseline] : [],
    }));

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('12.0%')).toBeInTheDocument());
    expect(screen.getByText('BASELINE')).toBeInTheDocument();
    expect(screen.queryByText(/^LOW$/)).not.toBeInTheDocument();
    expect(screen.getByText('Historical baseline')).toBeInTheDocument();
  });
});
