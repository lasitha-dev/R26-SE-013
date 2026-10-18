import React from 'react'
import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { buildNationalTimelineLayers } from '../adapters/spatialTimelineView'
import CorridorPopup from '../components/CorridorPopup'
import { buildTrajectoryLabels } from '../components/trajectoryLabels'
import { clusterForCase } from '../context/useStClusters'

afterEach(cleanup)

const RESULT = {
  clusters: [{ cluster_id: 'C1', member_count: 4, distinct_farm_or_support_count: 3, start_date: '2026-10-10', end_date: '2026-10-12', member_locations: [{ longitude: 80.5, latitude: 6.0 }] }],
  noise_locations: [[6.3, 80.9]],
}

// Engine 3.0 snapshot: S1 has a path; S2 has no directional evidence.
const path = [[80.5, 6.0], [80.505, 6.0], [80.51, 6.0], [80.515, 6.0]]
const frame = (day, upto) => ({
  day, date: `2026-10-${17 + day}`, horizon_status: day ? 'WITHIN_D1_D7_REACH_HORIZON' : 'AS_OF_OBSERVED_CONTEXT',
  reach: { nominal_reach_km: day ? 3.9 * day : null, interval_km: day ? [3.5 * day, 4.3 * day] : null },
  source_paths: [{
    source_id: 'S1', day, geometry: upto ? { type: 'LineString', coordinates: path.slice(0, upto + 1) } : null, front: path[upto],
    front_bearing_deg: upto ? 90 : null, length_km: upto * 0.5, stop_reason: upto === 3 ? 'NEXT_STEP_OFF_LAND' : null,
    heading_basis: upto ? { confidence: 0.62, wind_toward_deg: 80, wind_weight: 0.7, wind_kind: 'OPEN_METEO_FORECAST', cattle_here_per_km2: 6, cattle_ahead_per_km2: 9, case_bearing_deg: 95, case_share: 0.43, held_at_coast: upto === 3 } : null, origin_basis: { method: '8B.3', directional_share: 0.43, cases_within_25km: 2 },
    reach_interval_km: day ? [3.5 * day, 4.3 * day] : null, distance_check: upto ? { displacement_km: upto * 0.5, drawn_km: upto * 0.5 } : null,
  }],
})
const TIMELINE = {
  status: 'OK', disease: 'Lumpy skin disease', snapshot_id: 'stl_x', as_of: '2026-10-17',
  sources: [{ source_id: 'S1', longitude: 80.5, latitude: 6.0, record_domain: 'OPERATIONAL' }, { source_id: 'S2', longitude: 80.9, latitude: 6.3, record_domain: 'OPERATIONAL' }],
  sources_without_path: [{ source_id: 'S2', reason: 'NO_DIRECTIONAL_EVIDENCE', origin_basis: { directional_share: 0, cases_within_25km: 1 } }],
  source_paths: [{ source_id: 'S1', geometry: { type: 'LineString', coordinates: path }, day_front_index: [0, 2, 3] }],
  frames: [frame(0, 0), frame(1, 2), frame(2, 3)],
}

describe('Trajectory from model evidence only', () => {
  it('Test A: Day 0 shows the cases only -- no line, arrow or future end point', () => {
    const layers = buildNationalTimelineLayers(TIMELINE, 0)
    expect(layers.paths.features).toHaveLength(0)
    expect(layers.fronts.features).toHaveLength(0)
    expect(layers.remaining.features).toHaveLength(0)
    expect(layers.origins.features).toHaveLength(2)
  })

  it('Test D: a later day shows only the path so far with its heading factors, never the part still ahead', () => {
    const layers = buildNationalTimelineLayers(TIMELINE, 1)
    expect(layers.paths.features[0].geometry.coordinates).toEqual(path.slice(0, 3))
    expect(layers.remaining.features).toHaveLength(0)
    expect(layers.fronts.features[0].properties).toMatchObject({ confidence: 0.62, windTowardDeg: 80, cattleAhead: 9, caseShare: 0.43, reachLowKm: 3.5, reachHighKm: 4.3, heldAtCoast: false })
    const origin = layers.origins.features.find((f) => f.properties.sourceId === 'S2').properties
    expect(origin.noPathReason).toBe('NO_DIRECTIONAL_EVIDENCE')
  })

  it('Test B/G/I: no-evidence cases are labelled, a coast stop is labelled, no point at sea', () => {
    const layers = buildNationalTimelineLayers(TIMELINE, 2)
    const labels = buildTrajectoryLabels({ fronts: layers.fronts, origins: layers.origins, findPlace: () => ({ name: 'Dondra' }) })
    expect(labels.features.map((f) => f.properties.label)).toEqual(['Day 2 · near Dondra · stops at coast', 'Insufficient directional evidence'])
  })
})

describe('selected case -> its cluster result (no new trajectory is invented)', () => {
  it('matches the case by farm GPS: member, noise, loading or unavailable', () => {
    expect(clusterForCase({ status: 'ready', data: RESULT }, [80.5001, 6.0])).toMatchObject({ status: 'member', memberCount: 4, supportCount: 3 })
    expect(clusterForCase({ status: 'ready', data: RESULT }, [80.9, 6.3])).toEqual({ status: 'noise' })
    expect(clusterForCase({ status: 'loading' }, [80.5, 6.0])).toEqual({ status: 'loading' })
    expect(clusterForCase({ status: 'error', data: null }, [80.5, 6.0])).toEqual({ status: 'unavailable' })
    expect(clusterForCase({ status: 'ready', data: RESULT }, null)).toBeNull()
  })

  it('a case without a model direction says why, shows its cluster and its farm risk', () => {
    render(<CorridorPopup
      corridor={{ sourceId: 'OP:1', isOrigin: true, bearingDeg: null, lengthKm: 11.8, day: 3, noPathReason: 'NO_DIRECTIONAL_EVIDENCE', recordDomain: 'OPERATIONAL' }}
      cluster={{ status: 'noise' }}
      risk={{ band: 'elevated', score: 0.55, trend: 'stable', contributingCount: 1 }}
      onClose={vi.fn()}
    />)
    const text = document.body.textContent
    expect(text).toContain('Insufficient directional evidence')
    expect(text).toContain('give no preferred direction here')
    expect(text).toContain('Not in any space-time cluster')
    expect(text).toContain('Elevated · 0.55 · stable · 1 case')
    expect(text).toContain('Wind and cattle are labelled extensions')
    expect(text).not.toMatch(/Net wind \(this day\)|Cattle \(here/) // origin card: no path factors
  })

  it('a path card shows the factors of the day, the coast wait and its distance check', () => {
    render(<CorridorPopup corridor={{ sourceId: 'OP:2', bearingDeg: 95, lengthKm: 6.2, displacementKm: 6.1, day: 2, heldAtCoast: true, confidence: 0.62, windTowardDeg: 80, windWeight: 0.7, windSpeedMs: 4, windKind: 'OPEN_METEO_FORECAST', cattleHere: 6, cattleAhead: 9, caseBearingDeg: 95, caseShare: 0.43, casesWithin25Km: 2 }} onClose={vi.fn()} />)
    const text = document.body.textContent
    expect(text).toContain('Waited at the coast')
    expect(text).toContain('Straight-line from farm6.1 km')
    expect(text).toContain('Direction confidence62%')
    expect(text).toContain('toward E · 70% steady · 14 km/h · forecast')
    expect(text).toContain('6 → 9 /km²')
    expect(text).toContain('push toward E (43%) · 2 ≤ 25 km')
  })
})
