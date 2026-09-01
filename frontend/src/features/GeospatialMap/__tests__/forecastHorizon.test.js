import { describe, expect, it } from 'vitest'

import { deriveForecastHorizon } from '../adapters/forecastHorizon'

describe('deriveForecastHorizon', () => {
  it('is unavailable with no origin selected, never a fabricated default', () => {
    const result = deriveForecastHorizon(null)
    expect(result.available).toBe(false)
    expect(result.days).toBeNull()
  })

  it('is unavailable when the scientific model is not ready for the disease', () => {
    const result = deriveForecastHorizon({ status: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY' })
    expect(result.available).toBe(false)
  })

  it('is unavailable when nominal reach has no real day entries', () => {
    const result = deriveForecastHorizon({ status: 'AVAILABLE', originId: 'X', nominalReach: { days: [] } })
    expect(result.available).toBe(false)
  })

  it('uses the maximum real day with a real nominal reach value', () => {
    const result = deriveForecastHorizon({
      status: 'AVAILABLE',
      originId: 'ORIGIN:Sri Lanka:2020-09-28',
      nominalReach: {
        days: [
          { day: 1, nominalReachKm: 3.9 },
          { day: 2, nominalReachKm: 7.9 },
          { day: 7, nominalReachKm: 27.6 },
        ],
      },
    })
    expect(result.available).toBe(true)
    expect(result.days).toBe(7)
  })

  it('ignores a real day entry whose nominal reach value is itself null', () => {
    const result = deriveForecastHorizon({
      status: 'AVAILABLE',
      nominalReach: {
        days: [
          { day: 1, nominalReachKm: 3.9 },
          { day: 2, nominalReachKm: null },
        ],
      },
    })
    expect(result.days).toBe(1)
  })
})
