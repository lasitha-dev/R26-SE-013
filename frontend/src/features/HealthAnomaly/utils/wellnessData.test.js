import { beforeEach, describe, expect, it } from 'vitest'
import { cacheFarmLocation, normalizeLogDate } from './wellnessData.js'

describe('wellness data contracts', () => {
  beforeEach(() => localStorage.clear())

  it.each([['10/9/26', '2026-10-09'], ['2026.10.9', '2026-10-09'], ['2024-02-29', '2024-02-29'],
    ['2026-02-29', ''], ['2026-04-31', ''], ['15/10/2026', ''], ['', '']])('normalizes %s without calendar rollovers', (raw, expected) => {
    expect(normalizeLogDate(raw)).toBe(expected)
  })

  it('clears the previous farm location when switching to an account without coordinates', () => {
    cacheFarmLocation({ latitude: 7, longitude: 80, location_district: 'Kandy', location: 'Farm A' })
    cacheFarmLocation({ location_district: 'Galle' })
    expect(localStorage.getItem('registered_farm_lat')).toBeNull()
    expect(localStorage.getItem('registered_farm_lon')).toBeNull()
    expect(localStorage.getItem('registered_farm_location')).toBeNull()
    expect(localStorage.getItem('registered_farm_district')).toBe('Galle')
  })
})
