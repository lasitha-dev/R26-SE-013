/**
 * Observed-case age (pure). Colours an observed case by how long ago it was
 * REPORTED -- `reported_at` in `/national-cases`, `case_creation_time` in
 * `/operational-context` (both the ADRS case record's own creation time).
 * The API exposes no onset date, so the label always says "report date".
 *
 * Calendar days are Asia/Colombo dates (`sriLankaDateKey`). The reference
 * date is today's Asia/Colombo date in current mode, or the selected
 * analysis date in retrospective mode -- never the latest stored record.
 *
 * A missing or unparseable report date is DATE_UNKNOWN and a report dated
 * after the reference date is AFTER_REFERENCE: neither is ever treated as
 * recent, and no other timestamp (verification, today) is substituted.
 */
import { formatDisplayDate } from './forecastDate'
import { isValidCalendarDate, sriLankaDateKey } from './verificationTime'

// Monitoring-map display rule (not a diagnosis), by whole Asia/Colombo days
// since the report date:
//   0-14 days  RECENT   red, pulsing
//   15-30 days OLDER    muted brown, static
//   > 30 days  EXPIRED  no case marker (the record stays in MongoDB and in
//                       backend analyses; it is only not drawn as a current case)
export const RECENT_CASE_MAX_AGE_DAYS = 14
export const VISIBLE_CASE_MAX_AGE_DAYS = 30

export const CASE_AGE_CLASS = Object.freeze({
  RECENT: 'RECENT',
  OLDER: 'OLDER',
  EXPIRED: 'EXPIRED',
  DATE_UNKNOWN: 'DATE_UNKNOWN',
  AFTER_REFERENCE: 'AFTER_REFERENCE',
})

export const CASE_AGE_COLOR = Object.freeze({
  RECENT: '#dc2626',
  OLDER: '#8a6a4f',
  EXPIRED: '#8a6a4f',
  DATE_UNKNOWN: '#f8fafc',
  AFTER_REFERENCE: '#f8fafc',
})

/** Whether a case of this age class is drawn as a monitoring-map marker. */
export function isCaseMarkerVisible(ageClass) {
  return ageClass !== CASE_AGE_CLASS.EXPIRED
}

export const CASE_AGE_MODE = Object.freeze({ CURRENT: 'CURRENT', RETROSPECTIVE: 'RETROSPECTIVE' })

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/

function dayNumber(dateKey) {
  const match = typeof dateKey === 'string' ? DATE_ONLY.exec(dateKey) : null
  if (!match || !isValidCalendarDate(dateKey)) return null
  const ms = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isFinite(ms) ? Math.round(ms / 86400000) : null
}

/** Whole Asia/Colombo calendar days from the report date to the reference
 * date (0 = same day, negative = reported after the reference); null when
 * either date is unknown. */
export function caseAgeDays(reportedAt, referenceDateKey) {
  const report = dayNumber(sriLankaDateKey(reportedAt))
  const reference = dayNumber(referenceDateKey)
  if (report === null || reference === null) return null
  return reference - report
}

/** `{ ageClass, ageDays, reportDateKey }` for one observed case. */
export function classifyCaseAge(reportedAt, referenceDateKey) {
  const reportDateKey = sriLankaDateKey(reportedAt)
  const ageDays = caseAgeDays(reportedAt, referenceDateKey)
  let ageClass
  if (ageDays === null) ageClass = CASE_AGE_CLASS.DATE_UNKNOWN
  else if (ageDays < 0) ageClass = CASE_AGE_CLASS.AFTER_REFERENCE
  else if (ageDays <= RECENT_CASE_MAX_AGE_DAYS) ageClass = CASE_AGE_CLASS.RECENT
  else if (ageDays <= VISIBLE_CASE_MAX_AGE_DAYS) ageClass = CASE_AGE_CLASS.OLDER
  else ageClass = CASE_AGE_CLASS.EXPIRED
  return { ageClass, ageDays, reportDateKey }
}

/** The date ages are measured against. `basisAsOf` null = current mode
 * (today's Asia/Colombo date at runtime); a date = retrospective mode. */
export function caseAgeReference({ basisAsOf = null, todayKey = sriLankaDateKey(new Date()) } = {}) {
  const retrospective = isValidCalendarDate(basisAsOf)
  const dateKey = retrospective ? basisAsOf : todayKey
  return {
    dateKey,
    mode: retrospective ? CASE_AGE_MODE.RETROSPECTIVE : CASE_AGE_MODE.CURRENT,
    label: retrospective
      ? `Retrospective · age as of ${formatDisplayDate(dateKey)}`
      : `Current · age as of today (${formatDisplayDate(dateKey)})`,
  }
}

/** Short popup/list text for one case's age. */
export function caseAgeText({ ageClass, ageDays }) {
  if (ageClass === CASE_AGE_CLASS.DATE_UNKNOWN) return 'Report date unavailable -- age unknown'
  if (ageClass === CASE_AGE_CLASS.AFTER_REFERENCE) return 'Reported after the reference date'
  const days = `${ageDays} day${ageDays === 1 ? '' : 's'} since report`
  if (ageClass === CASE_AGE_CLASS.RECENT) return `${days} (≤${RECENT_CASE_MAX_AGE_DAYS} d)`
  if (ageClass === CASE_AGE_CLASS.OLDER) return `${days} (${RECENT_CASE_MAX_AGE_DAYS + 1}–${VISIBLE_CASE_MAX_AGE_DAYS} d)`
  return `${days} (>${VISIBLE_CASE_MAX_AGE_DAYS} d, not shown on the map)`
}

function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

/** Short hover text for a case marker (MapLibre feature properties). */
export function caseHoverHtml(properties) {
  if (!properties) return ''
  const verified = properties.verified === true || properties.verified === 'true'
  const count = Number(properties.count) || 1
  const reported = formatDisplayDate(properties.reportDateKey) ?? 'date unknown'
  const age = caseAgeText({ ageClass: properties.ageClass, ageDays: Number.isFinite(Number(properties.ageDays)) && properties.ageDays !== null ? Number(properties.ageDays) : null })
  return [
    `<strong>${escapeHtml(properties.disease)} · ${verified ? 'vet-verified' : 'pending verification'}</strong>`,
    properties.recordKey ? `Report ${escapeHtml(properties.recordKey)}` : '',
    `${escapeHtml(properties.district ?? 'District not recorded')}${count > 1 ? ` · ${count} reports here` : ''}`,
    `Reported ${escapeHtml(reported)} · ${escapeHtml(age)}`,
    'Click for full details',
  ].filter(Boolean).join('<br/>')
}

/** Collapses several cases at one marker into the class to draw: any recent
 * report makes the marker recent; unknown/after-reference never outrank a
 * known age. */
export function combinedAgeClass(ageClasses) {
  const set = new Set(ageClasses)
  for (const cls of [CASE_AGE_CLASS.RECENT, CASE_AGE_CLASS.OLDER, CASE_AGE_CLASS.EXPIRED, CASE_AGE_CLASS.AFTER_REFERENCE]) {
    if (set.has(cls)) return cls
  }
  return CASE_AGE_CLASS.DATE_UNKNOWN
}
