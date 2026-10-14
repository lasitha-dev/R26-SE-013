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
  label: 'USUAL LEVEL',
  class: 'bg-slate-800 text-slate-300 border-slate-600/40',
  title: 'The usual level for this district and month. No extra warning signs were found; this is not a model forecast.',
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

/**
 * Why a v2 record has a MEDIUM or HIGH tier, and how strong the evidence behind it is. The tier rule is
 * relative (probability against the usual rate for the district and month), so a high tier can sit on a
 * low absolute probability; stating the basis stops it being read as more than it is. Thresholds are
 * unchanged. Returns null for baseline, LOW and v1 records.
 */
export function describeTierBasis(record) {
  if (!isV2Record(record) || isBaselineRecord(record)) return null;
  const level = record.risk_level;
  if (level !== 'HIGH' && level !== 'MEDIUM') return null;
  const relative = record.relative_risk;
  const usual = typeof record.baseline_probability === 'number' ? `${(record.baseline_probability * 100).toFixed(1)}%` : null;
  let reason;
  if (level === 'HIGH' && typeof relative === 'number' && relative >= 4) {
    reason = `${relative.toFixed(1)}× the usual rate${usual ? ` of ${usual}` : ''} for this district and month (HIGH starts at 4×)`;
  } else if (level === 'HIGH' && typeof record.probability === 'number' && record.probability >= 0.5) {
    reason = 'the probability is 50% or more';
  } else if (typeof relative === 'number') {
    reason = `${relative.toFixed(1)}× the usual rate${usual ? ` of ${usual}` : ''} for this district and month (MEDIUM starts at 2×)`;
  } else {
    return null;
  }
  let evidence = null;
  if (record.deployment_status === 'back_tested') evidence = 'Model evidence: back-tested only, not yet confirmed on future data.';
  else if (record.deployment_status === 'exploratory') evidence = 'Model evidence: exploratory.';
  return { text: `${level} because ${reason}.`, evidence };
}

export function describePreviousMonth(observation) {
  if (!observation) return null;
  const [year, month] = String(observation.period || '').split('-').map(Number);
  const period = year && month ? `${MONTH_SHORT[month - 1]} ${year}` : 'Previous month';
  if (typeof observation.verified_cases === 'number' && typeof observation.deaths === 'number') {
    return `${period}: ${observation.verified_cases} verified case${observation.verified_cases === 1 ? '' : 's'}, ${observation.deaths} death${observation.deaths === 1 ? '' : 's'}`;
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
  soil_top_t1: 'Surface soil wetness last month',
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

function preferredFirst(a, b) {
  const v2 = Number(Boolean(b.model_version)) - Number(Boolean(a.model_version));
  if (v2 !== 0) return v2;
  const time = String(b.generated_at || '').localeCompare(String(a.generated_at || ''));
  return time !== 0 ? time : String(a.forecast_id || '').localeCompare(String(b.forecast_id || ''));
}

/**
 * The official record among several active ones for the same disease, district and month:
 * a current-version (v2) record wins over an older-version one, then the newest. The other records'
 * ids are kept in `related_forecast_ids` so advisories already written against them stay visible.
 */
export function pickOfficialRecord(records) {
  const active = (records || []).filter(isActiveRecord);
  if (active.length === 0) return null;
  const [official, ...others] = [...active].sort(preferredFirst);
  const related = others.map((r) => r.forecast_id).filter(Boolean);
  return related.length ? { ...official, related_forecast_ids: related } : official;
}

/** One official record per disease + district + target month (see pickOfficialRecord). */
export function selectOfficialRecords(records) {
  const groups = new Map();
  (records || []).filter(isActiveRecord).forEach((record) => {
    const key = [
      record.disease,
      String(record.district || '').toLowerCase(),
      record.target_year ?? record.targetYear,
      record.target_month ?? record.targetMonth,
    ].join('|');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  });
  return [...groups.values()].map(pickOfficialRecord);
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export function monthName(month) {
  return MONTHS[Number(month) - 1] || '';
}

/** "October 2026". */
export function periodLabel(year, month) {
  return `${monthName(month)} ${year}`.trim();
}

/** The month after (year, month). */
export function nextPeriod(year, month) {
  return Number(month) === 12 ? { year: Number(year) + 1, month: 1 } : { year: Number(year), month: Number(month) + 1 };
}

function wholePercent(fraction) {
  const pct = fraction * 100;
  if (pct < 1) return 'less than 1%';
  return `${Math.round(pct)}%`;
}

/** "about 30%": the chance as ordinary people read it (no decimals, no jargon). */
export function formatChance(probability) {
  if (typeof probability !== 'number' || Number.isNaN(probability)) return null;
  return probability * 100 < 1 ? 'less than 1%' : `about ${Math.round(probability * 100)}%`;
}

/** "likely between 18% and 47%" or null when the record has no range. */
export function formatLikelyRange(record) {
  const { probability_low: low, probability_high: high } = record || {};
  if (typeof low !== 'number' || typeof high !== 'number') return null;
  const lo = Math.round(low * 100);
  const hi = Math.round(high * 100);
  if (lo === hi) return null;
  return `likely between ${lo}% and ${hi}%`;
}

/**
 * Plain-language wording for a stored v2 or v1 forecast: the badge people see and one sentence on what it means.
 * Thresholds are unchanged; only the words are.
 */
export function describeRiskPlain(record, district, month) {
  const where = district ? `${district}` : 'this district';
  const when = month ? ` in ${monthName(month)}` : ' at this time of year';
  if (isBaselineRecord(record)) {
    return {
      level: 'USUAL',
      label: 'USUAL LEVEL',
      class: 'bg-slate-700/40 text-slate-200 border-slate-500/40',
      sentence: `This is the usual level for ${where}${when}. No extra warning signs at the moment.`,
    };
  }
  switch (String(record?.risk_level || '').toUpperCase()) {
    case 'HIGH':
      return {
        level: 'HIGH',
        label: 'HIGH RISK',
        class: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
        sentence: `Higher than usual for ${where}${when}. Check your animals closely and follow veterinary advice.`,
      };
    case 'MEDIUM':
      return {
        level: 'MEDIUM',
        label: 'MEDIUM RISK',
        class: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        sentence: `A little higher than usual for ${where}${when}. Stay alert.`,
      };
    case 'LOW':
      return {
        level: 'LOW',
        label: 'LOW RISK',
        class: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
        sentence: `Not higher than usual for ${where}${when}. Continue routine care.`,
      };
    default:
      return {
        level: 'UNKNOWN',
        label: String(record?.risk_level || 'UNKNOWN').toUpperCase(),
        class: 'bg-surface-container-high text-on-surface-variant border-outline-variant/40',
        sentence: '',
      };
  }
}

/** "Last month: 1 case and 2 deaths confirmed." or null when the counts are unknown. */
export function describeLastMonthPlain(observation) {
  const cases = observation?.verified_cases;
  const deaths = observation?.deaths;
  if (typeof cases !== 'number' || typeof deaths !== 'number') return null;
  if (cases === 0 && deaths === 0) return 'Last month: no cases or deaths reported.';
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  return `Last month: ${plural(cases, 'case')} and ${plural(deaths, 'death')} confirmed.`;
}

export const SEVERITY_CLASSES = Object.freeze(['LOW', 'MEDIUM', 'HIGH']);

/**
 * "Severity if an outbreak occurs" from a district's past outbreak years (annual records), in plain words.
 * Returns null when there is no history (a district without recorded outbreak years is unknown, not LOW).
 */
export function describeSeverityEstimate(entry) {
  if (!entry || !entry.probabilities || !SEVERITY_CLASSES.includes(entry.typical)) return null;
  const years = entry.outbreak_years;
  const span = Array.isArray(entry.years) ? `${entry.years[0]}–${entry.years[1]}` : '';
  return {
    level: entry.typical,
    percents: SEVERITY_CLASSES.map((c) => ({ level: c, text: `${Math.round((entry.probabilities[c] || 0) * 100)}%` })),
    evidence: `Based on ${years} past outbreak year${years === 1 ? '' : 's'}${span ? ` (${span})` : ''}.`,
  };
}

export const SEVERITY_BADGE_CLASS = Object.freeze({
  LOW: 'bg-emerald-950/70 text-emerald-300 border-emerald-800',
  MEDIUM: 'bg-amber-950/70 text-amber-300 border-amber-800',
  HIGH: 'bg-red-950/70 text-red-300 border-red-800',
});

// ─── Recorded cases and deaths → "severity watch" (rule-based, not a model forecast) ───

const WATCH_ORDER = ['NONE', 'LOW', 'MEDIUM', 'HIGH'];

/** Level of a month's recorded counts with the application's own rule: cases + 10 x deaths (0 / <10 / <30 / 30+). */
export function observedLevel(observation) {
  const cases = observation?.cases ?? observation?.verified_cases;
  const deaths = observation?.deaths;
  if (typeof cases !== 'number' || typeof deaths !== 'number') return null;
  const score = cases + 10 * deaths;
  if (score === 0) return 'NONE';
  if (score < 10) return 'LOW';
  if (score < 30) return 'MEDIUM';
  return 'HIGH';
}

function countsText(observation) {
  const cases = observation?.cases ?? observation?.verified_cases;
  const deaths = observation?.deaths;
  if (typeof cases !== 'number' || typeof deaths !== 'number') return null;
  if (cases === 0 && deaths === 0) return 'no cases or deaths';
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  return `${plural(cases, 'case')}, ${plural(deaths, 'death')}`;
}

/**
 * Severity watch: the higher of the levels of the recorded counts for the month so far and the previous month.
 * It is an early-warning indicator computed from recorded cases and deaths, not a model forecast.
 * `recent` is a list of { label, observation }; observations without counts (district not covered) are ignored.
 */
export function describeSeverityWatch(recent) {
  const known = (recent || [])
    .map((r) => ({ label: r.label, level: observedLevel(r.observation), text: countsText(r.observation) }))
    .filter((r) => r.level !== null);
  if (known.length === 0) return { level: null, lines: [], note: 'No app reports for this district yet.' };
  const level = known.map((r) => r.level).sort((a, b) => WATCH_ORDER.indexOf(b) - WATCH_ORDER.indexOf(a))[0];
  return { level, lines: known.map((r) => `${r.label}: ${r.text}`), note: null };
}

/**
 * The observations behind the severity watch for one stored forecast: the month it targets (recorded so far) when that
 * month has started, and the previous month stored with the forecast.
 */
export function buildRecentObservations(record, liveObservation, now = new Date()) {
  if (!record) return [];
  const started = record.target_year < now.getFullYear()
    || (record.target_year === now.getFullYear() && record.target_month <= now.getMonth() + 1);
  const isCurrent = record.target_year === now.getFullYear() && record.target_month === now.getMonth() + 1;
  const previous = isV2Record(record) ? record.previous_month_observation : null;
  const [prevYear, prevMonth] = String(previous?.period || '').split('-').map(Number);
  return [
    ...(started ? [{ label: `${periodLabel(record.target_year, record.target_month)}${isCurrent ? ' so far' : ''}`, observation: liveObservation }] : []),
    ...(previous && prevYear && prevMonth ? [{ label: periodLabel(prevYear, prevMonth), observation: previous }] : []),
  ];
}

export const WATCH_BADGE_CLASS = Object.freeze({
  NONE: 'bg-slate-800 text-slate-300 border-slate-600/40',
  LOW: SEVERITY_BADGE_CLASS.LOW,
  MEDIUM: SEVERITY_BADGE_CLASS.MEDIUM,
  HIGH: SEVERITY_BADGE_CLASS.HIGH,
});
