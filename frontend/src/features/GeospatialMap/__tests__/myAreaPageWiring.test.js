import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const page = readFileSync(join(ROOT, 'pages', 'MyAreaPage.jsx'), 'utf8')
const map = readFileSync(join(ROOT, 'components', 'MyAreaMapCanvas.jsx'), 'utf8')
// The real-case normaliser the page uses (moved out of the legacy module).
const helper = readFileSync(join(ROOT, 'adapters', 'timelinePresentation.js'), 'utf8')
const hook = readFileSync(join(ROOT, 'context', 'useMyAreaContext.js'), 'utf8')
const districtAdapter = readFileSync(join(ROOT, 'adapters', 'myAreaDistrict.js'), 'utf8')

describe('Page-2 authorized context and vet-district presentation wiring', () => {
  it('preserves authorized-farm empty and single-farm auto-selection states', () => {
    expect(page).toContain('authorizedFarms.length === 0')
    expect(page).toContain('authorizedFarms.length === 1')
    expect(page).toContain('ctx.selectArea(authorizedFarms[0].farmId)')
  })

  it("resolves the district from the vet's own operational context -- no fixed district, case ID or coordinate literal", () => {
    expect(page).not.toContain('MY_AREA_DEMO_DISTRICT_OVERRIDE')
    expect(page).not.toMatch(/matara/i)
    expect(page).toContain('resolveMyAreaDistrict({ operationalData: operational.data, selectedFarmId: ctx.selectedAreaId })')
    expect(page).toContain('const authorizedDistrict = districtResolution.district')
    expect(page).not.toMatch(/caseId:\s*['"][^'"]+['"]/)
    expect(page).not.toMatch(/coordinates:\s*\[\s*\d/)
  })

  it('builds mapped cases from real operational contexts and the real ADM2 district geometry', () => {
    expect(page).toContain('collectMyAreaCaseContexts({')
    expect(districtAdapter).toContain('operationalData?.surveillanceContexts')
    expect(districtAdapter).toContain('operationalData?.clinicalContexts')
    expect(page).toContain('useDistrictGeometry(authorizedDistrict)')
    expect(page).toContain('scopePointFeaturesToDistrict(buildObservedCaseFeatures(candidateCaseContexts), districtFeature)')
  })

  it('keeps the existing My Area API request at day zero and out of the presentation index dependencies', () => {
    expect(page).toContain('originId: null')
    expect(page).toContain('day: 0')
    expect(page).not.toContain('day: activeAreaForecastIndex')
    expect(hook).toMatch(/\[farmId, disease, originId, day, retryToken\]/)
  })

  it('retains live-event relevance gating and does not mutate cases client-side', () => {
    expect(page).toContain('isEventRelevantToMyArea(event, { selectedAreaId: ctx.selectedAreaId })')
    expect(page).toContain('setRetryToken((token) => token + 1)')
    expect(page).not.toContain('pushClinicalCase')
  })

  it('uses one map instance and one district fit while allowing explicit View-on-Map camera emphasis', () => {
    expect(map.split('new maplibregl.Map(').length - 1).toBe(1)
    expect(map.split('fitBounds(').length - 1).toBe(1)
    expect(map.split('easeTo(').length - 1).toBe(1)
    expect(map).not.toContain('flyTo(')
    expect(map).not.toContain('jumpTo(')
  })

  it('never moves a confirmed red marker as part of the forecast generator', () => {
    expect(page).toContain('observedCaseFeatures={impactLayerVisibility(showImpact, impactLayer).verifiedCases ? observedCaseFeatures : []}')
    expect(page).toContain('.filter((f) => !observedThrough')
    expect(page).toContain('ageClass: classifyCaseAge(f.properties?.reportedAt, caseAgeRef.dateKey).ageClass')
    expect(helper).toContain('geometry: { type: \'Point\', coordinates: [...feature.geometry.coordinates] }')
    expect(helper).not.toContain('Math.random')
  })

  it('keeps unavailable/session states explicit and does not invent fallback case data', () => {
    expect(page).toContain('MY_AREA_REQUEST_STATE.ERROR')
    expect(page).toContain('LABEL_MY_AREA_SESSION_REQUIRED')
    expect(page).toContain('Waiting for the backend spatial timeline.')
    expect(page).toContain('DISTRICT_STATUS_MESSAGE[districtResolution.status]')
    expect(page).not.toMatch(/area:\s*\{\s*farmId:\s*['"]/)
  })

  it('keeps host shell and auth ownership outside this page', () => {
    expect(page).not.toContain('VetLayout')
    expect(page).not.toContain('TopHeader')
    expect(page).not.toContain('localStorage')
  })
})
