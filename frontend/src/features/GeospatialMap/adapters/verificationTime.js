/**
 * GEO26B Section 6/25: single shared parser for the backend's
 * `verification_time` string (e.g. `'2026-01-02 10:00:00'` -- space-
 * separated, no timezone marker, confirmed by inspecting
 * `operationalContextAdapter.js`/its tests). `OperationalContextPopup.jsx`
 * already documents why no Asia/Colombo conversion is attempted for
 * DISPLAY; this module exists only so the observation-window filter and
 * farm-aggregation "latest verified" logic share exactly one definition
 * of "how old is this timestamp" rather than two divergent ones.
 *
 * Never guesses a date for a missing/malformed value -- returns `null`,
 * and every caller treats `null` as "unknown", never "now"/"oldest"/
 * "newest".
 */
export function parseVerificationTime(value) {
  if (typeof value !== 'string' || !value) return null
  const isoLike = value.includes('T') ? value : value.replace(' ', 'T')
  const date = new Date(isoLike)
  return Number.isNaN(date.getTime()) ? null : date
}
