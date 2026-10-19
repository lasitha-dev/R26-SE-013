/**
 * Recorded cases and deaths for a month, per district (read-only, live from the application's records).
 * It never throws and never invents a value: any failure means "no observations".
 */

import * as workflow from './riskForecastingWorkflowApi';

export async function loadObservations({ disease, year, month, signal } = {}) {
  try {
    const response = await workflow.getActiveSurveillance({ disease, year: Number(year), month: Number(month) }, { signal });
    return response?.districts && typeof response.districts === 'object' ? response.districts : {};
  } catch (_) {
    return {};
  }
}

/** True when the month has started (so "recorded so far" makes sense). */
export function monthHasStarted(year, month, now = new Date()) {
  return year < now.getFullYear() || (year === now.getFullYear() && month <= now.getMonth() + 1);
}
