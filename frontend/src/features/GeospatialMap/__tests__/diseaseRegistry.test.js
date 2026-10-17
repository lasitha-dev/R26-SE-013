import { describe, expect, it } from 'vitest'

import { CAPABILITY, DEFAULT_DISEASE_CODE, getDiseaseConfig, hasCapability, isDiseaseReady, listDiseaseCodes } from '../disease/diseaseRegistry'
import { FmdModelNotReadyError, buildForecastFrame as fmdBuildForecastFrame } from '../adapters/fmdOutbreakAdapter'
import { getOutbreakAdapter } from '../adapters/index'
import * as lsdOutbreakAdapter from '../adapters/lsdOutbreakAdapter'

describe('diseaseRegistry', () => {
  it('defaults to LSD (the first implementation target)', () => {
    expect(DEFAULT_DISEASE_CODE).toBe('LSD')
  })

  it('LSD is ready, FMD is not -- matches the live backend readiness check (2026-08-27)', () => {
    expect(isDiseaseReady('LSD')).toBe(true)
    expect(isDiseaseReady('FMD')).toBe(false)
  })

  it('LSD uses a diamond marker, FMD a circle -- shape differentiates disease, never risk colour', () => {
    expect(getDiseaseConfig('LSD').markerShape).toBe('diamond')
    expect(getDiseaseConfig('FMD').markerShape).toBe('circle')
  })

  it('apiValue matches the backend SUPPORTED_DISEASES abbreviation keys exactly', () => {
    expect(getDiseaseConfig('LSD').apiValue).toBe('lsd')
    expect(getDiseaseConfig('FMD').apiValue).toBe('fmd')
  })

  it('throws on an unknown disease code rather than silently returning undefined config', () => {
    expect(() => getDiseaseConfig('XYZ')).toThrow(/unknown disease code/)
  })

  it('lists both registered disease codes', () => {
    expect(listDiseaseCodes()).toEqual(['LSD', 'FMD'])
  })

  // GEO-TRAJECTORY-01: confirmed live against the running backend
  // (2026-09-01, `GET /analysis/{id}/cells?disease=lsd`) -- every sampled
  // real LSD origin's cells carry a real `direction.bearing_deg`, and
  // `nominal_reach_by_day` is real and non-zero for days 1-7. TRAJECTORY
  // must track DIRECTION/NOMINAL_REACH (both already `true` for LSD) --
  // it previously stayed `false` as a stale gate, not a real backend
  // limitation, which is what left the Trajectory mode pill permanently
  // disabled despite real data existing.
  it('LSD trajectory capability matches its real direction/reach capabilities (no stale gate)', () => {
    expect(hasCapability('LSD', CAPABILITY.TRAJECTORY)).toBe(true)
    expect(hasCapability('LSD', CAPABILITY.DIRECTION)).toBe(true)
    expect(hasCapability('LSD', CAPABILITY.NOMINAL_REACH)).toBe(true)
  })

  it('FMD has no trajectory capability -- no spatial-cell/direction model exists for it at all', () => {
    expect(hasCapability('FMD', CAPABILITY.TRAJECTORY)).toBe(false)
    expect(hasCapability('FMD', CAPABILITY.DIRECTION)).toBe(false)
    expect(hasCapability('FMD', CAPABILITY.SPATIAL_CELLS)).toBe(false)
  })
})

describe('adapter registry', () => {
  it('resolves LSD to the real lsdOutbreakAdapter', () => {
    expect(getOutbreakAdapter('LSD')).toBe(lsdOutbreakAdapter)
  })

  it('FMD adapter functions throw FmdModelNotReadyError rather than returning fabricated/empty data', () => {
    expect(() => fmdBuildForecastFrame()).toThrow(FmdModelNotReadyError)
  })

  it('throws for a disease code with no registered adapter', () => {
    expect(() => getOutbreakAdapter('XYZ')).toThrow(/no outbreak adapter registered/)
  })
})
