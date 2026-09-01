import { isPointInsideDistrictFeature } from './districtGeometry'

export const PAGE1_FORECAST_DATES = Object.freeze([
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

export const PAGE1_SPREAD_PROGRESS = Object.freeze([
  0.02, 0.08, 0.15, 0.23, 0.32, 0.42, 0.53, 0.64, 0.74, 0.83, 0.9, 0.95, 0.98, 1,
])

export const PAGE1_PLAYBACK_INTERVAL_MS = Object.freeze({ 0.5: 2200, 1: 1100, 2: 550 })

/**
 * Whether the ONE master Page-1 presentation timeline should be mounted
 * at all, given the CURRENT, unfiltered real outbreak collection.
 * Deliberately reads the full national/database set, never a
 * location-scope-filtered subset -- a district with zero currently loaded
 * outbreaks is a real, honest empty scope, not a reason to unmount the
 * master timeline and fall back to a different (legacy) timeline
 * component. Camera/location scope must never own time.
 */
export function isPage1MasterTimelineActive(outbreakFeatures) {
  const features = Array.isArray(outbreakFeatures) ? outbreakFeatures : outbreakFeatures?.features ?? []
  return features.length > 0
}

export function advancePage1ForecastIndex(currentIndex) {
  const current = clampFrameIndex(currentIndex)
  const finalIndex = PAGE1_FORECAST_DATES.length - 1
  if (current >= finalIndex) return { index: finalIndex, complete: true }
  const index = current + 1
  return { index, complete: index === finalIndex }
}

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

// Ordered lowest-severity-first -- both the required draw order (green
// under yellow under orange under red, `riskZones` is sorted into this
// order before being handed to MapLibre as ONE source) and the required
// `riskLevel` activation order (a tier only appears once the day's real
// severity phase has crossed its own threshold, see `RISK_TIER_SPECS`).
export const PAGE1_RISK_LEVEL_ORDER = Object.freeze([
  PAGE1_RISK_TIER.OUTER,
  PAGE1_RISK_TIER.MODERATE,
  PAGE1_RISK_TIER.ELEVATED,
  PAGE1_RISK_TIER.HIGHEST,
])

// Internal-only visualization multiplier -- drives contour size/severity,
// NEVER shown to a user and never labelled infection probability/
// confidence/model accuracy. Rises then gently settles, matching the
// required Sep01->Sep14 "expand, intensify, then stabilize" story.
export const PAGE1_RISK_PHASE = Object.freeze([
  0.3, 0.38, 0.47, 0.56, 0.66, 0.77, 0.88, 0.98, 1.08, 1.16, 1.22, 1.18, 1.1, 1.02,
])

const EMPTY_FEATURE_COLLECTION = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })
const EARTH_RADIUS_KM = 6371.0088
const PATH_STEPS = 18
const RISK_POLYGON_STEPS = 64
// Nested risk bands, largest/lowest-severity (green) to smallest/highest
// (red). `radiusKm` ratios sit inside the required size bands (yellow
// ~72-78%, orange ~48-58%, red ~25-35% of green: 4.1/5.6=73%,
// 2.9/5.6=52%, 1.8/5.6=32%). `activationThreshold` is the minimum
// `PAGE1_RISK_PHASE` value at which this band exists AT ALL -- lower
// bands (green) are always present once any risk is shown; higher bands
// (orange, red) only "unlock" once the deterministic phase curve has
// risen enough, so severity visibly escalates (and can later recede)
// across the 14-day playback instead of every band existing at full
// strength from day one. `lobeWeights` size the three trail lobes built
// around [near-origin, trajectory-midpoint, projected-front] -- see
// `buildOutbreakRiskFeatures` -- red is strongest at the real origin
// (current local influence), green is strongest at the leading edge
// (furthest honest reach), producing a natural directional trail instead
// of one static oval.
const RISK_TIER_SPECS = Object.freeze([
  { tier: PAGE1_RISK_TIER.OUTER, radiusKm: 5.6, activationThreshold: 0, lobeWeights: [0.55, 0.85, 1.0] },
  { tier: PAGE1_RISK_TIER.MODERATE, radiusKm: 4.1, activationThreshold: 0.25, lobeWeights: [0.7, 0.95, 0.9] },
  { tier: PAGE1_RISK_TIER.ELEVATED, radiusKm: 2.9, activationThreshold: 0.5, lobeWeights: [0.9, 0.95, 0.7] },
  { tier: PAGE1_RISK_TIER.HIGHEST, radiusKm: 1.8, activationThreshold: 0.8, lobeWeights: [1.0, 0.8, 0.5] },
])
// Trail lobe positions along the real origin -> current projected-front
// vector (0 = origin, 1 = front) -- never exactly 0/1 so every lobe stays
// a distinct, visible ellipse rather than degenerating onto the
// confirmed marker or the front marker itself.
const LOBE_POSITIONS = Object.freeze([0.12, 0.5, 0.9])

function clampFrameIndex(value) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(PAGE1_FORECAST_DATES.length - 1, Math.trunc(value)))
}

function toRadians(degrees) {
  return (degrees * Math.PI) / 180
}

function toDegrees(radians) {
  return (radians * 180) / Math.PI
}

function normalizeLongitude(longitude) {
  return ((longitude + 540) % 360) - 180
}

/** Pure destination-point calculation used only for this presentation layer. */
export function destinationPoint([longitude, latitude], bearingDegrees, distanceKm) {
  if (!(distanceKm > 0)) return [longitude, latitude]
  const angularDistance = distanceKm / EARTH_RADIUS_KM
  const bearing = toRadians(bearingDegrees)
  const latitude1 = toRadians(latitude)
  const longitude1 = toRadians(longitude)
  const latitude2 = Math.asin(
    Math.sin(latitude1) * Math.cos(angularDistance) +
      Math.cos(latitude1) * Math.sin(angularDistance) * Math.cos(bearing),
  )
  const longitude2 =
    longitude1 +
    Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude1),
      Math.cos(angularDistance) - Math.sin(latitude1) * Math.sin(latitude2),
    )
  return [normalizeLongitude(toDegrees(longitude2)), toDegrees(latitude2)]
}

export function stableForecastHash(value) {
  const text = String(value ?? '')
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function featureIdentity(feature) {
  const properties = feature?.properties ?? {}
  const coordinates = feature?.geometry?.coordinates ?? []
  return String(
    properties.caseId ??
      properties.sourceId ??
      properties.source_id ??
      properties.outbreakId ??
      properties.outbreak_id ??
      feature?.id ??
      `${coordinates[1]}:${coordinates[0]}`,
  )
}

function validPointFeature(feature) {
  const coordinates = feature?.geometry?.coordinates
  return (
    feature?.geometry?.type === 'Point' &&
    Array.isArray(coordinates) &&
    coordinates.length >= 2 &&
    Number.isFinite(coordinates[0]) &&
    Number.isFinite(coordinates[1])
  )
}

function isInsideSriLanka(coordinates, boundaryFeatures) {
  return boundaryFeatures.some((feature) => isPointInsideDistrictFeature(coordinates, feature))
}

function interpolatePoint(start, end, amount) {
  return [start[0] + (end[0] - start[0]) * amount, start[1] + (end[1] - start[1]) * amount]
}

function clipPointToBoundary(start, candidate, boundaryFeatures) {
  if (isInsideSriLanka(candidate, boundaryFeatures)) return candidate
  let low = 0
  let high = 1
  let best = start
  for (let step = 0; step < 12; step += 1) {
    const amount = (low + high) / 2
    const point = interpolatePoint(start, candidate, amount)
    if (isInsideSriLanka(point, boundaryFeatures)) {
      best = point
      low = amount
    } else {
      high = amount
    }
  }
  return best
}

function buildProjectedPath(origin, activeIndex, seed, boundaryFeatures) {
  const progress = PAGE1_SPREAD_PROGRESS[activeIndex]
  const baseBearing = seed % 360
  const phase = ((seed >>> 8) % 628) / 100
  const maxReachKm = 8 + ((seed >>> 16) % 7)
  const coordinates = [origin]
  let lastValid = origin

  for (let step = 1; step <= PATH_STEPS; step += 1) {
    const portion = step / PATH_STEPS
    const bearing = baseBearing + Math.sin(activeIndex * 0.45 + phase + portion * 1.7) * 10
    const candidate = destinationPoint(origin, bearing, maxReachKm * progress * portion)
    if (isInsideSriLanka(candidate, boundaryFeatures)) lastValid = candidate
    coordinates.push(lastValid)
  }

  return { coordinates, front: coordinates[coordinates.length - 1], bearing: baseBearing, progress }
}

/**
 * Builds one smooth, closed geographic ellipse ring (GeoJSON `[lng, lat]`
 * winding, first coordinate === last) around a real-world center, oriented
 * so its major axis points along `bearingDeg`. Pure local-tangent-plane
 * math (`destinationPoint`'s own great-circle formula), never a screen-
 * pixel/CSS shape -- this is what keeps every generated band a true
 * geographic polygon at any zoom/projection.
 */
export function buildDirectionalEllipse({ centerLat, centerLng, majorRadiusKm, minorRadiusKm, bearingDeg, steps = RISK_POLYGON_STEPS }) {
  const stepCount = Math.max(8, Math.trunc(steps))
  const ring = []
  for (let step = 0; step <= stepCount; step += 1) {
    const theta = (step / stepCount) * Math.PI * 2
    const forwardKm = majorRadiusKm * Math.cos(theta)
    const lateralKm = minorRadiusKm * Math.sin(theta)
    const distanceKm = Math.sqrt(forwardKm ** 2 + lateralKm ** 2)
    const offsetDeg = toDegrees(Math.atan2(lateralKm, forwardKm))
    ring.push(destinationPoint([centerLng, centerLat], bearingDeg + offsetDeg, distanceKm))
  }
  // Exact closure (not just "close enough" from the trig round-trip) --
  // required by the GeoJSON polygon spec and this module's own ring tests.
  ring[ring.length - 1] = ring[0]
  return ring
}

/**
 * BUGFIX (black/irregular risk polygon): the previous implementation
 * binary-search-clipped EACH ring vertex independently against the Sri
 * Lanka boundary. Near any coastline that could collapse several vertices
 * onto very different points along the coast, turning a simple oval into
 * a self-intersecting/bowtie ring -- WebGL then fills the overlapping
 * triangles from earcut triangulation on top of each other, which is what
 * actually read as a dark, jagged single "blob" over the real basemap (it
 * also, wrongly, only ever produced ONE polygon group regardless of how
 * many real outbreaks existed). `buildDirectionalEllipse` is simple/
 * non-self-intersecting BY CONSTRUCTION, and this function runs it once
 * PER REAL OUTBREAK, so N outbreaks always produce N independent local
 * risk fields, never one shared shape. The only remaining boundary guard
 * is the lobe CENTER itself: if a forward-shifted lobe center would land
 * outside Sri Lanka, it falls back to the real confirmed coordinate
 * (always on real land) instead of distorting the smooth ring.
 *
 * Builds every risk-contour feature for ONE real outbreak. For each
 * severity tier whose `activationThreshold` the day's real
 * `PAGE1_RISK_PHASE` has crossed, three overlapping translucent lobes are
 * placed along the origin -> projected-front vector (near-origin,
 * trajectory-midpoint, current front) -- an area-shaped directional trail
 * rather than one isolated oval per tier, oriented by that SAME outbreak's
 * own deterministic bearing (Section 17: different outbreaks -> different
 * orientations). Keyed only by the real outbreak's own stable identity --
 * no case-ID branching of any kind.
 */
function buildOutbreakRiskFeatures(identity, origin, projection, phase, boundaryFeatures, sharedProperties) {
  const features = []
  for (const spec of RISK_TIER_SPECS) {
    if (phase < spec.activationThreshold) continue
    LOBE_POSITIONS.forEach((t, lobeIndex) => {
      const lobeWeight = spec.lobeWeights[lobeIndex]
      const forwardCenter = interpolatePoint(origin, projection.front, t)
      const center = boundaryFeatures.length === 0 || isInsideSriLanka(forwardCenter, boundaryFeatures) ? forwardCenter : origin
      // Major axis (along the projected-spread bearing) grows faster than
      // the minor (lateral) axis as the day index advances -- visible
      // directional elongation (compact/round early, clearly egg-shaped
      // and forward-leaning by mid-playback).
      const majorRadiusKm = spec.radiusKm * phase * lobeWeight * (0.75 + projection.progress * 0.5)
      const minorRadiusKm = spec.radiusKm * phase * lobeWeight * (0.52 + projection.progress * 0.14)
      const visualizationFeatureId = `${identity}:risk:${spec.tier}:${lobeIndex}`
      features.push({
        type: 'Feature',
        id: visualizationFeatureId,
        properties: {
          ...sharedProperties,
          visualizationFeatureId,
          // Literal `"green" | "yellow" | "orange" | "red"` -- exactly
          // what `mapLibreAdapter.js`'s `match` expression keys on, so
          // there is never a translation step that could fall through to
          // an unstyled/default-black fill.
          riskLevel: spec.tier,
          color: PAGE1_RISK_COLORS[spec.tier],
        },
        geometry: {
          type: 'Polygon',
          coordinates: [
            buildDirectionalEllipse({
              centerLat: center[1],
              centerLng: center[0],
              majorRadiusKm,
              minorRadiusKm,
              bearingDeg: projection.bearing,
              steps: RISK_POLYGON_STEPS,
            }),
          ],
        },
      })
    })
  }
  return features
}

function featureCollection(features) {
  return { type: 'FeatureCollection', features }
}

/**
 * Builds the current Page-1 presentation frame from the CURRENT real
 * outbreak/source point array. No confirmed record, confirmed anchor
 * coordinate, probability, or API response is invented; only the
 * deterministic projected display geometry is new.
 */
export function buildPage1ForecastVisualization(outbreakFeatures, requestedIndex, sriLankaBoundaryFeatures = []) {
  const activeIndex = clampFrameIndex(requestedIndex)
  const anchors = (Array.isArray(outbreakFeatures) ? outbreakFeatures : outbreakFeatures?.features ?? []).filter(validPointFeature)
  const boundaryFeatures = (Array.isArray(sriLankaBoundaryFeatures)
    ? sriLankaBoundaryFeatures
    : sriLankaBoundaryFeatures?.features ?? []
  ).filter((feature) => feature?.geometry)

  if (anchors.length === 0) {
    return {
      activeIndex,
      date: PAGE1_FORECAST_DATES[activeIndex],
      anchorCount: 0,
      paths: EMPTY_FEATURE_COLLECTION,
      fronts: EMPTY_FEATURE_COLLECTION,
      riskZones: EMPTY_FEATURE_COLLECTION,
    }
  }

  const paths = []
  const fronts = []
  const riskZones = []
  const canProject = boundaryFeatures.length > 0

  for (const anchor of anchors) {
    const identity = featureIdentity(anchor)
    const seed = stableForecastHash(identity)
    const origin = anchor.geometry.coordinates.slice(0, 2)
    const projection = canProject
      ? buildProjectedPath(origin, activeIndex, seed, boundaryFeatures)
      : { coordinates: Array.from({ length: PATH_STEPS + 1 }, () => origin), front: origin, bearing: seed % 360, progress: PAGE1_SPREAD_PROGRESS[activeIndex] }
    const sharedProperties = {
      visualizationId: identity,
      sourceId: anchor.properties?.source_id ?? anchor.properties?.sourceId ?? identity,
      outbreakId: anchor.properties?.outbreakId ?? anchor.properties?.outbreak_id ?? null,
      activeIndex,
      date: PAGE1_FORECAST_DATES[activeIndex],
      presentationOnly: true,
    }

    paths.push({
      type: 'Feature',
      id: `${identity}:path`,
      properties: { ...sharedProperties, visualizationFeatureId: `${identity}:path` },
      geometry: { type: 'LineString', coordinates: projection.coordinates },
    })
    fronts.push({
      type: 'Feature',
      id: `${identity}:front`,
      properties: { ...sharedProperties, visualizationFeatureId: `${identity}:front` },
      geometry: { type: 'Point', coordinates: projection.front },
    })

    if (canProject) {
      riskZones.push(...buildOutbreakRiskFeatures(identity, origin, projection, PAGE1_RISK_PHASE[activeIndex], boundaryFeatures, sharedProperties))
    }
  }

  // Required draw order (green under yellow under orange under red) within
  // the ONE shared MapLibre risk source/layer -- a stable sort so lobes
  // belonging to the same outbreak/tier keep their relative order.
  riskZones.sort((a, b) => PAGE1_RISK_LEVEL_ORDER.indexOf(a.properties.riskLevel) - PAGE1_RISK_LEVEL_ORDER.indexOf(b.properties.riskLevel))

  return {
    activeIndex,
    date: PAGE1_FORECAST_DATES[activeIndex],
    anchorCount: anchors.length,
    paths: featureCollection(paths),
    fronts: featureCollection(fronts),
    riskZones: featureCollection(riskZones),
  }
}

function sameCoordinateShape(start, end) {
  if (Array.isArray(start) !== Array.isArray(end)) return false
  if (!Array.isArray(start)) return Number.isFinite(start) && Number.isFinite(end)
  if (start.length !== end.length) return false
  return start.every((value, index) => sameCoordinateShape(value, end[index]))
}

function interpolateCoordinates(start, end, amount) {
  if (!Array.isArray(start)) return start + (end - start) * amount
  return start.map((value, index) => interpolateCoordinates(value, end[index], amount))
}

function interpolateCollection(previous, next, amount) {
  if (!previous || previous.features.length !== next.features.length) return next
  const previousById = new Map(previous.features.map((feature) => [feature.properties?.visualizationFeatureId, feature]))
  const features = []
  for (const nextFeature of next.features) {
    const previousFeature = previousById.get(nextFeature.properties?.visualizationFeatureId)
    if (
      !previousFeature ||
      previousFeature.geometry?.type !== nextFeature.geometry?.type ||
      !sameCoordinateShape(previousFeature.geometry?.coordinates, nextFeature.geometry?.coordinates)
    ) {
      return next
    }
    features.push({
      ...nextFeature,
      geometry: {
        ...nextFeature.geometry,
        coordinates: interpolateCoordinates(previousFeature.geometry.coordinates, nextFeature.geometry.coordinates, amount),
      },
    })
  }
  return featureCollection(features)
}

export function interpolatePage1ForecastVisualization(previous, next, amount) {
  const clampedAmount = Math.max(0, Math.min(1, amount))
  if (!previous || clampedAmount >= 1 || previous.anchorCount !== next.anchorCount) return next
  return {
    ...next,
    paths: interpolateCollection(previous.paths, next.paths, clampedAmount),
    fronts: interpolateCollection(previous.fronts, next.fronts, clampedAmount),
    riskZones: interpolateCollection(previous.riskZones, next.riskZones, clampedAmount),
  }
}
