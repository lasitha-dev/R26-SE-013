import { describe, expect, it } from 'vitest'

import { addDaysToIsoDate, forecastDayLabel, formatDisplayDate } from '../adapters/forecastDate'

describe('forecastDate', () => {
  it('D0 is t0 itself', () => {
    expect(addDaysToIsoDate('2020-09-28', 0)).toBe('2020-09-28')
  })

  it('adds days within a month', () => {
    expect(addDaysToIsoDate('2020-09-28', 2)).toBe('2020-09-30')
  })

  it('rolls over a month boundary', () => {
    expect(addDaysToIsoDate('2020-09-28', 4)).toBe('2020-10-02')
  })

  it('rolls over a year boundary', () => {
    expect(addDaysToIsoDate('2020-12-30', 3)).toBe('2021-01-02')
  })

  it('handles a leap-year February correctly (2020 is a leap year)', () => {
    expect(addDaysToIsoDate('2020-02-27', 2)).toBe('2020-02-29')
    expect(addDaysToIsoDate('2020-02-27', 3)).toBe('2020-03-01')
  })

  it('does not shift day/month against a non-leap year (2021)', () => {
    expect(addDaysToIsoDate('2021-02-27', 1)).toBe('2021-02-28')
    expect(addDaysToIsoDate('2021-02-27', 2)).toBe('2021-03-01')
  })

  it('is stable under the classic "new Date(isoString) parses as UTC" pitfall regardless of running-machine timezone', () => {
    // If this were implemented with new Date('2020-09-28').getDate() and
    // read back with local-time getters, a negative-UTC-offset machine
    // would see 2020-09-27. Asserting the exact string catches that.
    expect(addDaysToIsoDate('2020-09-28', 7)).toBe('2020-10-05')
  })

  it('labels day 0 as D0 and everything else as D+n', () => {
    expect(forecastDayLabel(0)).toBe('D0')
    expect(forecastDayLabel(1)).toBe('D+1')
    expect(forecastDayLabel(7)).toBe('D+7')
  })

  it('formats a display date in a fixed, locale-independent form', () => {
    expect(formatDisplayDate('2020-09-28')).toBe('28 Sep 2020')
  })
})
