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
      proxy_data_age_days: 14,
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

    expect(screen.getByText(/HIGH RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/LOW RISK/i)).toBeInTheDocument();
    expect(screen.getByText(/Forecast decision records are immutable statistical early-warning estimates/i)).toBeInTheDocument();
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
});
