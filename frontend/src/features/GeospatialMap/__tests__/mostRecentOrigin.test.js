import { describe, expect, it } from 'vitest'

import { selectMostRecentOrigin } from '../adapters/mostRecentOrigin'

function origin(outbreakId, t0) {
  return { outbreakId, t0, country: 'Sri Lanka' }
}

describe('GEO-PAGE1-FINAL Section 24: selectMostRecentOrigin', () => {
  it('returns null for an empty/undefined list -- no fabricated default focus', () => {
    expect(selectMostRecentOrigin([])).toBeNull()
    expect(selectMostRecentOrigin(undefined)).toBeNull()
    expect(selectMostRecentOrigin(null)).toBeNull()
  })

  it('returns the only origin when exactly one is available', () => {
    const only = origin('ORIGIN:Sri Lanka:2020-09-07', '2020-09-07')
    expect(selectMostRecentOrigin([only])).toBe(only)
  })

  it('picks the real origin with the latest t0 among several, regardless of array order', () => {
    const oldest = origin('ORIGIN:Sri Lanka:2020-09-07', '2020-09-07')
    const middle = origin('ORIGIN:Sri Lanka:2020-09-28', '2020-09-28')
    const newest = origin('ORIGIN:Sri Lanka:2020-10-28', '2020-10-28')
    expect(selectMostRecentOrigin([middle, oldest, newest]).outbreakId).toBe(newest.outbreakId)
    expect(selectMostRecentOrigin([newest, middle, oldest]).outbreakId).toBe(newest.outbreakId)
  })

  it('reproduces the real live Sri Lanka LSD corpus shape (5 origins) -- picks the genuinely latest real t0', () => {
    const origins = [
      origin('ORIGIN:Sri Lanka:2020-09-07', '2020-09-07'),
      origin('ORIGIN:Sri Lanka:2020-09-09', '2020-09-09'),
      origin('ORIGIN:Sri Lanka:2020-09-28', '2020-09-28'),
      origin('ORIGIN:Sri Lanka:2020-09-29', '2020-09-29'),
      origin('ORIGIN:Sri Lanka:2020-10-28', '2020-10-28'),
    ]
    expect(selectMostRecentOrigin(origins).outbreakId).toBe('ORIGIN:Sri Lanka:2020-10-28')
  })

  it('never picks the documented slow-resolving straggler unless it genuinely is the most recent -- ties are broken deterministically, never by arrival order', () => {
    const a = origin('ORIGIN:Sri Lanka:2020-01-01', '2020-01-01')
    const b = origin('ORIGIN:Sri Lanka:2020-01-01-b', '2020-01-01')
    // Same real t0 (a genuine tie) -- the higher outbreakId wins both times, proving the choice does not depend on which element the reduce visits first.
    expect(selectMostRecentOrigin([a, b]).outbreakId).toBe('ORIGIN:Sri Lanka:2020-01-01-b')
    expect(selectMostRecentOrigin([b, a]).outbreakId).toBe('ORIGIN:Sri Lanka:2020-01-01-b')
  })

  it('never mutates the input array', () => {
    const origins = [origin('A', '2020-01-01'), origin('B', '2020-02-02')]
    const before = JSON.parse(JSON.stringify(origins))
    selectMostRecentOrigin(origins)
    expect(origins).toEqual(before)
  })
})
