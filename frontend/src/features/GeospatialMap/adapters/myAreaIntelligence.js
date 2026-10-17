/**
 * My Area district intelligence (pure). Joins three real data sets the page
 * already loads -- the vet-authorised operational context (registered farms,
 * verified clinical contexts), the privacy-reduced national case records
 * (pending and no-GPS reports) and ONE backend spatial-timeline snapshot --
 * into the view models for Future Impact, Verified Cases, the Future Risk
 * Outlook chart and Area Intelligence.
 *
 * Rules:
 *  - Nothing is scored or predicted here. Spatial facts are point-in-polygon
 *    tests of real farm GPS against backend geometry.
 *  - A farm inside a scored monitoring area is never "infected"; only a real
 *    verified report makes a farm a reporting farm.
 *  - A record without usable GPS is listed, never placed on the map.
 *  - Tiers are within-snapshot relative quartiles of the frozen C0 score over
 *    scored land cells -- never probabilities, never absolute safety.
 */
import { CASE_AGE_CLASS, classifyCaseAge } from './caseAge'
import { pointInGeometry, tierAtPoint } from './myAreaFarmIntelligence'
import { HORIZON_STATUS, TIER_ORDER, timelineFrames } from './spatialTimelineView'
import { sriLankaDateKey } from './verificationTime'
import { formatDisplayDate } from './forecastDate'

/** One label per backend tier, used by map legend, chart, KPIs and panel. */
export const RELATIVE_TIER_LABEL = Object.freeze({
  highest: 'Highest relative',
  high: 'Elevated relative',
  moderate: 'Moderate relative',
  lower: 'Lowest relative',
})

export const RELATIVE_TIER_NOTE = 'Within-snapshot quartile of the C0 relative score over scored land cells -- not a probability, not a safety level.'

/** Text for a clicked backend monitoring polygon. District names come from
 * the actual boundary; no village name or future case location is inferred. */
export function monitoringZoneDetails(properties, districtName) {
  const tierLabel = RELATIVE_TIER_LABEL[properties?.tier]
  if (!tierLabel) return []
  return [
    districtName || 'Authorised district',
    `${tierLabel} spatial concern`,
    Number.isFinite(properties.day) && properties.date ? `Day ${properties.day} · ${formatDisplayDate(properties.date)}` : null,
    Number.isFinite(properties.area_km2) ? `${properties.area_km2.toFixed(1)} km² in this relative tier` : null,
    'Scored monitoring area within nominal reach. Not a predicted infection location.',
    RELATIVE_TIER_NOTE,
  ].filter(Boolean)
}

export const FARM_STATUS = Object.freeze({
  REPORTING: 'REPORTING',
  MONITORED: 'IN_SCORED_AREA_WITHIN_REACH',
  SCORED: 'IN_SCORED_AREA',
  OUTSIDE: 'OUTSIDE_SCORED_AREA',
  NO_GPS: 'NO_GPS',
})

export const FARM_STATUS_LABEL = Object.freeze({
  [FARM_STATUS.REPORTING]: 'Verified report',
  [FARM_STATUS.MONITORED]: 'Scored area · within reach',
  [FARM_STATUS.SCORED]: 'Scored area',
  [FARM_STATUS.OUTSIDE]: 'Outside scored area',
  [FARM_STATUS.NO_GPS]: 'No GPS on record',
})

export const ACTION_BASIS = Object.freeze({
  REPORTS: 'Actual reports',
  MODEL: 'Modelled monitoring context',
  GUIDANCE: 'General clinical guidance',
})

function normalizeName(value) {
  if (typeof value !== 'string') return null
  let text = value.trim()
  const paren = text.match(/\(([^)]*)\)\s*$/)
  if (paren) text = paren[1]
  return text.replace(/\s+district$/i, '').trim().toLowerCase() || null
}

function hasGps(farm) {
  return farm?.locationStatus === 'VALID' && Number.isFinite(farm.latitude) && Number.isFinite(farm.longitude)
}

function uniqueBy(items, key) {
  const seen = new Map()
  for (const item of items) {
    const k = key(item)
    if (k != null && !seen.has(k)) seen.set(k, item)
  }
  return [...seen.values()]
}

function farmInDistrict(farm, districtName, districtFeature) {
  if (hasGps(farm) && districtFeature) return pointInGeometry(farm.longitude, farm.latitude, districtFeature)
  return Boolean(districtName) && normalizeName(farm.locationDistrict) === normalizeName(districtName)
}

function shortId(id) {
  return typeof id === 'string' && id.length > 6 ? id.slice(-6) : id
}

function frameAt(timeline, index) {
  const frames = timelineFrames(timeline)
  return frames[Math.max(0, Math.min(frames.length - 1, index))] ?? null
}

/** Every registered farm in the district the vet may see (assigned + district
 * surveillance farms), with real case history and spatial context. */
export function buildDistrictFarmRoster({ operationalData = null, farmNames = null, districtName = null, districtFeature = null, timeline = null, frameIndex = 0, disease = null } = {}) {
  // District farms, plus EVERY farm personally assigned to this vet -- an
  // assigned farm with no GPS/district or outside the district is still the
  // vet's own farm and must stay visible (flagged), never silently dropped.
  const assignedIds = new Set((operationalData?.farms ?? []).map((f) => f?.farmId))
  const farms = uniqueBy([...(operationalData?.farms ?? []), ...(operationalData?.surveillanceFarms ?? [])], (f) => f?.farmId)
    .filter((farm) => assignedIds.has(farm.farmId) || farmInDistrict(farm, districtName, districtFeature))
  const contexts = uniqueBy([...(operationalData?.clinicalContexts ?? []), ...(operationalData?.surveillanceContexts ?? [])], (c) => c?.caseId)
  const frame = frameAt(timeline, frameIndex)
  const envelope = frame?.reach_envelope ?? null
  const rows = farms.map((farm) => {
    const gps = hasGps(farm)
    const cases = contexts
      .filter((c) => c.farmId === farm.farmId)
      .map((c) => ({ caseId: c.caseId, disease: c.disease, verificationTime: c.verificationTime, reportedAt: c.reportedAt ?? null, date: sriLankaDateKey(c.verificationTime) }))
      .sort((a, b) => String(b.verificationTime ?? '').localeCompare(String(a.verificationTime ?? '')))
    const diseaseCases = disease ? cases.filter((c) => c.disease === disease) : cases
    const tier = gps && timeline ? tierAtPoint(timeline, farm.longitude, farm.latitude) : null
    const withinReach = gps && tier !== null && envelope ? pointInGeometry(farm.longitude, farm.latitude, envelope) : false
    const status = diseaseCases.length > 0 ? FARM_STATUS.REPORTING
      : !gps ? FARM_STATUS.NO_GPS
        : withinReach ? FARM_STATUS.MONITORED
          : tier ? FARM_STATUS.SCORED : FARM_STATUS.OUTSIDE
    const assigned = assignedIds.has(farm.farmId)
    const outsideDistrict = !farmInDistrict(farm, districtName, districtFeature)
    return {
      farmId: farm.farmId,
      label: (assigned && farmNames?.get(farm.farmId)?.name) || `${assigned ? 'Assigned' : 'District'} farm ·${shortId(farm.farmId)}`,
      personallyAssigned: assigned,
      outsideDistrict,
      hasGps: gps,
      coordinates: gps ? [farm.longitude, farm.latitude] : null,
      totalAnimals: assigned && Number.isFinite(farm.totalAnimals) ? farm.totalAnimals : null,
      cases,
      diseaseCaseCount: diseaseCases.length,
      latestCaseDate: diseaseCases[0]?.date ?? null,
      tier,
      withinReach,
      status,
    }
  })
  const order = [FARM_STATUS.REPORTING, FARM_STATUS.MONITORED, FARM_STATUS.SCORED, FARM_STATUS.OUTSIDE, FARM_STATUS.NO_GPS]
  rows.sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status)
    || TIER_ORDER.indexOf(b.tier) - TIER_ORDER.indexOf(a.tier)
    || a.label.localeCompare(b.label))
  // District figures count only farms IN the district; the vet's own farms
  // elsewhere are listed (flagged) but never counted as this district's.
  const inDistrict = rows.filter((r) => !r.outsideDistrict)
  const summary = {
    total: inDistrict.length,
    mapped: inDistrict.filter((r) => r.hasGps).length,
    withoutGps: inDistrict.filter((r) => !r.hasGps).length,
    reporting: inDistrict.filter((r) => r.status === FARM_STATUS.REPORTING).length,
    inScoredArea: inDistrict.filter((r) => r.tier !== null).length,
    monitoredWithinReach: inDistrict.filter((r) => r.withinReach).length,
    assigned: rows.filter((r) => r.personallyAssigned).length,
    assignedOutsideDistrict: rows.filter((r) => r.outsideDistrict).length,
  }
  return { rows, summary }
}

/** Registered farms as map points (GPS only). The red "reporting" ring
 * follows the monitoring-map age rule: only a farm with a report no more than
 * 30 days before the reference date is drawn as reporting -- older history
 * stays in the case list, never on the map as a current case. */
export function buildRegisteredFarmFeatures(roster, { ageReferenceDateKey = null, disease = null } = {}) {
  const withinVisibleAge = (c) => {
    const ageClass = classifyCaseAge(c.reportedAt ?? c.verificationTime, ageReferenceDateKey).ageClass
    return ageClass === CASE_AGE_CLASS.RECENT || ageClass === CASE_AGE_CLASS.OLDER
  }
  const currentlyReporting = (row) => row.status === FARM_STATUS.REPORTING
    && (!ageReferenceDateKey || row.cases.some((c) => (!disease || c.disease === disease) && withinVisibleAge(c)))
  return {
    type: 'FeatureCollection',
    features: (roster?.rows ?? []).filter((r) => r.coordinates && !r.outsideDistrict).map((r) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: r.coordinates },
      properties: { farmId: r.farmId, label: r.label, status: r.status, statusLabel: FARM_STATUS_LABEL[r.status], reporting: currentlyReporting(r), caseCount: r.diseaseCaseCount },
    })),
  }
}

function recordInDistrict(record, districtName, districtFeature) {
  if (record?.location_status === 'VALID' && Number.isFinite(record.longitude) && Number.isFinite(record.latitude) && districtFeature) {
    return pointInGeometry(record.longitude, record.latitude, districtFeature)
  }
  return Boolean(districtName) && normalizeName(record?.district) === normalizeName(districtName)
}

/** Verified Cases mode: real reports in the authorised district. */
export function buildVerifiedCaseIntelligence({ roster = null, nationalRecords = [], districtName = null, districtFeature = null, disease = null } = {}) {
  const reports = []
  for (const row of roster?.rows ?? []) {
    if (row.outsideDistrict) continue // the vet's own farm elsewhere: listed, not a district report
    for (const c of row.cases) {
      if (disease && c.disease !== disease) continue
      reports.push({ ...c, farmId: row.farmId, farmLabel: row.label, coordinates: row.coordinates, personallyAssigned: row.personallyAssigned })
    }
  }
  reports.sort((a, b) => String(b.verificationTime ?? '').localeCompare(String(a.verificationTime ?? '')))
  const districtRecords = (Array.isArray(nationalRecords) ? nationalRecords : [])
    .filter((r) => (!disease || r?.disease === disease) && recordInDistrict(r, districtName, districtFeature))
  const pending = districtRecords.filter((r) => r.verification_status === 'PENDING_VERIFICATION')
    .map((r) => ({ recordKey: r.record_key, date: sriLankaDateKey(r.reported_at), reportedAt: r.reported_at, hasGps: r.location_status === 'VALID', coordinates: r.location_status === 'VALID' ? [r.longitude, r.latitude] : null, severity: r.clinical_summary?.severity ?? null, stage: r.clinical_summary?.stage ?? null }))
  const verifiedWithoutGps = districtRecords.filter((r) => r.verification_status === 'VERIFIED' && r.location_status !== 'VALID')
    .map((r) => ({ recordKey: r.record_key, date: sriLankaDateKey(r.verified_at ?? r.reported_at), severity: r.clinical_summary?.severity ?? null, stage: r.clinical_summary?.stage ?? null }))
  const byDate = new Map()
  for (const r of reports) if (r.date) byDate.set(r.date, { date: r.date, verified: (byDate.get(r.date)?.verified ?? 0) + 1, pending: byDate.get(r.date)?.pending ?? 0 })
  for (const p of pending) if (p.date) byDate.set(p.date, { date: p.date, verified: byDate.get(p.date)?.verified ?? 0, pending: (byDate.get(p.date)?.pending ?? 0) + 1 })
  const history = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  return {
    reports,
    reportCount: reports.length + verifiedWithoutGps.length,
    mappedReportCount: reports.length,
    uniqueFarmCount: new Set(reports.map((r) => r.farmId)).size,
    uniqueAnimalCount: null, // animal identifiers are not exposed by the operational API
    pending,
    verifiedWithoutGps,
    latestDate: reports[0]?.date ?? null,
    history,
  }
}

/** Timeline sources split by district containment and evidence domain. */
export function buildSourceBreakdown(timeline, districtFeature) {
  const directions = new Map((timeline?.source_directions ?? []).map((d) => [d.source_id, d]))
  const sources = (timeline?.sources ?? []).map((s) => {
    const inside = districtFeature ? pointInGeometry(s.longitude, s.latitude, districtFeature) : null
    const direction = directions.get(s.source_id)
    return {
      sourceId: s.source_id,
      recordDomain: s.record_domain,
      evidence: s.record_domain === 'OPERATIONAL' ? 'Vet-verified case (not an official outbreak confirmation)' : 'Historical research record',
      privacyReduced: s.detail_access === 'PRIVACY_REDUCED_EXTERNAL_FARM',
      farmId: typeof s.farm_id === 'string' ? s.farm_id : null,
      inside,
      observationDate: s.observation_date,
      memberCount: s.member_count,
      coordinates: [s.longitude, s.latitude],
      bearingDeg: Number.isFinite(direction?.bearing_deg) ? direction.bearing_deg : null,
    }
  })
  return {
    sources,
    inside: sources.filter((s) => s.inside === true).length,
    outside: sources.filter((s) => s.inside === false).length,
    operational: sources.filter((s) => s.recordDomain === 'OPERATIONAL').length,
    historical: sources.filter((s) => s.recordDomain === 'HISTORICAL').length,
    withDirection: sources.filter((s) => s.bearingDeg !== null).length,
  }
}

/** Static (as-of) tier areas of the scored land in scope, km². */
export function staticTierAreas(timeline) {
  const areas = Object.fromEntries(TIER_ORDER.map((t) => [t, 0]))
  for (const f of timeline?.risk_zones?.features ?? []) {
    if (TIER_ORDER.includes(f?.properties?.tier) && Number.isFinite(f.properties.area_km2)) areas[f.properties.tier] += f.properties.area_km2
  }
  return areas
}

/** One Future Risk Outlook row per backend frame -- the same frame the map
 * draws: scored land area within nominal reach (per tier), monitored farms
 * and eligible sources. No case or infection counts. */
export function buildOutlookRows(timeline, roster) {
  const farmsWithTier = (roster?.rows ?? []).filter((r) => r.coordinates && r.tier)
  const sourceCount = (timeline?.sources ?? []).length
  return timelineFrames(timeline).map((frame, index) => {
    const tierAreas = Object.fromEntries(TIER_ORDER.map((t) => [t, 0]))
    for (const f of frame?.reach_limited_risk_zones?.features ?? []) {
      if (TIER_ORDER.includes(f?.properties?.tier) && Number.isFinite(f.properties.area_km2)) tierAreas[f.properties.tier] += f.properties.area_km2
    }
    const scoredAreaKm2 = TIER_ORDER.reduce((sum, t) => sum + tierAreas[t], 0)
    const envelope = frame?.reach_envelope ?? null
    const monitoredFarms = envelope ? farmsWithTier.filter((r) => pointInGeometry(r.coordinates[0], r.coordinates[1], envelope)).length : 0
    const highestTier = [...TIER_ORDER].reverse().find((t) => tierAreas[t] > 0) ?? null
    return {
      index,
      day: frame.day,
      date: frame.date,
      horizonStatus: frame.horizon_status,
      exploratory: frame.horizon_status === HORIZON_STATUS.EXPLORATORY,
      reachKm: Number.isFinite(frame?.reach?.nominal_reach_km) ? frame.reach.nominal_reach_km : null,
      tierAreas,
      scoredAreaKm2,
      highestTier,
      monitoredFarms,
      sourceCount,
    }
  })
}

/**
 * Advisory veterinary actions. Each states why it is shown and its evidence
 * basis. None is an order: quarantine, movement control and vaccination are
 * only ever "consider / review with the veterinary authority", and never
 * triggered by the relative score or nominal reach alone.
 */
export function buildRecommendedActions({ caseIntel = null, roster = null, breakdown = null, modelReady = true, timelineOk = false, diseaseShortLabel = 'the disease', districtLabel = 'your district' } = {}) {
  const reports = caseIntel?.reportCount ?? 0
  const pending = caseIntel?.pending?.length ?? 0
  const noGps = (roster?.summary?.withoutGps ?? 0)
  const monitored = roster?.summary?.monitoredWithinReach ?? 0
  const inScored = roster?.summary?.inScoredArea ?? 0
  const outside = breakdown?.outside ?? 0
  return [
    {
      id: 'surveillance',
      title: 'Increase surveillance and monitoring',
      why: timelineOk
        ? `${inScored} registered farm${inScored === 1 ? '' : 's'} sit in the scored monitoring area (${monitored} within the selected day's nominal reach)${outside ? `; ${outside} eligible source${outside === 1 ? '' : 's'} lie outside ${districtLabel}` : ''}. Prioritise visits there.`
        : 'No scored monitoring area for the selected date; keep routine surveillance.',
      basis: timelineOk ? ACTION_BASIS.MODEL : ACTION_BASIS.GUIDANCE,
      active: timelineOk && inScored > 0,
    },
    {
      id: 'review-cases',
      title: 'Review verified and pending clinical cases',
      why: `${reports} verified and ${pending} pending ${diseaseShortLabel} report${reports + pending === 1 ? '' : 's'} recorded in ${districtLabel}.`,
      basis: ACTION_BASIS.REPORTS,
      active: reports + pending > 0,
    },
    {
      id: 'examine',
      title: 'Examine suspected animals; review isolation and biosecurity',
      why: reports > 0
        ? `Reporting farms in ${districtLabel} have verified ${diseaseShortLabel} diagnoses; check in-contact animals and on-farm biosecurity.`
        : `Standard response to any ${diseaseShortLabel}-compatible clinical signs.`,
      basis: reports > 0 ? ACTION_BASIS.REPORTS : ACTION_BASIS.GUIDANCE,
      active: reports > 0,
    },
    {
      id: 'movement',
      title: 'Consider movement-restriction or quarantine assessment',
      why: 'Only through the relevant veterinary authority (DAPH / provincial) and on clinical evidence. Not triggered by relative score or nominal reach.',
      basis: reports > 0 ? ACTION_BASIS.REPORTS : ACTION_BASIS.GUIDANCE,
      active: reports > 0,
    },
    {
      id: 'vaccination',
      title: 'Review vaccination eligibility',
      why: `Check ${diseaseShortLabel} vaccination status and eligibility against authorised veterinary guidance. No vaccination decision is derived from this map.`,
      basis: ACTION_BASIS.GUIDANCE,
      active: modelReady && (reports > 0 || inScored > 0),
    },
    {
      id: 'follow-up',
      title: 'Follow up farms lacking GPS or recent case information',
      why: noGps > 0
        ? `${noGps} registered farm${noGps === 1 ? ' has' : 's have'} no GPS on record and cannot be placed on the map or in any scored area.`
        : 'All listed farms have GPS; confirm recent clinical status at the next visit.',
      basis: ACTION_BASIS.REPORTS,
      active: noGps > 0,
    },
  ]
}
