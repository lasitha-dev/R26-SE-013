/**
 * LSD-UI-01/05: forecast-day date arithmetic (plan Section 15/D). The
 * backend's `t0` (e.g. "2020-09-28") is already the resolved forecast
 * origin -- `forecast_origin_at -> model_run_at -> reported_at` fallback
 * priority is the BACKEND's job (`services/forecast_origin.py`); the
 * frontend only ever adds calendar days to the `t0` it was given, never
 * re-derives an origin from raw report timestamps itself.
 *
 * `t0` carries no time-of-day (date-only, Asia/Colombo civil date by
 * backend convention -- see GEOSPATIAL_API_PROTOCOL.md). The real risk
 * here is not the Colombo offset (a date-only string has no offset to
 * apply) but the classic JS pitfall of parsing "YYYY-MM-DD" with `new
 * Date(str)` (interpreted as UTC midnight) and then reading local-time
 * getters against it, which silently shifts the displayed day in any
 * negative-UTC-offset browser timezone. Every function below stays in
 * UTC-component arithmetic end to end to avoid that class of bug --
 * correct across month/year rollover and leap years for free, since
 * `Date.UTC` normalizes overflowing day/month values itself.
 */

const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/

function parseIsoDateUtc(isoDate) {
  const match = ISO_DATE_RE.exec(isoDate)
  if (!match) {
    throw new Error(`expected an ISO date (YYYY-MM-DD), got: ${isoDate}`)
  }
  const [, year, month, day] = match
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)))
}

/** t0 ("2020-09-28") + dayIndex (0..7) -> "2020-10-05", via UTC-safe
 * calendar-day addition (correct across month/year rollover and leap
 * years, since Date.UTC normalizes overflowing components itself). */
export function addDaysToIsoDate(t0, dayIndex) {
  const base = parseIsoDateUtc(t0)
  const shifted = new Date(base.getTime() + dayIndex * 86_400_000)
  const yyyy = shifted.getUTCFullYear()
  const mm = String(shifted.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(shifted.getUTCDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function forecastDayLabel(dayIndex) {
  return dayIndex === 0 ? 'D0' : `D+${dayIndex}`
}

/** Human-readable "11 Aug 2020" for the given ISO date, in a fixed
 * locale-independent form (never `toLocaleDateString()` without a
 * pinned locale -- that reads the browser's locale, which would make
 * this render differently per vet). */
export function formatDisplayDate(isoDate) {
  const date = parseIsoDateUtc(isoDate)
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`
}
