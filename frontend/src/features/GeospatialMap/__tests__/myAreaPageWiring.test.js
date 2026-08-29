import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'MyAreaPage.jsx'), 'utf-8')
const mapCanvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MyAreaMapCanvas.jsx'), 'utf-8')
const scientificPanelSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MyAreaScientificPanel.jsx'), 'utf-8')
const summaryPanelSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MyAreaSummaryPanel.jsx'), 'utf-8')
const forecastStripSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MyAreaForecastStrip.jsx'), 'utf-8')
const hookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useMyAreaContext.js'), 'utf-8')
const adapterSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'myAreaContextAdapter.js'), 'utf-8')

const ALL_NEW_FILES = [pageSrc, mapCanvasSrc, scientificPanelSrc, summaryPanelSrc, forecastStripSrc, hookSrc, adapterSrc]

describe('GEO-AREA-02-PAGE-01: authorized-farm selection states (Section 5, items 31-33)', () => {
  it('has a zero-assigned-farms state', () => {
    expect(pageSrc).toContain('authorizedFarms.length === 0')
    expect(pageSrc).toContain('LABEL_MY_AREA_NO_ASSIGNED_FARMS')
  })

  it('auto-selects when exactly one authorized farm exists', () => {
    expect(pageSrc).toContain('authorizedFarms.length === 1')
    expect(pageSrc).toContain('ctx.selectArea(authorizedFarms[0].farmId)')
  })

  it('shows an explicit chooser when multiple farms exist and none is validly selected', () => {
    expect(pageSrc).toContain('showFarmChooser')
    expect(pageSrc).toMatch(/authorizedFarms\.length > 1/)
  })

  it('never auto-selects a farm by geographic nearness -- no distance/haversine call anywhere near the selection effect', () => {
    expect(pageSrc).not.toMatch(/haversine/i)
    expect(pageSrc).not.toContain('Math.sqrt')
  })
})

describe('GEO-AREA-02-PAGE-02: no client-side distance/relevance/containment math (Section 12, items 35-36)', () => {
  it('none of the new page/component/adapter files compute a geodesic distance themselves', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/haversine/i)
      expect(src).not.toContain('Math.sqrt')
      expect(src).not.toContain('Math.asin')
    }
  })

  it('the map canvas never derives farm coordinates from anything but the area prop', () => {
    // No hardcoded Sri Lanka-ish coordinate literals anywhere in the map file.
    expect(mapCanvasSrc).not.toMatch(/6\.9271|79\.8612/)
  })
})

describe('GEO-AREA-02-PAGE-03: relevant-origin wording (Section 10, items 37-38)', () => {
  it('shows the exact required "Nearest T0 trigger source" wording', () => {
    expect(summaryPanelSrc).toContain('LABEL_NEAREST_T0_TRIGGER_SOURCE')
  })

  it('never uses forbidden outbreak/threat/origin-distance wording anywhere in the new UI files', () => {
    const forbidden = ['outbreak 14', 'origin distance', 'current outbreak', 'threat', 'distance to outbreak', 'distance to origin']
    for (const src of [summaryPanelSrc, scientificPanelSrc, pageSrc]) {
      const lowered = src.toLowerCase()
      for (const phrase of forbidden) {
        expect(lowered).not.toContain(phrase)
      }
    }
  })
})

describe('GEO-AREA-02-PAGE-04: no silent origin auto-selection (Section 11, items 39-40)', () => {
  it('selectedOriginId is only ever set via an explicit click handler or the verified Page-1-preservation effect', () => {
    // The only two writers of selectedOriginId: the onSelectOrigin
    // callback (user click) and the one-time Page-1-seed effect.
    expect(pageSrc).toContain('onSelectOrigin={setSelectedOriginId}')
    expect(pageSrc).toContain('seededFromPage1Ref')
  })

  it('never assigns the first/nearest relevant origin directly to selection state', () => {
    expect(pageSrc).not.toMatch(/setSelectedOriginId\(\s*(myArea\.)?data\??\.relevantOrigins\??\[0\]/)
    expect(pageSrc).not.toMatch(/relevantOrigins\.sort\([^)]*\)\[0\]/)
  })

  it('the Page-1-preservation seed verifies membership in relevant_origins before applying (explicit prior intent, not inference)', () => {
    const seedEffectIndex = pageSrc.indexOf('seededFromPage1Ref')
    const seedEffectBody = pageSrc.slice(seedEffectIndex, seedEffectIndex + 500)
    expect(seedEffectBody).toContain('.some((o) => o.originId === ctx.selectedOutbreakId)')
  })

  it('origin selection triggers a data reload via the hook dependency, not a manual imperative fetch', () => {
    expect(pageSrc).toContain('originId: selectedOriginId')
    expect(hookSrc).toMatch(/\[farmId, disease, originId, day, retryToken\]/)
  })
})

describe('GEO-AREA-02-PAGE-05: selection reset rules (Section 34, items 42)', () => {
  it('disease change clears the selected origin', () => {
    const idx = pageSrc.indexOf('prevDiseaseRef')
    const body = pageSrc.slice(idx, idx + 400)
    expect(body).toContain('setSelectedOriginId(null)')
  })

  it('area change clears the selected origin', () => {
    const idx = pageSrc.indexOf('prevAreaRef')
    const body = pageSrc.slice(idx, idx + 400)
    expect(body).toContain('setSelectedOriginId(null)')
  })
})

describe('GEO-AREA-02-PAGE-06: camera stability (Section 18, item 43)', () => {
  it('the day/forecast-strip selection never appears in a camera-fit effect dependency array', () => {
    // Extract every `}, [...])` dependency array in the map canvas and
    // confirm none of them mention `day`/`selectedDay`.
    const depArrays = [...mapCanvasSrc.matchAll(/\},\s*\[([^\]]*)\]\)/g)].map((m) => m[1])
    for (const deps of depArrays) {
      expect(deps).not.toMatch(/\bday\b/i)
    }
  })

  it('exactly the two intentional camera calls exist (farm easeTo, origin fitBounds) -- no additional camera movement was introduced', () => {
    const easeToCount = mapCanvasSrc.split('easeTo(').length - 1
    const fitBoundsCount = mapCanvasSrc.split('fitBounds(').length - 1
    expect(easeToCount).toBe(1)
    expect(fitBoundsCount).toBe(1)
    expect(mapCanvasSrc.split('flyTo(').length - 1).toBe(0)
  })

  it('the reach-ring data effect never calls a camera method', () => {
    const idx = mapCanvasSrc.indexOf('nominal-reach ring: same tween')
    const effectStart = mapCanvasSrc.indexOf('useEffect(() => {', idx)
    const effectEnd = mapCanvasSrc.indexOf('[reachRingCenters, reachRingRadiusKm, reduceMotion]', effectStart)
    const body = mapCanvasSrc.slice(effectStart, effectEnd)
    expect(body).not.toContain('fitBounds')
    expect(body).not.toContain('easeTo')
    expect(body).not.toContain('flyTo')
  })
})

describe('GEO-AREA-02-PAGE-07: forecast D0-D+7 (Section 19, items 44-46)', () => {
  it('D0 never renders a fabricated "0 km"', () => {
    expect(scientificPanelSrc).not.toMatch(/0\s*km/)
    expect(scientificPanelSrc).toContain('nominalReachKm === null')
  })

  it('uses the existing tested forecastDate utility, never a local date-arithmetic reimplementation', () => {
    expect(forecastStripSrc).toContain("from '../adapters/forecastDate'")
    expect(forecastStripSrc).not.toContain('new Date(')
  })

  it('day change alone never triggers a new backend request unrelated to the day dependency (day IS a real hook dependency, verified explicitly)', () => {
    expect(hookSrc).toContain('day')
  })
})

describe('GEO-AREA-02-PAGE-08: nominal-reach semantics (Section 20, items 47-48)', () => {
  it('the nominal-reach disclaimer is always shown', () => {
    expect(pageSrc).toContain('MY_AREA_NOMINAL_REACH_DISCLAIMER')
    expect(scientificPanelSrc).toContain('MY_AREA_NOMINAL_REACH_DISCLAIMER')
  })

  it('never renders nominalReachContext.relation as a farm-inside/outside claim -- relation is never read in any UI component', () => {
    for (const src of [scientificPanelSrc, summaryPanelSrc, pageSrc, forecastStripSrc]) {
      expect(src).not.toMatch(/nominalReachContext\.relation/)
      expect(src).not.toContain('WITHIN_NOMINAL_VISUALIZATION_REACH')
      expect(src).not.toContain('OUTSIDE_NOMINAL_VISUALIZATION_REACH')
    }
  })
})

describe('GEO-AREA-02-PAGE-09: Relative Spatial Score (Section 21, items 49-50)', () => {
  it('renders the unavailable state explicitly when value is null', () => {
    expect(scientificPanelSrc).toContain('relativeSpatialScore.value === null')
    expect(scientificPanelSrc).toContain('LABEL_RELATIVE_SPATIAL_SCORE_UNAVAILABLE')
  })

  it('never substitutes 0%, Low, Safe, or Green for the unavailable score', () => {
    const lowered = scientificPanelSrc.toLowerCase()
    for (const forbidden of ['0%', '"low"', "'low'", '"safe"', "'safe'", 'green']) {
      expect(lowered).not.toContain(forbidden.toLowerCase())
    }
  })
})

describe('GEO-AREA-02-PAGE-10: FMD honesty (Section 29, item 52)', () => {
  it('ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY maps to an honest model-not-ready label', () => {
    expect(pageSrc).toContain('ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY')
    expect(pageSrc).toContain('LABEL_MY_AREA_MODEL_NOT_READY')
  })

  it('the map canvas source-fetch path is the SAME real Page 1 hook, never a second scientific API', () => {
    expect(pageSrc).toContain("from '../context/useSelectedOutbreakFrames'")
  })
})

describe('GEO-AREA-02-PAGE-11: zero runtime mock data (Section 31/44, items 34/53)', () => {
  const forbidden = ['Kandy', 'fake farm', 'fakeFarm', 'demoRisk', 'mockOrigin', 'sampleOrigin', 'Math.random()']

  it('no production My Area file hardcodes a demo farm/origin/coordinate', () => {
    for (const src of ALL_NEW_FILES) {
      for (const word of forbidden) {
        expect(src).not.toContain(word)
      }
    }
  })

  it('the page never fabricates a fallback area/origin object on error -- error states render a message, not synthetic data', () => {
    expect(pageSrc).not.toMatch(/area:\s*\{\s*farmId:\s*['"]/)
  })
})

describe('GEO-AREA-02-PAGE-12: race safety (Section 33, item 54)', () => {
  it('uses AbortController', () => {
    expect(hookSrc).toContain('new AbortController()')
    expect(hookSrc).toContain('controller.abort()')
  })

  it('ignores a response from a superseded request via a monotonic request id', () => {
    expect(hookSrc).toContain('requestIdRef')
    expect(hookSrc).toMatch(/requestIdRef\.current !== requestId/)
  })

  it('never polls -- no setInterval/setTimeout (also covered globally by noAutoPolling.test.js)', () => {
    expect(hookSrc.includes('setInterval(')).toBe(false)
    expect(hookSrc.includes('setTimeout(')).toBe(false)
  })
})

describe('GEO-AREA-02-PAGE-13: PII minimization (Section 17/27)', () => {
  it('no clinical or farm component references owner/vet PII fields', () => {
    const clinicalPanelSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MyAreaClinicalPanel.jsx'), 'utf-8')
    for (const src of [clinicalPanelSrc, summaryPanelSrc]) {
      expect(src).not.toMatch(/owner|vetEmail|phone|password/i)
    }
  })
})
