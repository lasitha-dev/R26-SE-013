/**
 * Loads the Seasonal Outlook for a target month.
 *
 * 1. issued (stored) outlooks for that month;
 * 2. otherwise, only if the month is the next month, the server's computed PREVIEW (never stored);
 * 3. otherwise nothing. It never throws and never invents a value: any failure means "no outlook".
 */

import * as workflow from './riskForecastingWorkflowApi';

export const NO_OUTLOOK = Object.freeze({ source: 'none', records: [] });

export function outlookFor(outlooks, district, disease) {
  const wanted = String(district || '').toLowerCase();
  return (outlooks?.records || []).find(
    (o) => o.disease === disease && String(o.district || '').toLowerCase() === wanted
  ) || null;
}

export async function loadOutlooks({ year, month, district, signal } = {}) {
  try {
    const stored = await workflow.listOutlooks(
      { target_year: Number(year), target_month: Number(month), district, limit: 200 },
      { signal }
    );
    const issued = (stored?.records || []).filter((o) => o.status === 'ACTIVE');
    if (issued.length > 0) return { source: 'stored', records: issued };

    const preview = await workflow.previewOutlooks({ district }, { signal });
    const wantedPeriod = `${Number(year)}-${String(Number(month)).padStart(2, '0')}`;
    if (preview?.target_period === wantedPeriod && Array.isArray(preview.records)) {
      return { source: 'preview', records: preview.records };
    }
    return NO_OUTLOOK;
  } catch (_) {
    return NO_OUTLOOK;
  }
}
