/**
 * Analysis & Trends (current surveillance) over the real ADRS case reports
 * the vet may see (`GET /national-cases`: vet-verified + pending, privacy-
 * reduced) and the runtime ST-DBSCAN clusters (`GET /st-clusters`).
 *
 * - A record's district: its farm GPS inside the real ADM2 polygon when the
 *   GPS is valid, otherwise the farm's registered district name.
 * - Dates: the report date (`reported_at`) as an Asia/Colombo calendar day.
 * - "Current" = the selected window of W days ending today; "previous" = the
 *   W days just before it (same length), for the change column.
 * - "My district" scope: the vet's authenticated district only; nearby
 *   districts are those with a current record within the model's district
 *   influence range of the district boundary.
 * Nothing is modelled here except where the forecast horizon is read from
 * the backend spatial timeline.
 */
import { districtNameAtPoint, normalizeDistrictDisplayName } from './districtGeometry'
import { sriLankaDateKey } from './verificationTime'

const DAY_MS = 24 * 60 * 60 * 1000
const KM_PER_DEG_LAT = 110.574
const kmPerDegLon = (lat) => 111.32 * Math.cos((lat * Math.PI) / 180)

export function windowKeys(windowDays, nowMs = Date.now()) {
  const key = (offset) => sriLankaDateKey(new Date(nowMs - offset * DAY_MS))
  return {
    endKey: key(0),
    startKey: key(windowDays - 1),
    previousEndKey: key(windowDays),
    previousStartKey: key(2 * windowDays - 1),
    days: Array.from({ length: windowDays }, (_, i) => key(windowDays - 1 - i)),
  }
}

const hasGps = (r) => r?.location_status === 'VALID' && Number.isFinite(r.longitude) && Number.isFinite(r.latitude)

/** District of a record: GPS-in-polygon first, else the registered name. */
export function recordDistrict(record, districtCollection = null) {
  if (hasGps(record) && districtCollection) {
    const byGps = districtNameAtPoint(districtCollection, [record.longitude, record.latitude])
    if (byGps) return byGps
  }
  return normalizeDistrictDisplayName(record?.district) ?? null
}

/** Records of one disease with their resolved district and report day. */
export function prepareRecords(records, disease, districtCollection = null) {
  if (!disease) return []
  return (Array.isArray(records) ? records : [])
    .filter((r) => r?.disease === disease)
    .map((r) => ({ ...r, districtName: recordDistrict(r, districtCollection), dayKey: sriLankaDateKey(r.reported_at) }))
}

const sameDistrict = (a, b) => Boolean(a && b) && a.trim().toLowerCase() === b.trim().toLowerCase()
const isVerified = (r) => r.verification_status === 'VERIFIED'
const inRange = (r, start, end) => Boolean(r.dayKey) && r.dayKey >= start && r.dayKey <= end

export function scopeRecords(prepared, { scope = 'district', districtName = null } = {}) {
  if (scope === 'national') return prepared
  return districtName ? prepared.filter((r) => sameDistrict(r.districtName, districtName)) : []
}

/** KPI figures for the scoped records in the current window. */
export function summarizeWindow(scoped, { windowDays, nowMs = Date.now(), scope = 'district' } = {}) {
  const k = windowKeys(windowDays, nowMs)
  const current = scoped.filter((r) => inRange(r, k.startKey, k.endKey))
  const previous = scoped.filter((r) => inRange(r, k.previousStartKey, k.previousEndKey))
  // District scope: distinct farm locations (GPS) with a current report;
  // national scope: distinct districts with a current report.
  const locations = new Set(current.filter(hasGps).map((r) => `${r.latitude.toFixed(5)},${r.longitude.toFixed(5)}`))
  const districts = new Set(current.map((r) => r.districtName).filter(Boolean))
  const dated = scoped.filter((r) => r.dayKey && r.dayKey <= k.endKey).map((r) => r.dayKey).sort()
  return {
    ...k,
    current: current.length,
    verified: current.filter(isVerified).length,
    pending: current.filter((r) => !isVerified(r)).length,
    previous: previous.length,
    affectedAreas: scope === 'national' ? districts.size : locations.size,
    withoutGps: current.filter((r) => !hasGps(r)).length,
    withoutDistrict: current.filter((r) => !r.districtName).length,
    allDates: scoped.length,
    latestReportKey: dated.length ? dated[dated.length - 1] : null,
    dateUnknown: scoped.filter((r) => !r.dayKey).length,
  }
}

/** Verified and pending reports per day of the window (a day without
 * reports is a real 0). */
export function buildDailyActivity(scoped, { windowDays, nowMs = Date.now() } = {}) {
  const { days } = windowKeys(windowDays, nowMs)
  const byDay = new Map(days.map((d) => [d, { date: d, verified: 0, pending: 0 }]))
  for (const r of scoped) {
    const bucket = byDay.get(r.dayKey)
    if (!bucket) continue
    if (isVerified(r)) bucket.verified += 1
    else bucket.pending += 1
  }
  return days.map((d) => byDay.get(d))
}

function pointToSegmentKm(px, py, ax, ay, bx, by) {
  const dx = bx - ax
  const dy = by - ay
  const t = dx || dy ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy))) : 0
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}

/** Distance (km) from a point to a district polygon boundary; 0 inside. */
export function distanceToDistrictKm(feature, lon, lat) {
  const geometry = feature?.geometry
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : []
  if (!polygons.length) return null
  if (districtNameAtPoint({ features: [feature] }, [lon, lat]) !== null) return 0
  const kx = kmPerDegLon(lat)
  let best = Infinity
  for (const rings of polygons) {
    for (const ring of rings) {
      for (let i = 0; i < ring.length - 1; i += 1) {
        const d = pointToSegmentKm(lon * kx, lat * KM_PER_DEG_LAT, ring[i][0] * kx, ring[i][1] * KM_PER_DEG_LAT, ring[i + 1][0] * kx, ring[i + 1][1] * KM_PER_DEG_LAT)
        if (d < best) best = d
      }
    }
  }
  return best
}

/**
 * Most affected districts in the current window, with the change against
 * the previous window. National scope: every district with a current
 * record. District scope: the vet's district plus the districts with a
 * current record within `nearbyKm` of its boundary. The vet's district is
 * always shown (also with 0) and flagged `mine`.
 */
export function buildAffectedAreas(prepared, { windowDays, nowMs = Date.now(), scope = 'district', districtName = null, districtFeature = null, nearbyKm = null, topN = 10 } = {}) {
  const k = windowKeys(windowDays, nowMs)
  const rows = new Map()
  const rowFor = (name) => {
    if (!rows.has(name)) rows.set(name, { district: name, records: 0, verified: 0, pending: 0, lastObserved: null, previous: 0, mine: sameDistrict(name, districtName), nearestKm: null })
    return rows.get(name)
  }
  for (const r of prepared) {
    if (!r.districtName) continue
    if (inRange(r, k.startKey, k.endKey)) {
      const row = rowFor(r.districtName)
      row.records += 1
      if (isVerified(r)) row.verified += 1
      else row.pending += 1
      if (!row.lastObserved || r.dayKey > row.lastObserved) row.lastObserved = r.dayKey
      if (scope === 'district' && districtFeature && hasGps(r) && !row.mine) {
        const km = distanceToDistrictKm(districtFeature, r.longitude, r.latitude)
        if (km !== null && (row.nearestKm === null || km < row.nearestKm)) row.nearestKm = km
      }
    } else if (inRange(r, k.previousStartKey, k.previousEndKey)) {
      rowFor(r.districtName).previous += 1
    }
  }
  if (districtName) rowFor(normalizeDistrictDisplayName(districtName) ?? districtName)
  let list = [...rows.values()].filter((row) => row.records > 0 || row.mine)
  if (scope === 'district') list = list.filter((row) => row.mine || (Number.isFinite(nearbyKm) && row.nearestKm !== null && row.nearestKm <= nearbyKm))
  list = list.map((row) => ({ ...row, delta: row.records - row.previous }))
  list.sort((a, b) => b.records - a.records || String(b.lastObserved ?? '').localeCompare(String(a.lastObserved ?? '')) || a.district.localeCompare(b.district))
  const top = list.slice(0, topN)
  const mine = list.find((row) => row.mine)
  if (mine && !top.includes(mine)) top.push(mine) // the vet's district is never cut off
  return top
}

/** ST-DBSCAN clusters as table rows (C1 = largest). District scope keeps
 * clusters with at least one member inside the vet's district. */
export function buildClusterRows(stClusters, { districtCollection = null, districtFeature = null, scope = 'district' } = {}) {
  const clusters = Array.isArray(stClusters?.clusters) ? stClusters.clusters : []
  const rows = clusters.map((c) => {
    const members = (c.member_locations ?? []).filter((p) => Number.isFinite(p?.longitude) && Number.isFinite(p?.latitude))
    const districts = [...new Set(members.map((p) => (districtCollection ? districtNameAtPoint(districtCollection, [p.longitude, p.latitude]) : null)).filter(Boolean))].sort()
    const touchesMine = districtFeature ? members.some((p) => districtNameAtPoint({ features: [districtFeature] }, [p.longitude, p.latitude]) !== null) : false
    return {
      clusterId: c.cluster_id,
      cases: c.member_count,
      farms: c.distinct_farm_or_support_count ?? null,
      districts,
      radiusKm: Number.isFinite(c.radius_km) ? c.radius_km : null,
      driftKm: c.drift?.supported && Number.isFinite(c.drift.km) ? c.drift.km : null,
      bearingDeg: c.drift?.supported && Number.isFinite(c.drift.bearing_deg) ? c.drift.bearing_deg : null,
      startDate: c.start_date ?? null,
      endDate: c.end_date ?? null,
      touchesMine,
    }
  })
  rows.sort((a, b) => b.cases - a.cases || String(a.startDate).localeCompare(String(b.startDate)))
  const labelled = rows.map((row, i) => ({ ...row, label: `C${i + 1}` }))
  return scope === 'national' ? labelled : labelled.filter((row) => row.touchesMine)
}

/** Forecast horizon from the backend spatial timeline (same scope). */
export function forecastHorizon(timeline) {
  const frames = Array.isArray(timeline?.frames) ? timeline.frames : []
  if (!frames.length || timeline?.status === 'MODEL_NOT_READY') return null
  return {
    from: frames[0].date,
    to: frames[frames.length - 1].date,
    lastDay: frames[frames.length - 1].day,
    sources: Array.isArray(timeline.sources) ? timeline.sources.length : 0,
    relevanceKm: timeline.source_selection?.district_relevance_distance_km ?? null,
  }
}
