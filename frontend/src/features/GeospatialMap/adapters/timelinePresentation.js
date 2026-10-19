/**
 * Display-only constants and the real-case normaliser shared by the live
 * National Map and My Area pages. Kept apart from the legacy scripted
 * presentation modules (`page1ForecastVisualization.js`,
 * `myAreaPresentationForecast.js`) so that importing a colour or a playback
 * interval never pulls those modules' fixed date/risk arrays into the
 * production bundle. Every timeline value on screen comes from the backend
 * spatial-timeline snapshot (`spatialTimelineView.js`), never from here.
 */

export const PLAYBACK_INTERVAL_MS = Object.freeze({ 0.5: 2200, 1: 1100, 2: 550 })
export const PAGE1_PLAYBACK_INTERVAL_MS = PLAYBACK_INTERVAL_MS
export const AREA_PLAYBACK_INTERVAL_MS = PLAYBACK_INTERVAL_MS

// Values are the literal `riskLevel` strings MapLibre's paint `match`
// expression keys on (`mapLibreAdapter.js`'s `page1Risk*Expression`
// builders) -- keeping the existing `PAGE1_RISK_TIER.OUTER/MODERATE/
// ELEVATED/HIGHEST` accessor names (so `PageLegend.jsx` needs no change)
// while their VALUES are now the color name itself, never an internal
// tier id a paint expression would have to translate.
export const PAGE1_RISK_TIER = Object.freeze({
  OUTER: 'green',
  MODERATE: 'yellow',
  ELEVATED: 'orange',
  HIGHEST: 'red',
})

export const PAGE1_RISK_COLORS = Object.freeze({
  [PAGE1_RISK_TIER.OUTER]: '#22C55E',
  [PAGE1_RISK_TIER.MODERATE]: '#FACC15',
  [PAGE1_RISK_TIER.ELEVATED]: '#F97316',
  [PAGE1_RISK_TIER.HIGHEST]: '#EF4444',
})

export const AREA_RISK_COLORS = Object.freeze({
  green: '#22C55E',
  yellow: '#FACC15',
  orange: '#F97316',
  red: '#EF4444',
  purple: '#A855F7',
  purpleAccent: '#C084FC',
})

export function validCoordinate(coordinate) {
  return (
    Array.isArray(coordinate) &&
    coordinate.length === 2 &&
    coordinate.every(Number.isFinite) &&
    coordinate[0] >= -180 &&
    coordinate[0] <= 180 &&
    coordinate[1] >= -90 &&
    coordinate[1] <= 90
  )
}

export function areaCaseIdentity(feature) {
  const properties = feature?.properties ?? {}
  const explicit = properties.caseId ?? properties.sourceId ?? properties.source_id ?? properties.outbreakId ?? properties.outbreak_id ?? feature?.id
  if (explicit !== null && explicit !== undefined && String(explicit).trim()) return String(explicit)
  const coordinate = feature?.geometry?.coordinates
  return validCoordinate(coordinate) ? `${coordinate[1]}:${coordinate[0]}` : null
}

/** Keeps the caller's real case coordinate unchanged and drops malformed
 * input instead of repairing or substituting a district/farm centroid. */
export function normalizeRealAreaCaseFeatures(caseFeatures) {
  const byIdentity = new Map()
  for (const feature of Array.isArray(caseFeatures) ? caseFeatures : []) {
    if (feature?.geometry?.type !== 'Point' || !validCoordinate(feature.geometry.coordinates)) continue
    const identity = areaCaseIdentity(feature)
    if (!identity || byIdentity.has(identity)) continue
    byIdentity.set(identity, {
      ...feature,
      id: feature.id ?? identity,
      geometry: { type: 'Point', coordinates: [...feature.geometry.coordinates] },
      properties: { ...(feature.properties ?? {}), anchorId: identity },
    })
  }
  return [...byIdentity.values()].sort((a, b) => areaCaseIdentity(a).localeCompare(areaCaseIdentity(b)))
}
