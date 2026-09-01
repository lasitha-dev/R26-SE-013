import { describe, expect, it } from 'vitest'

import { adjacentMyAreaForecastDay, buildMyAreaForecastFrames, findMyAreaForecastFrame } from '../adapters/myAreaTimeline'

describe('My Area canonical real-frame timeline', () => {
  it('uses the real t0 and only genuine available days', () => {
    const frames = buildMyAreaForecastFrames({
      t0: '2026-08-31',
      nominalReachByDay: [
        { day: 1, nominal_reach_km: 3.5 },
        { day: 4, nominal_reach_km: 13.8 },
      ],
    })
    expect(frames.map((frame) => frame.day)).toEqual([0, 1, 4])
    expect(frames.map((frame) => frame.actualDate)).toEqual(['2026-08-31', '2026-09-01', '2026-09-04'])
  })

  it('never fabricates 0 km for D0', () => {
    expect(buildMyAreaForecastFrames({ t0: '2026-08-31' })[0].nominalReachKm).toBeNull()
  })

  it('drops malformed/missing reach entries rather than inventing frames', () => {
    const frames = buildMyAreaForecastFrames({
      t0: '2026-08-31',
      nominalReachByDay: [
        { day: 1, nominal_reach_km: null },
        { day: 2, nominal_reach_km: Number.NaN },
        { day: 3, nominal_reach_km: 9 },
        { day: 3, nominal_reach_km: 99 },
        { day: 0, nominal_reach_km: 0 },
      ],
    })
    expect(frames.map((frame) => [frame.day, frame.nominalReachKm])).toEqual([[0, null], [3, 9]])
  })

  it('sorts genuine sparse frames without interpolating missing days', () => {
    const frames = buildMyAreaForecastFrames({
      t0: '2026-01-01',
      nominalReachByDay: [{ day: 7, nominal_reach_km: 21 }, { day: 3, nominal_reach_km: 9 }],
    })
    expect(frames.map((frame) => frame.day)).toEqual([0, 3, 7])
  })

  it('keeps a real frame even when no display date can be derived', () => {
    const frames = buildMyAreaForecastFrames({ t0: null, nominalReachByDay: [{ day: 2, nominal_reach_km: 6 }] })
    expect(frames).toHaveLength(2)
    expect(frames[1].actualDate).toBeNull()
  })

  it('finds the canonical selected frame and safely falls back to D0', () => {
    const frames = buildMyAreaForecastFrames({ t0: '2026-01-01', nominalReachByDay: [{ day: 2, nominal_reach_km: 6 }] })
    expect(findMyAreaForecastFrame(frames, 2).day).toBe(2)
    expect(findMyAreaForecastFrame(frames, 1).day).toBe(0)
  })

  it('previous/next follows sparse real frames rather than day arithmetic', () => {
    const frames = buildMyAreaForecastFrames({ t0: '2026-01-01', nominalReachByDay: [{ day: 3, nominal_reach_km: 9 }, { day: 7, nominal_reach_km: 21 }] })
    expect(adjacentMyAreaForecastDay(frames, 3, -1)).toBe(0)
    expect(adjacentMyAreaForecastDay(frames, 3, 1)).toBe(7)
    expect(adjacentMyAreaForecastDay(frames, 7, 1)).toBe(7)
  })
})
