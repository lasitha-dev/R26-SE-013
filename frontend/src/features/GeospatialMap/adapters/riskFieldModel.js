/**
 * Risk-field model (pure) for the Risk Zones surface.
 *
 * Every value comes from ONE backend spatial-timeline snapshot:
 *  - `frames[d].risk_field.raster`: the backend's day-d practical risk field
 *    (engine.py RISK_FIELD_*, risk_raster.py) on a ~1.65 km lon/lat grid --
 *    each drawn cell's display score B = 1 - exp(-F_d), the number of cases
 *    contributing there and its top two cases with their shares. F_d is each
 *    active case's frozen C0 kernel, shown only as far as its spread can have
 *    travelled along its path by day d; overlapping cases add up, so a lone
 *    case peaks orange and only overlap reaches red. Fixed display bands:
 *    high >= 0.70, elevated >= 0.40, moderate >= 0.15, else low;
 *  - `cells`: the scored 5 km land cells -- nothing is drawn outside them
 *    (unscored land stays uncoloured).
 *
 * Nothing here computes a score: rasters are decoded, and bilinear
 * interpolation between neighbouring backend cells smooths the display
 * (never above the larger neighbour, never outside the drawn cells' reach).
 */
import { isPointInsideDistrictFeature } from './districtGeometry'
import { isTimelineRenderable, timelineFrames } from './spatialTimelineView'

/** Fallback when an older snapshot carries no `provenance.display_bands`. */
export const DEFAULT_DISPLAY_BANDS = Object.freeze([
  Object.freeze({ band: 'high', min: 0.7 }),
  Object.freeze({ band: 'elevated', min: 0.4 }),
  Object.freeze({ band: 'moderate', min: 0.15 }),
  Object.freeze({ band: 'low', min: 0 }),
])
export const BAND_LABEL = Object.freeze({ high: 'High', elevated: 'Elevated', moderate: 'Moderate', low: 'Low' })
const BAND_RANK = { low: 0, moderate: 1, elevated: 2, high: 3 }
// Raster grid fallback (risk_raster.py GRID_SPEC) for a snapshot without it.
const DEFAULT_GRID = Object.freeze({ west: 79.4, south: 5.7, step_deg: 0.015, levels: 250, min_score: 0.03 })
// Day-to-day score change below this reads as "stable".
export const TREND_EPSILON = 0.02
const KM_PER_DEG_LAT = 110.574

function displayBands(timeline) {
  const bands = timeline?.provenance?.display_bands
  const valid = Array.isArray(bands) && bands.length && bands.every((b) => b?.band in BAND_RANK && Number.isFinite(b.min))
  return valid ? [...bands].sort((a, b) => b.min - a.min) : DEFAULT_DISPLAY_BANDS
}

function rasterGrid(timeline) {
  const grid = timeline?.provenance?.risk_field_rule?.raster
  const valid = grid && ['west', 'south', 'step_deg', 'levels'].every((k) => Number.isFinite(grid[k])) && grid.step_deg > 0 && grid.levels > 0
  return valid ? { ...DEFAULT_GRID, ...grid } : DEFAULT_GRID
}

function base64Bytes(text) {
  const binary = globalThis.atob(text)
  const bytes = new Uint8Array(binary.length)
  for (let k = 0; k < binary.length; k += 1) bytes[k] = binary.charCodeAt(k)
  return bytes
}

/** Decode one backend day raster (risk_raster.py `build_day_raster`), or null. */
export function decodeDayRaster(raw, grid = DEFAULT_GRID) {
  const window = raw?.window
  if (!Array.isArray(window) || window.length !== 4 || !window.every(Number.isInteger) || typeof raw.mask !== 'string' || typeof raw.pixels !== 'string') return null
  const [i0, j0, w, h] = window
  let mask
  let pixels
  try {
    mask = base64Bytes(raw.mask)
    pixels = base64Bytes(raw.pixels)
  } catch {
    return null
  }
  const size = w * h
  const raster = {
    i0, j0, w, h,
    score: new Float32Array(size), // 0 = not drawn
    count: new Uint8Array(size),
    share1: new Float32Array(size),
    share2: new Float32Array(size),
    case1: new Uint16Array(size), // 1-based index into `sources`, 0 = none
    case2: new Uint16Array(size),
  }
  let n = 0
  for (let k = 0; k < size; k += 1) {
    if (!((mask[k >> 3] >> (7 - (k & 7))) & 1)) continue
    const o = n * 8
    if (o + 8 > pixels.length) break
    raster.score[k] = pixels[o] / grid.levels
    raster.count[k] = pixels[o + 1]
    raster.share1[k] = pixels[o + 2] / grid.levels
    raster.share2[k] = pixels[o + 3] / grid.levels
    raster.case1[k] = pixels[o + 4] | (pixels[o + 5] << 8)
    raster.case2[k] = pixels[o + 6] | (pixels[o + 7] << 8)
    n += 1
  }
  return raster
}

/** Display score at a point: bilinear between the four nearest raster cells
 * (cells not drawn count as 0, so a zone fades out at its edge). */
export function rasterScoreAt(raster, grid, lon, lat) {
  if (!raster) return 0
  const gx = (lon - grid.west) / grid.step_deg - 0.5 - raster.i0
  const gy = (lat - grid.south) / grid.step_deg - 0.5 - raster.j0
  const c0 = Math.floor(gx)
  const r0 = Math.floor(gy)
  if (c0 < -1 || r0 < -1 || c0 >= raster.w || r0 >= raster.h) return 0
  const fx = gx - c0
  const fy = gy - r0
  const at = (c, r) => (c < 0 || r < 0 || c >= raster.w || r >= raster.h ? 0 : raster.score[r * raster.w + c])
  return (at(c0, r0) * (1 - fx) + at(c0 + 1, r0) * fx) * (1 - fy) + (at(c0, r0 + 1) * (1 - fx) + at(c0 + 1, r0 + 1) * fx) * fy
}

/** Index of the raster cell holding a point, or -1. */
export function rasterCellIndex(raster, grid, lon, lat) {
  if (!raster) return -1
  const c = Math.floor((lon - grid.west) / grid.step_deg) - raster.i0
  const r = Math.floor((lat - grid.south) / grid.step_deg) - raster.j0
  return c < 0 || r < 0 || c >= raster.w || r >= raster.h ? -1 : r * raster.w + c
}

export function buildRiskFieldModel(timeline) {
  if (!isTimelineRenderable(timeline)) return null
  const frames = timelineFrames(timeline)
  const cells = []
  for (const cell of Array.isArray(timeline.cells) ? timeline.cells : []) {
    const lon = cell?.centroid?.longitude
    const lat = cell?.centroid?.latitude
    if (cell?.score_status !== 'SCORED' || !Number.isFinite(cell.bounded_score) || !(cell.band in BAND_RANK)) continue
    // Land-clipped display footprint; older snapshots only have the scope-clipped one.
    const geometry = cell.display_geometry ?? (cell.in_scope === false ? null : cell.geometry)
    if (!geometry?.type || !Number.isFinite(lon) || !Number.isFinite(lat)) continue
    cells.push({ id: cell.cell_id, centroid: [lon, lat], geometry, feature: { geometry } })
  }
  // Raster contributor order: the eligible sources, then the modelled new outbreaks.
  const sources = [
    ...(Array.isArray(timeline.sources) ? timeline.sources : []).map((s) => ({
      id: s?.source_id ?? null,
      coordinates: Number.isFinite(s?.longitude) && Number.isFinite(s?.latitude) ? [s.longitude, s.latitude] : null,
      recordDomain: s?.record_domain ?? null,
    })),
    ...(Array.isArray(timeline.possible_new_cases) ? timeline.possible_new_cases : []).map((p) => ({
      id: p?.id ?? null,
      coordinates: Number.isFinite(p?.longitude) && Number.isFinite(p?.latitude) ? [p.longitude, p.latitude] : null,
      recordDomain: 'POSSIBLE',
    })),
  ]
  const grid = rasterGrid(timeline)
  const decoded = new Map()
  return {
    // Fixed display bands: the same colour scale on every day and in every snapshot.
    bands: displayBands(timeline),
    key: timeline.snapshot_id ?? `${timeline.as_of}:${cells.length}`,
    frameCount: frames.length,
    cells,
    sources,
    grid,
    /** The decoded day-d raster (decoded once, on first use), or null. */
    rasterFor(day) {
      if (!decoded.has(day)) decoded.set(day, decodeDayRaster(frames[day]?.risk_field?.raster, grid))
      return decoded.get(day)
    },
    activeCasesByDay: frames.map((frame) => (Array.isArray(frame?.risk_field?.kernels) ? frame.risk_field.kernels.length : 0)),
    dates: frames.map((frame) => frame?.date ?? null),
    exploratoryFromDay: frames.findIndex((frame) => frame?.horizon_status === 'EXPLORATORY_BEYOND_D7_REACH_HORIZON'),
  }
}

/** Is the point on scored land (inside a backend cell footprint)? */
export function isOnScoredLand(model, lon, lat) {
  const point = [lon, lat]
  return (model?.cells ?? []).some((cell) => Math.abs(cell.centroid[0] - lon) < 0.06 && Math.abs(cell.centroid[1] - lat) < 0.06
    && isPointInsideDistrictFeature(point, cell.feature))
}

function kmBetween([lon1, lat1], [lon2, lat2]) {
  const kx = 111.32 * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180)
  return Math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * KM_PER_DEG_LAT)
}

/** Everything the hover card shows for one point on day `day`, or null where
 * nothing is drawn (unscored land or below the faint outer edge). */
export function probeRiskField(model, day, lon, lat) {
  if (!model || !Number.isFinite(lon) || !Number.isFinite(lat)) return null
  const d = Math.max(0, Math.min(model.frameCount - 1, Number.isInteger(day) ? day : 0))
  const raster = model.rasterFor(d)
  const score = rasterScoreAt(raster, model.grid, lon, lat)
  if (!(score >= (model.grid.min_score ?? DEFAULT_GRID.min_score)) || !isOnScoredLand(model, lon, lat)) return null
  const k = rasterCellIndex(raster, model.grid, lon, lat)
  const contributing = []
  if (k >= 0 && raster.score[k] > 0) {
    for (const [index, share] of [[raster.case1[k], raster.share1[k]], [raster.case2[k], raster.share2[k]]]) {
      const source = index > 0 ? model.sources[index - 1] : null
      if (!source?.coordinates) continue
      contributing.push({ sourceId: source.id, coordinates: source.coordinates, km: kmBetween(source.coordinates, [lon, lat]), share, recordDomain: source.recordDomain })
    }
  }
  const previous = d > 0 ? rasterScoreAt(model.rasterFor(d - 1), model.grid, lon, lat) : null
  const delta = previous == null ? null : score - previous
  const trend = delta == null ? null : delta > TREND_EPSILON ? 'increasing' : delta < -TREND_EPSILON ? 'decreasing' : 'stable'
  return {
    day: d, date: model.dates[d] ?? null, score, band: bandOfScore(score, model.bands),
    contributingCount: k >= 0 && raster.count[k] > 0 ? raster.count[k] : contributing.length,
    contributing, trend, delta,
    exploratory: model.exploratoryFromDay >= 0 && d >= model.exploratoryFromDay,
  }
}

// Legend colours per band; alpha falls with the band so low scores stay
// faint and the basemap stays readable.
export const BAND_RGBA = Object.freeze({
  high: [225, 45, 60, 0.82],
  elevated: [237, 106, 28, 0.72],
  moderate: [245, 200, 20, 0.6],
  low: [40, 190, 90, 0.42],
})
// Score distance from a band threshold over which colours blend (soft edges).
const BLEND = 0.04

/** Fixed display band of a bounded score. */
export function bandOfScore(score, bands = DEFAULT_DISPLAY_BANDS) {
  if (!Number.isFinite(score)) return null
  return (bands.find((b) => score >= b.min) ?? bands[bands.length - 1]).band
}

/** RGBA of a bounded score: its band's legend colour, blended half-way with
 * the neighbouring band exactly at a threshold (no hard stair-step edge). */
export function scoreColour(score, bands = DEFAULT_DISPLAY_BANDS) {
  const band = bandOfScore(score, bands)
  if (!band) return null
  const base = BAND_RGBA[band]
  const index = bands.findIndex((b) => b.band === band)
  const mix = (other, f) => base.map((v, i) => v + (other[i] - v) * f)
  const upper = index > 0 ? bands[index - 1] : null // next higher band
  const own = bands[index]
  if (upper && upper.min - score < BLEND) return mix(BAND_RGBA[upper.band], 0.5 * (1 - (upper.min - score) / BLEND))
  if (index < bands.length - 1 && score - own.min < BLEND) return mix(BAND_RGBA[bands[index + 1].band], 0.5 * (1 - (score - own.min) / BLEND))
  return base.slice()
}

/** Surface colour of a score: the band colour, with the faint outer edge
 * (`minScore` .. 0.15) fading in so a zone has no hard rim. */
export function surfaceColour(score, bands = DEFAULT_DISPLAY_BANDS, minScore = DEFAULT_GRID.min_score) {
  if (!(score >= minScore)) return null
  const rgba = scoreColour(score, bands)
  const lowTop = bands.find((b) => b.band === 'moderate')?.min ?? 0.15
  if (score < lowTop) rgba[3] *= Math.min(1, (score - minScore) / (lowTop - minScore) + 0.15)
  return rgba
}
