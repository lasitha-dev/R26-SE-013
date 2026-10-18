/**
 * GEO26B Section 6/25: single shared parser for case timestamps
 * (`verification_time`, `verified_at`, `reported_at`).
 *
 * The backend emits explicit UTC instants (`'2026-08-30T20:05:46+00:00'`,
 * `host_operational_adapter.host_timestamp_text`). Older payloads carried
 * the host's naive UTC text (`'2026-08-30 20:05:46'`, written with
 * `datetime.utcnow()`); a date-time WITHOUT an offset is therefore read as
 * UTC here too -- never as browser-local time. Text with an offset keeps
 * it, so no instant is converted twice. Calendar dates (case dates, windows,
 * replay days) are Asia/Colombo dates (`sriLankaDateKey`), the same basis the
 * backend uses for `as_of` and source eligibility.
 *
 * Never guesses a date for a missing/malformed value -- returns `null`,
 * and every caller treats `null` as "unknown", never "now"/"oldest"/
 * "newest".
 */
export const SRI_LANKA_UTC_OFFSET_MINUTES = 330 // Asia/Colombo, UTC+05:30, no DST

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/
const HAS_TIME = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/
const HAS_OFFSET = /(Z|[+-]\d{2}:?\d{2})$/i
const OFFSET_MS = SRI_LANKA_UTC_OFFSET_MINUTES * 60 * 1000

/** Reject calendar rollover (for example 30 February) before Date normalises it. */
export function isValidCalendarDate(value) {
  if (typeof value !== 'string' || !DATE_ONLY.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

export function parseVerificationTime(value) {
  if (typeof value !== 'string' || !value.trim()) return null
  const text = value.trim()
  if (!isValidCalendarDate(text.slice(0, 10))) return null
  let isoLike = text.includes('T') ? text : text.replace(' ', 'T')
  if (HAS_TIME.test(text) && !HAS_OFFSET.test(text)) isoLike = `${isoLike}Z`
  const date = new Date(isoLike)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Asia/Colombo calendar date (`YYYY-MM-DD`) of a timestamp string or Date;
 * a date-only string is already a calendar date and is returned unchanged. */
export function sriLankaDateKey(value) {
  if (typeof value === 'string' && DATE_ONLY.test(value.trim())) return isValidCalendarDate(value.trim()) ? value.trim() : null
  const date = value instanceof Date ? value : parseVerificationTime(value)
  if (!date || Number.isNaN(date.getTime())) return null
  return new Date(date.getTime() + OFFSET_MS).toISOString().slice(0, 10)
}

/** Epoch ms of the last millisecond of an Asia/Colombo calendar date. */
export function sriLankaEndOfDayMs(isoDate) {
  if (!isValidCalendarDate(isoDate)) return NaN
  return Date.parse(`${isoDate}T23:59:59.999+05:30`)
}

const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** A verification timestamp as Sri Lanka (Asia/Colombo) date and time, e.g.
 * "14 Oct 2026, 09:47"; null when absent or unparseable (never a guess). */
export function formatVerificationTime(value) {
  const date = parseVerificationTime(value)
  if (!date) return null
  const local = new Date(date.getTime() + OFFSET_MS)
  const hh = String(local.getUTCHours()).padStart(2, '0')
  const mm = String(local.getUTCMinutes()).padStart(2, '0')
  return `${local.getUTCDate()} ${SHORT_MONTHS[local.getUTCMonth()]} ${local.getUTCFullYear()}, ${hh}:${mm}`
}
