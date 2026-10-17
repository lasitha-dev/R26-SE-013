/**
 * PAGE-3-NATIONAL-KPI: a real, deterministic recency filter over the
 * backend's own already-bucketed `historical_trend.points`
 * (`analysisTrendsAdapter.js::normalizeHistoricalTrend`). This never
 * re-aggregates or re-buckets a single real record -- it only narrows
 * which already-real periods are displayed, so the "30D / 12W / YTD"
 * chart window never disagrees with the backend's own real counts.
 *
 * Anchored to the LAST real period already present in the dataset, not
 * to the browser's wall-clock date: this feature's own historical/model
 * evidence can be years old (real Sri Lanka LSD/FMD study data), so a
 * `Date.now()` anchor would silently empty the chart for genuinely real
 * data. 'YTD' anchors to the calendar year of that same last real
 * period, for the same reason.
 */

const WEEK_KEY_RE = /^(\d{4})-W(\d{2})$/
const MONTH_KEY_RE = /^(\d{4})-(\d{2})$/
const YEAR_KEY_RE = /^(\d{4})$/

function isoWeekMonday(year, week) {
  // ISO 8601: week 1 is the week containing the year's first Thursday.
  const jan4 = new Date(Date.UTC(year, 0, 4))
  const jan4Weekday = jan4.getUTCDay() || 7 // Monday=1 .. Sunday=7
  const week1Monday = new Date(jan4)
  week1Monday.setUTCDate(jan4.getUTCDate() - (jan4Weekday - 1))
  const monday = new Date(week1Monday)
  monday.setUTCDate(week1Monday.getUTCDate() + (week - 1) * 7)
  return monday
}

/** The real calendar end-date a `{period, periodBasis}` pair covers, or
 * `null` for an unrecognized/malformed shape -- never guessed. */
export function periodEndDate(period, periodBasis) {
  if (typeof period !== 'string') return null

  if (periodBasis === 'WEEK') {
    const match = WEEK_KEY_RE.exec(period)
    if (!match) return null
    const monday = isoWeekMonday(Number(match[1]), Number(match[2]))
    const sunday = new Date(monday)
    sunday.setUTCDate(monday.getUTCDate() + 6)
    return sunday
  }

  if (periodBasis === 'MONTH') {
    const match = MONTH_KEY_RE.exec(period)
    if (!match) return null
    // Day 0 of the following month == the last real day of this month.
    return new Date(Date.UTC(Number(match[1]), Number(match[2]), 0))
  }

  if (periodBasis === 'YEAR') {
    const match = YEAR_KEY_RE.exec(period)
    if (!match) return null
    return new Date(Date.UTC(Number(match[1]), 11, 31))
  }

  return null
}

export const TREND_WINDOW_OPTIONS = ['30D', '12W', 'YTD']

const WINDOW_DAYS = { '30D': 30, '12W': 84 }

/**
 * Narrows `points` to those whose real period falls inside `window`
 * ('30D' | '12W' | 'YTD'), relative to the most recent real period in
 * the set. Returns `points` unchanged for an unrecognized `window`/
 * `periodBasis` combination -- never drops real data it cannot
 * confidently place in time.
 */
export function filterTrendPointsByWindow(points, periodBasis, window) {
  const safePoints = Array.isArray(points) ? points : []
  if (safePoints.length === 0) return []
  if (!TREND_WINDOW_OPTIONS.includes(window)) return safePoints

  const dated = safePoints.map((point) => ({ point, end: periodEndDate(point.period, periodBasis) }))
  if (dated.some((entry) => !entry.end)) return safePoints // an unrecognized period shape -- never silently drop real data

  const lastEnd = dated.reduce((max, entry) => (entry.end > max ? entry.end : max), dated[0].end)

  if (window === 'YTD') {
    const year = lastEnd.getUTCFullYear()
    return dated.filter((entry) => entry.end.getUTCFullYear() === year).map((entry) => entry.point)
  }

  const days = WINDOW_DAYS[window]
  const cutoff = new Date(lastEnd)
  cutoff.setUTCDate(cutoff.getUTCDate() - days)
  return dated.filter((entry) => entry.end >= cutoff && entry.end <= lastEnd).map((entry) => entry.point)
}
