import { describe, expect, it } from 'vitest'

import {
  FARM_STATUS,
  buildDistrictFarmRoster,
  buildOutlookRows,
  buildRecommendedActions,
  buildRegisteredFarmFeatures,
  buildSourceBreakdown,
  buildVerifiedCaseIntelligence,
} from '../adapters/myAreaIntelligence'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'

// FICTIONAL fixtures only. The timeline fixture's sources sit at (6.05, 80.52) and (6.10, 80.48).
const DISTRICT = { type: 'Feature', properties: { shapeName: 'Matara District' }, geometry: { type: 'Polygon', coordinates: [[[80.3, 5.8], [80.8, 5.8], [80.8, 6.4], [80.3, 6.4], [80.3, 5.8]]] } }
const farm = (farmId, lat, lon, extra = {}) => ({ farmId, latitude: lat, longitude: lon, locationStatus: lat == null ? 'LOCATION_REQUIRED' : 'VALID', locationDistrict: 'Matara', personallyAssigned: false, ...extra })
const OPERATIONAL = {
  farms: [farm('F-OWN', 6.06, 80.52, { personallyAssigned: true, totalAnimals: 12 })],
  surveillanceFarms: [farm('F-NEAR', 6.09, 80.49), farm('F-NOGPS', null, null), farm('F-OTHER-DISTRICT', 7.29, 80.63, { locationDistrict: 'Kandy' })],
  clinicalContexts: [{ caseId: 'C1', farmId: 'F-OWN', disease: 'LSD', verificationTime: '2026-10-10T03:30:00+00:00' }],
  surveillanceContexts: [{ caseId: 'C1', farmId: 'F-OWN', disease: 'LSD', verificationTime: '2026-10-10T03:30:00+00:00' }],
}

describe('My Area district intelligence', () => {
  const roster = buildDistrictFarmRoster({ operationalData: OPERATIONAL, districtName: 'Matara', districtFeature: DISTRICT, timeline: mataraTimeline, frameIndex: 7, disease: 'LSD' })

  it('always lists the vet own assigned farm even with no GPS or district, flagged', () => {
    const op = { ...OPERATIONAL, farms: [...OPERATIONAL.farms, farm('F-ASSIGNED-NOGPS', null, null, { personallyAssigned: true, locationDistrict: null })] }
    const r = buildDistrictFarmRoster({ operationalData: op, districtName: 'Matara', districtFeature: DISTRICT, timeline: mataraTimeline, frameIndex: 7, disease: 'LSD' })
    const row = r.rows.find((x) => x.farmId === 'F-ASSIGNED-NOGPS')
    expect(row).toMatchObject({ personallyAssigned: true, outsideDistrict: true, hasGps: false, status: FARM_STATUS.NO_GPS })
    expect(r.rows.some((x) => x.farmId === 'F-OTHER-DISTRICT')).toBe(false) // not assigned, other district: never listed
    expect(r.summary).toMatchObject({ total: 3, assignedOutsideDistrict: 1 }) // never counted as a district farm
    const elsewhere = { ...OPERATIONAL, farms: [farm('F-MINE-KANDY', 7.29, 80.63, { personallyAssigned: true, locationDistrict: 'Kandy' })],
      clinicalContexts: [{ caseId: 'CK', farmId: 'F-MINE-KANDY', disease: 'LSD', verificationTime: '2026-10-10T03:30:00+00:00' }], surveillanceContexts: [] }
    const r2 = buildDistrictFarmRoster({ operationalData: elsewhere, districtName: 'Matara', districtFeature: DISTRICT, timeline: mataraTimeline, frameIndex: 7, disease: 'LSD' })
    expect(buildVerifiedCaseIntelligence({ roster: r2, districtName: 'Matara', districtFeature: DISTRICT, disease: 'LSD' }).reportCount).toBe(0)
    expect(buildRegisteredFarmFeatures(r2).features.some((f) => f.properties.farmId === 'F-MINE-KANDY')).toBe(false)
  })

  it('lists every registered district farm once, with real GPS status, never another district', () => {
    expect(roster.rows.map((r) => r.farmId).sort()).toEqual(['F-NEAR', 'F-NOGPS', 'F-OWN'])
    expect(roster.summary).toMatchObject({ total: 3, mapped: 2, withoutGps: 1, reporting: 1 })
    expect(buildRegisteredFarmFeatures(roster).features.map((f) => f.properties.farmId).sort()).toEqual(['F-NEAR', 'F-OWN'])
  })

  it('a farm inside a scored monitoring area is never labelled as a reporting (infected) farm', () => {
    const near = roster.rows.find((r) => r.farmId === 'F-NEAR')
    expect(near.tier).not.toBeNull()
    expect(near.status).not.toBe(FARM_STATUS.REPORTING)
    expect(near.diseaseCaseCount).toBe(0)
    expect(roster.rows.find((r) => r.farmId === 'F-OWN').status).toBe(FARM_STATUS.REPORTING)
    expect(roster.rows.find((r) => r.farmId === 'F-NOGPS').status).toBe(FARM_STATUS.NO_GPS)
  })

  it('verified, pending and no-GPS reports are counted separately; no-GPS records are listed, never mapped', () => {
    const national = [
      { record_key: 'CASE:p', disease: 'LSD', verification_status: 'PENDING_VERIFICATION', reported_at: '2026-10-11T02:00:00+00:00', location_status: 'VALID', latitude: 6.0, longitude: 80.5 },
      { record_key: 'CASE:n', disease: 'LSD', verification_status: 'VERIFIED', verified_at: '2026-10-09T20:00:00+00:00', location_status: 'LOCATION_REQUIRED', latitude: null, longitude: null, district: 'Matara District' },
      { record_key: 'CASE:x', disease: 'LSD', verification_status: 'PENDING_VERIFICATION', reported_at: '2026-10-11T02:00:00+00:00', location_status: 'VALID', latitude: 7.29, longitude: 80.63 },
    ]
    const intel = buildVerifiedCaseIntelligence({ roster, nationalRecords: national, districtName: 'Matara', districtFeature: DISTRICT, disease: 'LSD' })
    expect(intel.mappedReportCount).toBe(1)
    expect(intel.reportCount).toBe(2)
    expect(intel.uniqueFarmCount).toBe(1)
    expect(intel.uniqueAnimalCount).toBeNull()
    expect(intel.pending.map((p) => p.recordKey)).toEqual(['CASE:p'])
    expect(intel.verifiedWithoutGps).toEqual([{ recordKey: 'CASE:n', date: '2026-10-10', severity: null, stage: null }])
    expect(intel.history.map((h) => h.date)).toEqual(['2026-10-10', '2026-10-11'])
  })

  it('outlook rows read the same backend frames: scored land within reach and monitored farms', () => {
    const rows = buildOutlookRows(mataraTimeline, roster)
    expect(rows).toHaveLength(mataraTimeline.frames.length)
    expect(rows[0].scoredAreaKm2).toBe(0)
    expect(rows[0].monitoredFarms).toBe(0)
    expect(rows[7].monitoredFarms).toBe(2)
    expect(rows[8].exploratory).toBe(true)
    expect(rows.every((r) => !('infected' in r) && !('predictedCases' in r))).toBe(true)
  })

  it('splits sources inside and outside the district', () => {
    const breakdown = buildSourceBreakdown(mataraTimeline, DISTRICT)
    expect(breakdown.inside + breakdown.outside).toBe(mataraTimeline.sources.length)
  })

  it('recommended actions are advisory, evidence-labelled and never triggered by the score alone', () => {
    const actions = buildRecommendedActions({ caseIntel: { reportCount: 0, pending: [] }, roster, breakdown: { outside: 0 }, modelReady: true, timelineOk: true })
    expect(actions).toHaveLength(6)
    const movement = actions.find((a) => a.id === 'movement')
    expect(movement.active).toBe(false) // no reports -> no quarantine prompt from relative score/reach
    expect(movement.why).toMatch(/Not triggered by relative score or nominal reach/)
    expect(new Set(actions.map((a) => a.basis)).size).toBeGreaterThan(1)
  })
})
