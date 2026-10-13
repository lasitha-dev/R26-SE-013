import { describe, expect, it } from 'vitest'

import {
  DEFAULT_OBSERVATION_WINDOW_DAYS,
  OBSERVATION_WINDOW_OPTIONS,
  classifyRecency,
  isWithinObservationWindow,
} from '../adapters/observationWindow'

// `verification_time` carries no timezone marker (Section 6), so both
// `NOW` and `isoAgo` are expressed in the SAME local-time reference frame
// here -- otherwise the missing-timezone parse in `verificationTime.js`
// (which necessarily reads a bare "no offset" string as local time) would
// make this test's own expected/actual clocks disagree by the runner's
// UTC offset instead of testing the real day-boundary logic.
const NOW = new Date(2026, 7, 30, 12, 0, 0).getTime()
const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR

function pad(n) {
  return String(n).padStart(2, '0')
}

function isoAgo(ms) {
  const d = new Date(NOW - ms)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

describe('GEO26B Section 6/25: isWithinObservationWindow', () => {
  it('a case from a few hours ago is within every window, including Today (1 day)', () => {
    expect(isWithinObservationWindow(isoAgo(3 * HOUR), 1, NOW)).toBe(true)
  })

  it('a case from yesterday (~24h ago is borderline) remains visible in 7/14/30 day windows', () => {
    const yesterday = isoAgo(20 * HOUR)
    expect(isWithinObservationWindow(yesterday, 7, NOW)).toBe(true)
    expect(isWithinObservationWindow(yesterday, 14, NOW)).toBe(true)
    expect(isWithinObservationWindow(yesterday, 30, NOW)).toBe(true)
  })

  it('a case older than the selected window is excluded', () => {
    const tenDaysAgo = isoAgo(10 * DAY)
    expect(isWithinObservationWindow(tenDaysAgo, 7, NOW)).toBe(false)
    expect(isWithinObservationWindow(tenDaysAgo, 14, NOW)).toBe(true)
  })

  it('a case exactly on the 30-day boundary remains included', () => {
    expect(isWithinObservationWindow(isoAgo(30 * DAY), 30, NOW)).toBe(true)
    expect(isWithinObservationWindow(isoAgo(30 * DAY + HOUR), 30, NOW)).toBe(false)
  })

  it('a missing or unparseable verification time is excluded, never guessed as current', () => {
    expect(isWithinObservationWindow(null, 30, NOW)).toBe(false)
    expect(isWithinObservationWindow(undefined, 30, NOW)).toBe(false)
    expect(isWithinObservationWindow('not-a-date', 30, NOW)).toBe(false)
  })

  it('a slightly-future timestamp (clock skew) is still treated as current, not excluded', () => {
    expect(isWithinObservationWindow(isoAgo(-5 * 60 * 1000), 1, NOW)).toBe(true)
  })
})

describe('GEO26B Section 9: classifyRecency', () => {
  it('classifies within the fixed recent-threshold as recent', () => {
    expect(classifyRecency(isoAgo(1 * DAY), NOW)).toBe('recent')
  })

  it('classifies beyond the fixed recent-threshold as older, even inside a wide selected window', () => {
    expect(classifyRecency(isoAgo(10 * DAY), NOW)).toBe('older')
  })

  it('an unparseable/missing timestamp is classified older, never recent', () => {
    expect(classifyRecency(null, NOW)).toBe('older')
    expect(classifyRecency('garbage', NOW)).toBe('older')
  })
})

describe('GEO26B: OBSERVATION_WINDOW_OPTIONS / default', () => {
  it('exposes exactly Today / 7 / 14 / 30 days, in that order', () => {
    expect(OBSERVATION_WINDOW_OPTIONS.map((o) => o.days)).toEqual([1, 7, 14, 30])
  })

  it('defaults to 14 days', () => {
    expect(DEFAULT_OBSERVATION_WINDOW_DAYS).toBe(14)
  })
})
