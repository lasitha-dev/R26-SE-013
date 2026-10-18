import { describe, expect, it } from 'vitest'

import { buildRegisteredFarmFeatures } from '../adapters/myAreaIntelligence'

const row = (farmId, reportedAt, disease = 'LSD') => ({
  farmId, label: farmId, status: 'REPORTING', coordinates: [80.5, 5.95], outsideDistrict: false, diseaseCaseCount: 1,
  cases: [{ caseId: `${farmId}-c`, disease, reportedAt, verificationTime: reportedAt }],
})

describe('My Area reporting-farm ring follows the 30-day monitoring rule', () => {
  it('rings a farm only for a report within 30 days of the reference date', () => {
    const roster = { rows: [row('F-30', '2026-09-16T04:00:00+00:00'), row('F-31', '2026-09-15T04:00:00+00:00'), row('F-AUG', '2026-08-30T04:00:00+00:00')] }
    const fc = buildRegisteredFarmFeatures(roster, { ageReferenceDateKey: '2026-10-16', disease: 'LSD' })
    expect(fc.features.map((f) => [f.properties.farmId, f.properties.reporting])).toEqual([['F-30', true], ['F-31', false], ['F-AUG', false]])
    // The farm itself (and its case history) is still listed and drawn as a farm.
    expect(fc.features).toHaveLength(3)
  })

  it('only the selected disease counts, and a retrospective reference re-ages the same history', () => {
    const roster = { rows: [row('F-FMD', '2026-10-10T04:00:00+00:00', 'FMD'), row('F-AUG', '2026-08-30T04:00:00+00:00')] }
    expect(buildRegisteredFarmFeatures(roster, { ageReferenceDateKey: '2026-10-16', disease: 'LSD' }).features.map((f) => f.properties.reporting)).toEqual([false, false])
    expect(buildRegisteredFarmFeatures(roster, { ageReferenceDateKey: '2026-08-31', disease: 'LSD' }).features.map((f) => f.properties.reporting)).toEqual([false, true])
  })
})
