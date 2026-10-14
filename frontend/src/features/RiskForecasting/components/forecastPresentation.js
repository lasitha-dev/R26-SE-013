/**
 * Shared, honest presentation of forecast records (v2 and legacy v1).
 *
 * v2 records carry `model_version`, `forecaster` ('A' | 'S' | 'B' | 'climatology') and
 * `deployment_status` ('back_tested' | 'exploratory' | 'baseline'); see the v2 model card.
 */

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const SURVEILLANCE_STATUS_TEXT = Object.freeze({
  CONFIRMED_OUTBREAK: 'outbreak recorded',
  NO_OUTBREAK_RECORDED: 'no outbreak recorded',
  NO_REPORTED_CASES: 'no verified cases',
  NO_SURVEILLANCE_COVERAGE: 'no app surveillance coverage',
  UNVERIFIED_LABEL: 'records unverified',
  SOURCE_UNAVAILABLE: 'surveillance data unavailable',
});

export function isV2Record(record) {
  return Boolean(record && record.model_version);
}

export function describeForecastSource(record) {
  if (!record) return null;
  if (isV2Record(record)) {
    if (record.forecaster === 'climatology') {
      return {
        label: 'Historical baseline',
        tone: 'baseline',
        title: 'Surveillance for this district and its neighbours was not available, so the district\'s historical outbreak rate for this month is shown.',
      };
    }
    if (record.deployment_status === 'exploratory') {
      return {
        label: 'Exploratory model',
        tone: 'exploratory',
        title: 'Model passed back-testing but was selected after evaluation; it needs prospective confirmation (see model card).',
      };
    }
    return {
      label: 'Back-tested candidate',
      tone: 'backtested',
      title: 'Model beat the historical baseline in rolling back-testing. It has not yet been confirmed on future data (see model card).',
    };
  }
  return record.fallback_applied
    ? { label: 'v1 · proxy inputs', tone: 'legacy', title: `Legacy v1 record using historical proxy inputs (${record.data_quality || 'unknown'}).` }
    : { label: 'v1 · exact inputs', tone: 'legacy', title: `Legacy v1 record (${record.data_quality || 'unknown'}).` };
}

/**
 * A climatology record is the district's usual rate, not a model output: its relative risk is 1.0 by
 * construction, so a "LOW RISK" label would wrongly read as an assessment that risk is low.
 */
export function isBaselineRecord(record) {
  return isV2Record(record) && record.forecaster === 'climatology';
}

export const BASELINE_BADGE = Object.freeze({
  label: 'BASELINE',
  class: 'bg-slate-800 text-slate-300 border-slate-600/40',
  title: 'Seasonal baseline for this district and month. No elevated signal was assessed; this is not a model forecast.',
});

/** Provenance text for lists and detail panels: honest for v2 records, unchanged wording for v1. */
export function describeProvenance(record) {
  if (isV2Record(record)) return describeForecastSource(record).label;
  return record?.fallback_applied ? 'Fallback Proxy Applied' : 'Exact Period';
}

export function formatRelativeRisk(relativeRisk) {
  if (typeof relativeRisk !== 'number' || Number.isNaN(relativeRisk)) return null;
  return `${relativeRisk.toFixed(1)}× usual`;
}

/**
 * "80% range 12–48%": the uncertainty of the probability estimate (not of the 0/1 outcome).
 * Returns null for records without an interval (v1 records and older v2 records).
 */
export function formatProbabilityInterval(record) {
  const { probability_low: low, probability_high: high, interval_level: level } = record || {};
  if (![low, high, level].every((v) => typeof v === 'number' && !Number.isNaN(v))) return null;
  return `${Math.round(level * 100)}% range ${Math.round(low * 100)}–${Math.round(high * 100)}%`;
}

export function describePreviousMonth(observation) {
  if (!observation) return null;
  const [year, month] = String(observation.period || '').split('-').map(Number);
  const period = year && month ? `${MONTH_SHORT[month - 1]} ${year}` : 'Previous month';
  if (typeof observation.verified_cases === 'number' && typeof observation.deaths === 'number') {
    const severity = observation.observed_severity ? ` · ${observation.observed_severity}` : '';
    return `${period}: ${observation.verified_cases} verified case${observation.verified_cases === 1 ? '' : 's'}, ${observation.deaths} death${observation.deaths === 1 ? '' : 's'}${severity}`;
  }
  return `${period}: ${SURVEILLANCE_STATUS_TEXT[observation.status] || 'status unknown'}`;
}

const V2_FEATURE_LABELS = Object.freeze({
  own_t1: 'Outbreak in this district last month',
  own_t2: 'Outbreak in this district two months ago',
  neighbour_fraction_t1: 'Share of neighbouring districts with outbreaks last month',
  neighbour_count_t1: 'Neighbouring districts with outbreaks last month',
  neighbour_fraction_t2: 'Share of neighbouring districts with outbreaks two months ago',
  rain_t1: 'Rainfall last month',
  rain_t2: 'Rainfall two months ago',
  r3h_t1: '3-month rainfall total',
  rfq_t1: 'Rainfall anomaly last month',
  temp_t1: 'Temperature last month',
  humidity_t1: 'Humidity last month',
  wind_t1: 'Wind speed last month',
  nino34_anom_t2: 'El Niño index (2 months ago)',
  nino34_anom_t3: 'El Niño index (3 months ago)',
  buffalo_density: 'Buffalo density',
  livestock_density: 'Livestock density',
  climatology_logit: 'Usual risk for this district and month',
  sin_month: 'Season (cycle A)',
  cos_month: 'Season (cycle B)',
  monsoon_first_inter: 'First inter-monsoon season',
  monsoon_sw: 'South-west monsoon season',
  monsoon_second_inter: 'Second inter-monsoon season',
  monsoon_ne: 'North-east monsoon season',
});

export function featureLabel(name) {
  return V2_FEATURE_LABELS[name] || String(name).replace(/_/g, ' ');
}

/** Explanation payload (same shape as the live endpoint) built from a v2 record's stored contributions. */
export function storedExplanation(record) {
  const items = (record?.contributions || []).map((c) => ({
    display_label: featureLabel(c.feature),
    contribution_log_odds: c.contribution_log_odds,
  }));
  return {
    disease: record?.disease,
    explanation_info: {
      method: 'linear log-odds contributions stored with this forecast',
      notes: record?.forecaster === 'climatology'
        ? 'This forecast is the district\'s historical outbreak rate for the month; no model features were applied.'
        : 'Contributions recorded when the forecast was generated, relative to the training average.',
      top_risk_increasing: items.filter((c) => c.contribution_log_odds > 0),
      top_risk_decreasing: items.filter((c) => c.contribution_log_odds < 0),
    },
  };
}

/** Records that should drive current views (superseded records are history only). */
export function isActiveRecord(record) {
  return Boolean(record) && record.status !== 'SUPERSEDED';
}
