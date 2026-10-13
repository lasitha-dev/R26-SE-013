import { describe, expect, it } from 'vitest'

import { aggregateClinicalContextsByFarm, operationalFarmGroupsSignature } from '../adapters/operationalFarmAggregation'

const NOW = new Date('2026-08-30T12:00:00Z').getTime()

function context(overrides = {}) {
  return {
    caseId: 'C1',
    farmId: 'F1',
    disease: 'LSD',
    verificationTime: '2026-08-29 10:00:00',
    latitude: 6.9271,
    longitude: 79.8612,
    locationDistrict: 'Colombo',
    ...overrides,
  }
}

describe('GEO26B Section 8: aggregateClinicalContextsByFarm', () => {
  it('two verified cases at the same farm+disease collapse into one group with caseCount 2', () => {
    const result = aggregateClinicalContextsByFarm(
      [context({ caseId: 'C1' }), context({ caseId: 'C2', verificationTime: '2026-08-28 10:00:00' })],
      NOW,
    )
    expect(result).toHaveLength(1)
    expect(result[0].caseCount).toBe(2)
    expect(result[0].caseIds).toEqual(['C1', 'C2'])
  })

  it('a different disease at the same farm never cross-aggregates', () => {
    const result = aggregateClinicalContextsByFarm([context({ disease: 'LSD' }), context({ caseId: 'C2', disease: 'FMD' })], NOW)
    expect(result).toHaveLength(2)
    expect(result.map((g) => g.disease).sort()).toEqual(['FMD', 'LSD'])
  })

  it('a different farm never aggregates with another farm', () => {
    const result = aggregateClinicalContextsByFarm([context({ farmId: 'F1' }), context({ caseId: 'C2', farmId: 'F2' })], NOW)
    expect(result).toHaveLength(2)
  })

  it('latestVerificationTime is the real maximum among the group, not the first/last input order', () => {
    const result = aggregateClinicalContextsByFarm(
      [
        context({ caseId: 'C1', verificationTime: '2026-08-20 10:00:00' }),
        context({ caseId: 'C2', verificationTime: '2026-08-29 10:00:00' }),
        context({ caseId: 'C3', verificationTime: '2026-08-25 10:00:00' }),
      ],
      NOW,
    )
    expect(result[0].latestVerificationTime).toBe('2026-08-29 10:00:00')
  })

  it('a case with a null/missing verification time is still counted but never becomes "latest"', () => {
    const result = aggregateClinicalContextsByFarm(
      [context({ caseId: 'C1', verificationTime: null }), context({ caseId: 'C2', verificationTime: '2026-08-29 10:00:00' })],
      NOW,
    )
    expect(result[0].caseCount).toBe(2)
    expect(result[0].latestVerificationTime).toBe('2026-08-29 10:00:00')
  })

  it('a group whose every verification time is unparseable has a null latestVerificationTime and older recency, never fabricated', () => {
    const result = aggregateClinicalContextsByFarm([context({ verificationTime: null })], NOW)
    expect(result[0].latestVerificationTime).toBeNull()
    expect(result[0].recencyTier).toBe('older')
  })

  it('recencyTier reflects the real fixed threshold applied to latestVerificationTime', () => {
    const recent = aggregateClinicalContextsByFarm([context({ verificationTime: '2026-08-29 10:00:00' })], NOW)
    expect(recent[0].recencyTier).toBe('recent')

    const older = aggregateClinicalContextsByFarm([context({ verificationTime: '2026-08-01 10:00:00' })], NOW)
    expect(older[0].recencyTier).toBe('older')
  })

  it('empty input produces an empty array', () => {
    expect(aggregateClinicalContextsByFarm([], NOW)).toEqual([])
  })

  it('output is deterministically ordered by farmId then disease, regardless of input order', () => {
    const result = aggregateClinicalContextsByFarm(
      [context({ farmId: 'F2', disease: 'FMD' }), context({ caseId: 'C2', farmId: 'F1', disease: 'LSD' }), context({ caseId: 'C3', farmId: 'F1', disease: 'FMD' })],
      NOW,
    )
    expect(result.map((g) => `${g.farmId}::${g.disease}`)).toEqual(['F1::FMD', 'F1::LSD', 'F2::FMD'])
  })
})

describe('GEO-LIVE-FINAL-PROOF-09: operationalFarmGroupsSignature -- a cheap stable fingerprint for the setData() gate', () => {
  it('two independently-computed group lists with identical real content produce the identical signature', () => {
    const groupsA = aggregateClinicalContextsByFarm([context({ caseId: 'C1' })], NOW)
    const groupsB = aggregateClinicalContextsByFarm([context({ caseId: 'C1' })], NOW) // a fresh array/object graph, same content
    expect(operationalFarmGroupsSignature(groupsA)).toBe(operationalFarmGroupsSignature(groupsB))
  })

  it('a genuinely new case changes the signature (caseCount differs)', () => {
    const before = aggregateClinicalContextsByFarm([context({ caseId: 'C1' })], NOW)
    const after = aggregateClinicalContextsByFarm([context({ caseId: 'C1' }), context({ caseId: 'C2' })], NOW)
    expect(operationalFarmGroupsSignature(before)).not.toBe(operationalFarmGroupsSignature(after))
  })

  it('a re-verified (changed) case changes the signature (latestVerificationTime differs)', () => {
    const before = aggregateClinicalContextsByFarm([context({ verificationTime: '2026-08-29 10:00:00' })], NOW)
    const after = aggregateClinicalContextsByFarm([context({ verificationTime: '2026-08-30 09:00:00' })], NOW)
    expect(operationalFarmGroupsSignature(before)).not.toBe(operationalFarmGroupsSignature(after))
  })

  it('a recencyTier flip (pure time passing, no data change) still changes the signature -- the rendered opacity must never go stale', () => {
    const OLD_NOW = new Date('2026-08-30T12:00:00Z').getTime()
    const MUCH_LATER_NOW = new Date('2027-01-01T00:00:00Z').getTime()
    const groups = [context({ verificationTime: '2026-08-29 10:00:00' })]
    const before = aggregateClinicalContextsByFarm(groups, OLD_NOW)
    const after = aggregateClinicalContextsByFarm(groups, MUCH_LATER_NOW)
    expect(before[0].recencyTier).toBe('recent')
    expect(after[0].recencyTier).toBe('older')
    expect(operationalFarmGroupsSignature(before)).not.toBe(operationalFarmGroupsSignature(after))
  })

  it('group order never affects the signature (sorted internally)', () => {
    const groupsInOrderA = aggregateClinicalContextsByFarm([context({ farmId: 'F1' }), context({ caseId: 'C2', farmId: 'F2' })], NOW)
    const groupsInOrderB = [...groupsInOrderA].reverse()
    expect(operationalFarmGroupsSignature(groupsInOrderA)).toBe(operationalFarmGroupsSignature(groupsInOrderB))
  })

  it('empty input produces a stable empty-string signature', () => {
    expect(operationalFarmGroupsSignature([])).toBe('')
  })
})
