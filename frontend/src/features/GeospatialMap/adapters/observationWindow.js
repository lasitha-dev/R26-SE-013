/**
 * GEO26B Section 6/25: the "Observation Date Range" control -- a
 * DIFFERENT concept from the scientific forecast timeline
 * (`context/outbreakSelectionReducer.js`'s `selectedForecastDay`). This
 * window only ever filters real, already-verified clinical contexts by
 * how long ago `verification_time` was; it never selects a model/
 * forecast frame and is never read by any historical/model hook (kept
 * out of `GeospatialContext` on purpose -- Page 1's own local UI state).
 *
 * "Today" is a rolling 24h window, not a calendar-day boundary --
 * `verification_time` carries no timezone marker (see
 * `verificationTime.js`), so a calendar-day cutoff would silently depend
 * on the browser's local timezone in a way that isn't honestly
 * attributable to the backend. A rolling window has no such hidden
 * assumption and still satisfies the required invariant: a case from
 * yesterday remains visible in every window bigger than "Today".
 */
import { parseVerificationTime } from './verificationTime'

const DAY_MS = 24 * 60 * 60 * 1000

// National surveillance windows. LATEST_REPORTS_WINDOW is a sentinel resolved
// by `resolveObservationWindow` to the 14 days ending at the most recent real
// record; ALL_RECORDED_WINDOW (Infinity) keeps every record up to the
// analysis date, so older reports are never hidden by a recent-only window.
export const LATEST_REPORTS_WINDOW = -1
export const ALL_RECORDED_WINDOW = Infinity
export const OBSERVATION_WINDOW_OPTIONS = [
  { id: 'latest', days: LATEST_REPORTS_WINDOW, label: 'Latest reports' },
  { id: 'today', days: 1, label: 'Today' },
  { id: '7d', days: 7, label: 'Last 7 days' },
  { id: '14d', days: 14, label: 'Last 14 days' },
  { id: '30d', days: 30, label: 'Last 30 days' },
  { id: 'all', days: ALL_RECORDED_WINDOW, label: 'All recorded' },
]

export const DEFAULT_OBSERVATION_WINDOW_DAYS = 14

// GEO26B Section 9: "recent" vs "older" marker-opacity tier -- a fixed,
// documented threshold (not tied to whichever window is currently
// selected), so switching the Date Range control alone never silently
// changes which already-visible markers look "recent".
export const RECENT_MARKER_THRESHOLD_DAYS = 3

/**
 * A case with no parseable `verification_time` is excluded, never
 * guessed into or out of the window (mirrors the risk-score
 * null-handling convention in `mapLibreAdapter.js`: unavailable is never
 * treated as a favorable/default value).
 */
export function isWithinObservationWindow(verificationTime, windowDays, nowMs = Date.now()) {
  const parsed = parseVerificationTime(verificationTime)
  if (!parsed) return false
  const ageMs = nowMs - parsed.getTime()
  if (ageMs < 0) return true // clock-skew safety: a slightly-future timestamp is still current
  return ageMs <= windowDays * DAY_MS
}

/** 'recent' | 'older' -- an unparseable timestamp is classified 'older'
 * (never 'recent'), consistent with the "never favorable when unknown" rule. */
export function classifyRecency(verificationTime, nowMs = Date.now()) {
  const parsed = parseVerificationTime(verificationTime)
  if (!parsed) return 'older'
  const ageMs = nowMs - parsed.getTime()
  if (ageMs < 0) return 'recent'
  return ageMs <= RECENT_MARKER_THRESHOLD_DAYS * DAY_MS ? 'recent' : 'older'
}

/** Concrete `{ days, endIsoDate }` for a window option: Latest reports = the
 * 14 days ending at `latestRecordDate`; otherwise the option's own length,
 * ending at the analysis date (`basisAsOf`) when one is chosen, else now. */
export function resolveObservationWindow(daysOption, { basisAsOf = null, latestRecordDate = null } = {}) {
  if (daysOption === LATEST_REPORTS_WINDOW) {
    return { days: 14, endIsoDate: latestRecordDate ?? basisAsOf ?? null }
  }
  return { days: daysOption, endIsoDate: basisAsOf ?? null }
}
