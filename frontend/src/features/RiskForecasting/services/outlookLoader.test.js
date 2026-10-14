import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./riskForecastingWorkflowApi', () => ({
  listOutlooks: vi.fn(),
  previewOutlooks: vi.fn(),
}));

import * as workflow from './riskForecastingWorkflowApi';
import { loadOutlooks, outlookFor } from './outlookLoader';

const outlook = (overrides) => ({ disease: 'FMD', district: 'Colombo', status: 'ACTIVE', probability: 0.033, ...overrides });

describe('loadOutlooks', () => {
  beforeEach(() => {
    workflow.listOutlooks.mockReset();
    workflow.previewOutlooks.mockReset();
  });

  it('uses issued outlooks and ignores voided or corrected ones', async () => {
    workflow.listOutlooks.mockResolvedValue({ records: [outlook(), outlook({ status: 'VOIDED' }), outlook({ status: 'CORRECTED' })] });
    const result = await loadOutlooks({ year: 2026, month: 11, district: 'Colombo' });
    expect(result.source).toBe('stored');
    expect(result.records).toHaveLength(1);
    expect(workflow.previewOutlooks).not.toHaveBeenCalled();
  });

  it('falls back to the server preview only when it is for the requested month', async () => {
    workflow.listOutlooks.mockResolvedValue({ records: [] });
    workflow.previewOutlooks.mockResolvedValue({ target_period: '2026-11', records: [outlook()] });
    expect((await loadOutlooks({ year: 2026, month: 11 })).source).toBe('preview');
    expect((await loadOutlooks({ year: 2026, month: 12 })).source).toBe('none');
    expect((await loadOutlooks({ year: 2026, month: 10 })).records).toEqual([]);
  });

  it('never throws: any failure means no outlook', async () => {
    workflow.listOutlooks.mockRejectedValue(new Error('down'));
    expect(await loadOutlooks({ year: 2026, month: 11 })).toEqual({ source: 'none', records: [] });
  });

  it('finds an outlook by district (case-insensitive) and disease', () => {
    const outlooks = { records: [outlook(), outlook({ disease: 'LSD' })] };
    expect(outlookFor(outlooks, 'colombo', 'LSD').disease).toBe('LSD');
    expect(outlookFor(outlooks, 'Kandy', 'FMD')).toBeNull();
  });
});
