import { describe, expect, it } from 'vitest'

import { buildMataraOriginActivityPoints, mataraObservedPeriod } from '../adapters/mataraOriginActivity'

describe('URGENT-MATARA-REAL-FILTER: buildMataraOriginActivityPoints', () => {
  it('buckets real origin t0 dates by month, sorted chronologically', () => {
    const origins = [{ t0: '2020-09-28' }, { t0: '2020-09-07' }, { t0: '2020-10-05' }]
    const result = buildMataraOriginActivityPoints(origins)
    expect(result.periodBasis).toBe('MONTH')
    expect(result.countBasis).toBe('ORIGINS')
    expect(result.points).toEqual([
      { period: '2020-09', count: 2, count_basis: 'ORIGINS' },
      { period: '2020-10', count: 1, count_basis: 'ORIGINS' },
    ])
  })

  it('returns an empty points list for zero origins -- never a fabricated point', () => {
    expect(buildMataraOriginActivityPoints([])).toEqual({ periodBasis: 'MONTH', countBasis: 'ORIGINS', points: [] })
    expect(buildMataraOriginActivityPoints(null)).toEqual({ periodBasis: 'MONTH', countBasis: 'ORIGINS', points: [] })
  })

  it('excludes an origin with a missing/malformed t0 rather than guessing a bucket', () => {
    const origins = [{ t0: '2020-09-28' }, { t0: null }, { t0: 'not-a-date' }]
    expect(buildMataraOriginActivityPoints(origins).points).toEqual([{ period: '2020-09', count: 1, count_basis: 'ORIGINS' }])
  })
})

describe('URGENT-MATARA-REAL-FILTER: mataraObservedPeriod', () => {
  it('returns the real min/max t0 across the given origins', () => {
    const origins = [{ t0: '2020-09-28' }, { t0: '2020-09-07' }, { t0: '2020-10-05' }]
    expect(mataraObservedPeriod(origins)).toEqual({ firstDate: '2020-09-07', lastDate: '2020-10-05' })
  })

  it('returns null for zero origins -- never substitutes the national window', () => {
    expect(mataraObservedPeriod([])).toBeNull()
    expect(mataraObservedPeriod(null)).toBeNull()
  })
})
