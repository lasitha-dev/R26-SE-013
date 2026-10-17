/**
 * National case-surveillance view model (pure). Input: the backend's
 * privacy-reduced `national-cases` records. Output: point features for the
 * Cases layer + honest counts. Verified and pending records keep their own
 * status (drawn differently); records without usable farm GPS are counted,
 * never placed. Window dates: a verified record is dated by its
 * verification, a pending one by its report date. Marker colour is the
 * report-date age (`caseAge.js`): 0-14 days red, 15-30 days brown, older
 * than 30 days not placed (counted as `hiddenOlder`), unknown or
 * after-reference dates neutral -- never another date substituted.
 */
import { CASE_AGE_CLASS, classifyCaseAge, isCaseMarkerVisible } from './caseAge'
import { isPointInsideDistrictFeature, normalizeDistrictDisplayName } from './districtGeometry'
import { isWithinObservationWindow } from './observationWindow'
import { isWithinWindowEndingAt } from './spatialStory'
import { parseVerificationTime, sriLankaDateKey, sriLankaEndOfDayMs } from './verificationTime'

export function caseDate(record) {
  return record?.verification_status === 'VERIFIED' ? record.verified_at ?? record.reported_at : record?.reported_at ?? null
}

/** Asia/Colombo calendar date (`YYYY-MM-DD`) of a record's case date. */
export function caseDateKey(record) {
  return sriLankaDateKey(caseDate(record))
}

function inWindow(record, windowDays, endIsoDate) {
  if (!Number.isFinite(windowDays)) {
    // "All recorded": everything up to the analysis date (or now).
    if (!endIsoDate) return true
    const parsed = parseVerificationTime(caseDate(record))
    return Boolean(parsed) && parsed.getTime() <= sriLankaEndOfDayMs(endIsoDate)
  }
  return endIsoDate ? isWithinWindowEndingAt(caseDate(record), windowDays, endIsoDate) : isWithinObservationWindow(caseDate(record), windowDays)
}

function emptyAgeCounts() {
  return Object.fromEntries(Object.values(CASE_AGE_CLASS).map((cls) => [cls, 0]))
}

export function buildNationalCaseView(records, { disease, windowDays, endIsoDate = null, districtFeature = null, ageReferenceDateKey = sriLankaDateKey(new Date()), observedThrough = null } = {}) {
  const features = []
  const unmappedRecords = []
  const replayDates = new Set()
  const counts = {
    inWindow: 0,
    verified: 0,
    pending: 0,
    withoutGps: 0,
    inDistrictVerified: 0,
    inDistrictPending: 0,
    // Records (not markers) by report-date age; `mappedByAge` = placed only.
    byAge: emptyAgeCounts(),
    mappedByAge: emptyAgeCounts(),
    mappedVerified: 0,
    mappedPending: 0,
    // Mappable records older than the 30-day monitoring limit: not drawn.
    hiddenOlder: 0,
  }
  for (const record of Array.isArray(records) ? records : []) {
    if (disease && record?.disease !== disease) continue
    if (!inWindow(record, windowDays, endIsoDate)) continue
    const observedDate = caseDateKey(record)
    if (observedDate) replayDates.add(observedDate)
    // Replay the same real reports that the map draws. Unknown dates have
    // no chronological position; retain them only in the at-latest view.
    if (observedThrough && (!observedDate || observedDate > observedThrough)) continue
    counts.inWindow += 1
    const verified = record.verification_status === 'VERIFIED'
    if (verified) counts.verified += 1
    else counts.pending += 1
    const age = classifyCaseAge(record.reported_at, ageReferenceDateKey)
    counts.byAge[age.ageClass] += 1
    if (record.location_status !== 'VALID' || !Number.isFinite(record.longitude) || Math.abs(record.longitude) > 180 || !Number.isFinite(record.latitude) || Math.abs(record.latitude) > 90) {
      counts.withoutGps += 1
      unmappedRecords.push({
        recordKey: record.record_key, disease: record.disease,
        verificationStatus: record.verification_status, verified,
        reportedAt: record.reported_at ?? null, verifiedAt: record.verified_at ?? null,
        district: normalizeDistrictDisplayName(record.district) ?? null,
        ...age, locationQuality: 'MISSING',
        severity: record.clinical_summary?.severity ?? null,
        stage: record.clinical_summary?.stage ?? null,
        modelConfidence: record.clinical_summary?.model_confidence ?? null,
      })
      continue
    }
    if (!isCaseMarkerVisible(age.ageClass)) {
      counts.hiddenOlder += 1
      continue
    }
    counts.mappedByAge[age.ageClass] += 1
    counts[verified ? 'mappedVerified' : 'mappedPending'] += 1
    const coordinates = [record.longitude, record.latitude]
    const inDistrict = Boolean(districtFeature) && isPointInsideDistrictFeature(coordinates, districtFeature)
    if (inDistrict) counts[verified ? 'inDistrictVerified' : 'inDistrictPending'] += 1
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates },
      properties: {
        recordKey: record.record_key,
        disease: record.disease,
        verificationStatus: record.verification_status,
        verified,
        statusLabel: record.status_label ?? null,
        reportedAt: record.reported_at ?? null,
        verifiedAt: record.verified_at ?? null,
        // Farm labels look like "5.9478, 80.5483 (Matara District)" -> "Matara".
        district: normalizeDistrictDisplayName(record.district) ?? record.district ?? null,
        locationQuality: record.location_quality ?? null,
        severity: record.clinical_summary?.severity ?? null,
        stage: record.clinical_summary?.stage ?? null,
        modelConfidence: record.clinical_summary?.model_confidence ?? null,
        source: record.source ?? null,
        inDistrict,
        ageClass: age.ageClass,
        ageDays: age.ageDays,
        reportDateKey: age.reportDateKey,
      },
    })
  }
  // Several reports often come from ONE farm: stack them into one marker per
  // (location, verification status, age class) carrying the real count, never
  // one invisible dot per record on top of each other -- and never a red
  // marker silently standing in for older reports.
  const stacks = new Map()
  for (const feature of features) {
    const [lon, lat] = feature.geometry.coordinates
    const key = `${lon},${lat}:${feature.properties.verified}:${feature.properties.ageClass}`
    const stack = stacks.get(key)
    if (!stack) {
      stacks.set(key, { ...feature, properties: { ...feature.properties, count: 1, countLabel: '', recordKeys: [feature.properties.recordKey] } })
    } else {
      stack.properties.count += 1
      stack.properties.countLabel = String(stack.properties.count)
      stack.properties.recordKeys.push(feature.properties.recordKey)
      const latest = (feature.properties.verifiedAt ?? feature.properties.reportedAt ?? '') > (stack.properties.verifiedAt ?? stack.properties.reportedAt ?? '')
      if (latest) Object.assign(stack.properties, { verifiedAt: feature.properties.verifiedAt, reportedAt: feature.properties.reportedAt, severity: feature.properties.severity, stage: feature.properties.stage, modelConfidence: feature.properties.modelConfidence })
      // Youngest report in the stack (its age is what the marker is drawn by).
      if (Number.isFinite(feature.properties.ageDays) && !(feature.properties.ageDays >= stack.properties.ageDays)) {
        Object.assign(stack.properties, { ageDays: feature.properties.ageDays, reportDateKey: feature.properties.reportDateKey })
      }
    }
  }
  const stacked = [...stacks.values()]
  // Pending under verified, older under recent, so neither a confirmed nor a
  // recent marker is ever hidden beneath another.
  const ageRank = { [CASE_AGE_CLASS.DATE_UNKNOWN]: 0, [CASE_AGE_CLASS.AFTER_REFERENCE]: 0, [CASE_AGE_CLASS.EXPIRED]: 0, [CASE_AGE_CLASS.OLDER]: 1, [CASE_AGE_CLASS.RECENT]: 2 }
  stacked.sort((a, b) => Number(a.properties.verified) - Number(b.properties.verified) || ageRank[a.properties.ageClass] - ageRank[b.properties.ageClass])
  return {
    featureCollection: { type: 'FeatureCollection', features: stacked }, counts, unmappedRecords, replayDates: [...replayDates].sort(),
    reconciliation: {
      returned: Array.isArray(records) ? records.length : 0,
      excludedByDisease: (Array.isArray(records) ? records : []).filter((r) => disease && r?.disease !== disease).length,
      excludedByWindowOrReplay: (Array.isArray(records) ? records : []).filter((r) => !disease || r?.disease === disease).length - counts.inWindow,
      included: counts.inWindow,
      withoutGps: counts.withoutGps,
      hiddenOlderThanVisibleLimit: counts.hiddenOlder,
      mappable: counts.mappedVerified + counts.mappedPending,
      markerSymbolsBeforeZoomGrouping: stacked.length,
      representedRecords: stacked.reduce((total, feature) => total + feature.properties.count, 0),
    },
  }
}

/** Real case records reported in the last `days` Asia/Colombo days whose
 * farm has no usable map location (backend `location_status` not VALID).
 * They cannot be placed on any map or used as model sources until the farm
 * location is set in ADRS; listed so the vet sees they exist. */
export function recentUnmappedRecords(records, { disease = null, todayKey, days = 14 } = {}) {
  const today = typeof todayKey === 'string' ? Date.parse(`${todayKey}T00:00:00Z`) : NaN
  if (!Number.isFinite(today)) return []
  const sinceKey = new Date(today - (days - 1) * 86400000).toISOString().slice(0, 10)
  return (Array.isArray(records) ? records : []).filter((r) => {
    if (disease && r?.disease !== disease) return false
    if (r?.location_status === 'VALID' && Number.isFinite(r.latitude) && Number.isFinite(r.longitude)) return false
    const key = sriLankaDateKey(r?.reported_at)
    return Boolean(key) && key >= sinceKey && key <= todayKey
  })
}

/** One-line explanation + fix for unmapped recent cases. */
export function unmappedNoticeText(list, diseaseLabel = '') {
  if (!list.length) return null
  const todayCount = list.length
  return `${todayCount} ${diseaseLabel ? `${diseaseLabel} ` : ''}case${todayCount === 1 ? '' : 's'} reported in the last 14 days ${todayCount === 1 ? 'has' : 'have'} no farm map location, so ${todayCount === 1 ? 'it is' : 'they are'} not on the map and not used in risk zones. Fix: the farmer sets the farm location in Health → Settings → Farm configuration.`
}
