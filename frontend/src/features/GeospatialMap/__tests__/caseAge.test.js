import { describe, expect, it } from 'vitest'

import { CASE_AGE_CLASS, CASE_AGE_COLOR, CASE_AGE_MODE, caseAgeDays, caseAgeReference, classifyCaseAge, combinedAgeClass, isCaseMarkerVisible } from '../adapters/caseAge'
import { sriLankaDateKey } from '../adapters/verificationTime'
import { buildNationalCaseView } from '../adapters/nationalCases'
import { buildOperationalMarkerFeatureCollection } from '../components/operationalMarkerLayer'

const REF = '2026-10-16'

describe('observed-case report-date age (Asia/Colombo): 0-14 red, 15-30 brown, >30 hidden', () => {
  it('applies the monitoring-map bands at their exact boundaries', () => {
    expect(classifyCaseAge('2026-10-16T01:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.RECENT, ageDays: 0 })
    expect(classifyCaseAge('2026-10-10T05:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.RECENT, ageDays: 6 })
    expect(classifyCaseAge('2026-10-02T05:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.RECENT, ageDays: 14 })
    expect(classifyCaseAge('2026-10-01T05:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.OLDER, ageDays: 15 })
    expect(classifyCaseAge('2026-09-16T05:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.OLDER, ageDays: 30 })
    expect(classifyCaseAge('2026-09-15T05:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.EXPIRED, ageDays: 31 })
    expect(isCaseMarkerVisible(CASE_AGE_CLASS.RECENT)).toBe(true)
    expect(isCaseMarkerVisible(CASE_AGE_CLASS.OLDER)).toBe(true)
    expect(isCaseMarkerVisible(CASE_AGE_CLASS.EXPIRED)).toBe(false)
    // Unknown dates are never hidden as "old" nor shown as recent.
    expect(isCaseMarkerVisible(CASE_AGE_CLASS.DATE_UNKNOWN)).toBe(true)
    expect(CASE_AGE_COLOR.OLDER).not.toBe(CASE_AGE_COLOR.RECENT)
  })

  it('re-classifies at Asia/Colombo midnight, not UTC midnight', () => {
    const reported = '2026-10-02T04:00:00+00:00' // 09:30 on 2 Oct in Colombo
    // 23:59 on 16 Oct in Colombo (18:29 UTC): still day 14 -> red.
    const lateEvening = sriLankaDateKey(new Date('2026-10-16T18:29:00Z'))
    expect(lateEvening).toBe('2026-10-16')
    expect(classifyCaseAge(reported, lateEvening)).toMatchObject({ ageClass: CASE_AGE_CLASS.RECENT, ageDays: 14 })
    // 00:01 on 17 Oct in Colombo (18:31 UTC, still 16 Oct in UTC): day 15 -> brown.
    const afterMidnight = sriLankaDateKey(new Date('2026-10-16T18:31:00Z'))
    expect(afterMidnight).toBe('2026-10-17')
    expect(classifyCaseAge(reported, afterMidnight)).toMatchObject({ ageClass: CASE_AGE_CLASS.OLDER, ageDays: 15 })
    // A 30-day-old report disappears the next Colombo day.
    expect(classifyCaseAge('2026-09-16T04:00:00+00:00', lateEvening).ageClass).toBe(CASE_AGE_CLASS.OLDER)
    expect(classifyCaseAge('2026-09-16T04:00:00+00:00', afterMidnight).ageClass).toBe(CASE_AGE_CLASS.EXPIRED)
  })

  it('uses the Asia/Colombo calendar date of the instant, not UTC or browser time', () => {
    // 20:00 UTC on 15 Sep is 01:30 on 16 Sep in Colombo -> 30 days.
    expect(caseAgeDays('2026-09-15T20:00:00+00:00', REF)).toBe(30)
    // 18:00 UTC on 15 Sep is 23:30 on 15 Sep in Colombo -> 31 days.
    expect(caseAgeDays('2026-09-15T18:00:00+00:00', REF)).toBe(31)
    // Naive host text is UTC (verificationTime.js rule).
    expect(caseAgeDays('2026-09-15 19:00:00', REF)).toBe(30)
  })

  it('never treats a missing, invalid or future report date as recent', () => {
    expect(classifyCaseAge(null, REF).ageClass).toBe(CASE_AGE_CLASS.DATE_UNKNOWN)
    expect(classifyCaseAge('', REF).ageClass).toBe(CASE_AGE_CLASS.DATE_UNKNOWN)
    expect(classifyCaseAge('not-a-date', REF).ageClass).toBe(CASE_AGE_CLASS.DATE_UNKNOWN)
    expect(classifyCaseAge('2026-10-17T03:00:00+00:00', REF)).toMatchObject({ ageClass: CASE_AGE_CLASS.AFTER_REFERENCE, ageDays: -1 })
    expect(classifyCaseAge('2026-10-01T03:00:00+00:00', null).ageClass).toBe(CASE_AGE_CLASS.DATE_UNKNOWN)
  })

  it('current mode = today at runtime; retrospective mode = the selected date, labelled', () => {
    expect(caseAgeReference({ basisAsOf: null, todayKey: REF })).toMatchObject({ dateKey: REF, mode: CASE_AGE_MODE.CURRENT })
    const retro = caseAgeReference({ basisAsOf: '2020-10-28', todayKey: REF })
    expect(retro).toMatchObject({ dateKey: '2020-10-28', mode: CASE_AGE_MODE.RETROSPECTIVE })
    expect(retro.label).toMatch(/Retrospective/)
  })

  it('a farm with any recent report is drawn recent; unknown never outranks a known age', () => {
    expect(combinedAgeClass([CASE_AGE_CLASS.OLDER, CASE_AGE_CLASS.RECENT])).toBe(CASE_AGE_CLASS.RECENT)
    expect(combinedAgeClass([CASE_AGE_CLASS.DATE_UNKNOWN, CASE_AGE_CLASS.OLDER])).toBe(CASE_AGE_CLASS.OLDER)
    expect(combinedAgeClass([])).toBe(CASE_AGE_CLASS.DATE_UNKNOWN)
  })
})

describe('national case markers carry the age class and are stacked per class', () => {
  const at = (lon, lat) => ({ location_status: 'VALID', longitude: lon, latitude: lat })
  const records = [
    { record_key: 'CASE:1', disease: 'LSD', verification_status: 'VERIFIED', reported_at: '2026-10-10T04:00:00+00:00', verified_at: '2026-10-11T04:00:00+00:00', ...at(80.5, 5.95) },
    { record_key: 'CASE:2', disease: 'LSD', verification_status: 'VERIFIED', reported_at: '2026-08-01T04:00:00+00:00', verified_at: '2026-08-02T04:00:00+00:00', ...at(80.5, 5.95) },
    { record_key: 'CASE:3', disease: 'LSD', verification_status: 'VERIFIED', reported_at: '2026-08-03T04:00:00+00:00', verified_at: '2026-08-04T04:00:00+00:00', ...at(80.5, 5.95) },
    { record_key: 'CASE:4', disease: 'LSD', verification_status: 'PENDING_VERIFICATION', reported_at: null, verified_at: null, ...at(80.0, 7.0) },
    { record_key: 'CASE:5', disease: 'LSD', verification_status: 'VERIFIED', reported_at: '2026-07-01T04:00:00+00:00', verified_at: '2026-07-02T04:00:00+00:00', location_status: 'LOCATION_REQUIRED', latitude: null, longitude: null },
    { record_key: 'CASE:6', disease: 'LSD', verification_status: 'VERIFIED', reported_at: '2026-09-25T04:00:00+00:00', verified_at: '2026-09-25T06:00:00+00:00', ...at(80.6, 5.95) },
  ]

  it('draws 0-30 day cases (red / brown), hides older ones, counts records not markers', () => {
    const view = buildNationalCaseView(records, { disease: 'LSD', windowDays: Infinity, ageReferenceDateKey: REF })
    const markers = view.featureCollection.features.map((f) => [f.properties.ageClass, f.properties.verified, f.properties.count])
    // CASE:2/CASE:3 (Aug, > 30 days) are not drawn; CASE:6 (21 days) is brown.
    expect(markers).toEqual([
      [CASE_AGE_CLASS.DATE_UNKNOWN, false, 1],
      [CASE_AGE_CLASS.OLDER, true, 1],
      [CASE_AGE_CLASS.RECENT, true, 1],
    ])
    expect(view.counts.byAge).toEqual({ RECENT: 1, OLDER: 1, EXPIRED: 3, DATE_UNKNOWN: 1, AFTER_REFERENCE: 0 })
    expect(view.counts).toMatchObject({ inWindow: 6, withoutGps: 1, hiddenOlder: 2, mappedVerified: 2, mappedPending: 1 })
    expect(view.featureCollection.features.every((f) => f.properties.ageClass !== CASE_AGE_CLASS.EXPIRED)).toBe(true)
  })

  it('retrospective reference re-ages the same records against the selected date', () => {
    const view = buildNationalCaseView(records, { disease: 'LSD', windowDays: Infinity, endIsoDate: '2026-08-20', ageReferenceDateKey: '2026-08-20' })
    // Only records dated up to 20 Aug exist at that date (the undated pending
    // record has no date to place it there). At 20 Aug the 1-3 Aug reports are
    // 17-19 days old (brown); the 1 Jul report is 50 days old (not drawn).
    expect(view.featureCollection.features.map((f) => [f.properties.ageClass, f.properties.count])).toEqual([[CASE_AGE_CLASS.OLDER, 2]])
    expect(view.counts.byAge).toEqual({ RECENT: 0, OLDER: 2, EXPIRED: 1, DATE_UNKNOWN: 0, AFTER_REFERENCE: 0 })
  })

  it('vet-district clinical icons use the same report-date rule', () => {
    const fc = buildOperationalMarkerFeatureCollection(
      [
        { farmId: 'F1', disease: 'LSD', latitude: 6, longitude: 80, caseCount: 2, caseIds: ['a', 'b'], reportedAts: ['2026-08-01T00:00:00+00:00', '2026-10-10T00:00:00+00:00'] },
        { farmId: 'F2', disease: 'LSD', latitude: 6, longitude: 80.1, caseCount: 1, caseIds: ['c'], reportedAts: ['2026-08-01T00:00:00+00:00'] },
        { farmId: 'F3', disease: 'FMD', latitude: 6, longitude: 80.2, caseCount: 1, caseIds: ['d'], reportedAts: [null] },
        { farmId: 'F4', disease: 'LSD', latitude: 6, longitude: 80.3, caseCount: 1, caseIds: ['e'], reportedAts: ['2026-09-20T00:00:00+00:00'] },
      ],
      { ageReferenceDateKey: REF },
    )
    // F2's only report is > 30 days old: no marker for that farm.
    expect(fc.features.map((f) => [f.properties.farmId, f.properties.ageClass])).toEqual([['F1', CASE_AGE_CLASS.RECENT], ['F3', CASE_AGE_CLASS.DATE_UNKNOWN], ['F4', CASE_AGE_CLASS.OLDER]])
  })
})
