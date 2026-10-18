/**
 * LSD-UI-04: draws the backend's real `nominal_reach_km` value (plan
 * Section 22/26 -- "Nominal reach -- visualization only, not a disease
 * boundary") as a ring on the map. This module does NOT compute a
 * reach/rate value itself -- the radius always comes verbatim from
 * `nominal_reach_by_day` (see `lsdOutbreakAdapter.js`). Its only job is
 * turning "draw a ring of radius R km around this point" into map
 * polygon coordinates, which needs some km-to-degrees conversion the
 * same way `mapProjection.js`/`computeCombinedLngLatBounds` already do
 * lon/lat degree math for camera framing -- a presentation/rendering
 * concern, not a re-derivation of the model's rate or reach numbers.
 *
 * Uses a fixed local-flat approximation (a constant km-per-degree-
 * latitude, longitude scaled by cos(latitude)) which is accurate enough
 * for a compact ring at the ~5-30km scale these values fall in; it does
 * not attempt to reproduce the backend's own real-world distance
 * mathematics, and must never be used for anything but drawing this
 * one honestly-labelled ring.
 */

const KM_PER_DEGREE_LATITUDE = 111.32

/** Builds a GeoJSON Polygon Feature approximating a ring of `radiusKm`
 * around `[lon, lat]`. Returns `null` for a non-positive radius (D0 has
 * no forward reach to show). */
export function buildReachRingPolygon([lon, lat], radiusKm, steps = 64) {
  if (!(radiusKm > 0)) return null

  const latDegreesPerKm = 1 / KM_PER_DEGREE_LATITUDE
  const lonDegreesPerKm = 1 / (KM_PER_DEGREE_LATITUDE * Math.cos((lat * Math.PI) / 180))

  const ring = []
  for (let i = 0; i <= steps; i += 1) {
    const angle = (2 * Math.PI * i) / steps
    const dLon = radiusKm * lonDegreesPerKm * Math.cos(angle)
    const dLat = radiusKm * latDegreesPerKm * Math.sin(angle)
    ring.push([lon + dLon, lat + dLat])
  }

  return {
    type: 'Feature',
    // `centerLonLat`/`radiusKm` are carried on the feature so a caller
    // animating between two radii (see `MapLibreCanvas.jsx`) can rebuild
    // intermediate rings around the SAME real center without having to
    // reverse-engineer it from polygon coordinates.
    properties: { radiusKm, centerLonLat: [lon, lat] },
    geometry: { type: 'Polygon', coordinates: [ring] },
  }
}

export function emptyReachRingFeatureCollection() {
  return { type: 'FeatureCollection', features: [] }
}

export function reachRingFeatureCollection(centerLonLat, radiusKm) {
  const feature = buildReachRingPolygon(centerLonLat, radiusKm)
  return feature ? { type: 'FeatureCollection', features: [feature] } : emptyReachRingFeatureCollection()
}

/**
 * `nominal_reach_by_day` is one value for the whole origin, not
 * per-source (the backend's per-CELL reference is instead the nearest
 * eligible source -- `NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE`).
 * Rather than arbitrarily picking one of an origin's real source points
 * as "the" ring center, this draws the SAME real radius around EVERY
 * real source in the selected origin -- visually honest ("up to this
 * far from any observed point"), never implying a single point of
 * origin the data doesn't actually establish.
 */
export function buildReachRingFeatureCollectionForCenters(centers, radiusKm) {
  const features = (centers ?? []).map((center) => buildReachRingPolygon(center, radiusKm)).filter(Boolean)
  return { type: 'FeatureCollection', features }
}

// GEO-REACH-GRADIENT-01: MapLibre GL has no native gradient fill for a
// polygon (`fill-color` is one flat color/opacity per feature) -- so a
// soft radial "hot at the origin, fading at the edge" look is built the
// same way the wider map-styling community does it: several concentric
// FILLED disks of the SAME real radius (never a second/different radius
// value), each painted at a small, EQUAL opacity, largest-first so the
// smaller disks layer on top and their alpha naturally compounds toward
// the center (standard alpha-over compositing: with N equal-opacity
// layers of per-layer opacity a, the composited opacity at a point
// covered by k of them is `1 - (1-a)^k`). This is a pure geometry/opacity
// RENDERING technique over the one real `radiusKm` already drawn by
// `buildReachRingPolygon` above -- it never derives a second radius value
// and never touches the real km-per-day number itself.
export const REACH_GRADIENT_BAND_COUNT = 8
// `1 - (1 - REACH_GRADIENT_BAND_OPACITY) ** REACH_GRADIENT_BAND_COUNT` ~= 0.25
// at the very center (every band overlapping); the outermost sliver
// (covered by only the single largest band) reads at this one flat value,
// close to 0 -- matching "~25% opacity at the origin, ~0% at the edge".
export const REACH_GRADIENT_BAND_OPACITY = 0.035

/**
 * Builds the concentric-disk gradient FeatureCollection for every real
 * center in `centers`, all at fractions of the SAME real `radiusKm` (never
 * a fabricated/independent radius). Each feature carries `bandFraction`
 * (1 = the full real radius, down to `1/bandCount`) purely for
 * inspection/testing -- paint uses one flat, equal opacity per band
 * (`REACH_GRADIENT_BAND_OPACITY`), the compositing itself produces the
 * gradient. Returns an empty collection for a non-positive radius, same
 * as `buildReachRingFeatureCollectionForCenters`.
 */
export function buildReachGradientFeatureCollectionForCenters(centers, radiusKm, bandCount = REACH_GRADIENT_BAND_COUNT) {
  if (!(radiusKm > 0)) return emptyReachRingFeatureCollection()
  const features = []
  for (const center of centers ?? []) {
    for (let band = bandCount; band >= 1; band -= 1) {
      const fraction = band / bandCount
      const feature = buildReachRingPolygon(center, radiusKm * fraction)
      if (feature) {
        feature.properties.bandFraction = fraction
        features.push(feature)
      }
    }
  }
  return { type: 'FeatureCollection', features }
}
