import { describe, expect, it } from 'vitest'

import { buildObservedReplayDates, filterContextsByReplayDate, isRevealedByReplayDate } from '../adapters/observedReplay'

function ctx(verificationTime) {
  return { verificationTime }
}

describe('GEO31A Section 6: buildObservedReplayDates', () => {
  it('derives distinct real dates only, ascending, from real verification timestamps', () => {
    const dates = buildObservedReplayDates([
      ctx('2026-08-30 09:00:00'),
      ctx('2026-08-24 10:00:00'),
      ctx('2026-08-29 08:00:00'),
      ctx('2026-08-24 15:30:00'), // same day as an earlier entry -- collapses to one
    ])
    expect(dates).toEqual(['2026-08-24', '2026-08-29', '2026-08-30'])
  })

  it('never fabricates a date between two real observed dates', () => {
    const dates = buildObservedReplayDates([ctx('2026-08-24 10:00:00'), ctx('2026-08-30 10:00:00')])
    expect(dates).toEqual(['2026-08-24', '2026-08-30'])
    expect(dates).not.toContain('2026-08-25')
    expect(dates).not.toContain('2026-08-27')
  })

  it('excludes a missing/unparseable verification time, never treats it as "today"', () => {
    const dates = buildObservedReplayDates([ctx(null), ctx(undefined), ctx('not-a-date'), ctx('2026-08-24 10:00:00')])
    expect(dates).toEqual(['2026-08-24'])
  })

  it('an empty or missing input yields an empty array, never a fabricated placeholder date', () => {
    expect(buildObservedReplayDates([])).toEqual([])
    expect(buildObservedReplayDates(undefined)).toEqual([])
  })
})

describe('GEO31A Section 6: isRevealedByReplayDate', () => {
  it('a case verified on or before the replay date is revealed', () => {
    expect(isRevealedByReplayDate('2026-08-24 10:00:00', '2026-08-24')).toBe(true)
    expect(isRevealedByReplayDate('2026-08-24 10:00:00', '2026-08-30')).toBe(true)
  })

  it('a case verified AFTER the replay date is never revealed early', () => {
    expect(isRevealedByReplayDate('2026-08-30 10:00:00', '2026-08-24')).toBe(false)
  })

  it('a null replayDateKey means "no replay in progress" -- always revealed', () => {
    expect(isRevealedByReplayDate('2026-08-30 10:00:00', null)).toBe(true)
    expect(isRevealedByReplayDate(null, null)).toBe(true)
  })

  it('an unparseable verification time is never revealed while an explicit replay date is active', () => {
    expect(isRevealedByReplayDate('not-a-date', '2026-08-24')).toBe(false)
    expect(isRevealedByReplayDate(null, '2026-08-24')).toBe(false)
  })
})

describe('GEO31A Section 6: filterContextsByReplayDate', () => {
  it('returns every context unfiltered when replayDateKey is nullish (at latest)', () => {
    const contexts = [ctx('2026-08-24 10:00:00'), ctx('2026-08-30 10:00:00')]
    expect(filterContextsByReplayDate(contexts, null)).toEqual(contexts)
    expect(filterContextsByReplayDate(contexts, undefined)).toEqual(contexts)
  })

  it('keeps only contexts revealed by the given replay date', () => {
    const early = ctx('2026-08-24 10:00:00')
    const late = ctx('2026-08-30 10:00:00')
    expect(filterContextsByReplayDate([early, late], '2026-08-24')).toEqual([early])
    expect(filterContextsByReplayDate([early, late], '2026-08-30')).toEqual([early, late])
  })
})
