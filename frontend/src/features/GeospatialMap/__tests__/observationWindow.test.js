import { describe, expect, it } from 'vitest'

import {
  DEFAULT_OBSERVATION_WINDOW_DAYS,
  OBSERVATION_WINDOW_OPTIONS,
  classifyRecency,
  isWithinObservationWindow,
} from '../adapters/observationWindow'

// Legacy `verification_time` text carries no timezone marker but is UTC
// (the host wrote it with `datetime.utcnow()`), so `isoAgo` renders the
// naive text in UTC -- independent of the test runner's own timezone.
const NOW = Date.UTC(2026, 7, 30, 12, 0, 0)
const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR

function pad(n) {
  return String(n).padStart(2, '0')
}

function isoAgo(ms) {
  const d = new Date(NOW - ms)
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
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
    expect(OBSERVATION_WINDOW_OPTIONS.map((o) => o.days)).toEqual([-1, 1, 7, 14, 30, Infinity])
  })

  it('defaults to 14 days', () => {
    expect(DEFAULT_OBSERVATION_WINDOW_DAYS).toBe(14)
  })
})
