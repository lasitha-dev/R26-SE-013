import { isPointInPolygonRing } from './geo'
import { isPointInsideDistrictFeature } from './districtGeometry'
import { buildReachRingFeatureCollectionForCenters } from '../components/nominalReachRing'

function validCoordinatePair(longitude, latitude) {
  return (
    typeof longitude === 'number' &&
    Number.isFinite(longitude) &&
    longitude >= -180 &&
    longitude <= 180 &&
    typeof latitude === 'number' &&
    Number.isFinite(latitude) &&
    latitude >= -90 &&
    latitude <= 90
  )
}

/**
 * Creates observed-case markers only when the case record itself carries
 * an explicit valid coordinate. The authorized farm coordinate is never
 * substituted as a case coordinate.
 */
export function buildObservedCaseFeatures(clinicalContexts) {
  const features = []
  for (const clinical of Array.isArray(clinicalContexts) ? clinicalContexts : []) {
    if (!validCoordinatePair(clinical?.longitude, clinical?.latitude)) continue
    features.push({
      type: 'Feature',
      id: clinical.caseId,
      geometry: { type: 'Point', coordinates: [clinical.longitude, clinical.latitude] },
      properties: {
        caseId: clinical.caseId,
        farmId: clinical.farmId,
        disease: clinical.disease,
        semanticClass: clinical.semanticClass,
        verificationTime: clinical.verificationTime,
        locationDistrict: clinical.locationDistrict,
        personallyAssigned: clinical.personallyAssigned,
      },
    })
  }
  return features
}

/** District scoping is presentation-only containment over real points and
 * the real ADM2 geometry. It does not change or recompute a risk value. */
export function scopePointFeaturesToDistrict(features, districtFeature) {
  if (!districtFeature) return []
  return (Array.isArray(features) ? features : []).filter((feature) =>
    isPointInsideDistrictFeature(feature?.geometry?.coordinates, districtFeature),
  )
}

/**
 * Highlights the portion of a static risk surface that lies inside the
 * currently displayed source-centered nominal-reach polygons. The ring
 * geometry is the existing visualization-only geometry; no risk score,
 * reach value, missing day, or epidemiological threshold is computed.
 */
export function scopeRiskCellsToNominalReach(cellFeatures, centers, nominalReachKm) {
  if (!(nominalReachKm > 0) || !Array.isArray(centers) || centers.length === 0) return []
  const reachPolygons = buildReachRingFeatureCollectionForCenters(centers, nominalReachKm).features
  return (Array.isArray(cellFeatures) ? cellFeatures : []).filter((cell) => {
    const point = cell?.geometry?.coordinates
    if (!Array.isArray(point) || point.length !== 2) return false
    return reachPolygons.some((polygon) => {
      const ring = polygon?.geometry?.coordinates?.[0]
      return Array.isArray(ring) && isPointInPolygonRing(point, ring)
    })
  })
}
