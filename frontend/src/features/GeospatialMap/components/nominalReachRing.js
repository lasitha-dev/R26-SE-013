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
