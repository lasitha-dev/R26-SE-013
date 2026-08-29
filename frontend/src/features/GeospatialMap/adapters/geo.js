/**
 * LSD-UI-01: minimal geometry helper for the Page 2 relevance rule
 * (plan Section E) -- point-in-polygon only.
 *
 * A great-circle earth-distance formula was deliberately removed from
 * here after `visualLayerStructural.test.js` ("Part 20: no frontend
 * scientific recomputation in the visual layer") correctly flagged it
 * as a forbidden signature: this project's hard rule is that real-world
 * distance computation belongs to the backend's own WGS84 math
 * (`pyproj`, per `backend/requirements.txt`), never a client-side
 * approximation that could silently diverge from it. Point-in-polygon
 * containment is plain computational geometry (no earth-distance
 * formula involved), so it stays here; a "within N km of the boundary"
 * relevance test needs either a real backend endpoint or a
 * server-computed buffer polygon, not a frontend distance estimate --
 * see plan Section E/Q for the corrected relevance rule.
 */

/** Standard ray-casting point-in-polygon test. `polygon` is an array of
 * [lon, lat] rings (GeoJSON Polygon `coordinates[0]`, no holes needed
 * for district boundaries). Accurate for district-scale polygons; not
 * meant for anti-meridian-crossing or global-scale geometry. */
export function isPointInPolygonRing(point, ring) {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const intersects = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
    if (intersects) inside = !inside
  }
  return inside
}
