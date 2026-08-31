/**
 * Checkpoint 11A Part 13: pure, framework-independent screen-space
 * projection helpers -- extracted from `MapCanvas.jsx` for testability.
 *
 * GeoJSON coordinates are always `[longitude, latitude]` (RFC 7946,
 * EPSG:4326) -- `coordinates[0]` is ALWAYS read as longitude,
 * `coordinates[1]` ALWAYS as latitude. This is a presentation-only
 * screen projection, never a scientific distance calculation.
 */

export function computeBounds(points) {
  if (points.length === 0) return null
  let minLon = Infinity
  let maxLon = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity
  for (const [lon, lat] of points) {
    if (lon < minLon) minLon = lon
    if (lon > maxLon) maxLon = lon
    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
  }
  const lonSpan = maxLon - minLon || 0.01
  const latSpan = maxLat - minLat || 0.01
  return { minLon, maxLon, minLat, maxLat, lonSpan, latSpan }
}

export function project(lon, lat, bounds, width, height, padding) {
  const x = padding + ((lon - bounds.minLon) / bounds.lonSpan) * (width - 2 * padding)
  const y = height - padding - ((lat - bounds.minLat) / bounds.latSpan) * (height - 2 * padding)
  return [x, y]
}

/** Extracts `[longitude, latitude]` from a GeoJSON Point feature,
 * verbatim, never reversed. */
export function lonLatFromFeature(feature) {
  const [lon, lat] = feature.geometry.coordinates
  return [lon, lat]
}
