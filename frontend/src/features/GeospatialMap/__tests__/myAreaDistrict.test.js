import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { findDistrictFeature } from '../adapters/districtGeometry'
import {
  collectMyAreaCaseContexts,
  MY_AREA_DISTRICT_SOURCE,
  MY_AREA_DISTRICT_STATUS,
  resolveMyAreaDistrict,
} from '../adapters/myAreaDistrict'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const realDistricts = JSON.parse(readFileSync(join(FEATURE_ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8'))

function context(overrides = {}) {
  return { vetDistrict: null, farms: [], surveillanceFarms: [], surveillanceContexts: [], clinicalContexts: [], surveillanceStatus: null, ...overrides }
}

describe("resolveMyAreaDistrict: My Area follows the logged-in vet's authorised district", () => {
  it('is LOADING until the operational context has arrived', () => {
    expect(resolveMyAreaDistrict({ operationalData: null })).toEqual({ status: MY_AREA_DISTRICT_STATUS.LOADING, district: null, source: null })
  })

  it("uses the district on the vet's profile", () => {
    expect(resolveMyAreaDistrict({ operationalData: context({ vetDistrict: 'Galle' }) })).toEqual({
      status: MY_AREA_DISTRICT_STATUS.RESOLVED, district: 'Galle', source: MY_AREA_DISTRICT_SOURCE.VET_PROFILE,
    })
  })

  it('normalizes the profile spelling ("KURUNEGALA DISTRICT" -> "Kurunegala")', () => {
    expect(resolveMyAreaDistrict({ operationalData: context({ vetDistrict: 'KURUNEGALA DISTRICT' }) }).district).toBe('Kurunegala')
  })

  it('never falls back to a fixed district when the profile has none', () => {
    const result = resolveMyAreaDistrict({ operationalData: context({ surveillanceStatus: 'NO_REGISTERED_DISTRICT' }) })
    expect(result).toEqual({ status: MY_AREA_DISTRICT_STATUS.NO_REGISTERED_DISTRICT, district: null, source: null })
  })

  it('reports a failed district lookup separately from a missing district', () => {
    const result = resolveMyAreaDistrict({ operationalData: context({ surveillanceStatus: 'DISTRICT_DATA_UNAVAILABLE' }) })
    expect(result.status).toBe(MY_AREA_DISTRICT_STATUS.DISTRICT_DATA_UNAVAILABLE)
    expect(result.district).toBeNull()
  })

  it('a national (ALL_DISTRICTS) account focuses on the selected assigned farm district', () => {
    const operationalData = context({
      vetDistrict: 'ALL_DISTRICTS',
      farms: [{ farmId: 'F1', locationDistrict: 'Badulla' }, { farmId: 'F2', locationDistrict: 'Ampara' }],
    })
    expect(resolveMyAreaDistrict({ operationalData, selectedFarmId: 'F2' })).toEqual({
      status: MY_AREA_DISTRICT_STATUS.RESOLVED, district: 'Ampara', source: MY_AREA_DISTRICT_SOURCE.SELECTED_FARM,
    })
  })

  it('a national account with no selected farm is asked to select one instead of guessing', () => {
    const operationalData = context({ vetDistrict: 'all_districts', farms: [{ farmId: 'F1', locationDistrict: 'Badulla' }] })
    expect(resolveMyAreaDistrict({ operationalData, selectedFarmId: null }).status).toBe(MY_AREA_DISTRICT_STATUS.SELECT_FARM_FOR_NATIONAL_SCOPE)
  })

  it('every one of the 25 real Sri Lankan districts resolves to its own real ADM2 boundary', () => {
    const shapeNames = realDistricts.features.map((f) => f.properties.shapeName)
    expect(shapeNames).toHaveLength(25)
    for (const shapeName of shapeNames) {
      const bareName = shapeName.replace(/\s+District$/i, '')
      for (const spelling of [bareName, shapeName, bareName.toUpperCase(), `7.0, 80.0 (${shapeName})`]) {
        const { district } = resolveMyAreaDistrict({ operationalData: context({ vetDistrict: spelling }) })
        expect(district).toBe(bareName)
        expect(findDistrictFeature(realDistricts, district)?.properties.shapeName).toBe(shapeName)
      }
    }
  })
})

describe('collectMyAreaCaseContexts: real verified cases only', () => {
  const lsd = (caseId, extra = {}) => ({ caseId, disease: 'LSD', ...extra })

  it("merges district surveillance, the vet's own cases and /my-area cases, one per case id", () => {
    const operationalData = context({
      surveillanceContexts: [lsd('A'), lsd('B')],
      clinicalContexts: [lsd('B'), lsd('C')],
    })
    const result = collectMyAreaCaseContexts({ operationalData, myAreaContexts: [lsd('C'), lsd('D')], disease: 'LSD' })
    expect(result.map((c) => c.caseId).sort()).toEqual(['A', 'B', 'C', 'D'])
  })

  it('keeps only the selected disease and drops contexts without a case id', () => {
    const operationalData = context({ surveillanceContexts: [lsd('A'), { caseId: 'F', disease: 'FMD' }, { disease: 'LSD' }] })
    expect(collectMyAreaCaseContexts({ operationalData, disease: 'LSD' }).map((c) => c.caseId)).toEqual(['A'])
  })

  it('returns nothing without a disease or data -- never invented cases', () => {
    expect(collectMyAreaCaseContexts({ operationalData: context({ surveillanceContexts: [lsd('A')] }), disease: null })).toEqual([])
    expect(collectMyAreaCaseContexts({ operationalData: null, disease: 'LSD' })).toEqual([])
  })
})
