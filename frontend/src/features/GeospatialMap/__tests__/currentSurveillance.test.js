import { describe, expect, it } from 'vitest'

import {
  buildCurrentMostAffectedAreas,
  buildRecentActivityBuckets,
  deriveCurrentAffectedAreas,
  deriveCurrentRecordCount,
  filterCurrentContextsByDisease,
} from '../adapters/currentSurveillance'

function context({ caseId, disease, locationDistrict, verificationTime }) {
  return { caseId, disease, locationDistrict, verificationTime }
}

describe('filterCurrentContextsByDisease', () => {
  it('keeps only real contexts for the selected disease', () => {
    const contexts = [context({ caseId: 'A', disease: 'LSD' }), context({ caseId: 'B', disease: 'FMD' })]
    expect(filterCurrentContextsByDisease(contexts, 'LSD')).toEqual([contexts[0]])
  })

  it('returns an empty list for a missing disease, never "every disease" merged', () => {
    const contexts = [context({ caseId: 'A', disease: 'LSD' })]
    expect(filterCurrentContextsByDisease(contexts, null)).toEqual([])
  })
})

describe('deriveCurrentRecordCount', () => {
  it('counts distinct real caseIds', () => {
    const contexts = [context({ caseId: 'A' }), context({ caseId: 'B' })]
    expect(deriveCurrentRecordCount(contexts)).toBe(2)
  })

  it('never double-counts a repeated real caseId', () => {
    const contexts = [context({ caseId: 'A' }), context({ caseId: 'A' })]
    expect(deriveCurrentRecordCount(contexts)).toBe(1)
  })

  it('is zero for an empty real dataset, never a fabricated fallback count', () => {
    expect(deriveCurrentRecordCount([])).toBe(0)
  })
})

describe('deriveCurrentAffectedAreas', () => {
  it('counts unique real districts among current cases', () => {
    const contexts = [
      context({ caseId: 'A', locationDistrict: 'Matara' }),
      context({ caseId: 'B', locationDistrict: 'Galle' }),
      context({ caseId: 'C', locationDistrict: 'Matara' }),
    ]
    const result = deriveCurrentAffectedAreas(contexts)
    expect(result.count).toBe(2)
    expect(result.districts).toEqual(['Galle', 'Matara'])
  })

  it('excludes a real case with no resolved district, never guesses one', () => {
    const contexts = [context({ caseId: 'A', locationDistrict: null })]
    expect(deriveCurrentAffectedAreas(contexts).count).toBe(0)
  })
})

describe('buildCurrentMostAffectedAreas', () => {
  it('sorts districts descending by real current-case count', () => {
    const contexts = [
      context({ caseId: 'A', locationDistrict: 'Matara', verificationTime: '2026-08-20 09:00:00' }),
      context({ caseId: 'B', locationDistrict: 'Matara', verificationTime: '2026-08-21 09:00:00' }),
      context({ caseId: 'C', locationDistrict: 'Galle', verificationTime: '2026-08-19 09:00:00' }),
    ]
    const rows = buildCurrentMostAffectedAreas(contexts)
    expect(rows.map((r) => r.district)).toEqual(['Matara', 'Galle'])
    expect(rows[0].records).toBe(2)
  })

  it('lastObserved is the latest real verificationTime for that district', () => {
    const contexts = [
      context({ caseId: 'A', locationDistrict: 'Matara', verificationTime: '2026-08-20 09:00:00' }),
      context({ caseId: 'B', locationDistrict: 'Matara', verificationTime: '2026-08-25 09:00:00' }),
    ]
    expect(buildCurrentMostAffectedAreas(contexts)[0].lastObserved).toBe('2026-08-25 09:00:00')
  })

  it('never pads a short real result with filler rows', () => {
    const contexts = [context({ caseId: 'A', locationDistrict: 'Matara', verificationTime: '2026-08-20 09:00:00' })]
    expect(buildCurrentMostAffectedAreas(contexts, { topN: 5 })).toHaveLength(1)
  })

  it('respects topN', () => {
    const contexts = [
      context({ caseId: 'A', locationDistrict: 'Matara', verificationTime: '2026-08-20 09:00:00' }),
      context({ caseId: 'B', locationDistrict: 'Galle', verificationTime: '2026-08-19 09:00:00' }),
    ]
    expect(buildCurrentMostAffectedAreas(contexts, { topN: 1 })).toHaveLength(1)
  })

  it('still counts a record with an unparseable verificationTime, but never as the latest date', () => {
    const contexts = [context({ caseId: 'A', locationDistrict: 'Matara', verificationTime: null })]
    const rows = buildCurrentMostAffectedAreas(contexts)
    expect(rows[0].records).toBe(1)
    expect(rows[0].lastObserved).toBeNull()
  })
})

describe('buildRecentActivityBuckets', () => {
  const nowMs = new Date(2026, 7, 25, 12, 0, 0).getTime() // 25 Aug 2026, local time

  it('produces exactly windowDays real calendar-day buckets ending today', () => {
    const { points } = buildRecentActivityBuckets([], 7, nowMs)
    expect(points).toHaveLength(7)
    expect(points[0].period).toBe('2026-08-19')
    expect(points[6].period).toBe('2026-08-25')
  })

  it('counts a real case on its own real local calendar day', () => {
    const contexts = [context({ caseId: 'A', verificationTime: '2026-08-25 08:30:00' })]
    const { points } = buildRecentActivityBuckets(contexts, 7, nowMs)
    expect(points.find((p) => p.period === '2026-08-25').count).toBe(1)
  })

  it('a day with no real case is a genuine zero, never omitted', () => {
    const { points } = buildRecentActivityBuckets([], 7, nowMs)
    expect(points.every((p) => p.count === 0)).toBe(true)
  })

  it('excludes a case outside the window from the chart, without discarding it from the caller-visible list', () => {
    const contexts = [context({ caseId: 'A', verificationTime: '2026-01-01 08:30:00' })]
    const { points } = buildRecentActivityBuckets(contexts, 7, nowMs)
    expect(points.every((p) => p.count === 0)).toBe(true)
    expect(contexts).toHaveLength(1) // still a real record for Current Records/Affected Areas elsewhere
  })

  it('excludes an unparseable verificationTime from the chart and reports it via excludedCount', () => {
    const contexts = [context({ caseId: 'A', verificationTime: 'not-a-date' })]
    const { points, excludedCount } = buildRecentActivityBuckets(contexts, 7, nowMs)
    expect(points.every((p) => p.count === 0)).toBe(true)
    expect(excludedCount).toBe(1)
  })

  it('30D window produces 30 buckets', () => {
    expect(buildRecentActivityBuckets([], 30, nowMs).points).toHaveLength(30)
  })
})
