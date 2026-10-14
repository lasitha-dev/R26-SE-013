import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { VeterinaryForecastOverview } from './VeterinaryForecastOverview';
import * as workflowApi from '../../services/riskForecastingWorkflowApi';
import { resetSeverityHistoryCache } from '../../services/severityHistoryLoader';
import { ROLES, SCOPE_LEVELS } from '../../contracts/viewerContext';

vi.mock('../../services/riskForecastingWorkflowApi', () => ({
  listForecastRecords: vi.fn(),
  listOutlooks: vi.fn(),
  previewOutlooks: vi.fn(),
  getSeverityHistory: vi.fn(),
  getActiveSurveillance: vi.fn(),
}));

const respond = (records) => ({ total_count: records.length, limit: 200, offset: 0, records });

describe('VeterinaryForecastOverview (plain-language overview)', () => {
  const validVetContext = {
    userId: 'vet_officer_01',
    role: ROLES.VETERINARY_OFFICER,
    authorization: {
      scopeLevel: SCOPE_LEVELS.DISTRICT,
      authorizedDistricts: ['Anuradhapura'],
      assignedFarmIds: ['farm_1'],
    },
    permissions: { viewDataQuality: true, viewModelTransparency: true },
  };

  const forecast = (disease, overrides = {}) => ({
    forecast_id: `fdr_${disease}_${overrides.target_month || 1}`, disease, district: 'Anuradhapura',
    target_year: 2025, target_month: 1, risk_level: 'MEDIUM', probability: 0.31, probability_pct: 31.0,
    predicted_severity: null, status: 'GENERATED', generated_at: '2026-10-13T00:00:00Z',
    model_variant: 'fmd_v2.1:O', model_version: 'fmd_v2.1', forecaster: 'O', deployment_status: 'back_tested',
    relative_risk: 2.4, data_quality: 'V2_MODEL', fallback_applied: false, source_year: 2024, source_month: 12,
    data_age_months: 1, ...overrides,
  });

  const outlook = (disease, overrides = {}) => ({
    disease, district: 'Anuradhapura', status: 'ACTIVE', probability: 0.033, probability_low: 0.0,
    probability_high: 0.097, interval_level: 0.8, years_observed: 7, positive_years: 0,
    target_year: 2025, target_month: 2, issue_date: '2026-10-15', lead_days: 17, ...overrides,
  });

  beforeEach(() => {
    vi.resetAllMocks();
    resetSeverityHistoryCache();
    workflowApi.listOutlooks.mockResolvedValue({ records: [] });
    workflowApi.previewOutlooks.mockResolvedValue({ target_period: '1900-01', records: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('requests records only for the assigned district', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(workflowApi.listForecastRecords).toHaveBeenCalled());
    const districts = workflowApi.listForecastRecords.mock.calls.map((call) => call[0].district);
    expect(districts.every((d) => d === 'Anuradhapura')).toBe(true);
    expect(districts).not.toContain('Colombo');
  });

  it('shows the chance, the risk level and one plain sentence for each disease', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('FMD', { model_version: undefined, forecaster: undefined, risk_level: 'HIGH', probability: 0.784, probability_pct: 78.4, relative_risk: undefined, data_quality: 'PROXY', fallback_applied: true, predicted_severity: 'MODERATE_OUTBREAK' }),
      forecast('LSD', { model_version: undefined, forecaster: undefined, risk_level: 'LOW', probability: 0.121, probability_pct: 12.1, relative_risk: undefined, status: 'APPROVED', data_age_months: 0 }),
    ]));

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('about 78%')).toBeInTheDocument());
    expect(screen.getByText('HIGH RISK')).toBeInTheDocument();
    expect(screen.getByText('LOW RISK')).toBeInTheDocument();
    expect(screen.getByText('about 12%')).toBeInTheDocument();
    expect(screen.getByText('Higher than usual for Anuradhapura in January. Check your animals closely and follow veterinary advice.')).toBeInTheDocument();
    expect(screen.getByText('Not higher than usual for Anuradhapura in January. Continue routine care.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Disease Risk Forecast', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(/No Forecast/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SHAP/)).not.toBeInTheDocument();
    // Technical facts remain available, but inside "More details"
    expect(screen.getAllByText('More details').length).toBe(2);
    expect(screen.getByText('1 month')).toBeInTheDocument();
    expect(screen.getByText('0 months')).toBeInTheDocument();
  });

  it('ends with one short reassurance line instead of a long scientific paragraph', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([forecast('FMD')]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    expect(await screen.findByText(/not a diagnosis; confirm suspected cases in the field/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Epidemiological & Diagnostic Guardrails/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/immutable statistical early-warning estimates/i)).not.toBeInTheDocument();
  });

  it('shows no empty "No forecast" card when only one disease has a forecast', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('LSD', { risk_level: 'MEDIUM', probability: 0.45, probability_pct: 45.0 }),
    ]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('about 45%')).toBeInTheDocument());
    expect(screen.queryByText(/Foot-and-Mouth/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No official stored forecast/)).not.toBeInTheDocument();
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
  });

  it('shows one friendly line, not placeholders or invented numbers, when nothing is issued yet', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    expect(await screen.findByText(/will appear here as soon as they are issued/i)).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No Forecast/i)).not.toBeInTheDocument();
  });

  it('fails closed when the viewer context has no authorized district', () => {
    render(<VeterinaryForecastOverview viewerContext={{
      userId: 'vet_01', role: ROLES.VETERINARY_OFFICER,
      authorization: { scopeLevel: SCOPE_LEVELS.DISTRICT, authorizedDistricts: [], assignedFarmIds: [] },
      permissions: {},
    }} />);
    expect(screen.getByText(/Access context unavailable/i)).toBeInTheDocument();
  });

  it('does not render trends, charts, Advisory Centre, History or outbox UI', () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);
    expect(screen.queryByText(/Trend/i)).toBeNull();
    expect(screen.queryByText(/Outbox/i)).toBeNull();
    expect(screen.queryByText(/Advisory Centre/i)).toBeNull();
    expect(screen.queryByText(/History/i)).toBeNull();
  });

  it('only offers months that have a forecast, newest first, and switches between them', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('FMD', { target_year: 2025, target_month: 1, probability: 0.31, probability_pct: 31 }),
      forecast('FMD', { target_year: 2024, target_month: 12, probability: 0.12, probability_pct: 12, risk_level: 'LOW' }),
    ]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const select = await screen.findByLabelText('Month:');
    expect(Array.from(select.options).map((o) => o.text)).toEqual(['January 2025', 'December 2024']);
    await waitFor(() => expect(screen.getByText('about 31%')).toBeInTheDocument());

    fireEvent.change(select, { target: { value: '2024-12' } });
    await waitFor(() => expect(screen.getByText('about 12%')).toBeInTheDocument());
    expect(screen.queryByText('about 31%')).not.toBeInTheDocument();
  });

  it('opens on the forecast nearest to the current month, not on a stray far-future record', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('FMD', { target_year: 2026, target_month: 12, probability: 0.5, probability_pct: 50, forecast_id: 'far_future' }),
      forecast('FMD', { target_year: 2025, target_month: 1, probability: 0.31, probability_pct: 31 }),
    ]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('about 31%')).toBeInTheDocument());
    expect(screen.queryByText('about 50%')).not.toBeInTheDocument();
    const select = screen.getByLabelText('Month:');
    expect(select.value).toBe('2025-1');
    expect(Array.from(select.options).map((o) => o.text)).toEqual(['January 2025', 'December 2026']);   // still selectable, grouped under "Other months"
    expect(Array.from(select.querySelectorAll('optgroup')).map((g) => g.label)).toEqual(['Other months']);
  });

  it('keeps the exact figures, the reason and the stored explanation behind "More details", with no live call', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('FMD', {
        probability_low: 0.18, probability_high: 0.47, interval_level: 0.8,
        previous_month_observation: { period: '2024-12', status: 'CONFIRMED_OUTBREAK', verified_cases: 4, deaths: 0, observed_severity: 'LOW' },
        contributions: [
          { feature: 'own_t1', value: 1, contribution_log_odds: 0.62 },
          { feature: 'rain_t1', value: 80, contribution_log_odds: -0.21 },
        ],
      }),
    ]));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('about 31%')).toBeInTheDocument());
    expect(screen.getByText('likely between 18% and 47%')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM RISK')).toBeInTheDocument();
    expect(screen.getByText('December 2024: 4 cases, 0 deaths')).toBeInTheDocument();
    // details (collapsed by default, still in the document)
    expect(screen.getByText('2.4× usual for this district and month')).toBeInTheDocument();
    expect(screen.getByText('80% range 18–47%')).toBeInTheDocument();
    expect(screen.getByTestId('tier-basis')).toHaveTextContent('MEDIUM because 2.4× the usual rate for this district and month (MEDIUM starts at 2×).');
    expect(screen.getByText('Back-tested candidate')).toBeInTheDocument();
    expect(screen.getByText('31.0%')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /EXPLAIN FORECAST/i }));
    await waitFor(() => {
      expect(screen.getByText('Outbreak in this district last month')).toBeInTheDocument();
      expect(screen.getByText('Rainfall last month')).toBeInTheDocument();
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('explains an earlier-version (v1) record with a notice and never runs the old model live', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('FMD', { model_version: undefined, forecaster: undefined, model_variant: '30_feature_baseline', probability: 0.4, probability_pct: 40.0, predicted_severity: 'LOW', fallback_applied: true, data_quality: 'HISTORICAL_SAME_MONTH_PROXY' }),
    ]));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);
    await waitFor(() => expect(screen.getByText('about 40%')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /EXPLAIN FORECAST/i }));

    await waitFor(() => expect(screen.getByText(/earlier version of the forecasting system/i)).toBeInTheDocument());
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('shows a seasonal baseline as the usual level, never as an assessed LOW RISK', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([
      forecast('FMD', { district: 'Anuradhapura', risk_level: 'LOW', probability: 0.12, probability_pct: 12.0, forecaster: 'climatology', deployment_status: 'baseline', relative_risk: 1.0, data_quality: 'V2_BASELINE', fallback_applied: true, model_variant: 'fmd_v2.1:climatology' }),
    ]));
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('about 12%')).toBeInTheDocument());
    expect(screen.getByText('USUAL LEVEL')).toBeInTheDocument();
    expect(screen.queryByText('LOW RISK')).not.toBeInTheDocument();
    expect(screen.getByText(/This is the usual level for Anuradhapura in January/)).toBeInTheDocument();
  });

  describe('Looking ahead (next-month outlook)', () => {
    it('shows the next month under the current forecast, in plain words and without a risk tier', async () => {
      workflowApi.listForecastRecords.mockResolvedValue(respond([forecast('FMD'), forecast('LSD', { probability: 0.1, probability_pct: 10, risk_level: 'LOW' })]));
      workflowApi.listOutlooks.mockImplementation(async ({ target_month }) => (
        target_month === 2 ? { records: [outlook('FMD'), outlook('LSD', { probability: 0.027 })] } : { records: [] }
      ));

      render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

      const heading = await screen.findByRole('heading', { name: 'Looking ahead: February 2025' });
      const section = heading.closest('section');
      expect(within(section).getAllByText('about 3%').length).toBe(2);
      expect(within(section).getAllByText('likely between 0% and 10%').length).toBe(2);
      expect(within(section).getAllByText('An outbreak was recorded in this month in 0 of the last 7 years.').length).toBe(2);
      expect(within(section).queryByText(/RISK|HIGH|MEDIUM|LOW/)).not.toBeInTheDocument();
      expect(within(section).getByText(/Based on past years only/)).toBeInTheDocument();
      expect(within(section).queryByText('Preview')).not.toBeInTheDocument();
    });

    it('shows the outlook as the main content, labelled Preview, when no forecast is issued yet', async () => {
      workflowApi.listForecastRecords.mockResolvedValue(respond([]));
      workflowApi.previewOutlooks.mockResolvedValue({
        target_period: '2025-01',
        records: [outlook('FMD', { target_month: 1 }), outlook('LSD', { target_month: 1, probability: 0.027 })],
      });

      render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

      expect(await screen.findByRole('heading', { name: 'Outlook for January 2025' })).toBeInTheDocument();
      expect(screen.getAllByText('Preview').length).toBe(2);
      expect(screen.queryByText(/No Forecast|No official stored forecast/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/will appear here/)).not.toBeInTheDocument();
    });

    it('keeps the outlook given earlier for the same month inside "More details"', async () => {
      workflowApi.listForecastRecords.mockResolvedValue(respond([forecast('FMD')]));
      workflowApi.listOutlooks.mockImplementation(async ({ target_month }) => (
        target_month === 1 ? { records: [outlook('FMD', { target_month: 1 })] } : { records: [] }
      ));

      render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

      await waitFor(() => expect(screen.getByTestId('outlook-compact')).toHaveTextContent('Outlook given earlier: about 3% (likely between 0% and 10%)'));
      expect(screen.getByText('about 31%')).toBeInTheDocument();          // the forecast remains the main figure
      expect(screen.queryByRole('heading', { name: /Looking ahead/ })).not.toBeInTheDocument();
    });
  });

  it('lists the outlook month as a choice and shows its outlook when picked', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([forecast('FMD')]));
    workflowApi.listOutlooks.mockResolvedValue({ records: [outlook('FMD')] });
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    const select = await screen.findByLabelText('Month:');
    await waitFor(() => expect(Array.from(select.options).some((o) => /\(outlook\)$/.test(o.text))).toBe(true));
    const outlookOption = Array.from(select.options).find((o) => /\(outlook\)$/.test(o.text));
    expect(select.value).toBe('2025-1');   // opens on the forecast, not on the outlook

    fireEvent.change(select, { target: { value: outlookOption.value } });
    await waitFor(() => expect(screen.getByRole('heading', { name: /^Outlook for / })).toBeInTheDocument());
    expect(screen.queryByText(/Chance of an outbreak in/)).not.toBeInTheDocument();
  });

  it('shows the usual severity of the district if an outbreak occurs, with the shares, and no invented severity otherwise', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([forecast('FMD'), forecast('LSD')]));
    workflowApi.getSeverityHistory.mockResolvedValue({ diseases: { FMD: { years: [2017, 2024], districts: { Anuradhapura: {
      outbreak_years: 4, counts: { LOW: 1, MEDIUM: 2, HIGH: 1 }, probabilities: { LOW: 0.3, MEDIUM: 0.45, HIGH: 0.25 }, typical: 'MEDIUM' } } } } });
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);

    await waitFor(() => expect(screen.getByText('Low 30% · Medium 45% · High 25%')).toBeInTheDocument());
    expect(screen.getAllByText('Severity if an outbreak occurs')).toHaveLength(1);   // LSD has no history for this district
    expect(screen.getByText('Based on 4 past outbreak years (2017–2024).')).toBeInTheDocument();
    expect(screen.queryByText(/Predicted Severity|MODERATE|N\/A/)).not.toBeInTheDocument();
  });

  it('severity watch follows the recorded counts: it changes when more cases and deaths are recorded', async () => {
    const withPrevious = forecast('FMD', {
      target_year: 2025, target_month: 1,
      previous_month_observation: { period: '2024-12', status: 'CONFIRMED_OUTBREAK', verified_cases: 2, deaths: 0, observed_severity: 'LOW' },
    });
    workflowApi.listForecastRecords.mockResolvedValue(respond([withPrevious]));
    workflowApi.getActiveSurveillance.mockResolvedValue({ districts: { Anuradhapura: { status: 'CONFIRMED_OUTBREAK', cases: 3, deaths: 0 } } });
    const first = render(<VeterinaryForecastOverview viewerContext={validVetContext} />);
    await waitFor(() => expect(screen.getByTestId('severity-watch')).toHaveTextContent('LOW'));
    expect(screen.getByText('January 2025: 3 cases, 0 deaths')).toBeInTheDocument();
    expect(screen.getByText('December 2024: 2 cases, 0 deaths')).toBeInTheDocument();
    expect(screen.getByText(/Rule-based indicator from pilot records; not a model forecast\./)).toBeInTheDocument();
    first.unmount();

    workflowApi.getActiveSurveillance.mockResolvedValue({ districts: { Anuradhapura: { status: 'CONFIRMED_OUTBREAK', cases: 12, deaths: 2 } } });
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);
    await waitFor(() => expect(screen.getByTestId('severity-watch')).toHaveTextContent('HIGH'));
    expect(screen.getByText('January 2025: 12 cases, 2 deaths')).toBeInTheDocument();
  });

  it('shows "No app reports" instead of a level when the district is not covered', async () => {
    workflowApi.listForecastRecords.mockResolvedValue(respond([forecast('FMD', { previous_month_observation: { period: '2024-12', status: 'NO_SURVEILLANCE_COVERAGE', verified_cases: null, deaths: null } })]));
    workflowApi.getActiveSurveillance.mockResolvedValue({ districts: { Anuradhapura: { status: 'NO_SURVEILLANCE_COVERAGE', cases: null, deaths: null } } });
    render(<VeterinaryForecastOverview viewerContext={validVetContext} />);
    await waitFor(() => expect(screen.getByText('No app reports for this district yet.')).toBeInTheDocument());
    expect(screen.getByTestId('severity-watch')).not.toHaveTextContent(/LOW|MEDIUM|HIGH/);
  });
});
