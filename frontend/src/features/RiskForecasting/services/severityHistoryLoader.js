/**
 * Loads the district severity history once per page session (about 50 small entries).
 * It never throws and never invents a value: any failure means "no history".
 */

import * as workflow from './riskForecastingWorkflowApi';

export const NO_SEVERITY_HISTORY = Object.freeze({ diseases: {} });

let cached = null;

export function resetSeverityHistoryCache() {
  cached = null;
}

export async function loadSeverityHistory() {
  if (!cached) {
    cached = (async () => {
      try {
        const history = await workflow.getSeverityHistory();
        return history && history.diseases ? history : NO_SEVERITY_HISTORY;
      } catch (_) {
        cached = null;
        return NO_SEVERITY_HISTORY;
      }
    })();
  }
  return cached;
}

/** The entry for one district, or null when the district has no recorded outbreak year (not "LOW"). */
export function severityFor(history, disease, district) {
  const block = history?.diseases?.[String(disease || '').toUpperCase()];
  const entry = block?.districts?.[district];
  if (!entry) return null;
  return { disease: String(disease).toUpperCase(), district, ...entry, years: block.years };
}
