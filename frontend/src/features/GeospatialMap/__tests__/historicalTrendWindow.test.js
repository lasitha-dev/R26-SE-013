import { describe, expect, it } from 'vitest'

import { filterTrendPointsByWindow, periodEndDate } from '../adapters/historicalTrendWindow'

describe('periodEndDate', () => {
  it('resolves a WEEK period to its real ISO week Sunday', () => {
    // ISO week 1 of 2026 starts Monday 2025-12-29.
    const end = periodEndDate('2026-W01', 'WEEK')
    expect(end.toISOString().slice(0, 10)).toBe('2026-01-04')
  })

  it('resolves a MONTH period to its real last day', () => {
    expect(periodEndDate('2026-02', 'MONTH').toISOString().slice(0, 10)).toBe('2026-02-28')
  })

  it('resolves a YEAR period to real Dec 31', () => {
    expect(periodEndDate('2026', 'YEAR').toISOString().slice(0, 10)).toBe('2026-12-31')
  })

  it('returns null for a malformed period', () => {
    expect(periodEndDate('not-a-period', 'MONTH')).toBeNull()
  })
})

describe('filterTrendPointsByWindow', () => {
  const monthPoints = [
    { period: '2026-01', count: 1 },
    { period: '2026-02', count: 2 },
    { period: '2026-03', count: 3 },
    { period: '2026-06', count: 0 },
  ]

  it('30D keeps only the real period(s) within 30 days of the last real period', () => {
    const result = filterTrendPointsByWindow(monthPoints, 'MONTH', '30D')
    expect(result).toEqual([{ period: '2026-06', count: 0 }])
  })

  it('12W (84 days) keeps real periods within ~3 months of the last one', () => {
    const result = filterTrendPointsByWindow(monthPoints, 'MONTH', '12W')
    expect(result.map((p) => p.period)).toEqual(['2026-06'])
  })

  it('YTD keeps every real period in the calendar year of the last period', () => {
    const result = filterTrendPointsByWindow(monthPoints, 'MONTH', 'YTD')
    expect(result.map((p) => p.period)).toEqual(['2026-01', '2026-02', '2026-03', '2026-06'])
  })

  it('YTD excludes a real period from an earlier calendar year', () => {
    const points = [{ period: '2025-12', count: 4 }, { period: '2026-01', count: 1 }]
    expect(filterTrendPointsByWindow(points, 'MONTH', 'YTD').map((p) => p.period)).toEqual(['2026-01'])
  })

  it('returns an empty array for an empty real input, never a fabricated point', () => {
    expect(filterTrendPointsByWindow([], 'MONTH', '30D')).toEqual([])
  })

  it('passes real points through unchanged for an unrecognized window', () => {
    expect(filterTrendPointsByWindow(monthPoints, 'MONTH', 'ALL')).toEqual(monthPoints)
  })

  it('passes real points through unchanged rather than dropping them when a period cannot be parsed', () => {
    const malformed = [{ period: 'weird', count: 5 }]
    expect(filterTrendPointsByWindow(malformed, 'MONTH', '30D')).toEqual(malformed)
  })
})
