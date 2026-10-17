/**
 * My Area farm intelligence: joins the vet's real assigned farms
 * (operational context), their real verified clinical cases, and the
 * backend Spatial Timeline geometry into one per-farm watchlist.
 *
 * Nothing here is scored or predicted. Every value is either a backend
 * field passed through, or a deterministic point-in-polygon test of a
 * farm's GPS against geometry the backend returned:
 *   - `tier`        -> the static C0 relative-tier zone (`risk_zones`) the
 *                      farm GPS falls in (snapshot-relative quartile, the
 *                      same on every day; never a probability).
 *   - `withinReach` -> whether the farm GPS falls inside the selected
 *                      day's nominal-reach outline (`frames[i].reach_envelope`,
 *                      a distance-only visualisation, never an infection
 *                      boundary).
 */

import { TIER_ORDER } from './spatialTimelineView'

function pointInRing(lon, lat, ring) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

function pointInPolygonRings(lon, lat, rings) {
  if (!Array.isArray(rings) || rings.length === 0 || !pointInRing(lon, lat, rings[0])) return false
  return !rings.slice(1).some((hole) => pointInRing(lon, lat, hole))
}

/** Point-in-polygon for a GeoJSON Polygon / MultiPolygon geometry (or a
 * Feature wrapping one). Returns false for anything else. */
export function pointInGeometry(lon, lat, geometryOrFeature) {
  const geometry = geometryOrFeature?.type === 'Feature' ? geometryOrFeature.geometry : geometryOrFeature
  if (!geometry || !Number.isFinite(lon) || !Number.isFinite(lat)) return false
  if (geometry.type === 'Polygon') return pointInPolygonRings(lon, lat, geometry.coordinates)
  if (geometry.type === 'MultiPolygon') return (geometry.coordinates ?? []).some((rings) => pointInPolygonRings(lon, lat, rings))
  return false
}

const TIER_LABEL_FALLBACK = Object.freeze({
  lower: 'Lower relative risk',
  moderate: 'Moderate relative risk',
  high: 'Elevated relative risk',
  highest: 'Highest relative risk',
})

export function tierLabel(tier, zones) {
  const fromBackend = (zones ?? []).find((f) => f?.properties?.tier === tier)?.properties?.label
  return fromBackend || TIER_LABEL_FALLBACK[tier] || null
}

/** The static relative tier at a point: the highest-ranked backend tier
 * zone containing it, or null when outside every scored zone. */
export function tierAtPoint(timeline, lon, lat) {
  const zones = timeline?.risk_zones?.features ?? []
  let best = null
  for (const zone of zones) {
    const tier = zone?.properties?.tier
    if (!TIER_ORDER.includes(tier) || !pointInGeometry(lon, lat, zone)) continue
    if (best === null || TIER_ORDER.indexOf(tier) > TIER_ORDER.indexOf(best)) best = tier
  }
  return best
}

/** Snapshot (as-of, static) summary for one district from the backend's
 * top-level `district_summaries`; null when the backend has none. */
export function districtSnapshotSummary(timeline, districtName) {
  if (!districtName) return null
  const wanted = String(districtName).trim().toLowerCase()
  const row = (timeline?.district_summaries ?? []).find((s) => String(s?.district ?? '').trim().toLowerCase() === wanted)
  if (!row) return null
  // The backend `max_tier` counts cells whose CENTROID is in the district. A
  // district reached only at its edge (scored land inside, no centroid) has
  // max_tier null but a real `tier_area_km2` -- use the highest tier with
  // scored area there instead of reporting nothing.
  const centroidTier = TIER_ORDER.includes(row.max_tier) ? row.max_tier : null
  const areaTier = centroidTier ? null : [...TIER_ORDER].reverse().find((tier) => Number(row.tier_area_km2?.[tier]) > 0) ?? null
  const maxTier = centroidTier ?? areaTier
  return {
    maxTier,
    maxTierFromEdgeArea: Boolean(areaTier),
    maxTierLabel: tierLabel(maxTier, timeline?.risk_zones?.features),
    districtAreaKm2: Number.isFinite(row.district_area_km2) ? row.district_area_km2 : null,
    scoredAreaKm2: Number.isFinite(row.scored_area_km2) ? row.scored_area_km2 : null,
    sourcesInDistrict: Number.isFinite(row.n_sources_in_district) ? row.n_sources_in_district : null,
    asOf: timeline?.as_of ?? null,
  }
}

const DISEASE_LABEL = Object.freeze({ LSD: 'LSD', FMD: 'FMD' })

/**
 * One row per assigned farm, ordered by what a vet would check first:
 * a verified case of the selected disease, then the highest static tier
 * at the farm, then inside the selected day's reach outline.
 */
export function buildFarmWatchlist({ farms = [], clinicalContexts = [], timeline = null, frameIndex = 0, farmNames = null, disease = null }) {
  const frame = Array.isArray(timeline?.frames) ? timeline.frames[frameIndex] ?? null : null
  const envelope = frame?.reach_envelope ?? null
  const zones = timeline?.risk_zones?.features ?? []
  const rows = farms.map((farm) => {
    const hasGps = farm.locationStatus === 'VALID' && Number.isFinite(farm.latitude) && Number.isFinite(farm.longitude)
    const cases = clinicalContexts
      .filter((c) => c.farmId === farm.farmId)
      .map((c) => ({ caseId: c.caseId, disease: DISEASE_LABEL[c.disease] ?? c.disease, verificationTime: c.verificationTime }))
      .sort((a, b) => String(b.verificationTime ?? '').localeCompare(String(a.verificationTime ?? '')))
    const tier = hasGps && timeline ? tierAtPoint(timeline, farm.longitude, farm.latitude) : null
    const withinReach = hasGps && envelope ? pointInGeometry(farm.longitude, farm.latitude, envelope) : false
    const selectedDiseaseCases = disease ? cases.filter((c) => c.disease === disease) : cases
    return {
      farmId: farm.farmId,
      name: farmNames?.get(farm.farmId)?.name ?? null,
      district: farm.locationDistrict ?? farmNames?.get(farm.farmId)?.district ?? null,
      hasGps,
      latitude: hasGps ? farm.latitude : null,
      longitude: hasGps ? farm.longitude : null,
      cases,
      selectedDiseaseCaseCount: selectedDiseaseCases.length,
      tier,
      tierLabel: tier ? tierLabel(tier, zones) : null,
      withinReach,
      reachDay: frame?.day ?? null,
    }
  })
  const rank = (row) => [
    row.selectedDiseaseCaseCount > 0 ? 0 : 1,
    row.tier ? TIER_ORDER.length - TIER_ORDER.indexOf(row.tier) : TIER_ORDER.length + 1,
    row.withinReach ? 0 : 1,
    row.hasGps ? 0 : 1,
  ]
  return rows.sort((a, b) => {
    const ra = rank(a)
    const rb = rank(b)
    for (let i = 0; i < ra.length; i += 1) if (ra[i] !== rb[i]) return ra[i] - rb[i]
    return String(a.name ?? a.farmId).localeCompare(String(b.name ?? b.farmId))
  })
}

/**
 * Non-prescriptive follow-up prompts, each tied to a fact on screen.
 * Never an order: no quarantine, vaccination or movement instruction.
 */
export function buildFollowUpItems({ watchlist = [], diseaseShortLabel = 'the selected disease', districtLabel = 'your district', modelReady = true }) {
  const items = []
  const withCases = watchlist.filter((r) => r.selectedDiseaseCaseCount > 0)
  const highTierNoCase = watchlist.filter((r) => r.selectedDiseaseCaseCount === 0 && (r.tier === 'highest' || r.tier === 'high'))
  const noGps = watchlist.filter((r) => !r.hasGps)
  if (withCases.length > 0) {
    items.push({
      id: 'review-cases',
      text: `Review the ${withCases.length === 1 ? 'verified case record' : `${withCases.length} farms' verified case records`} for ${diseaseShortLabel} in Clinical Records (history, lesions, herd details).`,
      link: '/vet/clinical-records',
    })
  }
  if (highTierNoCase.length > 0) {
    items.push({
      id: 'check-nearby',
      text: `${highTierNoCase.length} assigned farm${highTierNoCase.length === 1 ? ' sits' : 's sit'} in a higher relative-score zone without a verified case: consider a check of recent reports or a visit when planning rounds.`,
    })
  }
  if (withCases.length > 0 || highTierNoCase.length > 0) {
    items.push({ id: 'monitor', text: `Watch for new ${diseaseShortLabel}-compatible signs on nearby farms and report suspected cases through Smart Diagnostics so they can be verified.`, link: '/vet/diagnostics' })
  }
  if (noGps.length > 0) {
    items.push({ id: 'gps', text: `${noGps.length} assigned farm${noGps.length === 1 ? ' has' : 's have'} no GPS on record, so ${noGps.length === 1 ? 'it is' : 'they are'} not placed on the map or in any zone. Ask the farm to update its location.` })
  }
  if (!modelReady) {
    items.push({ id: 'model', text: `No validated spatial model exists for ${diseaseShortLabel}; rely on verified cases and your own clinical judgement.` })
  }
  items.push({ id: 'protocol', text: `Any investigation or escalation follows the applicable DAPH / provincial reporting procedures for ${districtLabel}. This page does not issue control measures.` })
  return items
}
