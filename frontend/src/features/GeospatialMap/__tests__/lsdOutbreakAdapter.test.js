import { describe, expect, it } from 'vitest'

import {
  buildForecastFrame,
  computeRelevantOrigins,
  getAvailableForecastDays,
  mapOriginsToOutbreakSummaries,
} from '../adapters/lsdOutbreakAdapter'
import {
  FIXTURE_AREA_RING_FAR_AWAY_KANDY,
  FIXTURE_AREA_RING_NEAR_JAFFNA,
  REAL_CELLS_20200928,
  REAL_ORIGINS_RESPONSE,
  REAL_SOURCES_20200928,
  REAL_SUMMARY_20200928,
} from './fixtures/realLsdOriginFixture'

describe('lsdOutbreakAdapter (against real captured backend responses)', () => {
  it('maps /origins response items to outbreak summaries, all 5 real Sri Lanka LSD origins', () => {
    const summaries = mapOriginsToOutbreakSummaries(REAL_ORIGINS_RESPONSE)
    expect(summaries).toHaveLength(5)
    expect(summaries[2]).toEqual({
      outbreakId: 'ORIGIN:Sri Lanka:2020-09-28',
      country: 'Sri Lanka',
      t0: '2020-09-28',
      sourceCount: 2,
    })
  })

  it('derives the real 8-frame horizon (D0 + real D1..D7 from nominal_reach_by_day), never a hardcoded 14/15', () => {
    expect(getAvailableForecastDays(REAL_SUMMARY_20200928)).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
  })

  it('an origin with no nominal_reach_by_day still gets day 0 alone, not an empty list', () => {
    expect(getAvailableForecastDays({})).toEqual([0])
  })

  it('builds an observed (D0) frame: real markers/cells, zero reach, no fabricated fields', () => {
    const frame = buildForecastFrame({ summary: REAL_SUMMARY_20200928, sources: REAL_SOURCES_20200928, cells: REAL_CELLS_20200928, dayIndex: 0 })
    expect(frame.outbreakId).toBe('ORIGIN:Sri Lanka:2020-09-28')
    expect(frame.disease).toBe('LSD')
    expect(frame.modelRunId).toBe('8b523733c7504ab5b0e09a492436ca37e17990d3f8a0688d4069b76bc9a807a7')
    expect(frame.dayLabel).toBe('D0')
    expect(frame.actualDate).toBe('2020-09-28')
    expect(frame.status).toBe('observed')
    expect(frame.confirmedMarkers).toBe(REAL_SOURCES_20200928)
    expect(frame.riskSurface).toBe(REAL_CELLS_20200928)
    expect(frame.nominalReachKm).toBe(0)
    // Never fabricated -- explicitly null until the backend exposes them.
    expect(frame.clusterBoundaries).toBeNull()
    expect(frame.riskZones).toBeNull()
    expect(frame.predictedHotspots).toBeNull()
    expect(frame.trajectory).toBeNull()
    expect(frame.uncertainty).toBeNull()
    expect(frame.confidence).toBeNull()
    expect(frame.aiExplanation).toBeNull()
    expect(frame.recommendedActions).toBeNull()
  })

  it('builds a forecast (D+5) frame: same real markers/cells, real day-5 nominal reach, forward-dated', () => {
    const frame = buildForecastFrame({ summary: REAL_SUMMARY_20200928, sources: REAL_SOURCES_20200928, cells: REAL_CELLS_20200928, dayIndex: 5 })
    expect(frame.dayLabel).toBe('D+5')
    expect(frame.actualDate).toBe('2020-10-03')
    expect(frame.status).toBe('forecast')
    // Real value from the fixture, not a formula re-derived here.
    expect(frame.nominalReachKm).toBe(19.732107215773755)
    expect(frame.nominalReachIntervalKm).toEqual({ lower: 17.745523085453883, upper: 21.71538664781862 })
    // Confirmed markers/risk cells don't vary by day (plan Section D --
    // the backend has no day-varying risk surface yet).
    expect(frame.confirmedMarkers).toBe(REAL_SOURCES_20200928)
    expect(frame.riskSurface).toBe(REAL_CELLS_20200928)
  })

  it('LSD-UI-04: selecting a later day increases the real nominal reach; selecting an earlier day shrinks it back (Section 25/31)', () => {
    const dayIndices = [1, 2, 3, 4, 5, 6, 7]
    const reaches = dayIndices.map(
      (dayIndex) => buildForecastFrame({ summary: REAL_SUMMARY_20200928, sources: REAL_SOURCES_20200928, cells: REAL_CELLS_20200928, dayIndex }).nominalReachKm,
    )
    // Strictly increasing day-over-day -- moving the timeline forward
    // must never shrink the reach, and moving it back must never grow it.
    for (let i = 1; i < reaches.length; i += 1) {
      expect(reaches[i]).toBeGreaterThan(reaches[i - 1])
    }
    // Concretely: going from D+5 back to D+3 shrinks the real value.
    const d5 = buildForecastFrame({ summary: REAL_SUMMARY_20200928, sources: REAL_SOURCES_20200928, cells: REAL_CELLS_20200928, dayIndex: 5 }).nominalReachKm
    const d3 = buildForecastFrame({ summary: REAL_SUMMARY_20200928, sources: REAL_SOURCES_20200928, cells: REAL_CELLS_20200928, dayIndex: 3 }).nominalReachKm
    expect(d3).toBeLessThan(d5)
  })

  it('computeRelevantOrigins: real Jaffna-area sources are relevant to a Jaffna-area polygon (point-in-polygon only, see Section Q)', () => {
    const originsWithSources = [{ outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', country: 'Sri Lanka', t0: '2020-09-28', sourcesFeatureCollection: REAL_SOURCES_20200928 }]
    const relevant = computeRelevantOrigins(originsWithSources, FIXTURE_AREA_RING_NEAR_JAFFNA)
    expect(relevant).toHaveLength(1)
    expect(relevant[0].outbreakId).toBe('ORIGIN:Sri Lanka:2020-09-28')
    expect(relevant[0].reason).toBe('SOURCE_INSIDE_ASSIGNED_AREA')
  })

  it('computeRelevantOrigins: the same real sources are NOT relevant to a distant (Kandy-area) polygon -- honest empty result, not a fabricated match', () => {
    const originsWithSources = [{ outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', country: 'Sri Lanka', t0: '2020-09-28', sourcesFeatureCollection: REAL_SOURCES_20200928 }]
    const relevant = computeRelevantOrigins(originsWithSources, FIXTURE_AREA_RING_FAR_AWAY_KANDY)
    expect(relevant).toHaveLength(0)
  })

  it('computeRelevantOrigins: an empty/missing area polygon never crashes and never reports relevance', () => {
    const originsWithSources = [{ outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', country: 'Sri Lanka', t0: '2020-09-28', sourcesFeatureCollection: REAL_SOURCES_20200928 }]
    expect(computeRelevantOrigins(originsWithSources, null)).toEqual([])
    expect(computeRelevantOrigins(originsWithSources, [])).toEqual([])
  })
})
