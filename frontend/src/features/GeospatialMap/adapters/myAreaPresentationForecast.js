import { computeFeatureBounds } from './districtGeometry'

export const AREA_FORECAST_DATES = Object.freeze([
  '2026-09-01',
  '2026-09-02',
  '2026-09-03',
  '2026-09-04',
  '2026-09-05',
  '2026-09-06',
  '2026-09-07',
  '2026-09-08',
  '2026-09-09',
  '2026-09-10',
  '2026-09-11',
  '2026-09-12',
  '2026-09-13',
  '2026-09-14',
])

export const AREA_SPREAD_PROGRESS = Object.freeze([
  0.02, 0.08, 0.15, 0.23, 0.32, 0.42, 0.53,
  0.64, 0.74, 0.83, 0.9, 0.95, 0.98, 1,
])

export const AREA_DISTRICT_RISK_LEVELS = Object.freeze([
  'low',
  'low',
  'moderate',
  'moderate',
  'elevated',
  'elevated',
  'high',
  'high',
  'high',
  'high',
  'elevated',
  'elevated',
  'moderate',
  'moderate',
])

export const AREA_RISK_COLORS = Object.freeze({
  green: '#22C55E',
  yellow: '#FACC15',
  orange: '#F97316',
  red: '#EF4444',
  purple: '#A855F7',
  purpleAccent: '#C084FC',
})

export const AREA_PLAYBACK_INTERVAL_MS = Object.freeze({
  0.5: 2200,
  1: 1100,
  2: 550,
})

export const AREA_FORECAST_OUTLOOK = Object.freeze(
  AREA_FORECAST_DATES.map((date, index) => Object.freeze({
    index,
    date,
    riskLevel: AREA_DISTRICT_RISK_LEVELS[index],
  })),
)

const EMPTY_COLLECTION = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })
const EARTH_RADIUS_KM = 6371.0088
const RISK_TIERS = Object.freeze([
  { riskLevel: 'green', majorScale: 1, minorScale: 0.48 },
  { riskLevel: 'yellow', majorScale: 0.74, minorScale: 0.37 },
  { riskLevel: 'orange', majorScale: 0.52, minorScale: 0.28 },
  { riskLevel: 'red', majorScale: 0.34, minorScale: 0.21 },
])

function toRadians(value) {
  return (value * Math.PI) / 180
}

function toDegrees(value) {
  return (value * 180) / Math.PI
}

function normalizeLongitude(longitude) {
  return ((longitude + 540) % 360) - 180
}

function validCoordinate(coordinate) {
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

export function clampAreaForecastIndex(index) {
  return Math.max(0, Math.min(AREA_FORECAST_DATES.length - 1, Number.isInteger(index) ? index : 0))
}

export function advanceAreaForecastIndex(index) {
  const current = clampAreaForecastIndex(index)
  const finalIndex = AREA_FORECAST_DATES.length - 1
  if (current >= finalIndex) return { index: finalIndex, complete: true }
  const next = current + 1
  return { index: next, complete: next === finalIndex }
}

export function stableAreaCaseHash(value) {
  const input = String(value ?? '')
  let hash = 2166136261
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
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

export function destinationAreaPoint([longitude, latitude], bearingDegrees, distanceKm) {
  if (!(distanceKm > 0)) return [longitude, latitude]
  const angularDistance = distanceKm / EARTH_RADIUS_KM
  const bearing = toRadians(bearingDegrees)
  const latitude1 = toRadians(latitude)
  const longitude1 = toRadians(longitude)
  const latitude2 = Math.asin(
    Math.sin(latitude1) * Math.cos(angularDistance) +
      Math.cos(latitude1) * Math.sin(angularDistance) * Math.cos(bearing),
  )
  const longitude2 = longitude1 + Math.atan2(
    Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude1),
    Math.cos(angularDistance) - Math.sin(latitude1) * Math.sin(latitude2),
  )
  return [normalizeLongitude(toDegrees(longitude2)), toDegrees(latitude2)]
}

export function areaDistanceKm(a, b) {
  if (!validCoordinate(a) || !validCoordinate(b)) return Number.POSITIVE_INFINITY
  const latitude1 = toRadians(a[1])
  const latitude2 = toRadians(b[1])
  const deltaLatitude = latitude2 - latitude1
  const deltaLongitude = toRadians(b[0] - a[0])
  const angularTerm = Math.sin(deltaLatitude / 2) ** 2 + Math.cos(latitude1) * Math.cos(latitude2) * Math.sin(deltaLongitude / 2) ** 2
  return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(angularTerm), Math.sqrt(1 - angularTerm))
}

function bearingBetween(a, b) {
  const latitude1 = toRadians(a[1])
  const latitude2 = toRadians(b[1])
  const deltaLongitude = toRadians(b[0] - a[0])
  const y = Math.sin(deltaLongitude) * Math.cos(latitude2)
  const x = Math.cos(latitude1) * Math.sin(latitude2) - Math.sin(latitude1) * Math.cos(latitude2) * Math.cos(deltaLongitude)
  return (toDegrees(Math.atan2(y, x)) + 360) % 360
}

function midpoint(a, b, fraction = 0.5) {
  return [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction]
}

function districtCenter(districtFeature, anchors) {
  const bounds = districtFeature ? computeFeatureBounds(districtFeature) : null
  if (bounds) return midpoint(bounds[0], bounds[1])
  if (anchors.length === 0) return null
  const sum = anchors.reduce((result, feature) => [
    result[0] + feature.geometry.coordinates[0],
    result[1] + feature.geometry.coordinates[1],
  ], [0, 0])
  return [sum[0] / anchors.length, sum[1] / anchors.length]
}

function caseProjectionParameters(feature, targetCenter) {
  const identity = areaCaseIdentity(feature)
  const hash = stableAreaCaseHash(identity)
  const origin = feature.geometry.coordinates
  const centerBearing = targetCenter && areaDistanceKm(origin, targetCenter) > 0.3
    ? bearingBetween(origin, targetCenter)
    : hash % 360
  return {
    identity,
    bearing: (centerBearing + ((hash >>> 7) % 45) - 22 + 360) % 360,
    curveDegrees: ((hash >>> 14) % 31) - 15,
    maximumReachKm: 8 + ((hash >>> 20) % 81) / 10,
  }
}

function buildCurvedPath(origin, { bearing, curveDegrees, maximumReachKm }, progress) {
  const pointCount = 24
  const coordinates = []
  for (let step = 0; step <= pointCount; step += 1) {
    const fraction = step / pointCount
    const localBearing = bearing + Math.sin(Math.PI * fraction) * curveDegrees
    coordinates.push(destinationAreaPoint(origin, localBearing, maximumReachKm * progress * fraction))
  }
  return coordinates
}

function buildEllipseRing(center, bearing, majorRadiusKm, minorRadiusKm, pointCount = 64) {
  const ring = []
  for (let step = 0; step < pointCount; step += 1) {
    const angle = (step / pointCount) * Math.PI * 2
    const alongKm = majorRadiusKm * Math.cos(angle)
    const acrossKm = minorRadiusKm * Math.sin(angle)
    const radiusKm = Math.sqrt(alongKm ** 2 + acrossKm ** 2)
    const offsetBearing = bearing + toDegrees(Math.atan2(acrossKm, alongKm))
    ring.push(destinationAreaPoint(center, offsetBearing, radiusKm))
  }
  ring.push([...ring[0]])
  return ring
}

function tierOpacity(riskLevel, activeIndex) {
  if (riskLevel === 'green') return activeIndex >= 11 ? 0.1 : 0.13
  if (riskLevel === 'yellow') return activeIndex >= 1 ? (activeIndex >= 12 ? 0.16 : 0.2) : 0
  if (riskLevel === 'orange') return activeIndex >= 3 ? (activeIndex >= 12 ? 0.13 : 0.25) : 0
  if (riskLevel === 'red') return activeIndex >= 6 && activeIndex <= 11 ? (activeIndex === 11 ? 0.14 : 0.31) : 0
  return 0
}

function makeRiskFeature({ center, bearing, majorRadiusKm, tier, anchorId, date, overlap = false, secondaryAnchorId = null }) {
  const fillOpacity = tierOpacity(tier.riskLevel, AREA_FORECAST_DATES.indexOf(date))
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [buildEllipseRing(center, bearing, majorRadiusKm * tier.majorScale, majorRadiusKm * tier.minorScale)],
    },
    properties: {
      anchorId,
      secondaryAnchorId,
      riskLevel: tier.riskLevel,
      fillOpacity,
      lineOpacity: Math.min(0.72, fillOpacity * 2.2),
      date,
      overlap,
      presentationOnly: true,
    },
  }
}

export function classifyAreaRiskOverlap({ distanceKm, combinedReachKm, activeIndex }) {
  const index = clampAreaForecastIndex(activeIndex)
  if (!(combinedReachKm > 0) || !(distanceKm <= combinedReachKm * 1.08) || index < 2) return null
  const districtRisk = AREA_DISTRICT_RISK_LEVELS[index]
  const strongIntersection = distanceKm <= combinedReachKm * 0.82
  if (districtRisk === 'high') return strongIntersection ? 'red' : 'orange'
  if (districtRisk === 'elevated') return strongIntersection ? 'orange' : 'yellow'
  if (districtRisk === 'moderate') return strongIntersection ? 'yellow' : 'green'
  return 'green'
}

export function areaInfluenceStatus(activeIndex, overlaps = false) {
  const index = clampAreaForecastIndex(activeIndex)
  if (index <= 2) return 'APPROACHING AREA'
  if (index <= 5) return 'PROJECTED PATH APPROACHING'
  if (index <= 8) return 'PROJECTED PATH AFFECTS AREA'
  if (index <= 10 && overlaps) return 'OVERLAPPING AREA INFLUENCE'
  if (index <= 10) return 'PROJECTED PATH AFFECTS AREA'
  return 'PROJECTED IMPACT STABILIZING'
}

function influenceDescription(status) {
  if (status === 'APPROACHING AREA') return 'Projected spread remains close to this real verified source in the early frames.'
  if (status === 'PROJECTED PATH APPROACHING') return 'The projected spread corridor is approaching the Matara impact area.'
  if (status === 'OVERLAPPING AREA INFLUENCE') return 'This projected corridor overlaps another local influence during the peak frames.'
  if (status === 'PROJECTED IMPACT STABILIZING') return 'The projected corridor remains visible while the district outlook stabilizes.'
  return 'The projected spread corridor contributes to the current Matara risk field.'
}

/**
 * Builds the complete frontend-only Page-2 presentation snapshot from the
 * currently loaded real verified-case feature collection. It performs no
 * request and never invents or relocates a confirmed red anchor.
 *
 * The Page-2 presentation is deliberately scoped to the first two real
 * cases (by the same stable identity sort `normalizeRealAreaCaseFeatures`
 * already applies) so the map keeps exactly two purple corridors even
 * when more verified Matara cases exist in the operational feed -- never
 * a fabricated case, only a bounded, deterministic slice of the real
 * ones, keeping the map readable instead of visually crowded.
 */
export const MAX_PRESENTATION_ANCHORS = 2

export function buildMyAreaPresentationForecast(caseFeatures, activeIndex, districtFeature = null) {
  const index = clampAreaForecastIndex(activeIndex)
  const date = AREA_FORECAST_DATES[index]
  const progress = AREA_SPREAD_PROGRESS[index]
  const anchors = normalizeRealAreaCaseFeatures(caseFeatures).slice(0, MAX_PRESENTATION_ANCHORS)
  if (anchors.length === 0) {
    return {
      activeIndex: index,
      date,
      districtRisk: AREA_DISTRICT_RISK_LEVELS[index],
      anchorCount: 0,
      anchors: EMPTY_COLLECTION,
      paths: EMPTY_COLLECTION,
      fronts: EMPTY_COLLECTION,
      riskZones: EMPTY_COLLECTION,
      influences: [],
      overlapRiskLevel: null,
    }
  }

  const targetCenter = districtCenter(districtFeature, anchors)
  const projections = anchors.map((feature) => {
    const parameters = caseProjectionParameters(feature, targetCenter)
    const coordinates = buildCurvedPath(feature.geometry.coordinates, parameters, progress)
    const frontCoordinate = coordinates.at(-1)
    const fieldCenter = coordinates[Math.round((coordinates.length - 1) * 0.58)]
    const majorRadiusKm = Math.max(0.75, parameters.maximumReachKm * (0.1 + progress * 0.62))
    return { feature, parameters, coordinates, frontCoordinate, fieldCenter, majorRadiusKm }
  })

  const paths = projections.map(({ feature, parameters, coordinates }) => ({
    type: 'Feature',
    id: `path:${parameters.identity}`,
    geometry: { type: 'LineString', coordinates },
    properties: {
      anchorId: parameters.identity,
      caseId: feature.properties.caseId ?? parameters.identity,
      date,
      projected: true,
    },
  }))

  const fronts = projections.map(({ feature, parameters, frontCoordinate }) => ({
    type: 'Feature',
    id: `front:${parameters.identity}`,
    geometry: { type: 'Point', coordinates: frontCoordinate },
    properties: {
      anchorId: parameters.identity,
      caseId: feature.properties.caseId ?? parameters.identity,
      date,
      projected: true,
    },
  }))

  const riskFeatures = []
  for (const tier of RISK_TIERS) {
    for (const projection of projections) {
      riskFeatures.push(makeRiskFeature({
        center: projection.fieldCenter,
        bearing: projection.parameters.bearing,
        majorRadiusKm: projection.majorRadiusKm,
        tier,
        anchorId: projection.parameters.identity,
        date,
      }))
    }
  }

  const overlappingAnchors = new Set()
  const overlapFeatures = []
  for (let firstIndex = 0; firstIndex < projections.length; firstIndex += 1) {
    for (let secondIndex = firstIndex + 1; secondIndex < projections.length; secondIndex += 1) {
      const first = projections[firstIndex]
      const second = projections[secondIndex]
      const distanceKm = areaDistanceKm(first.fieldCenter, second.fieldCenter)
      const combinedReachKm = first.majorRadiusKm + second.majorRadiusKm
      const riskLevel = classifyAreaRiskOverlap({ distanceKm, combinedReachKm, activeIndex: index })
      if (!riskLevel) continue
      overlappingAnchors.add(first.parameters.identity)
      overlappingAnchors.add(second.parameters.identity)
      const tier = RISK_TIERS.find((candidate) => candidate.riskLevel === riskLevel)
      const overlapMajorRadiusKm = Math.max(0.8, (combinedReachKm - distanceKm) * 0.42 + 0.7)
      overlapFeatures.push(makeRiskFeature({
        center: midpoint(first.fieldCenter, second.fieldCenter),
        bearing: bearingBetween(first.fieldCenter, second.fieldCenter),
        majorRadiusKm: overlapMajorRadiusKm,
        tier,
        anchorId: first.parameters.identity,
        secondaryAnchorId: second.parameters.identity,
        date,
        overlap: true,
      }))
    }
  }
  riskFeatures.push(...overlapFeatures)

  const districtLabel = districtFeature?.properties?.shapeName ?? districtFeature?.properties?.name ?? null
  const influences = projections.map(({ feature, parameters, frontCoordinate }) => {
    const status = areaInfluenceStatus(index, overlappingAnchors.has(parameters.identity))
    return {
      anchorId: parameters.identity,
      caseId: feature.properties.caseId ?? parameters.identity,
      disease: feature.properties.disease ?? null,
      locationDistrict: feature.properties.locationDistrict ?? districtLabel,
      verificationTime: feature.properties.verificationTime ?? null,
      status,
      description: influenceDescription(status),
      frontCoordinate,
    }
  })

  const overlapRiskLevel = overlapFeatures.reduce((highest, feature) => {
    const order = ['green', 'yellow', 'orange', 'red']
    return order.indexOf(feature.properties.riskLevel) > order.indexOf(highest) ? feature.properties.riskLevel : highest
  }, null)

  return {
    activeIndex: index,
    date,
    districtRisk: AREA_DISTRICT_RISK_LEVELS[index],
    anchorCount: anchors.length,
    anchors: { type: 'FeatureCollection', features: anchors },
    paths: { type: 'FeatureCollection', features: paths },
    fronts: { type: 'FeatureCollection', features: fronts },
    riskZones: { type: 'FeatureCollection', features: riskFeatures },
    influences,
    overlapRiskLevel,
  }
}
