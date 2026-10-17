/**
 * Trajectory place labels: "Day 7 · near Akuressa" at the front of each
 * backend source path for the selected day (it moves with the front), and
 * "Insufficient directional evidence" under a source the model gives no
 * direction to (no path is drawn for it).
 * Nothing is labelled on Day 0, before playback.
 *
 * The place is the nearest populated place (city/town/village/suburb) in the
 * basemap's own OpenStreetMap vector tiles (OpenMapTiles `place` layer) within
 * `maxKm` of the point -- real reference data, never a guessed or invented
 * name. With no mapped place close enough the label falls back to the
 * compass heading. A label names where the ESTIMATED direction line ends; it
 * never says a case has reached that place.
 */
import { compassPoint } from '../adapters/spatialTimelineView'

const PLACE_CLASSES = new Set(['city', 'town', 'village', 'suburb'])
// A town or city is the more useful reference: preferred over a village up to
// this much farther away.
const TOWN_PREFERENCE_KM = 2
export const NEARBY_PLACE_MAX_KM = 8
export const NEARBY_PLACE_FAR_KM = 15
const STOP_LABEL = { NEXT_STEP_OFF_LAND: 'stops at coast', REACHED_25KM_LOCAL_DOMAIN: '25 km model limit' }

function kmBetween([lon1, lat1], [lon2, lat2]) {
  const kx = 111.32 * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180)
  return Math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * 110.574)
}

/** The basemap's vector source that carries the OpenMapTiles `place` layer. */
export function basemapPlaceSourceId(map) {
  const sources = map?.getStyle?.()?.sources ?? {}
  if (sources.openmaptiles?.type === 'vector') return 'openmaptiles'
  return Object.keys(sources).find((id) => sources[id]?.type === 'vector') ?? null
}

function placeName(properties) {
  const name = properties?.['name:en'] ?? properties?.name_en ?? properties?.['name:latin'] ?? properties?.name
  return typeof name === 'string' && name.trim() ? name.trim() : null
}

/** `{ name, km }` of the nearest mapped place to `point`, or null. Only tiles
 * already loaded by the map are searched (no extra network request). */
export function nearestMappedPlace(map, point, { maxKm = null } = {}) {
  // Zoomed out, the tiles only carry larger towns (no villages): search wider.
  const limitKm = maxKm ?? (typeof map?.getZoom === 'function' && map.getZoom() < 10 ? NEARBY_PLACE_FAR_KM : NEARBY_PLACE_MAX_KM)
  const sourceId = basemapPlaceSourceId(map)
  if (!sourceId || !Array.isArray(point)) return null
  let features = []
  try {
    features = map.querySourceFeatures(sourceId, { sourceLayer: 'place' }) ?? []
  } catch {
    return null
  }
  let best = null
  for (const feature of features) {
    if (!PLACE_CLASSES.has(feature?.properties?.class) || feature.geometry?.type !== 'Point') continue
    const name = placeName(feature.properties)
    if (!name) continue
    const km = kmBetween(point, feature.geometry.coordinates)
    const rank = km - (feature.properties.class === 'town' || feature.properties.class === 'city' ? TOWN_PREFERENCE_KM : 0)
    if (km <= limitKm && (!best || rank < best.rank)) best = { name, km, rank }
  }
  return best
}

/** Label points for the selected frame. `findPlace(point)` -> `{ name }` | null. */
export function buildTrajectoryLabels({ fronts, origins, findPlace = () => null }) {
  const features = []
  for (const front of fronts?.features ?? []) {
    const point = front.geometry?.coordinates
    const day = front.properties?.day
    if (!Array.isArray(point) || !Number.isInteger(day) || day < 1) continue
    const place = findPlace(point)
    const where = place ? `near ${place.name}` : Number.isFinite(front.properties?.bearingDeg) ? `heading ${compassPoint(front.properties.bearingDeg)}` : null
    // A path the model stopped says so (its front is the last point on land).
    const stopped = STOP_LABEL[front.properties?.stopReason] ?? (front.properties?.heldAtCoast ? 'waiting at coast' : null)
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: point },
      properties: { label: [`Day ${day}`, where, stopped].filter(Boolean).join(' · '), sourceId: front.properties?.sourceId ?? null, placeName: place?.name ?? null, role: 'CORRIDOR_TIP' },
    })
  }
  // A case belonging to any drawn outbreak path is covered by that path.
  const covered = new Set((fronts?.features ?? []).flatMap((f) => f.properties?.memberSourceIds ?? [f.properties?.sourceId]))
  for (const origin of origins?.features ?? []) {
    const point = origin.geometry?.coordinates
    if (!Array.isArray(point) || !(origin.properties?.day >= 1) || covered.has(origin.properties?.sourceId)) continue
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: point },
      properties: { label: 'Insufficient directional evidence', sourceId: origin.properties?.sourceId ?? null, placeName: null, role: 'NO_DIRECTION' },
    })
  }
  return { type: 'FeatureCollection', features }
}
