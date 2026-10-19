import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { findDistrictFeature, isPointInsideDistrictFeature } from '../adapters/districtGeometry'
import { bandOfScore, buildRiskFieldModel, rasterScoreAt } from '../adapters/riskFieldModel'
import { buildRiskOutlookRows } from '../adapters/riskOutlook'
import { buildMyAreaTimelineView } from '../adapters/spatialTimelineView'
import { buildTrajectoryLabels } from '../components/trajectoryLabels'
import fixture from './fixtures/spatialTimeline.galleRaster.json'

// Real engine output (3 FICTIONAL farms, Galle district view; fixtures/spatialTimeline.galleRaster.json).
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const GALLE = findDistrictFeature(JSON.parse(readFileSync(join(ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8')), 'Galle')
const MODEL = buildRiskFieldModel(fixture)
const ROWS = buildRiskOutlookRows(MODEL, GALLE)
const S0 = 3.9461
const view = (day) => buildMyAreaTimelineView(fixture, day, 'Galle')
// Place lookup stand-in: the label follows the modelled point (real labels use basemap OSM places).
const findPlace = ([lon, lat]) => ({ name: `${lat.toFixed(2)},${lon.toFixed(2)}` })

describe('My Area Future Impact timeline: Days 0, 3, 7, 13, 14 from one backend snapshot', () => {
  it('Day 0-14 dates are the as-of date + d (the backend Asia/Colombo dates, never re-derived)', () => {
    const dates = view(0).dates
    expect(dates).toHaveLength(15)
    expect(dates[0]).toBe(fixture.as_of)
    dates.forEach((date, d) => expect(date).toBe(fixture.frames[d].date))
    for (let d = 1; d < dates.length; d += 1) expect(Date.parse(dates[d]) - Date.parse(dates[d - 1])).toBe(86400000)
  })

  it('Day 0: source markers and the baseline zones, but no trajectory line, arrow or label', () => {
    const v = view(0)
    expect(v.origins.features).toHaveLength(fixture.sources.length)
    expect(v.paths.features).toHaveLength(0)
    expect(v.fronts.features).toHaveLength(0) // fronts carry the arrowheads
    expect(buildTrajectoryLabels({ fronts: v.fronts, origins: v.origins, findPlace }).features).toHaveLength(0)
    expect(ROWS[0].coloredKm2).toBeGreaterThan(0) // each farm's own Day-0 zone
    for (const source of fixture.sources) {
      const score = rasterScoreAt(MODEL.rasterFor(0), MODEL.grid, source.longitude, source.latitude)
      expect(['elevated', 'high']).toContain(bandOfScore(score, MODEL.bands)) // a farm's own zone: orange, red where farms overlap
    }
  })

  it.each([3, 7, 13, 14])('Day %i: day-specific direction within the reach; labels follow the modelled front', (day) => {
    const v = view(day)
    expect(v.fronts.features).toHaveLength(fixture.source_paths.length)
    for (const f of v.fronts.features) expect(f.properties.lengthKm).toBeLessThanOrEqual(Math.min(S0 * day, 25) + 0.01)
    const labels = buildTrajectoryLabels({ fronts: v.fronts, origins: v.origins, findPlace }).features.map((f) => f.properties.label)
    for (const f of v.fronts.features) {
      const [lon, lat] = f.geometry.coordinates
      expect(labels.some((l) => l.startsWith(`Day ${day} · near ${lat.toFixed(2)},${lon.toFixed(2)}`))).toBe(true)
    }
    // A case without directional evidence gets a label, never an invented line.
    expect(labels.filter((l) => l === 'Insufficient directional evidence')).toHaveLength(fixture.sources_without_path.length)
  })

  it('the front moves day by day (labels change with the modelled position), never jumping', () => {
    const front = (day) => view(day).fronts.features.find((f) => f.properties.sourceId === fixture.source_paths[0].source_id).geometry.coordinates
    expect(front(3)).not.toEqual(front(7))
    const km = ([a, b], [c, d]) => Math.hypot((c - a) * 110.6 * Math.cos((b * Math.PI) / 180), (d - b) * 110.6)
    expect(km(front(3), front(7))).toBeLessThanOrEqual(4 * S0 + 0.5)
  })

  it('outlook rows are exactly the map rasters inside Galle (selected day, fixed bands, no forced increase)', () => {
    for (const day of [0, 3, 7, 13, 14]) {
      const raster = MODEL.rasterFor(day)
      let max = 0
      for (let r = 0; r < raster.h; r += 1) {
        for (let c = 0; c < raster.w; c += 1) {
          const score = raster.score[r * raster.w + c]
          if (!(score > 0)) continue
          const lon = MODEL.grid.west + (raster.i0 + c + 0.5) * MODEL.grid.step_deg
          const lat = MODEL.grid.south + (raster.j0 + r + 0.5) * MODEL.grid.step_deg
          if (isPointInsideDistrictFeature([lon, lat], GALLE)) max = Math.max(max, score)
        }
      }
      expect(ROWS[day].day).toBe(day)
      expect(ROWS[day].maxScore).toBeCloseTo(max, 9)
      expect(ROWS[day].maxBand).toBe(bandOfScore(max, MODEL.bands))
    }
    expect(ROWS.map((r) => r.exploratory)).toEqual(fixture.frames.map((f) => f.horizon_status === 'EXPLORATORY_BEYOND_D7_REACH_HORIZON'))
  })

  it('the outside source is listed as influencing only from its backend first-influence day', () => {
    const ext = fixture.district_influence.sources.find((s) => !s.inside_district)
    const first = ext.first_influence_day
    const statusOn = (day) => view(day).influences.find((i) => i.sourceId === ext.source_id)
    expect(statusOn(0).status).toBe(`FROM DAY ${first}`)
    if (first > 1) expect(statusOn(first - 1).district.influencing).toBe(false)
    expect(statusOn(first).status).toBe('INFLUENCING MY DISTRICT')
    for (const day of [13, 14]) expect(statusOn(day).district.areaKm2).toBe(ext.by_day[day].area_km2)
    expect(view(7).influences.slice(0, 2).every((i) => i.district.insideDistrict)).toBe(true) // local sources listed first
  })
})
