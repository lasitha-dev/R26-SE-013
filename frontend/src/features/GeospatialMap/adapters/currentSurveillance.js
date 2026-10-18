/**
 * PAGE-3-CURRENT-DASHBOARD: pure derivations over the SAME real, current,
 * DB-backed Verified Clinical Context collection that already powers
 * Page 1's own confirmed-case markers (traced, not guessed:
 * `context/useOperationalContext.js` -> `adapters/operationalContextAdapter.js`'s
 * `clinicalContexts`/`surveillanceContexts` -> `OutbreakMapPage.jsx`'s
 * `operationalContextsForDisease` -> `operationalMarkerLayer.js`'s solid
 * RED diamond/circle icons, `CLINICAL_MARKER_COLOR_HEX = '#ef4444'` in
 * `operationalIcons.js`). Every function here reuses that same real
 * `{ caseId, disease, locationDistrict, verificationTime }` shape -- never
 * the separate, retrospective (2020-era WAHIS/FAO research) `/origins` or
 * `/analysis-trends` ledgers, and never a second/duplicated fetch.
 *
 * `locationDistrict` already arrives pre-resolved from each farm's own
 * real `location_district` field (`operationalContextAdapter.js`), so no
 * point-in-polygon geometry is needed here at all.
 */
import { isPointInsideDistrictFeature, normalizeDistrictDisplayName } from './districtGeometry'
import { parseVerificationTime, sriLankaDateKey } from './verificationTime'

export const CURRENT_ACTIVITY_WINDOW_OPTIONS = [
  { id: '7d', days: 7, label: '7D' },
  { id: '14d', days: 14, label: '14D' },
  { id: '30d', days: 30, label: '30D' },
  // Longer view so older real activity is visible when the recent windows are empty.
  { id: '90d', days: 90, label: '90D' },
]

export const DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS = 14

/** Scope privacy-reduced operational reports to the district resolved by
 * authentication. An unresolved district never falls back to national data. */
export function recordsForDistrict(records, district) {
  const name = normalizeDistrictDisplayName(district)?.trim().toLowerCase()
  if (!name || name.replace(/[^a-z]/g, '') === 'alldistricts') return []
  return (Array.isArray(records) ? records : []).filter((record) => normalizeDistrictDisplayName(record?.district)?.trim().toLowerCase() === name)
}

/** Keep the national clustering calculation intact; select clusters with
 * an actual backend member location inside the authenticated district. */
export function clustersForDistrict(clusters, districtFeature) {
  if (!districtFeature) return []
  return (Array.isArray(clusters) ? clusters : []).filter((cluster) =>
    (Array.isArray(cluster.member_locations) ? cluster.member_locations : []).some((point) =>
      Number.isFinite(point?.longitude) && Number.isFinite(point?.latitude) &&
      isPointInsideDistrictFeature([point.longitude, point.latitude], districtFeature)))
}

/** Keeps only real contexts for `disease` -- an unset/unknown disease
 * yields an empty list, never "every disease" merged together. */
export function filterCurrentContextsByDisease(contexts, disease) {
  const list = Array.isArray(contexts) ? contexts : []
  if (!disease) return []
  return list.filter((c) => c?.disease === disease)
}

/** Distinct real `caseId`s only -- defensive dedup even though the
 * upstream adapter already de-duplicates by construction (Section 8:
 * "use stable IDs for deduplication"). */
export function deriveCurrentRecordCount(contexts) {
  const ids = new Set()
  for (const c of contexts ?? []) {
    if (c?.caseId) ids.add(c.caseId)
  }
  return ids.size
}

/** `{ count, districts }` -- unique real `locationDistrict` values among
 * the current, disease-filtered contexts. A context with no resolved
 * district is excluded, never guessed. */
export function deriveCurrentAffectedAreas(contexts) {
  const districts = new Set()
  for (const c of contexts ?? []) {
    if (c?.locationDistrict) districts.add(c.locationDistrict)
  }
  return { count: districts.size, districts: [...districts].sort() }
}

/**
 * Top-N real districts by real current-record count, descending (ties
 * broken alphabetically). A district with zero real current cases never
 * appears -- no filler rows. `lastObserved` is the most recent real
 * `verificationTime` among that district's own real cases (never a
 * proxy -- unlike the historical/origin system, each current case
 * already carries its own real timestamp).
 */
export function buildCurrentMostAffectedAreas(contexts, { topN = 5 } = {}) {
  const byDistrict = new Map()

  for (const c of contexts ?? []) {
    if (!c?.locationDistrict) continue
    const entry = byDistrict.get(c.locationDistrict) ?? { district: c.locationDistrict, records: 0, lastObserved: null, lastObservedMs: null }
    entry.records += 1
    const parsed = parseVerificationTime(c.verificationTime)
    if (parsed && (entry.lastObservedMs == null || parsed.getTime() > entry.lastObservedMs)) {
      entry.lastObservedMs = parsed.getTime()
      entry.lastObserved = c.verificationTime
    }
    byDistrict.set(c.locationDistrict, entry)
  }

  return [...byDistrict.values()]
    .map(({ district, records, lastObserved }) => ({ district, records, lastObserved }))
    .sort((a, b) => b.records - a.records || a.district.localeCompare(b.district))
    .slice(0, topN)
}

// Daily buckets are Asia/Colombo calendar dates (no DST), matching the
// backend's verification-date basis -- never the browser's own timezone.
function localDateKey(date) {
  return sriLankaDateKey(date)
}

/**
 * Real, wall-clock-anchored daily buckets for the "Recent Outbreak
 * Activity" chart: `windowDays` real calendar days ending today
 * (Section 14: "today minus 13 days through today" for the 14D default),
 * using each real context's own `verificationTime` -- never anchored to
 * the last record in the dataset (this is current surveillance, not
 * retrospective research). A day with no real case is a genuine `0`
 * (Section 15's "sparse bars are acceptable"), never smoothed/omitted. A
 * context with no parseable `verificationTime` is excluded from the
 * chart (`excludedCount`) but is NOT removed from the caller's own
 * `contexts` list, so it still counts toward `Current Records`/`Affected
 * Areas` elsewhere (Section 16).
 */
export function buildRecentActivityBuckets(contexts, windowDays, nowMs = Date.now()) {
  const days = []
  for (let i = windowDays - 1; i >= 0; i -= 1) {
    days.push(localDateKey(new Date(nowMs - i * 24 * 60 * 60 * 1000)))
  }

  const counts = new Map(days.map((key) => [key, 0]))
  let excludedCount = 0

  for (const c of contexts ?? []) {
    const parsed = parseVerificationTime(c?.verificationTime)
    if (!parsed) {
      excludedCount += 1
      continue
    }
    const key = localDateKey(parsed)
    if (counts.has(key)) counts.set(key, counts.get(key) + 1)
    // Outside the selected window entirely -- not a chart bar, but still
    // a real record counted elsewhere (Current Records/Affected Areas).
  }

  const points = days.map((period) => ({ period, count: counts.get(period), count_basis: 'CURRENT_VERIFIED_CASES' }))
  return { points, excludedCount }
}

// ---- National population (`GET /national-cases`) --------------------------
// The Analysis page's scope is Sri Lanka, so its population is the national,
// privacy-reduced ADRS case records (vet-verified + pending) -- not the
// vet's own district surveillance contexts. Basis: one record = one ADRS
// diagnostic case report; dates are its report date (`reported_at`) as an
// Asia/Colombo calendar date. Historical WAHIS/EMPRES research records are a
// different population and never enter these numbers.

/** Disease-filtered national records; an unset disease yields []. */
export function nationalRecordsForDisease(records, disease) {
  if (!disease) return []
  return (Array.isArray(records) ? records : []).filter((r) => r?.disease === disease)
}

function recordDistrict(record) {
  return normalizeDistrictDisplayName(record?.district)
}

/** Whole-population counts plus how many reports fall inside the
 * `windowDays` calendar days ending on `todayKey` (Asia/Colombo). */
export function summarizeNationalRecords(records, { windowDays = DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS, nowMs = Date.now() } = {}) {
  const todayKey = sriLankaDateKey(new Date(nowMs))
  const windowStartKey = sriLankaDateKey(new Date(nowMs - (windowDays - 1) * 24 * 60 * 60 * 1000))
  const summary = {
    total: 0,
    verified: 0,
    pending: 0,
    districts: new Set(),
    withoutDistrict: 0,
    inWindow: 0,
    beforeWindow: 0,
    afterToday: 0,
    dateUnknown: 0,
    latestReportDate: null,
    windowStartKey,
    windowEndKey: todayKey,
  }
  for (const record of Array.isArray(records) ? records : []) {
    summary.total += 1
    if (record?.verification_status === 'VERIFIED') summary.verified += 1
    else summary.pending += 1
    const district = recordDistrict(record)
    if (district) summary.districts.add(district)
    else summary.withoutDistrict += 1
    const key = sriLankaDateKey(record?.reported_at)
    if (!key) summary.dateUnknown += 1
    else if (key > todayKey) summary.afterToday += 1
    else if (key < windowStartKey) summary.beforeWindow += 1
    else summary.inWindow += 1
    if (key && key <= todayKey && (!summary.latestReportDate || key > summary.latestReportDate)) summary.latestReportDate = key
  }
  return { ...summary, districtCount: summary.districts.size, districts: [...summary.districts].sort() }
}

/** Daily report counts (verified + pending) for the `windowDays` calendar
 * days ending today, by report date. A day without reports is a real 0. */
export function buildNationalActivityBuckets(records, windowDays, nowMs = Date.now()) {
  const days = []
  for (let i = windowDays - 1; i >= 0; i -= 1) days.push(localDateKey(new Date(nowMs - i * 24 * 60 * 60 * 1000)))
  const counts = new Map(days.map((key) => [key, 0]))
  let excludedCount = 0
  for (const record of Array.isArray(records) ? records : []) {
    const key = sriLankaDateKey(record?.reported_at)
    if (!key) {
      excludedCount += 1
      continue
    }
    if (counts.has(key)) counts.set(key, counts.get(key) + 1)
  }
  const points = days.map((period) => ({ period, count: counts.get(period), count_basis: 'ADRS_CASE_REPORTS_BY_REPORT_DATE' }))
  return { points, excludedCount }
}

/** Districts by number of national records (all dates), descending; ties
 * alphabetical. Records without a district are left out (counted in the
 * summary's `withoutDistrict`). */
export function buildNationalMostAffectedAreas(records, { topN = 5 } = {}) {
  const byDistrict = new Map()
  for (const record of Array.isArray(records) ? records : []) {
    const district = recordDistrict(record)
    if (!district) continue
    const entry = byDistrict.get(district) ?? { district, records: 0, verified: 0, pending: 0, lastReported: null }
    entry.records += 1
    if (record.verification_status === 'VERIFIED') entry.verified += 1
    else entry.pending += 1
    const key = sriLankaDateKey(record.reported_at)
    if (key && (!entry.lastReported || key > entry.lastReported)) entry.lastReported = key
    byDistrict.set(district, entry)
  }
  return [...byDistrict.values()].sort((a, b) => b.records - a.records || a.district.localeCompare(b.district)).slice(0, topN)
}
