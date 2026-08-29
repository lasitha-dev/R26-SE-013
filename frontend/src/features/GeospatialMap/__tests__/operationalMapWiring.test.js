import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const mapLibreCanvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
const outbreakMapPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')

function countOccurrences(source, substring) {
  return source.split(substring).length - 1
}

/** Extracts one named function's body (naive brace-matching, sufficient
 * for this file's plain `function name(...) { ... }` declarations). */
function extractFunctionBody(source, functionName) {
  const start = source.indexOf(`function ${functionName}(`)
  expect(start, `expected to find "function ${functionName}(" in source`).toBeGreaterThanOrEqual(0)
  const braceOpen = source.indexOf('{', start)
  let depth = 0
  for (let i = braceOpen; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1
    if (source[i] === '}') {
      depth -= 1
      if (depth === 0) return source.slice(braceOpen, i + 1)
    }
  }
  throw new Error(`unbalanced braces reading function ${functionName}`)
}

describe('GEO-INT-03-WIRING-01: operational refresh never moves the camera (Section 13)', () => {
  it('MapLibreCanvas.jsx calls fitBounds only at its 3 pre-existing sites -- none newly added for the operational layer', () => {
    expect(countOccurrences(mapLibreCanvasSrc, 'fitBounds(')).toBe(3)
  })

  it('MapLibreCanvas.jsx never calls flyTo or easeTo anywhere', () => {
    expect(countOccurrences(mapLibreCanvasSrc, 'flyTo(')).toBe(0)
    expect(countOccurrences(mapLibreCanvasSrc, 'easeTo(')).toBe(0)
  })

  it("the operational-features data-update effect exists and is a distinct effect from any fitBounds-containing effect", () => {
    expect(mapLibreCanvasSrc).toContain('[operationalFeatures]')
    const dependencyIndex = mapLibreCanvasSrc.indexOf('[operationalFeatures]')
    const effectStart = mapLibreCanvasSrc.lastIndexOf('useEffect(() => {', dependencyIndex)
    const effectBody = mapLibreCanvasSrc.slice(effectStart, dependencyIndex)
    expect(effectBody).not.toContain('fitBounds')
    expect(effectBody).not.toContain('flyTo')
    expect(effectBody).not.toContain('easeTo')
  })
})

describe('GEO-INT-03-WIRING-02: operational marker click never triggers scientific analysis (Section 11/12/26/27)', () => {
  const handlerBody = extractFunctionBody(outbreakMapPageSrc, 'handleSelectOperationalCase')

  it('does not call the analysis-fetching API functions', () => {
    for (const forbidden of ['fetchAnalysisSummary', 'fetchAnalysisCells', 'fetchAnalysisSources']) {
      expect(handlerBody).not.toContain(forbidden)
    }
  })

  it('does not call ctx.selectOutbreak -- selectedOutbreakId is never overwritten by an operational click', () => {
    expect(handlerBody).not.toContain('selectOutbreak')
  })

  it('does not start timeline playback or draw a reach ring', () => {
    expect(handlerBody).not.toContain('ctx.play')
    expect(handlerBody).not.toContain('reachRing')
  })

  it('only sets the dedicated operational popup state, never popupFeature (the historical-source popup state)', () => {
    expect(handlerBody).toContain('setOperationalPopupCase')
    expect(handlerBody).not.toContain('setPopupFeature')
  })
})

describe('GEO-INT-03-WIRING-03: Cases-mode-only gating (Section 10)', () => {
  it('showOperationalLayer is derived from ANALYSIS_MODE.CASES, not a hardcoded true/always-on flag', () => {
    expect(outbreakMapPageSrc).toMatch(/showOperationalLayer\s*=\s*ctx\.analysisMode\s*===\s*ANALYSIS_MODE\.CASES/)
  })
})

describe('GEO-INT-03-WIRING-04: disease filtering never defaults to LSD (Section 18/25)', () => {
  it('operational contexts are filtered by the actually-selected disease, not hardcoded to LSD', () => {
    expect(outbreakMapPageSrc).toContain('c.disease === ctx.selectedDisease')
  })
})

describe('GEO-INT-03-WIRING-05: separate selection state (Section 12)', () => {
  it('a dedicated operationalPopupCase state exists, distinct from selectedOutbreakId/popupFeature', () => {
    expect(outbreakMapPageSrc).toContain('operationalPopupCase')
  })
})

describe('GEO-INT-03-WIRING-06: cleanup safety (Section 17) -- structural presence check', () => {
  const hookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useOperationalContext.js'), 'utf-8')

  it('cancels the RAF loop and aborts any in-flight request in the mount effect cleanup', () => {
    const cleanupStart = hookSrc.lastIndexOf('return () => {')
    const cleanupBody = hookSrc.slice(cleanupStart)
    expect(cleanupBody).toContain('cancelAnimationFrame')
    expect(cleanupBody).toContain('.abort()')
  })

  it('uses requestAnimationFrame, never setInterval/setTimeout (also covered globally by noAutoPolling.test.js)', () => {
    expect(hookSrc).toContain('requestAnimationFrame')
    expect(hookSrc.includes('setInterval(')).toBe(false)
    expect(hookSrc.includes('setTimeout(')).toBe(false)
  })

  it('a manual refresh aborts a still-in-flight request before starting a new one (no duplicate requests)', () => {
    expect(hookSrc).toContain('inFlightRef.current')
    expect(hookSrc).toContain('abortControllerRef.current?.abort()')
  })
})

describe('GEO-INT-03-WIRING-07: historical Page 1 flow untouched', () => {
  it('OutbreakMapPage.jsx still wires the pre-existing historical handlers/props unchanged', () => {
    expect(outbreakMapPageSrc).toContain('function handleSelectSource(outbreakId, sourceId)')
    expect(outbreakMapPageSrc).toContain('ctx.selectOutbreak(outbreakId)')
    expect(outbreakMapPageSrc).toContain('nationalSources={nationalSourcesFC}')
  })

  it('the operational overlay is additive -- MapLibreCanvas still receives every pre-existing historical prop', () => {
    for (const prop of ['cellFeatures=', 'selectedOutbreakId=', 'reachRingCenters=', 'onSelectSource=', 'onSelectCell=']) {
      expect(outbreakMapPageSrc).toContain(prop)
    }
  })
})

describe('GEO-OWNED-FINAL-08-WIRING-09: logout/token-disappearance terminates the request loop immediately', () => {
  const hookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useOperationalContext.js'), 'utf-8')
  const eventsHookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useVerifiedClinicalEvents.js'), 'utf-8')

  it('useOperationalContext.js checks for a disappeared token on every tick, before the interval-based fetch branch', () => {
    const tickStart = hookSrc.indexOf('const tick = () => {')
    const tickBody = hookSrc.slice(tickStart, hookSrc.indexOf('rafRef.current = requestAnimationFrame(tick)', tickStart))
    expect(tickBody).toContain('hasTokenDisappeared(')
    expect(tickBody.indexOf('hasTokenDisappeared(')).toBeLessThan(tickBody.indexOf('shouldFetchOnTick('))
  })

  it('useOperationalContext.js aborts the in-flight request and surfaces SESSION_REQUIRED on token disappearance', () => {
    const tickStart = hookSrc.indexOf('const tick = () => {')
    const tickBody = hookSrc.slice(tickStart, hookSrc.indexOf('rafRef.current = requestAnimationFrame(tick)', tickStart))
    expect(tickBody).toContain('abortControllerRef.current?.abort()')
    expect(tickBody).toContain("operationalStatus: 'SESSION_REQUIRED'")
  })

  it('useVerifiedClinicalEvents.js checks for a disappeared token on every tick, before the reconnect-timer branch', () => {
    const tickStart = eventsHookSrc.indexOf('const tick = () => {')
    const tickBody = eventsHookSrc.slice(tickStart, eventsHookSrc.indexOf('rafRef.current = requestAnimationFrame(tick)', tickStart))
    expect(tickBody).toContain('hasTokenDisappeared(')
    expect(tickBody.indexOf('hasTokenDisappeared(')).toBeLessThan(tickBody.indexOf('reconnectAtRef.current != null'))
  })

  it('useVerifiedClinicalEvents.js aborts the stream and moves to SESSION_REQUIRED (never re-reconnects) on token disappearance', () => {
    const tickStart = eventsHookSrc.indexOf('const tick = () => {')
    const tickBody = eventsHookSrc.slice(tickStart, eventsHookSrc.indexOf('rafRef.current = requestAnimationFrame(tick)', tickStart))
    expect(tickBody).toContain('abortControllerRef.current?.abort()')
    expect(tickBody).toContain("connectionLost(prev, 'SESSION_REQUIRED')")
  })
})

describe('GEO-INT-03-WIRING-08: zero runtime mock data (Section 27)', () => {
  const productionFiles = [
    'api/operationalApi.js',
    'adapters/operationalContextAdapter.js',
    'context/operationalRefreshReducer.js',
    'context/useOperationalContext.js',
    'components/operationalIcons.js',
    'components/operationalMarkerLayer.js',
    'components/OperationalStatusChip.jsx',
    'components/OperationalContextPopup.jsx',
  ]

  it('no production operational file hardcodes a demo farm/case/coordinate', () => {
    for (const relativePath of productionFiles) {
      const src = readFileSync(join(FEATURE_ROOT, relativePath), 'utf-8')
      for (const forbidden of ['Kandy', 'fake farm', 'fakeFarm', 'demoRisk', 'mockClinical', 'sampleCase']) {
        expect(src).not.toContain(forbidden)
      }
    }
  })

  it('the API client and adapter never fabricate a fallback response on failure -- errors always propagate/exclude, never substitute data', () => {
    const apiSrc = readFileSync(join(FEATURE_ROOT, 'api', 'operationalApi.js'), 'utf-8')
    expect(apiSrc).not.toMatch(/return\s*\{\s*status:\s*['"]OK['"]/)
  })
})
