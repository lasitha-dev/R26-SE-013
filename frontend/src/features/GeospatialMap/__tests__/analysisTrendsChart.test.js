import { describe, expect, it } from 'vitest'

import { buildTrendChartGeometry, formatTrendPeriodLabel } from '../components/AnalysisTrendsChart'

describe('GEO-ANALYSIS-02-CHART-01: formatTrendPeriodLabel', () => {
  it('formats a real WEEK period', () => {
    expect(formatTrendPeriodLabel('2020-W37', 'WEEK')).toBe("Wk 37 '20")
  })

  it('formats a real MONTH period', () => {
    expect(formatTrendPeriodLabel('2020-01', 'MONTH')).toBe("Jan '20")
  })

  it('returns a YEAR period verbatim', () => {
    expect(formatTrendPeriodLabel('2020', 'YEAR')).toBe('2020')
  })

  it('falls back to the raw string for an unrecognized basis, never guesses', () => {
    expect(formatTrendPeriodLabel('2020-Q1', 'QUARTER')).toBe('2020-Q1')
  })

  it('never throws on a malformed period string', () => {
    expect(formatTrendPeriodLabel('not-a-period', 'WEEK')).toBe('not-a-period')
  })
})

describe('GEO-ANALYSIS-02-CHART-02: buildTrendChartGeometry is pure and deterministic', () => {
  const points = [
    { period: '2020-W36', count: 0 },
    { period: '2020-W37', count: 4 },
    { period: '2020-W38', count: 2 },
  ]

  it('produces exactly one bar per real point, in the same order', () => {
    const geometry = buildTrendChartGeometry(points)
    expect(geometry.bars).toHaveLength(3)
    expect(geometry.bars.map((b) => b.period)).toEqual(['2020-W36', '2020-W37', '2020-W38'])
  })

  it('the zero-count point gets zero bar height, never an invented value', () => {
    const geometry = buildTrendChartGeometry(points)
    expect(geometry.bars[0].height).toBe(0)
  })

  it('the maximum real count sets the y-axis scale', () => {
    const geometry = buildTrendChartGeometry(points)
    expect(geometry.maxCount).toBe(4)
  })

  it('the tallest bar corresponds to the real maximum count', () => {
    const geometry = buildTrendChartGeometry(points)
    const tallest = geometry.bars.reduce((max, b) => (b.height > max.height ? b : max))
    expect(tallest.period).toBe('2020-W37')
  })

  it('deterministic: same input always produces the same geometry', () => {
    const a = buildTrendChartGeometry(points)
    const b = buildTrendChartGeometry(points)
    expect(a.bars.map((x) => ({ x: x.x, y: x.y, height: x.height }))).toEqual(b.bars.map((x) => ({ x: x.x, y: x.y, height: x.height })))
  })

  it('empty points produce zero bars, never a fabricated placeholder bar', () => {
    const geometry = buildTrendChartGeometry([])
    expect(geometry.bars).toHaveLength(0)
    expect(geometry.maxCount).toBe(0)
  })

  it('all-zero points produce zero-height bars, never divides by zero into NaN', () => {
    const geometry = buildTrendChartGeometry([{ period: '2020-W01', count: 0 }])
    expect(geometry.bars[0].height).toBe(0)
    expect(Number.isNaN(geometry.bars[0].height)).toBe(false)
  })

  it('never reorders points -- geometry preserves input array order even if counts are non-monotonic', () => {
    const shuffled = [
      { period: '2020-W40', count: 1 },
      { period: '2020-W38', count: 5 },
      { period: '2020-W39', count: 2 },
    ]
    const geometry = buildTrendChartGeometry(shuffled)
    expect(geometry.bars.map((b) => b.period)).toEqual(['2020-W40', '2020-W38', '2020-W39'])
  })

  it('a sparse long YEAR series (real FMD shape) still produces one bar per real year, no synthesized points', () => {
    const years = ['2009', '2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019'].map((y) => ({ period: y, count: y === '2018' ? 2 : 0 }))
    const geometry = buildTrendChartGeometry(years)
    expect(geometry.bars).toHaveLength(11)
    expect(geometry.labelEvery).toBeLessThanOrEqual(2)
  })
})
