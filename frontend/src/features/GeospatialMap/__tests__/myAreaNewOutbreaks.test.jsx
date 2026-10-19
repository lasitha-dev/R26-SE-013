// New outbreaks in the vet's district (My Area Future Impact). FICTIONAL frames.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { buildAreaExplainer } from '../adapters/areaExplainer'
import { buildMyAreaTimelineView, buildPossibleCases } from '../adapters/spatialTimelineView'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const line = (coords) => ({ type: 'LineString', coordinates: coords })
// One existing outbreak whose front became a new outbreak on Day 1; on Day 3
// the old path stops at the hand-over point and the new outbreak moves on.
const TIMELINE = {
  status: 'OK', as_of: '2026-10-17', horizon_days: 3, disease: 'Lumpy skin disease',
  sources: [{ source_id: 'S1', record_domain: 'OPERATIONAL', latitude: 6.0, longitude: 80.5, observation_date: '2026-10-16', member_record_ids: ['c1'] }],
  possible_new_cases: [{ id: 'POSSIBLE:S1', farm_id: null, latitude: 6.0, longitude: 80.536, seed_day: 1, seed_date: '2026-10-18', seed_score: 0.47, generation: 1, arrival: 'FIRST_MOVE_INSIDE_DISTRICT', triggered_by: ['S1'] }],
  provenance: { display_bands: [{ band: 'high', min: 0.7 }, { band: 'elevated', min: 0.4 }, { band: 'moderate', min: 0.15 }, { band: 'low', min: 0 }] },
  cells: [],
  frames: [0, 1, 2, 3].map((day) => ({
    day, date: `2026-10-${17 + day}`, horizon_status: day === 0 ? 'AS_OF' : 'EVALUATED', reach: { nominal_reach_km: day ? 3.9 * day : null },
    source_paths: day === 0 ? [] : [
      { source_id: 'S1', geometry: line([[80.5, 6.0], [80.536, 6.0]]), front: [80.536, 6.0], front_bearing_deg: 90, handover_day: 1, handed_over_to: 'POSSIBLE:S1' },
      ...(day >= 2 ? [{ source_id: 'POSSIBLE:S1', possible_new_case: true, geometry: line([[80.536, 6.0], [80.536 + 0.036 * (day - 1), 6.01]]), front: [80.536 + 0.036 * (day - 1), 6.01], front_bearing_deg: 80 }] : []),
    ],
    risk_field: { kernels: [], raster: null },
  })),
}

describe('existing outbreak hands over to a new outbreak', () => {
  it('the old path stays drawn to the hand-over point but has no arrow there; the new path is pink', () => {
    const view = buildMyAreaTimelineView(TIMELINE, 3, 'Testshire')
    const old = view.paths.features.find((f) => f.properties.sourceId === 'S1')
    const created = view.paths.features.find((f) => f.properties.sourceId === 'POSSIBLE:S1')
    expect(old.properties).toMatchObject({ handedOverTo: 'POSSIBLE:S1', handoverDay: 1, possibleNewCase: false })
    expect(created.properties.possibleNewCase).toBe(true)
    expect(view.fronts.features.map((f) => f.properties.sourceId)).toEqual(['POSSIBLE:S1'])
  })

  it('the pink marker appears on its day with the new label', () => {
    expect(buildPossibleCases(TIMELINE, { day: 0 }).features).toHaveLength(0)
    const [marker] = buildPossibleCases(TIMELINE, { day: 1 }).features
    expect(marker.properties).toMatchObject({ label: 'New outbreak · Day 1', newToday: true, arrival: 'FIRST_MOVE_INSIDE_DISTRICT' })
  })
})

describe('explainer names the new outbreaks', () => {
  const base = { districtName: 'Testshire', futureMode: true, timelineOk: true, asOf: '2026-10-17',
    summary: { frame: { day: 2, date: '2026-10-19', count: 4, horizonStatus: 'EVALUATED' }, risk: { band: 'elevated', peakScore: 0.6 }, area: { coloredKm2: 50, share: 0.05 } } }
  const outbreaks = [
    { seedDay: 1, place: 'Fictional Town A', local: true, causePlace: 'Fictional Town A' },
    { seedDay: 6, place: 'Fictional Town B', local: false, causePlace: 'Otherland' },
  ]
  it('started ones by the selected day, else the first upcoming one', () => {
    const day2 = buildAreaExplainer({ ...base, newOutbreaks: outbreaks }).text
    expect(day2).toContain('1 new outbreak is modelled in Testshire by Day 2: near Fictional Town A from Day 1 (first move of the local outbreak)')
    expect(day2).not.toContain('Fictional Town B')
    const day0 = buildAreaExplainer({ ...base, summary: { ...base.summary, frame: { ...base.summary.frame, day: 0 } }, newOutbreaks: outbreaks }).text
    expect(day0).toContain('The first new outbreak in Testshire is modelled near Fictional Town A from Day 1')
    const day7 = buildAreaExplainer({ ...base, summary: { ...base.summary, frame: { ...base.summary.frame, day: 7 } }, newOutbreaks: outbreaks }).text
    expect(day7).toContain('near Fictional Town B from Day 6 (arriving from Otherland)')
  })
})

describe('map styling', () => {
  const canvas = readFileSync(join(ROOT, 'components', 'MyAreaMapCanvas.jsx'), 'utf-8')
  it('existing outbreaks are small red hollow rings; new outbreaks and their paths are pink with a hover card', () => {
    expect(canvas).toContain("const EXISTING_OUTBREAK_RED = '#ef4444'")
    expect(canvas).toContain("'circle-color': 'rgba(0,0,0,0)',\n            'circle-stroke-color': EXISTING_OUTBREAK_RED,".replace(/\n/g, canvas.includes('\r\n') ? '\r\n' : '\n'))
    expect(canvas).toContain("const NEW_OUTBREAK_PINK = '#ec4899'")
    expect(canvas).toContain("['case', ['boolean', ['get', 'possibleNewCase'], false], NEW_OUTBREAK_PINK, '#8B5CF6']")
    expect(canvas).toContain("map.on('mousemove', 'my-area-possible-case-ring'")
  })
  it('the district fit is kept on resize until the vet moves the camera', () => {
    expect(canvas).toContain('districtFitRef.current = districtBounds')
    expect(canvas).toContain("map.on('movestart', (e) => { if (e?.originalEvent) userMovedCameraRef.current = true })")
  })
})
