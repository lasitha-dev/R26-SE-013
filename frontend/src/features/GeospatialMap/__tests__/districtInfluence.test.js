import { describe, expect, it } from 'vitest'

import { buildMyAreaTimelineView, districtInfluenceStatus } from '../adapters/spatialTimelineView'

// Backend `district_influence` entry shape (engine `_district_influence`), FICTIONAL values:
// an external source whose own modeled risk first colours district land on Day 13.
const byDay = (firstDay, horizon = 14) => Array.from({ length: horizon + 1 }, (_, day) => ({
  day, date: `2026-10-${String(17 + day).padStart(2, '0')}`,
  area_km2: day >= firstDay ? 12 * (day - firstDay + 1) : 0, max_score: day >= firstDay ? (5 + day - firstDay) / 100 : null,
}))
const EXTERNAL = { source_id: 'EXT', inside_district: false, distance_to_district_km: 48.1, first_influence_day: 13, first_nominal_reach_day: 13, by_day: byDay(13) }
const LOCAL = { source_id: 'LOC', inside_district: true, distance_to_district_km: 0, first_influence_day: 0, first_nominal_reach_day: 0, by_day: byDay(0) }
const NEVER = { source_id: 'FAR', inside_district: false, distance_to_district_km: 120, first_influence_day: null, first_nominal_reach_day: null, by_day: byDay(99) }

describe('My Area: when an outside source starts to influence the district', () => {
  it('Days 0-12: not influencing (first influence day reported); Day 13 and 14: influencing with that day\'s backend area', () => {
    for (let day = 0; day <= 12; day += 1) {
      const status = districtInfluenceStatus(EXTERNAL, day, 'Galle')
      expect(status.influencing).toBe(false)
      expect(status.label).toBe('FROM DAY 13')
      expect(status.areaKm2).toBe(0)
      expect(status.text).toBe(`No modeled influence inside Galle on Day ${day}. First influence Day 13.`)
    }
    const d13 = districtInfluenceStatus(EXTERNAL, 13, 'Galle')
    expect(d13).toMatchObject({ influencing: true, label: 'INFLUENCING MY DISTRICT', areaKm2: 12, maxScore: 0.05, firstInfluenceDay: 13 })
    expect(districtInfluenceStatus(EXTERNAL, 14, 'Galle')).toMatchObject({ influencing: true, areaKm2: 24, maxScore: 0.06 })
  })

  it('a nominal reach day differing from the influence day is reported separately; a never-reaching source says so', () => {
    const reachEarlier = { ...EXTERNAL, first_nominal_reach_day: 11 }
    expect(districtInfluenceStatus(reachEarlier, 12, 'Galle').text).toBe('No modeled influence inside Galle on Day 12. First influence Day 13; first nominal reach Day 11.')
    const never = districtInfluenceStatus(NEVER, 14, 'Kandy')
    expect(never).toMatchObject({ influencing: false, label: 'NO MODELED INFLUENCE', firstInfluenceDay: null })
    expect(never.text).toBe('No modeled influence inside Kandy within the 14-day horizon.')
    expect(districtInfluenceStatus(LOCAL, 0, 'Galle')).toMatchObject({ insideDistrict: true, influencing: true, label: 'IN MY DISTRICT' })
    expect(districtInfluenceStatus(null, 3)).toBeNull()
  })

  it('the influence cards list local, then influencing, then upcoming, then never-influencing sources', () => {
    const timeline = {
      status: 'OK', as_of: '2026-10-17', disease: 'Lumpy skin disease',
      sources: ['FAR', 'EXT', 'LOC'].map((id) => ({ source_id: id, record_domain: 'OPERATIONAL', latitude: 6, longitude: 80.5, observation_date: '2026-10-16' })),
      frames: byDay(0).map(({ day, date }) => ({ day, date, horizon_status: day === 0 ? 'AS_OF_OBSERVED_CONTEXT' : 'WITHIN_D1_D7_REACH_HORIZON', reach: { nominal_reach_km: day ? 3.9 * day : null } })),
      district_influence: { district: 'Galle', sources: [NEVER, EXTERNAL, LOCAL] },
    }
    expect(buildMyAreaTimelineView(timeline, 5, 'Galle').influences.map((i) => [i.sourceId, i.status])).toEqual([['LOC', 'IN MY DISTRICT'], ['EXT', 'FROM DAY 13'], ['FAR', 'NO MODELED INFLUENCE']])
    expect(buildMyAreaTimelineView(timeline, 13, 'Galle').influences.map((i) => [i.sourceId, i.status])).toEqual([['LOC', 'IN MY DISTRICT'], ['EXT', 'INFLUENCING MY DISTRICT'], ['FAR', 'NO MODELED INFLUENCE']])
  })
})
