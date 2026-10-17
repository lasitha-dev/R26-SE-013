import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'

import { computeFeatureBounds, findDistrictFeature, isPointInsideDistrictFeature } from '../adapters/districtGeometry'
import { MY_AREA_DISTRICT_STATUS, resolveMyAreaDistrict } from '../adapters/myAreaDistrict'
import { IMPACT_LAYER, caseDetailRows, caseFocusStyle, impactLayerVisibility, outsideDistrictMask } from '../adapters/myAreaMapPresentation'

// The real geoBoundaries ADM2 dataset the app loads (data/ATTRIBUTION.md).
const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const DISTRICTS = JSON.parse(readFileSync(join(FEATURE_ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8'))
// Test probes only (town centres), never app data.
const TOWNS = { Matara: [80.535, 5.948], Galle: [80.217, 6.035], Kandy: [80.636, 7.291] }

function pointInMaskHoles(point, mask) {
  const holes = mask.features[0].geometry.coordinates.slice(1)
  return holes.some((ring) => isPointInsideDistrictFeature(point, { geometry: { type: 'Polygon', coordinates: [ring] } }))
}

describe('My Area focuses the logged-in vet district (Matara, Galle, Kandy)', () => {
  it.each(Object.keys(TOWNS))('%s: the profile district resolves, its real polygon fits the camera and is the only clear area', (name) => {
    // 1. District from the authenticated operational context (vet profile).
    const resolution = resolveMyAreaDistrict({ operationalData: { vetDistrict: name } })
    expect(resolution).toMatchObject({ status: MY_AREA_DISTRICT_STATUS.RESOLVED, district: name })
    // 2. Its real ADM2 polygon and bounds (what the map fits to).
    const feature = findDistrictFeature(DISTRICTS, resolution.district)
    expect(feature).toBeTruthy()
    const [[west, south], [east, north]] = computeFeatureBounds(feature)
    const [lon, lat] = TOWNS[name]
    expect(lon).toBeGreaterThan(west); expect(lon).toBeLessThan(east)
    expect(lat).toBeGreaterThan(south); expect(lat).toBeLessThan(north)
    expect(east - west).toBeLessThan(1.5) // a district, not the island
    // 3. The fade covers everything outside: the district (and only it) is a hole.
    const mask = outsideDistrictMask(feature)
    expect(pointInMaskHoles(TOWNS[name], mask)).toBe(true)
    for (const other of Object.keys(TOWNS).filter((n) => n !== name)) expect(pointInMaskHoles(TOWNS[other], mask)).toBe(false)
  })

  it('a national account without a selected farm does not guess a district; no polygon -> no fade', () => {
    expect(resolveMyAreaDistrict({ operationalData: { vetDistrict: 'ALL_DISTRICTS', farms: [] } }).status).toBe(MY_AREA_DISTRICT_STATUS.SELECT_FARM_FOR_NATIONAL_SCOPE)
    expect(resolveMyAreaDistrict({ operationalData: {} }).status).toBe(MY_AREA_DISTRICT_STATUS.NO_REGISTERED_DISTRICT)
    expect(outsideDistrictMask(null).features).toEqual([])
  })

  it('the fit leaves room for the bottom timeline dock at every width', async () => {
    if (!globalThis.URL.createObjectURL) globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock') // MapLibre worker setup
    const { getMyAreaMapPadding } = await import('../components/MyAreaMapCanvas')
    for (const width of [360, 700, 1200]) {
      const padding = getMyAreaMapPadding(width)
      expect(padding.bottom).toBeGreaterThan(padding.top)
    }
  }, 30000) // loading MapLibre in a test worker can be slow
})

describe('Future Impact views and case selection', () => {
  it('Cases / Risk Zones / Trajectory each draw their own layers; Verified Cases shows the cases only', () => {
    expect(impactLayerVisibility(true, IMPACT_LAYER.CASES)).toEqual({ riskSurface: false, trajectory: false, modelSources: true, verifiedCases: true })
    expect(impactLayerVisibility(true, IMPACT_LAYER.RISK)).toEqual({ riskSurface: true, trajectory: false, modelSources: true, verifiedCases: false })
    expect(impactLayerVisibility(true, IMPACT_LAYER.TRAJECTORY)).toEqual({ riskSurface: false, trajectory: true, modelSources: true, verifiedCases: false })
    expect(impactLayerVisibility(false, IMPACT_LAYER.RISK)).toEqual({ riskSurface: false, trajectory: false, modelSources: false, verifiedCases: true })
  })

  it('a selected case stays clear and pulsing; the other markers fade but stay visible', () => {
    expect(caseFocusStyle(null)).toEqual({ coreOpacity: 0.98, strokeOpacity: 1, pulseFilter: ['==', ['get', 'ageClass'], 'RECENT'] })
    const style = caseFocusStyle('case-7')
    expect(style.coreOpacity).toEqual(['case', ['==', ['get', 'anchorId'], 'case-7'], 0.98, 0.3])
    expect(style.coreOpacity[3]).toBeGreaterThan(0) // faded, never hidden
    expect(style.pulseFilter).toEqual(['all', ['==', ['get', 'ageClass'], 'RECENT'], ['==', ['get', 'anchorId'], 'case-7']])
  })

  it('the case popup lists only the real record fields', () => {
    const rows = caseDetailRows({ caseId: 'C-1', disease: 'LSD', reportedAt: '2026-10-16T08:00:00', verificationTime: '2026-10-16T09:30:00', farmId: 'F-9', ageClass: 'RECENT' }, 'Matara')
    expect(rows).toEqual([
      ['Verified case', 'C-1'],
      ['Disease', 'LSD'],
      ['Reported', '2026-10-16 (reported 0–14 days ago)'],
      ['Verified', '2026-10-16 09:30'],
      ['District', 'Matara'],
      ['Farm', 'F-9'],
      ['Status', 'Vet-verified diagnosis (not an official outbreak confirmation)'],
    ])
    expect(caseDetailRows({ caseId: 'C-2' }).map(([label]) => label)).toEqual(['Verified case', 'Status'])
  })
})
