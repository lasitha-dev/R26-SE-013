import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import { buildRecentActivityBuckets } from '../adapters/currentSurveillance'
import { buildNationalCaseView, caseDateKey } from '../adapters/nationalCases'
import { buildObservedReplayDates } from '../adapters/observedReplay'
import { isWithinWindowEndingAt, latestVerifiedDate } from '../adapters/spatialStory'
import { formatVerificationTime, parseVerificationTime, sriLankaDateKey, sriLankaEndOfDayMs } from '../adapters/verificationTime'

// P0: case timestamps are UTC instants (backend sends `+00:00`; legacy naive
// host text is also UTC). Calendar dates are Asia/Colombo (UTC+05:30).
// Every expectation below is independent of the test runner's timezone.

describe('P0: case instants and Asia/Colombo calendar dates', () => {
  it('reads naive host text as UTC and never re-converts an explicit offset', () => {
    const naive = parseVerificationTime('2026-08-30 20:05:46')
    expect(naive.toISOString()).toBe('2026-08-30T20:05:46.000Z')
    expect(parseVerificationTime('2026-08-30T20:05:46+00:00').getTime()).toBe(naive.getTime())
    expect(parseVerificationTime('2026-08-31T01:35:46+05:30').getTime()).toBe(naive.getTime())
    expect(parseVerificationTime('2026-08-31T18:28:38.880000+00:00').toISOString()).toBe('2026-08-31T18:28:38.880Z')
    expect(parseVerificationTime('not a date')).toBeNull()
  })

  it('crosses the Sri Lanka midnight at 18:30 UTC', () => {
    expect(sriLankaDateKey('2026-08-30T18:29:59+00:00')).toBe('2026-08-30')
    expect(sriLankaDateKey('2026-08-30T18:30:00+00:00')).toBe('2026-08-31')
    expect(sriLankaDateKey('2026-08-30 20:05:46')).toBe('2026-08-31')
    expect(sriLankaDateKey('2026-08-30')).toBe('2026-08-30') // a calendar date is never shifted
    expect(sriLankaDateKey(null)).toBeNull()
    expect(sriLankaEndOfDayMs('2026-08-30')).toBe(Date.parse('2026-08-30T18:29:59.999Z'))
  })

  it('formats in Sri Lanka time regardless of the browser timezone', () => {
    expect(formatVerificationTime('2026-08-30T20:05:46+00:00')).toBe('31 Aug 2026, 01:35')
  })

  it('latest verified date and the analysis window use the Sri Lanka date', () => {
    const contexts = [
      { disease: 'LSD', verificationTime: '2026-08-30T07:30:00+00:00' },
      { disease: 'LSD', verificationTime: '2026-08-30T20:05:46+00:00' },
    ]
    expect(latestVerifiedDate(contexts, 'LSD')).toBe('2026-08-31')
    expect(isWithinWindowEndingAt('2026-08-30T20:05:46+00:00', 14, '2026-08-30')).toBe(false)
    expect(isWithinWindowEndingAt('2026-08-30T20:05:46+00:00', 14, '2026-08-31')).toBe(true)
    expect(isWithinWindowEndingAt('2026-08-30T07:30:00+00:00', 14, '2026-08-30')).toBe(true)
  })

  it('national case view and its latest date follow the Sri Lanka date', () => {
    const record = (key, verifiedAt) => ({
      record_key: key, disease: 'LSD', verification_status: 'VERIFIED', verified_at: verifiedAt, reported_at: verifiedAt,
      location_status: 'VALID', latitude: 5.95, longitude: 80.55,
    })
    const records = [record('CASE:a', '2026-08-30T07:30:00+00:00'), record('CASE:b', '2026-08-30T20:05:46+00:00')]
    expect(caseDateKey(records[1])).toBe('2026-08-31')
    const allToAug30 = buildNationalCaseView(records, { disease: 'LSD', windowDays: Infinity, endIsoDate: '2026-08-30' })
    expect(allToAug30.counts.verified).toBe(1)
    const allToAug31 = buildNationalCaseView(records, { disease: 'LSD', windowDays: Infinity, endIsoDate: '2026-08-31' })
    expect(allToAug31.counts.verified).toBe(2)
  })

  it('replay days and daily activity buckets are Sri Lanka days', () => {
    const contexts = [{ verificationTime: '2026-08-30T20:05:46+00:00' }, { verificationTime: '2026-08-30T07:30:00+00:00' }]
    expect(buildObservedReplayDates(contexts)).toEqual(['2026-08-30', '2026-08-31'])
    const { points } = buildRecentActivityBuckets(contexts, 2, Date.parse('2026-08-31T06:00:00Z'))
    expect(points.map((p) => [p.period, p.count])).toEqual([['2026-08-30', 1], ['2026-08-31', 1]])
  })
})

describe('P0: outside-district sources are never labelled as the vet\'s own farm', () => {
  it('a privacy-reduced operational source shows as a vet-verified case', () => {
    const card = { kind: 'APPROACHING AREA', modelData: true, series: [0, 0.1], directionText: 'direction unavailable', dayStatusText: 'reaches the district on Day 1' }
    const influences = [{ anchorId: 'CASE:x', caseId: 'CASE:x', sourceId: 'OP:LSD:Fabc', recordDomain: 'OPERATIONAL', farmId: null, privacyReduced: true, description: 'Vet-verified case.', status: 'AS OF', card }]
    render(<MyAreaOutbreaksInfluencing influences={influences} farmNames={new Map([['F1', { name: 'Fictional Farm' }]])} />)
    expect(screen.getByText('OP:LSD:Fabc')).toBeTruthy() // its one-way source key only
    expect(screen.queryByText('Assigned farm')).toBeNull()
    expect(screen.queryByText('Fictional Farm')).toBeNull()
  })
})
