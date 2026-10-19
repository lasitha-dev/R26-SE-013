import { describe, expect, it } from 'vitest'

import { buildNationalTimelineLayers } from '../adapters/spatialTimelineView'

const coords = [[80.56, 5.95], [80.565, 5.951], [80.57, 5.952], [80.575, 5.954], [80.58, 5.957]]
const path = (day, upto) => ({
  path_id: `path:d${day}:S1`, source_id: 'S1', day,
  geometry: upto >= 1 ? { type: 'LineString', coordinates: coords.slice(0, upto + 1) } : null,
  front: coords[upto], front_bearing_deg: upto >= 1 ? 72 : null, length_km: upto * 0.5, stop_reason: null,
})
const TIMELINE = {
  status: 'OK', disease: 'Lumpy skin disease', as_of: '2026-08-31',
  sources: [{ source_id: 'S1', longitude: 80.56, latitude: 5.95, record_domain: 'OPERATIONAL' }],
  source_directions: [{ source_id: 'S1', bearing_deg: 80 }],
  source_paths: [{ source_id: 'S1', geometry: { type: 'LineString', coordinates: coords }, day_front_index: [0, 2, 4] }],
  frames: [
    { day: 0, date: '2026-08-31', source_paths: [path(0, 0)], source_corridors: [] },
    { day: 1, date: '2026-09-01', source_paths: [path(1, 2)], source_corridors: [] },
    { day: 2, date: '2026-09-02', source_paths: [path(2, 4)], source_corridors: [] },
  ],
}

describe('Trajectory uses the backend day-by-day source paths', () => {
  it('Day 0 draws no path, arrow or remaining preview -- only the source', () => {
    const layers = buildNationalTimelineLayers(TIMELINE, 0)
    expect(layers.paths.features).toHaveLength(0)
    expect(layers.fronts.features).toHaveLength(0)
    expect(layers.remaining.features).toHaveLength(0)
    expect(layers.origins.features).toHaveLength(1)
  })

  it('a later day draws the path travelled so far and its front (arrow), never the part still ahead', () => {
    const layers = buildNationalTimelineLayers(TIMELINE, 1)
    expect(layers.paths.features[0].geometry.coordinates).toEqual(coords.slice(0, 3)) // curved backend path, not a straight corridor
    expect(layers.fronts.features[0].geometry.coordinates).toEqual(coords[2])
    expect(layers.fronts.features[0].properties).toMatchObject({ sourceId: 'S1', bearingDeg: 72, day: 1 })
    expect(layers.remaining.features).toHaveLength(0) // no future line or end point
    expect(buildNationalTimelineLayers(TIMELINE, 2).remaining.features).toHaveLength(0)
  })

  it('an older snapshot without source_paths still falls back to its corridors', () => {
    const corridor = { source_id: 'S1', bearing_deg: 80, geometry: { type: 'LineString', coordinates: [[80.56, 5.95], [80.6, 5.96]] }, length_km: 4, nominal_reach_km: 4 }
    const older = { ...TIMELINE, source_paths: undefined, frames: TIMELINE.frames.map((f) => ({ day: f.day, date: f.date, source_corridors: f.day ? [corridor] : [] })) }
    expect(buildNationalTimelineLayers(older, 1, { landDomain: undefined }).paths.features).toHaveLength(1)
    expect(buildNationalTimelineLayers(older, 1).remaining.features).toHaveLength(0)
  })
})
