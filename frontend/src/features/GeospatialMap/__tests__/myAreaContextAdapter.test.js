import { describe, expect, it } from 'vitest'

import { normalizeMyAreaContext } from '../adapters/myAreaContextAdapter'

function rawArea(overrides = {}) {
  return { farm_id: 'F1', latitude: 6.9271, longitude: 79.8612, location_status: 'VALID', location_district: 'Colombo', total_animals: 12, ...overrides }
}

function rawOrigin(overrides = {}) {
  return { origin_id: 'ORIGIN:X', disease: 'LSD', t0: '2026-01-01', distance_from_area_km: 12.3, distance_basis: 'NEAREST_T0_TRIGGER_SOURCE', scientific_mode: 'RETROSPECTIVE_PROXY', ...overrides }
}

function rawSelectedOriginContext(overrides = {}) {
  return {
    origin_id: 'ORIGIN:X', disease: 'LSD', forecast_day: 1, forecast_date: null, t0: '2026-01-01',
    nearest_historical_source: { source_id: 'S1', distance_from_area_km: 5.5, availability_quality: 'ACTUAL', gps_quality: 'EXACT' },
    relative_spatial_score: { value: null, label: 'Relative Spatial Score', temporal_basis: 'STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT', status: 'SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT', scientific_cell_id: null },
    nominal_reach_context: { day: 1, forecast_date: null, basis: 'FORECAST', nominal_reach_km: 10.0, relation: 'NOT_APPLICABLE', anchor_basis: 'NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR', disclaimer: 'Nominal reach — visualization only, not a disease boundary.' },
    ...overrides,
  }
}

function rawClinicalContext(overrides = {}) {
  return { case_id: 'C1', farm_id: 'F1', disease: 'LSD', semantic_class: 'VERIFIED_CLINICAL_CONTEXT', verification_time: '2026-01-02 10:00:00', timestamp_basis: 'VERIFICATION_TIME', ...overrides }
}

describe('GEO-AREA-02-ADAPTER-01: area/farm handling', () => {
  it('valid authorized farm accepted', () => {
    const result = normalizeMyAreaContext({ status: 'OK', area: rawArea() })
    expect(result.area.farmId).toBe('F1')
    expect(result.area.locationStatus).toBe('VALID')
  })

  it('malformed coordinate does not survive as a usable marker location', () => {
    const result = normalizeMyAreaContext({ status: 'LOCATION_REQUIRED', area: rawArea({ latitude: Number.NaN }) })
    expect(result.area.latitude).toBeNull()
    expect(result.area.locationStatus).toBe('LOCATION_REQUIRED')
  })

  it('area with no farm_id is dropped entirely', () => {
    const result = normalizeMyAreaContext({ status: 'ASSIGNED_AREA_NOT_FOUND', area: { latitude: 1, longitude: 1 } })
    expect(result.area).toBeNull()
  })
})

describe('GEO-AREA-02-ADAPTER-02: relevant origins preserve distance_basis (never an alias)', () => {
  it('relevant origins preserved with their real fields', () => {
    const result = normalizeMyAreaContext({ status: 'OK', relevant_origins: [rawOrigin()] })
    expect(result.relevantOrigins).toHaveLength(1)
    expect(result.relevantOrigins[0].originId).toBe('ORIGIN:X')
  })

  it('distance_basis preserved verbatim', () => {
    const result = normalizeMyAreaContext({ status: 'OK', relevant_origins: [rawOrigin()] })
    expect(result.relevantOrigins[0].distanceBasis).toBe('NEAREST_T0_TRIGGER_SOURCE')
  })

  it('no distance_to_origin alias is ever created on the normalized shape', () => {
    const result = normalizeMyAreaContext({ status: 'OK', relevant_origins: [rawOrigin()] })
    const keys = Object.keys(result.relevantOrigins[0])
    expect(keys).not.toContain('distanceToOrigin')
    expect(keys).not.toContain('distanceToOriginKm')
  })

  it('unknown disease excluded, never defaulted to LSD', () => {
    const result = normalizeMyAreaContext({ status: 'OK', relevant_origins: [rawOrigin({ disease: 'RABIES' })] })
    expect(result.relevantOrigins).toHaveLength(0)
  })

  it('deterministic ordering by distance then id', () => {
    const result = normalizeMyAreaContext({
      status: 'OK',
      relevant_origins: [rawOrigin({ origin_id: 'O2', distance_from_area_km: 5 }), rawOrigin({ origin_id: 'O1', distance_from_area_km: 5 }), rawOrigin({ origin_id: 'O3', distance_from_area_km: 1 })],
    })
    expect(result.relevantOrigins.map((o) => o.originId)).toEqual(['O3', 'O1', 'O2'])
  })

  it('missing distance is dropped, never fabricated as 0', () => {
    const result = normalizeMyAreaContext({ status: 'OK', relevant_origins: [rawOrigin({ distance_from_area_km: undefined })] })
    expect(result.relevantOrigins).toHaveLength(0)
  })
})

describe('GEO-AREA-02-ADAPTER-03: selected origin context', () => {
  it('t0 preserved', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.t0).toBe('2026-01-01')
  })

  it('nearest historical source preserved separately from relevant-origin distance', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.nearestHistoricalSource.sourceId).toBe('S1')
    expect(result.selectedOriginContext.nearestHistoricalSource.distanceFromAreaKm).toBe(5.5)
  })

  it('nominal_reach_km preserved', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.nominalReachContext.nominalReachKm).toBe(10.0)
  })

  it('relation NOT_APPLICABLE preserved, never recomputed', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.nominalReachContext.relation).toBe('NOT_APPLICABLE')
  })

  it('anchor_basis preserved', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.nominalReachContext.anchorBasis).toBe('NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR')
  })

  it('disclaimer preserved verbatim', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.nominalReachContext.disclaimer).toBe('Nominal reach — visualization only, not a disease boundary.')
  })

  it('Relative Spatial Score null remains null', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.relativeSpatialScore.value).toBeNull()
  })

  it('null score never becomes zero', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.relativeSpatialScore.value).not.toBe(0)
  })

  it('relative_spatial_score.status preserved', () => {
    const result = normalizeMyAreaContext({ status: 'OK', selected_origin_context: rawSelectedOriginContext() })
    expect(result.selectedOriginContext.relativeSpatialScore.status).toBe('SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT')
  })

  it('missing selected_origin_context normalizes to null, never a fabricated empty object', () => {
    const result = normalizeMyAreaContext({ status: 'NO_RELEVANT_ORIGINS' })
    expect(result.selectedOriginContext).toBeNull()
  })
})

describe('GEO-AREA-02-ADAPTER-04: verified clinical context stays separate', () => {
  it('verified clinical context preserved separately from origins/model context', () => {
    const result = normalizeMyAreaContext({ status: 'OK', verified_clinical_contexts: [rawClinicalContext()] })
    expect(result.verifiedClinicalContexts).toHaveLength(1)
    expect(result.verifiedClinicalContexts[0].semanticClass).toBe('VERIFIED_CLINICAL_CONTEXT')
  })

  it('a record with the wrong semantic_class is dropped', () => {
    const result = normalizeMyAreaContext({ status: 'OK', verified_clinical_contexts: [rawClinicalContext({ semantic_class: 'CONFIRMED_OUTBREAK' })] })
    expect(result.verifiedClinicalContexts).toHaveLength(0)
  })

  it('deterministic ordering by case id', () => {
    const result = normalizeMyAreaContext({
      status: 'OK',
      verified_clinical_contexts: [rawClinicalContext({ case_id: 'C2' }), rawClinicalContext({ case_id: 'C1' })],
    })
    expect(result.verifiedClinicalContexts.map((c) => c.caseId)).toEqual(['C1', 'C2'])
  })

  it('keeps coordinates null when the case record does not expose them', () => {
    const result = normalizeMyAreaContext({ status: 'OK', verified_clinical_contexts: [rawClinicalContext()] })
    expect(result.verifiedClinicalContexts[0].latitude).toBeNull()
    expect(result.verifiedClinicalContexts[0].longitude).toBeNull()
  })

  it('preserves only explicit valid case-level coordinates', () => {
    const result = normalizeMyAreaContext({
      status: 'OK',
      verified_clinical_contexts: [rawClinicalContext({ latitude: 5.9549, longitude: 80.555 })],
    })
    expect(result.verifiedClinicalContexts[0].latitude).toBe(5.9549)
    expect(result.verifiedClinicalContexts[0].longitude).toBe(80.555)
  })
})

describe('GEO-AREA-02-ADAPTER-05: defensive against malformed/missing input', () => {
  it('handles a completely empty response body', () => {
    const result = normalizeMyAreaContext({})
    expect(result.area).toBeNull()
    expect(result.relevantOrigins).toEqual([])
    expect(result.verifiedClinicalContexts).toEqual([])
  })

  it('handles null/undefined input without throwing', () => {
    expect(() => normalizeMyAreaContext(null)).not.toThrow()
    expect(() => normalizeMyAreaContext(undefined)).not.toThrow()
  })

  it('unknown top-level disease is excluded, never defaulted to LSD', () => {
    const result = normalizeMyAreaContext({ status: 'OK', disease: 'RABIES' })
    expect(result.disease).toBeNull()
  })
})
