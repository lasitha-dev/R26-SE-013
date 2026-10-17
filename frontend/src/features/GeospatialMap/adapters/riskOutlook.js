/**
 * Future Risk Outlook rows -- read from the SAME backend day rasters the Risk
 * Zones map colours (adapters/riskFieldModel.js), so the bars and the map
 * always show one quantity.
 *
 * For each day: the land area of the backend raster cells whose centre lies
 * inside the vet's district, summed per fixed display band (high >= 0.70,
 * elevated >= 0.40, moderate >= 0.15, low below), as km2 and as a share of the
 * district's own area (one fixed denominator on every day); the highest score
 * in the district; registered farms on coloured land (and their animals);
 * how far the colour reaches from its main contributing case; the change
 * since the previous day. Nothing here computes a risk score: cells are only
 * counted and measured.
 */
import { isPointInsideDistrictFeature } from './districtGeometry'
import { HORIZON_STATUS } from './spatialTimelineView'
import { bandOfScore, rasterScoreAt } from './riskFieldModel'

export const OUTLOOK_BANDS = Object.freeze(['high', 'elevated', 'moderate', 'low'])
const KM_PER_DEG_LAT = 110.574
const kmPerDegLon = (lat) => 111.32 * Math.cos((lat * Math.PI) / 180)

function ringAreaKm2(ring) {
  // Planar shoelace in local km (exact enough for a district, < 0.5 %).
  if (!Array.isArray(ring) || ring.length < 4) return 0
  const lat0 = ring.reduce((s, p) => s + p[1], 0) / ring.length
  const kx = kmPerDegLon(lat0)
  let twice = 0
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i]
    const [x2, y2] = ring[i + 1]
    twice += x1 * kx * (y2 * KM_PER_DEG_LAT) - x2 * kx * (y1 * KM_PER_DEG_LAT)
  }
  return Math.abs(twice) / 2
}

/** Area of a district polygon (outer rings minus holes), km2. */
export function districtAreaKm2(feature) {
  const geometry = feature?.geometry
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : []
  return polygons.reduce((sum, rings) => sum + ringAreaKm2(rings[0]) - rings.slice(1).reduce((h, r) => h + ringAreaKm2(r), 0), 0)
}

/** `farms`: [lon, lat] pairs or { coordinates, totalAnimals } rows. */
function farmPoint(farm) {
  const coordinates = Array.isArray(farm) ? farm : farm?.coordinates
  if (!Array.isArray(coordinates) || coordinates.length !== 2 || !coordinates.every(Number.isFinite)) return null
  return { coordinates, animals: Number.isFinite(farm?.totalAnimals) ? farm.totalAnimals : null }
}

export function buildRiskOutlookRows(model, districtFeature, { farms = [] } = {}) {
  if (!model || !districtFeature) return []
  const districtKm2 = districtAreaKm2(districtFeature)
  const { west, south, step_deg: step } = model.grid
  const inside = new Map() // global cell key -> inside the district (cells repeat across days)
  const insideCell = (i, j, lon, lat) => {
    const key = `${i}:${j}`
    if (!inside.has(key)) inside.set(key, isPointInsideDistrictFeature([lon, lat], districtFeature))
    return inside.get(key)
  }
  const farmPoints = (farms ?? []).map(farmPoint).filter(Boolean)
  const sourceAt = (index) => model.sources[index - 1]?.coordinates ?? null
  const rows = []
  for (let d = 0; d < model.frameCount; d += 1) {
    const raster = model.rasterFor(d)
    const bandAreas = Object.fromEntries(OUTLOOK_BANDS.map((b) => [b, 0]))
    let maxScore = 0
    // Farthest drawn cell (anywhere) from the case that contributes most there, km.
    let extentKm = 0
    if (raster) {
      for (let r = 0; r < raster.h; r += 1) {
        const lat = south + (raster.j0 + r + 0.5) * step
        const cellKm2 = step * kmPerDegLon(lat) * step * KM_PER_DEG_LAT
        for (let c = 0; c < raster.w; c += 1) {
          const score = raster.score[r * raster.w + c]
          if (!(score > 0)) continue
          const lon = west + (raster.i0 + c + 0.5) * step
          const origin = sourceAt(raster.case1?.[r * raster.w + c] ?? 0)
          if (origin) {
            const km = Math.hypot((lon - origin[0]) * kmPerDegLon(lat), (lat - origin[1]) * KM_PER_DEG_LAT)
            if (km > extentKm) extentKm = km
          }
          if (!insideCell(raster.i0 + c, raster.j0 + r, lon, lat)) continue
          bandAreas[bandOfScore(score, model.bands)] += cellKm2
          if (score > maxScore) maxScore = score
        }
      }
    }
    const coloredKm2 = OUTLOOK_BANDS.reduce((sum, b) => sum + bandAreas[b], 0)
    const onColour = raster ? farmPoints.filter(({ coordinates: [lon, lat] }) => rasterScoreAt(raster, model.grid, lon, lat) >= (model.grid.min_score ?? 0.03)) : []
    const previous = rows[d - 1]
    rows.push({
      index: d,
      day: d,
      date: model.dates[d] ?? null,
      exploratory: model.exploratoryFromDay >= 0 && d >= model.exploratoryFromDay,
      horizonStatus: d === 0 ? HORIZON_STATUS.AS_OF : model.exploratoryFromDay >= 0 && d >= model.exploratoryFromDay ? HORIZON_STATUS.EXPLORATORY : HORIZON_STATUS.EVALUATED,
      bandAreas,
      coloredKm2,
      districtKm2,
      coloredShare: districtKm2 > 0 ? coloredKm2 / districtKm2 : 0,
      maxScore: maxScore > 0 ? maxScore : null,
      maxBand: maxScore > 0 ? bandOfScore(maxScore, model.bands) : null,
      deltaKm2: previous ? coloredKm2 - previous.coloredKm2 : null,
      monitoredFarms: onColour.length,
      // Animals on those farms (registered herd size); farms without one are counted apart.
      monitoredAnimals: onColour.reduce((sum, f) => sum + (f.animals ?? 0), 0),
      monitoredFarmsWithoutAnimalCount: onColour.filter((f) => f.animals === null).length,
      extentKm: extentKm > 0 ? extentKm : null,
      sourceCount: model.sources.length,
    })
  }
  return rows
}
