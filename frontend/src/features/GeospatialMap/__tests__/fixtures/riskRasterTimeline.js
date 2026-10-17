/**
 * FICTIONAL test snapshot with backend-format risk rasters
 * (risk_raster.py layout: bitset mask + 8-byte pixels), for the Risk Zones /
 * Future Risk Outlook tests. One case at (80.5, 6.0); its coloured block
 * grows from 3 x 3 cells (Day 0) by one ring per day; the centre score rises.
 */
export const GRID = { west: 79.4, south: 5.7, step_deg: 0.015, levels: 250, min_score: 0.03, min_share: 0.01 }
export const cellOf = (lon, lat) => [Math.floor((lon - GRID.west) / GRID.step_deg), Math.floor((lat - GRID.south) / GRID.step_deg)]

export function encodeRaster(drawn) {
  const keys = [...drawn.keys()].map((k) => k.split(',').map(Number))
  const i0 = Math.min(...keys.map(([i]) => i)); const j0 = Math.min(...keys.map(([, j]) => j))
  const w = Math.max(...keys.map(([i]) => i)) - i0 + 1; const h = Math.max(...keys.map(([, j]) => j)) - j0 + 1
  const mask = new Uint8Array(Math.ceil((w * h) / 8))
  const pixels = []
  for (let r = 0; r < h; r += 1) {
    for (let c = 0; c < w; c += 1) {
      const p = drawn.get(`${i0 + c},${j0 + r}`)
      if (!p) continue
      const k = r * w + c
      mask[k >> 3] |= 1 << (7 - (k & 7))
      pixels.push(Math.round(p.score * 250), p.count ?? 1, Math.round((p.share1 ?? 1) * 250), 0, p.case1 ?? 1, 0, 0, 0)
    }
  }
  const b64 = (bytes) => btoa(String.fromCharCode(...bytes))
  return { window: [i0, j0, w, h], drawn_cells: drawn.size, mask: b64(mask), pixels: b64(pixels) }
}

const [CI, CJ] = cellOf(80.5, 6.0)
function block(radius, centreScore) {
  const drawn = new Map()
  for (let di = -radius; di <= radius; di += 1) {
    for (let dj = -radius; dj <= radius; dj += 1) {
      const ring = Math.max(Math.abs(di), Math.abs(dj))
      drawn.set(`${CI + di},${CJ + dj}`, { score: Math.max(0.05, centreScore - ring * 0.2) })
    }
  }
  return drawn
}

const square = (lon, lat, d) => ({ type: 'Polygon', coordinates: [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]] })
// District: a 0.06 deg square around the case (cells beyond it are outside).
export const DISTRICT = { type: 'Feature', properties: { shapeName: 'Testshire' }, geometry: square(80.5, 6.0, 0.06) }

const DATES = Array.from({ length: 15 }, (_, d) => `2026-10-${String(17 + d).padStart(2, '0')}`)
export const RISK_TIMELINE = {
  status: 'OK',
  snapshot_id: 'stl_fictional_raster',
  as_of: DATES[0],
  provenance: { risk_field_rule: { raster: GRID } },
  sources: [{ source_id: 'S1', longitude: 80.5, latitude: 6.0, record_domain: 'OPERATIONAL' }],
  cells: [{ cell_id: 'c', centroid: { longitude: 80.5, latitude: 6.0 }, score_status: 'SCORED', bounded_score: 0.6, band: 'elevated', in_scope: true, geometry: square(80.5, 6.0, 0.3) }],
  frames: DATES.map((date, d) => ({
    day: d,
    date,
    horizon_status: d === 0 ? 'AS_OF_OBSERVED_CONTEXT' : d <= 7 ? 'WITHIN_D1_D7_REACH_HORIZON' : 'EXPLORATORY_BEYOND_D7_REACH_HORIZON',
    risk_field: { kernels: [{}], raster: encodeRaster(block(Math.min(1 + d, 6), Math.min(0.8, 0.6 + d * 0.03))) },
  })),
}
