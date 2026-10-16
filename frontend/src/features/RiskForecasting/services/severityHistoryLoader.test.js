import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./riskForecastingWorkflowApi', () => ({ getSeverityHistory: vi.fn() }));
import * as workflow from './riskForecastingWorkflowApi';
import { loadSeverityHistory, resetSeverityHistoryCache, severityFor, NO_SEVERITY_HISTORY } from './severityHistoryLoader';

const history = { diseases: { FMD: { years: [2017, 2024], districts: { Colombo: { outbreak_years: 3, typical: 'LOW' } } } } };

describe('severityHistoryLoader', () => {
  beforeEach(() => { resetSeverityHistoryCache(); workflow.getSeverityHistory.mockReset(); });

  it('loads once and reuses the result', async () => {
    workflow.getSeverityHistory.mockResolvedValue(history);
    expect(await loadSeverityHistory()).toBe(history);
    await loadSeverityHistory();
    expect(workflow.getSeverityHistory).toHaveBeenCalledTimes(1);
  });

  it('never throws: a failure means no history, and the next call retries', async () => {
    workflow.getSeverityHistory.mockRejectedValueOnce(new Error('down'));
    expect(await loadSeverityHistory()).toBe(NO_SEVERITY_HISTORY);
    workflow.getSeverityHistory.mockResolvedValue(history);
    expect(await loadSeverityHistory()).toBe(history);
  });

  it('finds a district entry, and returns null (not LOW) when there is none', () => {
    expect(severityFor(history, 'fmd', 'Colombo')).toMatchObject({ typical: 'LOW', years: [2017, 2024] });
    expect(severityFor(history, 'FMD', 'Galle')).toBeNull();
    expect(severityFor(NO_SEVERITY_HISTORY, 'FMD', 'Colombo')).toBeNull();
  });
});
