/**
 * URGENT-MATARA-REAL-FILTER: buckets `mataraOrigins` (already real,
 * already filtered by `districtGeometry.js::filterOriginsInsideDistrict`
 * -- never a second/duplicated fetch) into a real per-month activity
 * series for the "Matara Origin Activity" chart. Deliberately a plain,
 * fixed MONTH bucketing rather than reimplementing the backend's own
 * WEEK/MONTH/YEAR span-threshold rule (`services/analysis_trends/
 * historical_trend.py::choose_trend_period_basis`) -- that rule exists
 * for the FULL national corpus; the real Matara-filtered subset is
 * expected to be small/sparse for this demo, so one honest, always-
 * correct basis is used rather than a second, drifting reimplementation
 * of the backend's own threshold logic. Never fabricates a missing
 * month -- a sparse real dataset produces a sparse real chart (Section
 * 8's explicit rule).
 */

const COUNT_BASIS = 'ORIGINS'

function monthPeriod(isoDate) {
  return typeof isoDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(isoDate) ? isoDate.slice(0, 7) : null
}

/** `mataraOrigins` -> `{ periodBasis: 'MONTH', countBasis: 'ORIGINS',
 * points: [{ period: 'YYYY-MM', count }] }`, sorted chronologically.
 * Real origin timestamps only -- an origin with no valid `t0` is simply
 * excluded, never coerced into a fabricated bucket. */
export function buildMataraOriginActivityPoints(mataraOrigins) {
  const counts = new Map()
  for (const origin of mataraOrigins ?? []) {
    const period = monthPeriod(origin?.t0)
    if (!period) continue
    counts.set(period, (counts.get(period) ?? 0) + 1)
  }
  const points = [...counts.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([period, count]) => ({ period, count, count_basis: COUNT_BASIS }))
  return { periodBasis: 'MONTH', countBasis: COUNT_BASIS, points }
}

/** `{ firstDate, lastDate }` (real ISO `t0` strings, chronologically
 * min/max -- ISO 8601 sorts lexicographically) or `null` when there are
 * no real Matara origins. Never substitutes the national observation
 * window. */
export function mataraObservedPeriod(mataraOrigins) {
  const dates = (mataraOrigins ?? []).map((o) => o?.t0).filter((t0) => typeof t0 === 'string' && t0)
  if (dates.length === 0) return null
  return { firstDate: dates.reduce((a, b) => (a < b ? a : b)), lastDate: dates.reduce((a, b) => (a > b ? a : b)) }
}
