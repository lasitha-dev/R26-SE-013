/**
 * My Area map presentation rules (pure, no MapLibre): which layers each
 * Future Impact view shows, the subtle wash outside the vet's district, the
 * selected-case emphasis and the case popup rows. Nothing here computes a
 * risk value or touches the Future Impact model; it only decides what is drawn.
 */

// Future Impact views, the same three as the Outbreak Map's modes.
export const IMPACT_LAYER = Object.freeze({ CASES: 'CASES', RISK: 'RISK', TRAJECTORY: 'TRAJECTORY' })
export const IMPACT_LAYER_LABEL = Object.freeze({ CASES: 'Cases', RISK: 'Risk Zones', TRAJECTORY: 'Trajectory' })

/** What the map draws for a mode (`showImpact` = Future Impact, else Verified
 * Cases) and a Future Impact view. */
export function impactLayerVisibility(showImpact, layer) {
  return {
    riskSurface: Boolean(showImpact) && layer === IMPACT_LAYER.RISK,
    trajectory: Boolean(showImpact) && layer === IMPACT_LAYER.TRAJECTORY,
    modelSources: Boolean(showImpact),
    verifiedCases: !showImpact || layer === IMPACT_LAYER.CASES,
  }
}

/** World polygon with the district cut out (one hole per district part):
 * the subtle wash outside My Area. Presentation only -- records from other
 * districts are never sent to this page. */
export function outsideDistrictMask(districtFeature) {
  const geometry = districtFeature?.geometry
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : []
  const holes = polygons.map((polygon) => polygon?.[0]).filter((ring) => Array.isArray(ring) && ring.length >= 4)
  if (!holes.length) return { type: 'FeatureCollection', features: [] }
  const world = [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]
  return { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [world, ...holes] } }] }
}

/** Paint for the verified-case markers: a selected case stays clear and only
 * it keeps pulsing; every other marker fades (never hidden). */
export function caseFocusStyle(focusedCaseId) {
  const recent = ['==', ['get', 'ageClass'], 'RECENT']
  if (!focusedCaseId) return { coreOpacity: 0.98, strokeOpacity: 1, pulseFilter: recent }
  const isFocus = ['==', ['get', 'anchorId'], focusedCaseId]
  return { coreOpacity: ['case', isFocus, 0.98, 0.3], strokeOpacity: ['case', isFocus, 1, 0.3], pulseFilter: ['all', recent, isFocus] }
}

/** Case popup rows -- real record fields only, nothing inferred. */
export function caseDetailRows(properties = {}, districtName = null) {
  const age = { RECENT: 'reported 0–14 days ago', OLDER: 'reported 15–30 days ago' }[properties.ageClass] ?? null
  return [
    ['Verified case', properties.caseId],
    ['Disease', properties.disease],
    ['Reported', properties.reportedAt ? `${String(properties.reportedAt).slice(0, 10)}${age ? ` (${age})` : ''}` : null],
    ['Verified', properties.verificationTime ? String(properties.verificationTime).slice(0, 16).replace('T', ' ') : null],
    ['District', properties.locationDistrict ?? districtName ?? null],
    ['Farm', properties.farmId ? `${properties.farmId}${properties.personallyAssigned ? ' (assigned to you)' : ''}` : null],
    ['Status', 'Vet-verified diagnosis (not an official outbreak confirmation)'],
  ].filter(([, value]) => value)
}
