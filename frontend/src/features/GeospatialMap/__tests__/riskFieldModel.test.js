import { describe, expect, it } from 'vitest'

import {
  BAND_RGBA, DEFAULT_DISPLAY_BANDS, bandOfScore, buildRiskFieldModel, decodeDayRaster, probeRiskField, rasterCellIndex, rasterScoreAt,
  scoreColour, surfaceColour,
} from '../adapters/riskFieldModel'
import { riskHoverHtml } from '../components/riskHoverCard'
import { pointAlong } from '../components/stageLayers'

const GRID = { west: 79.4, south: 5.7, step_deg: 0.015, levels: 250, min_score: 0.03, min_share: 0.01 }
const square = (lon, lat, d = 0.3) => ({ type: 'Polygon', coordinates: [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]] })
const cell = (id, lon, lat) => ({
  cell_id: id, centroid: { longitude: lon, latitude: lat }, score_status: 'SCORED', in_scope: true,
  raw_c0_score: 0.5, bounded_score: 0.4, band: 'elevated', tier: 'high', geometry: square(lon, lat),
})
// Grid cell (i, j) holding a point, and its centre.
const cellOf = (lon, lat) => [Math.floor((lon - GRID.west) / GRID.step_deg), Math.floor((lat - GRID.south) / GRID.step_deg)]
const centreOf = (i, j) => [GRID.west + (i + 0.5) * GRID.step_deg, GRID.south + (j + 0.5) * GRID.step_deg]

/** Encode a raster the way risk_raster.py `build_day_raster` does.
 * `drawn`: Map of "i,j" -> { score, count, share1, share2, case1, case2 }. */
function encodeRaster(drawn) {
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
      pixels.push(Math.round(p.score * 250), p.count, Math.round(p.share1 * 250), Math.round((p.share2 ?? 0) * 250), p.case1 & 255, p.case1 >> 8, (p.case2 ?? 0) & 255, (p.case2 ?? 0) >> 8)
    }
  }
  const b64 = (bytes) => btoa(String.fromCharCode(...bytes))
  return { window: [i0, j0, w, h], drawn_cells: drawn.size, mask: b64(mask), pixels: b64(pixels) }
}

// A 3 x 3 block of drawn cells around the case S1 at (80.5, 6.0); on Day 1 a
// second case S2 adds to the centre cell; on Day 2 the backend score is lower.
const [CI, CJ] = cellOf(80.5, 6.0)
const block = (centre, ring, extra = {}) => new Map(
  [-1, 0, 1].flatMap((di) => [-1, 0, 1].map((dj) => [`${CI + di},${CJ + dj}`, { score: di || dj ? ring : centre, count: 1, share1: 1, case1: 1, ...(di || dj ? {} : extra) }])),
)
const TIMELINE = {
  status: 'OK',
  snapshot_id: 'stl_test',
  provenance: {
    display_bands: [{ band: 'high', min: 0.7 }, { band: 'elevated', min: 0.4 }, { band: 'moderate', min: 0.15 }, { band: 'low', min: 0 }],
    risk_field_rule: { raster: GRID },
  },
  sources: [{ source_id: 'S1', longitude: 80.5, latitude: 6.0, record_domain: 'OPERATIONAL' }, { source_id: 'S2', longitude: 80.52, latitude: 6.0, record_domain: 'HISTORICAL' }],
  cells: [cell('a', 80.5, 6.0), { ...cell('unscored', 81.5, 6.0), score_status: 'NOT_SCORED' }],
  frames: [
    { day: 0, date: '2026-10-17', risk_field: { kernels: [{}], raster: encodeRaster(block(0.6, 0.2)) } },
    { day: 1, date: '2026-10-18', risk_field: { kernels: [{}, {}], raster: encodeRaster(block(0.8, 0.3, { count: 2, share1: 0.7, share2: 0.3, case2: 2 })) } },
    { day: 2, date: '2026-10-19', horizon_status: 'EXPLORATORY_BEYOND_D7_REACH_HORIZON', risk_field: { kernels: [{}], raster: encodeRaster(block(0.35, 0.1, { case1: 2 })) } },
    { day: 3, date: '2026-10-20', risk_field: { kernels: [], raster: null } },
  ],
}
const [CLON, CLAT] = centreOf(CI, CJ)

describe('risk field model (backend day rasters)', () => {
  it('decodes the backend raster layout exactly', () => {
    const raster = decodeDayRaster(TIMELINE.frames[1].risk_field.raster, GRID)
    expect([raster.w, raster.h]).toEqual([3, 3])
    const k = rasterCellIndex(raster, GRID, CLON, CLAT)
    expect(k).toBe(4) // the centre of the 3 x 3 block
    expect(raster.score[k]).toBeCloseTo(0.8, 6)
    expect([raster.count[k], raster.case1[k], raster.case2[k]]).toEqual([2, 1, 2])
    expect(raster.share1[k]).toBeCloseTo(0.7, 6)
    expect(decodeDayRaster(null)).toBeNull()
    expect(decodeDayRaster({ window: [0, 0, 1, 1], mask: '%%%', pixels: '' })).toBeNull()
  })

  it('interpolates between backend cells, never above the larger neighbour, fading to 0 outside', () => {
    const raster = decodeDayRaster(TIMELINE.frames[0].risk_field.raster, GRID)
    expect(rasterScoreAt(raster, GRID, CLON, CLAT)).toBeCloseTo(0.6, 6)
    const between = rasterScoreAt(raster, GRID, CLON + GRID.step_deg / 2, CLAT)
    expect(between).toBeCloseTo(0.4, 6)
    expect(rasterScoreAt(raster, GRID, CLON + 1.5 * GRID.step_deg, CLAT)).toBeCloseTo(0.1, 6) // half-way to an undrawn cell
    expect(rasterScoreAt(raster, GRID, CLON + 5 * GRID.step_deg, CLAT)).toBe(0)
    expect(rasterScoreAt(null, GRID, CLON, CLAT)).toBe(0)
  })

  it('builds one lazily decoded raster per day and only scored cells as drawable land', () => {
    const model = buildRiskFieldModel(TIMELINE)
    expect(model.frameCount).toBe(4)
    expect(model.cells.map((c) => c.id)).toEqual(['a'])
    expect(model.rasterFor(1)).toBe(model.rasterFor(1)) // decoded once
    expect(model.rasterFor(3)).toBeNull()
    expect(model.activeCasesByDay).toEqual([1, 2, 1, 0])
    expect(buildRiskFieldModel({ status: 'NO_ELIGIBLE_SOURCES', frames: [] })).toBeNull()
  })

  it('hover probe: score, band, contributing cases, trend and the exploratory flag', () => {
    const model = buildRiskFieldModel(TIMELINE)
    const p0 = probeRiskField(model, 0, CLON, CLAT)
    expect(p0.band).toBe('elevated')
    expect(p0.trend).toBeNull() // Day 0 has no previous day
    const p1 = probeRiskField(model, 1, CLON, CLAT)
    expect(p1.band).toBe('high') // two cases overlapping
    expect(p1.contributingCount).toBe(2)
    expect(p1.contributing.map((c) => c.sourceId)).toEqual(['S1', 'S2'])
    expect(p1.contributing[0].km).toBeLessThan(1.5)
    expect(p1.trend).toBe('increasing')
    const p2 = probeRiskField(model, 2, CLON, CLAT)
    expect(p2.trend).toBe('decreasing')
    expect(p2.exploratory).toBe(true)
    expect(probeRiskField(model, 3, CLON, CLAT)).toBeNull() // nothing drawn that day
    expect(probeRiskField(model, 0, 81.5, 6.0)).toBeNull() // unscored land
  })

  it('hover card names the cases, their share and the place, and escapes names', () => {
    const model = buildRiskFieldModel(TIMELINE)
    const html = riskHoverHtml(probeRiskField(model, 1, CLON, CLAT), {
      pointPlace: { name: 'Akuressa', km: 1 }, district: 'Matara', casePlace: (c) => (c[0] === 80.5 ? { name: '<Kamburupitiya>' } : null),
    })
    expect(html).toContain('Day 1')
    expect(html).toContain('Contributing cases: 2')
    expect(html).toContain('Near Akuressa · Matara district')
    expect(html).toContain('&lt;Kamburupitiya&gt; case')
    expect(html).toContain('Historical record')
    expect(html).toContain('70%')
    expect(html).toContain('Increasing')
    expect(html).toContain('not an infection probability')
    expect(riskHoverHtml(null)).toBe('')
  })

  it('trajectory flow points travel along the backend line geometry', () => {
    const line = [[80, 6], [80, 6.2], [80.2, 6.2]]
    expect(pointAlong(line, 0)).toEqual([80, 6])
    const quarter = pointAlong(line, 0.25)
    expect(quarter[0]).toBeCloseTo(80, 9)
    expect(quarter[1]).toBeCloseTo(6.1, 9)
    expect(pointAlong(line, 1)).toEqual([80.2, 6.2])
  })
})

describe('score colour follows the fixed display bands', () => {
  it('a band centre takes its legend colour; red only at >= 0.70', () => {
    expect(bandOfScore(0.86)).toBe('high')
    expect(bandOfScore(0.7)).toBe('high')
    expect(bandOfScore(0.6999)).toBe('elevated')
    expect(bandOfScore(0.63)).toBe('elevated') // a single isolated source peaks here
    expect(bandOfScore(0.2)).toBe('moderate')
    expect(bandOfScore(0.05)).toBe('low')
    expect(scoreColour(0.9)).toEqual(BAND_RGBA.high)
    expect(scoreColour(0.55)).toEqual(BAND_RGBA.elevated)
    expect(scoreColour(0.27)).toEqual(BAND_RGBA.moderate)
    expect(scoreColour(0.08)).toEqual(BAND_RGBA.low)
    expect(scoreColour(null)).toBeNull()
    expect(DEFAULT_DISPLAY_BANDS.map((b) => b.band)).toEqual(['high', 'elevated', 'moderate', 'low'])
  })

  it('blends only near a threshold, half-way exactly at it (no hard stair-step)', () => {
    const at = scoreColour(0.4)
    const half = BAND_RGBA.elevated.map((v, i) => (v + BAND_RGBA.moderate[i]) / 2)
    at.forEach((v, i) => expect(v).toBeCloseTo(half[i], 6))
  })

  it('the green outer edge fades in instead of ending in a hard rim', () => {
    expect(surfaceColour(0.02)).toBeNull()
    expect(surfaceColour(0.04)[3]).toBeLessThan(surfaceColour(0.1)[3])
    expect(surfaceColour(0.3)).toEqual(scoreColour(0.3))
  })
})

describe('modeled possible new cases in the risk field', () => {
  it('possible cases follow the sources in raster contributor order and are named as possible, not verified', () => {
    const possible = { id: 'POSSIBLE:F9', farm_id: 'F9', longitude: 80.51, latitude: 6.0, seed_day: 1, seed_score: 0.42 }
    const timeline = {
      ...TIMELINE,
      possible_new_cases: [possible],
      frames: [
        TIMELINE.frames[0],
        { ...TIMELINE.frames[1], risk_field: { kernels: [{}, {}], raster: encodeRaster(block(0.8, 0.3, { count: 2, share1: 0.6, share2: 0.4, case2: 3 })) } },
      ],
    }
    const model = buildRiskFieldModel(timeline)
    const probe = probeRiskField(model, 1, CLON, CLAT)
    expect(probe.contributing.map((c) => c.sourceId)).toEqual(['S1', 'POSSIBLE:F9'])
    expect(probe.contributing[1].recordDomain).toBe('POSSIBLE')
    const html = riskHoverHtml(probe, { district: 'Matara' })
    expect(html).toContain('New outbreak (modelled)')
    expect(html).not.toContain('Historical record')
  })
})
