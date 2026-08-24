import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VeterinaryForecastOverview, getNextTargetPeriod, getLatestRecord } from './VeterinaryForecastOverview';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  listForecastRecords: vi.fn(),
  createForecastRecord: vi.fn(),
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

  it('Pure helper getNextTargetPeriod calculates normal month and December rollover', () => {
    const normal = getNextTargetPeriod(new Date(2026, 7, 15)); // August -> Sept 2026
    expect(normal).toEqual({ targetYear: 2026, targetMonth: 9 });

    const dec = getNextTargetPeriod(new Date(2026, 11, 20)); // December -> Jan 2027
    expect(dec).toEqual({ targetYear: 2027, targetMonth: 1 });
  });

  it('Pure helper getLatestRecord sorts deterministically by year, month, and timestamp descending', () => {
    const records = [
      { forecast_id: 'rec_old', target_year: 2024, target_month: 5, generated_at: '2024-05-01T10:00:00Z' },
      { forecast_id: 'rec_new', target_year: 2024, target_month: 6, generated_at: '2024-06-01T10:00:00Z' },
      { forecast_id: 'rec_mid', target_year: 2024, target_month: 5, generated_at: '2024-05-02T10:00:00Z' },
    ];
    const latest = getLatestRecord(records);
    expect(latest.forecast_id).toBe('rec_new');
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
      target_year: 2026,
      target_month: 9,
      risk_level: 'HIGH',
      probability_pct: 78.4,
      predicted_severity: 'MODERATE_OUTBREAK',
      status: 'GENERATED',
      generated_at: '2026-08-22T10:00:00Z',
      model_variant: 'Standard_FMD_v1',
      data_quality: 'PROXY',
      fallback_applied: true,
      source_year: 2025,
      source_month: 9,
      proxy_data_age_days: 14,
    };

    const lsdRecordFixture = {
      forecast_id: 'fdr_lsd_200',
      disease: 'LSD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 9,
      risk_level: 'LOW',
      probability_pct: 12.1,
      predicted_severity: null,
      status: 'APPROVED',
      generated_at: '2026-08-22T10:05:00Z',
      model_variant: 'Standard_LSD_v1',
      data_quality: 'EXACT',
      fallback_applied: false,
      source_year: 2026,
      source_month: 8,
      proxy_data_age_days: null,
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

    expect(screen.getByText('HIGH RISK')).toBeInTheDocument();
    expect(screen.getByText('LOW RISK')).toBeInTheDocument();
    expect(screen.getByText('Proxy / Historical Input Data Applied')).toBeInTheDocument();
    expect(screen.getByText(/Forecast decision records are immutable statistical early-warning estimates/i)).toBeInTheDocument();
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
            target_year: 2026,
            target_month: 9,
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

  it('Generation does not occur on component mount and occurs only after explicit button click', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Generate Next-Month Official Forecasts/i })).toBeInTheDocument();
    });

    expect(workflowApi.createForecastRecord).not.toHaveBeenCalled();
  });

  it('Clicking Generate triggers createForecastRecord for both FMD & LSD with deterministic idempotency keys and actor ID', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });

    const generatedFmd = {
      forecast_id: 'fdr_new_fmd',
      disease: 'FMD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 9,
      risk_level: 'MEDIUM',
      probability_pct: 55.0,
      generated_at: '2026-08-22T12:00:00Z',
    };
    const generatedLsd = {
      forecast_id: 'fdr_new_lsd',
      disease: 'LSD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 9,
      risk_level: 'LOW',
      probability_pct: 15.0,
      generated_at: '2026-08-22T12:00:00Z',
    };

    workflowApi.createForecastRecord.mockImplementation(({ disease }) => {
      if (disease === 'FMD') return Promise.resolve(generatedFmd);
      return Promise.resolve(generatedLsd);
    });

    render(
      <VeterinaryForecastOverview
        viewerContext={validVetContext}
        referenceDate={new Date(2026, 7, 15)} // Aug 2026 -> Sept 2026 target
      />
    );

    const btn = await screen.findByRole('button', { name: /Generate Next-Month Official Forecasts/i });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);

    await waitFor(() => {
      expect(workflowApi.createForecastRecord).toHaveBeenCalledTimes(2);
    });

    expect(workflowApi.createForecastRecord).toHaveBeenCalledWith({
      disease: 'FMD',
      district: 'Anuradhapura',
      year: 2026,
      month: 9,
      trigger_type: 'MANUAL',
      generated_by: 'vet_officer_01',
      idempotency_key: 'vet_officer_01_Anuradhapura_FMD_2026_9_overview_gen',
    });

    expect(workflowApi.createForecastRecord).toHaveBeenCalledWith({
      disease: 'LSD',
      district: 'Anuradhapura',
      year: 2026,
      month: 9,
      trigger_type: 'MANUAL',
      generated_by: 'vet_officer_01',
      idempotency_key: 'vet_officer_01_Anuradhapura_LSD_2026_9_overview_gen',
    });
  });

  it('Handles partial FMD success with LSD failure gracefully', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });

    workflowApi.createForecastRecord.mockImplementation(({ disease }) => {
      if (disease === 'FMD') {
        return Promise.resolve({
          forecast_id: 'fdr_fmd_ok',
          disease: 'FMD',
          district: 'Anuradhapura',
          target_year: 2026,
          target_month: 9,
          risk_level: 'HIGH',
          probability_pct: 82.0,
        });
      }
      return Promise.reject(new Error('LSD model service timeout'));
    });

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const btn = await screen.findByRole('button', { name: /Generate Next-Month Official Forecasts/i });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getAllByText(/Generated FMD forecast/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/LSD generation failed/i).length).toBeGreaterThan(0);
    });
  });

  it('Handles partial LSD success with FMD failure gracefully', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });

    workflowApi.createForecastRecord.mockImplementation(({ disease }) => {
      if (disease === 'LSD') {
        return Promise.resolve({
          forecast_id: 'fdr_lsd_ok',
          disease: 'LSD',
          district: 'Anuradhapura',
          target_year: 2026,
          target_month: 9,
          risk_level: 'LOW',
          probability_pct: 10.0,
        });
      }
      return Promise.reject(new Error('FMD model feature error'));
    });

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const btn = await screen.findByRole('button', { name: /Generate Next-Month Official Forecasts/i });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getAllByText(/Generated LSD forecast/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/FMD generation failed/i).length).toBeGreaterThan(0);
    });
  });

  it('Handles total generation failure for both diseases gracefully', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });
    workflowApi.createForecastRecord.mockImplementation(() =>
      Promise.resolve().then(() => {
        throw new Error('Backend prediction service failed');
      })
    );

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const btn = await screen.findByRole('button', { name: /Generate Next-Month Official Forecasts/i });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Failed to generate official forecasts/i).length).toBeGreaterThan(0);
  });

  it('Blocks duplicate generation click while generation is pending', async () => {
    workflowApi.listForecastRecords.mockResolvedValue({ total_count: 0, limit: 50, offset: 0, records: [] });

    let resolveGen;
    const pendingPromise = new Promise((resolve) => {
      resolveGen = resolve;
    });
    workflowApi.createForecastRecord.mockReturnValue(pendingPromise);

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const btn = await screen.findByRole('button', { name: /Generate Next-Month Official Forecasts/i });
    fireEvent.click(btn);
    fireEvent.click(btn);

    expect(workflowApi.createForecastRecord).toHaveBeenCalledTimes(2); // 1 call per disease (FMD & LSD) for first click, second click ignored because button disabled
    expect(btn).toBeDisabled();

    resolveGen({
      forecast_id: 'fdr_resolved',
      disease: 'FMD',
      district: 'Anuradhapura',
      target_year: 2026,
      target_month: 9,
    });
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
});
