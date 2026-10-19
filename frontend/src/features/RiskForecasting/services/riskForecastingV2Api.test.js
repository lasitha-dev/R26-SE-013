import { describe, it, expect, vi, afterEach } from 'vitest';
import { generateV2Forecasts } from './riskForecastingWorkflowApi';

function mockFetchOk(payload = { summary: {} }) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(payload),
  });
}

describe('generateV2Forecasts request body', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends a preview as dry_run without a confirmation count', async () => {
    const fetchSpy = mockFetchOk();
    await generateV2Forecasts({ year: 2025, month: 1, dryRun: true });

    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain('/api/v1/risk-forecasting/v2/forecasts/generate');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ dry_run: true, year: 2025, month: 1 });
  });

  it('sends the previewed supersede count with a real run, including zero', async () => {
    const fetchSpy = mockFetchOk();
    await generateV2Forecasts({ year: 2025, month: 1, expectedSupersedeCount: 49 });
    expect(JSON.parse(fetchSpy.mock.calls[0][1].body)).toEqual({
      dry_run: false, expected_supersede_count: 49, year: 2025, month: 1,
    });

    await generateV2Forecasts({ year: 2025, month: 1, expectedSupersedeCount: 0 });
    expect(JSON.parse(fetchSpy.mock.calls[1][1].body).expected_supersede_count).toBe(0);
  });

  it('omits the confirmation field when none is given', async () => {
    const fetchSpy = mockFetchOk();
    await generateV2Forecasts({ year: 2026, month: 3, diseases: ['FMD'] });
    expect(JSON.parse(fetchSpy.mock.calls[0][1].body)).toEqual({ dry_run: false, year: 2026, month: 3, diseases: ['FMD'] });
  });
});
