import { describe, expect, it } from 'vitest'

import { normalizeOperationalContext } from '../adapters/operationalContextAdapter'

function rawFarm(overrides = {}) {
  return { farm_id: 'F1', latitude: 6.9271, longitude: 79.8612, location_status: 'VALID', location_district: 'Colombo', ...overrides }
}

function rawContext(overrides = {}) {
  return {
    case_id: 'C1',
    farm_id: 'F1',
    disease: 'LSD',
    semantic_class: 'VERIFIED_CLINICAL_CONTEXT',
    verification_time: '2026-01-02 10:00:00',
    timestamp_basis: 'VERIFICATION_TIME',
    ...overrides,
  }
}

describe('GEO-INT-03-ADAPTER-01: disease handling', () => {
  it('accepts a valid LSD context', () => {
    const result = normalizeOperationalContext({ status: 'OK', farms: [rawFarm()], clinical_contexts: [rawContext()] })
    expect(result.clinicalContexts).toHaveLength(1)
    expect(result.clinicalContexts[0].disease).toBe('LSD')
  })

  it('accepts a valid FMD context, remaining distinct from LSD', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ case_id: 'C2', disease: 'FMD' })],
    })
    expect(result.clinicalContexts[0].disease).toBe('FMD')
  })

  it('excludes an unknown disease -- never defaults to LSD or FMD', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ disease: 'MASTITIS' })],
    })
    expect(result.clinicalContexts).toHaveLength(0)
  })

  it('excludes a context missing semantic_class or carrying the wrong one', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ semantic_class: 'CONFIRMED_OUTBREAK' })],
    })
    expect(result.clinicalContexts).toHaveLength(0)
  })
})

describe('GEO-INT-03-ADAPTER-02: location handling', () => {
  it('excludes a context whose farm has an invalid latitude', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm({ latitude: Number.NaN })],
      clinical_contexts: [rawContext()],
    })
    expect(result.clinicalContexts).toHaveLength(0)
  })

  it('excludes a context whose farm has an invalid longitude', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm({ longitude: Number.POSITIVE_INFINITY })],
      clinical_contexts: [rawContext()],
    })
    expect(result.clinicalContexts).toHaveLength(0)
  })

  it('LOCATION_REQUIRED farms are excluded from producing a marker but still counted', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm({ location_status: 'LOCATION_REQUIRED', latitude: null, longitude: null })],
      clinical_contexts: [rawContext()],
    })
    expect(result.clinicalContexts).toHaveLength(0)
    expect(result.locationRequiredFarmCount).toBe(1)
    expect(result.farms[0].latitude).toBeNull()
    expect(result.farms[0].longitude).toBeNull()
  })

  it('never invents a coordinate for a farm with missing latitude/longitude', () => {
    const result = normalizeOperationalContext({ status: 'OK', farms: [rawFarm({ latitude: undefined, longitude: undefined })], clinical_contexts: [] })
    expect(result.farms[0].latitude).toBeNull()
    expect(result.farms[0].longitude).toBeNull()
  })
})

describe('GEO-INT-03-ADAPTER-03: preserves semantic_class and timestamp_basis', () => {
  it('round-trips both fields unchanged', () => {
    const result = normalizeOperationalContext({ status: 'OK', farms: [rawFarm()], clinical_contexts: [rawContext()] })
    expect(result.clinicalContexts[0].semanticClass).toBe('VERIFIED_CLINICAL_CONTEXT')
    expect(result.clinicalContexts[0].timestampBasis).toBe('VERIFICATION_TIME')
  })
})

describe('GEO-INT-03-ADAPTER-04: deterministic ordering', () => {
  it('sorts clinical contexts by caseId regardless of input order', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ case_id: 'C3' }), rawContext({ case_id: 'C1' }), rawContext({ case_id: 'C2' })],
    })
    expect(result.clinicalContexts.map((c) => c.caseId)).toEqual(['C1', 'C2', 'C3'])
  })
})

describe('GEO-INT-03-ADAPTER-05: malformed/missing input handled defensively', () => {
  it('handles a completely empty response body', () => {
    const result = normalizeOperationalContext({})
    expect(result.farms).toEqual([])
    expect(result.clinicalContexts).toEqual([])
  })

  it('handles null/undefined input without throwing', () => {
    expect(() => normalizeOperationalContext(null)).not.toThrow()
    expect(() => normalizeOperationalContext(undefined)).not.toThrow()
  })

  it('drops a context with no case_id and a farm with no farm_id', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm({ farm_id: undefined }), rawFarm()],
      clinical_contexts: [rawContext({ case_id: undefined })],
    })
    expect(result.farms).toHaveLength(1)
    expect(result.clinicalContexts).toHaveLength(0)
  })

  it('drops a context pointing at a farm_id that does not exist in the farms list', () => {
    const result = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ farm_id: 'F-UNKNOWN' })],
    })
    expect(result.clinicalContexts).toHaveLength(0)
  })
})

describe('GEO-OWNED-FINAL-08 Section 1/3: each call is independent -- never append-only, never a merge with a prior result', () => {
  it('a case verified LSD on the first call and re-verified FMD on the second reflects only FMD, never both', () => {
    const first = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ disease: 'LSD' })],
    })
    expect(first.clinicalContexts.map((c) => c.disease)).toEqual(['LSD'])

    const second = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext({ disease: 'FMD', verification_time: '2026-02-01 09:00:00' })],
    })
    expect(second.clinicalContexts.map((c) => c.disease)).toEqual(['FMD'])
  })

  it('a case present on the first call and absent from the second (deleted/unverified upstream) is gone, never carried over', () => {
    const first = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm()],
      clinical_contexts: [rawContext()],
    })
    expect(first.clinicalContexts).toHaveLength(1)

    const second = normalizeOperationalContext({ status: 'NO_VERIFIED_CLINICAL_CONTEXT', farms: [rawFarm()], clinical_contexts: [] })
    expect(second.clinicalContexts).toHaveLength(0)
  })

  it("a farm's coordinates changing between calls is reflected fresh, never the first call's cached value", () => {
    const first = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm({ latitude: 6.9271, longitude: 79.8612 })],
      clinical_contexts: [rawContext()],
    })
    expect(first.clinicalContexts[0].latitude).toBe(6.9271)

    const second = normalizeOperationalContext({
      status: 'OK',
      farms: [rawFarm({ latitude: 7.5, longitude: 81.0 })],
      clinical_contexts: [rawContext()],
    })
    expect(second.clinicalContexts[0].latitude).toBe(7.5)
    expect(second.clinicalContexts[0].longitude).toBe(81.0)
  })
})
