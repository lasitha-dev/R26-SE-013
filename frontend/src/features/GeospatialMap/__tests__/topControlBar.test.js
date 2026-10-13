import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { ANALYSIS_MODE, initialOutbreakSelectionState, outbreakSelectionReducer } from '../context/outbreakSelectionReducer'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const outbreakMapPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')
const statusMenuSrc = readFileSync(join(FEATURE_ROOT, 'components', 'StatusDiagnosticsMenu.jsx'), 'utf-8')

/** Mirrors `operationalMapWiring.test.js`'s own naive brace-matching
 * function-body extractor. */
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

describe('GEO30A Section 2/12: district chip is a context indicator, never a data filter', () => {
  it('the district chip renders from real operational-context data (vetDistrict), not a hardcoded value', () => {
    expect(outbreakMapPageSrc).toContain('operational.data?.vetDistrict')
    expect(outbreakMapPageSrc).not.toMatch(/MY DISTRICT[^`]*Matara/i)
  })

  it('national data fetching (useNationalOutbreaks) never receives or depends on the vet district', () => {
    const hookCallLine = outbreakMapPageSrc.split('\n').find((l) => l.includes('useNationalOutbreaks('))
    expect(hookCallLine).toBeTruthy()
    expect(hookCallLine).not.toMatch(/district/i)
  })

  it('the Cases-mode disease/window filter never references vetDistrict as a gate', () => {
    const memoStart = outbreakMapPageSrc.indexOf('const operationalContextsForDisease = useMemo(')
    const knownDepsArray = '[operational.data, ctx.selectedDisease, observationWindowDays],'
    const memoEnd = outbreakMapPageSrc.indexOf(knownDepsArray, memoStart)
    expect(memoEnd).toBeGreaterThan(memoStart)
    const memoBody = outbreakMapPageSrc.slice(memoStart, memoEnd + knownDepsArray.length)
    expect(memoBody).not.toContain('vetDistrict')
  })
})

describe('GEO30A Section 4: disease switch never shows a technical capability banner in Cases mode', () => {
  it('the readiness warning is gated OFF for ANALYSIS_MODE.CASES', () => {
    expect(outbreakMapPageSrc).toMatch(/showDiseaseReadinessWarning\s*=\s*!diseaseReady\s*&&\s*ctx\.analysisMode\s*!==\s*ANALYSIS_MODE\.CASES/)
  })

  it('default mode is Cases, so the banner is invisible on a fresh page load regardless of disease readiness', () => {
    expect(initialOutbreakSelectionState.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })
})

describe('GEO30A Section 4: switching disease while on an unsupported mode falls back to Cases', () => {
  it('SELECT_DISEASE resets analysisMode to CASES when the new disease does not support the current mode', () => {
    const lsdOnRiskZones = outbreakSelectionReducer(initialOutbreakSelectionState, { type: 'SET_MODE', payload: { mode: ANALYSIS_MODE.RISK_ZONES } })
    expect(lsdOnRiskZones.analysisMode).toBe(ANALYSIS_MODE.RISK_ZONES)

    const afterSwitchToFmd = outbreakSelectionReducer(lsdOnRiskZones, { type: 'SELECT_DISEASE', payload: { disease: 'FMD' } })
    // FMD has no spatialCells/riskZones capability (diseaseRegistry.js) -- must fall back.
    expect(afterSwitchToFmd.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })

  it('switching disease while already on Cases stays on Cases (both diseases support it)', () => {
    const onCases = outbreakSelectionReducer(initialOutbreakSelectionState, { type: 'SELECT_DISEASE', payload: { disease: 'FMD' } })
    expect(onCases.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })
})

describe('GEO30A Section 7/8: Fit Sri Lanka / Focus My District are camera-only actions', () => {
  it('handleFitSriLanka never touches disease, observation window, or map mode state', () => {
    const body = extractFunctionBody(outbreakMapPageSrc, 'handleFitSriLanka')
    expect(body).toContain('setLocationScope(LOCATION_SCOPE.SRI_LANKA)')
    expect(body).toContain('resetView()')
    for (const forbidden of ['selectDisease', 'setObservationWindowDays', 'ctx.setMode', 'setMode(']) {
      expect(body).not.toContain(forbidden)
    }
  })

  it('handleFocusMyDistrict never touches disease, observation window, or map mode state, and never mutates national/operational data', () => {
    const body = extractFunctionBody(outbreakMapPageSrc, 'handleFocusMyDistrict')
    expect(body).toContain('setLocationScope(LOCATION_SCOPE.MY_DISTRICT)')
    expect(body).toContain('resetView(bounds)')
    for (const forbidden of ['selectDisease', 'setObservationWindowDays', 'ctx.setMode', 'setMode(', 'setRefreshToken']) {
      expect(body).not.toContain(forbidden)
    }
  })

  it('the Location select delegates both options to the same two camera-only handlers', () => {
    const body = extractFunctionBody(outbreakMapPageSrc, 'handleLocationScopeChange')
    expect(body).toContain('handleFocusMyDistrict()')
    expect(body).toContain('handleFitSriLanka()')
  })
})

describe('GEO30A Section 9: fullscreen keeps map overlays available', () => {
  it('fullscreen targets the whole map card (mapWrapperRef), not just the MapLibre canvas', () => {
    expect(outbreakMapPageSrc).toContain('mapWrapperRef.current?.requestFullscreen')
  })

  it('leaving fullscreen calls resize() so MapLibre repaints at the correct size', () => {
    const listenerStart = outbreakMapPageSrc.indexOf('function onFullscreenChange()')
    const listenerBody = outbreakMapPageSrc.slice(listenerStart, listenerStart + 300)
    expect(listenerBody).toContain('mapCanvasRef.current?.resize()')
  })
})

describe('GEO30A Section 10/14: no engineering status blocks in the normal top UI; compact LIVE status only', () => {
  it('OutbreakMapPage never renders raw "SNAPSHOT"/"Check for newer snapshot" text directly -- only via the collapsed diagnostics menu', () => {
    expect(outbreakMapPageSrc).not.toMatch(/SNAPSHOT UNAVAILABLE/)
    expect(outbreakMapPageSrc).not.toContain('Check for newer snapshot')
    expect(outbreakMapPageSrc).toContain('<StatusDiagnosticsMenu')
  })

  it('GEO-HYBRID-LIVE-SYNC-08 Phase 10: StatusDiagnosticsMenu exposes a compact, HONEST push-vs-fallback label -- CONNECTED / LIVE UPDATE / SYNCING / RECONNECTING / LIVE DATA UNAVAILABLE -- as the always-visible text, never a bare "LIVE" claim from an open transport alone', () => {
    expect(statusMenuSrc).toContain("'CONNECTED'")
    expect(statusMenuSrc).toContain("'LIVE UPDATE'")
    expect(statusMenuSrc).toContain("'SYNCING'")
    expect(statusMenuSrc).toContain("'RECONNECTING'")
    expect(statusMenuSrc).toContain("'LIVE DATA UNAVAILABLE'")
    // The old label collapsed "poll succeeded" to a bare "LIVE" claim --
    // that exact standalone token must never reappear as its own quoted
    // string literal (the honest label is always a longer phrase).
    expect(statusMenuSrc).not.toContain("'LIVE'")
  })

  it('GEO-HYBRID-LIVE-SYNC-08 Phase 10: the label is never CONNECTED/LIVE UPDATE from operational (poll) state alone -- it genuinely reads the push-transport state too', () => {
    const labelFnStart = statusMenuSrc.indexOf('function liveStatusLabel(')
    expect(labelFnStart).toBeGreaterThanOrEqual(0)
    const braceOpen = statusMenuSrc.indexOf('{', labelFnStart)
    let depth = 0
    let end = braceOpen
    for (let i = braceOpen; i < statusMenuSrc.length; i += 1) {
      if (statusMenuSrc[i] === '{') depth += 1
      if (statusMenuSrc[i] === '}') {
        depth -= 1
        if (depth === 0) {
          end = i + 1
          break
        }
      }
    }
    const body = statusMenuSrc.slice(braceOpen, end)
    expect(body).toContain('pushState')
    expect(body).toContain('pushTransportMode')
    expect(body).toContain('lastGenuineUpdateAt')
  })

  it('GEO-HYBRID-LIVE-SYNC-08 Phase 10: deterministic priority -- LIVE UPDATE beats RECONNECTING beats SYNCING beats CONNECTED', () => {
    const labelFnStart = statusMenuSrc.indexOf('function liveStatusLabel(')
    const liveUpdateIndex = statusMenuSrc.indexOf("'LIVE UPDATE'", labelFnStart)
    const reconnectingIndex = statusMenuSrc.indexOf("'RECONNECTING'", labelFnStart)
    const syncingIndex = statusMenuSrc.indexOf("'SYNCING'", labelFnStart)
    const connectedIndex = statusMenuSrc.indexOf("'CONNECTED'", labelFnStart)
    expect(liveUpdateIndex).toBeGreaterThan(0)
    expect(liveUpdateIndex).toBeLessThan(reconnectingIndex)
    expect(reconnectingIndex).toBeLessThan(syncingIndex)
    expect(syncingIndex).toBeLessThan(connectedIndex)
  })
})

describe('GEO30A Section 14/15: map modes and the scientific timeline are NOT in the top control bar', () => {
  it('ModeToolbar and TimelineControl are rendered inside the map wrapper, after the control-bar closes', () => {
    // `showDiseaseReadinessWarning` is the first thing rendered right
    // after the control bar's closing tags -- a stable anchor for "the
    // control bar has ended" without depending on exact whitespace.
    const controlBarEnd = outbreakMapPageSrc.indexOf('{showDiseaseReadinessWarning &&')
    const modeToolbarIndex = outbreakMapPageSrc.indexOf('<ModeToolbar')
    const timelineIndex = outbreakMapPageSrc.indexOf('<TimelineControl')
    expect(controlBarEnd).toBeGreaterThan(0)
    expect(modeToolbarIndex).toBeGreaterThan(controlBarEnd)
    expect(timelineIndex).toBeGreaterThan(controlBarEnd)
  })
})

describe('GEO30A Section 16/21: top bar accessibility -- every icon-only control has a real label', () => {
  it('Fit Sri Lanka / Focus My District / Fullscreen buttons all carry aria-label and title', () => {
    for (const label of ['Fit Sri Lanka', 'Focus My District']) {
      expect(outbreakMapPageSrc).toContain(`aria-label="${label}"`)
    }
    // GEO-UI-TIMELINE-01 Part 1: tooltip wording is now "Enter/Exit
    // fullscreen" (previously "Fullscreen Map"/"Exit fullscreen") --
    // aria-label and title stay identical strings for this control.
    expect(outbreakMapPageSrc).toMatch(/aria-label=\{isFullscreen \? 'Exit fullscreen' : 'Enter fullscreen'\}/)
    expect(outbreakMapPageSrc).toMatch(/title=\{isFullscreen \? 'Exit fullscreen' : 'Enter fullscreen'\}/)
  })

  it('GEO-UI-TIMELINE-01 Part 1: the three map utility controls are grouped in one labeled control cluster', () => {
    const groupStart = outbreakMapPageSrc.indexOf('aria-label="Map utility controls"')
    expect(groupStart).toBeGreaterThan(0)
    const fitIndex = outbreakMapPageSrc.indexOf('aria-label="Fit Sri Lanka"')
    const districtIndex = outbreakMapPageSrc.indexOf('aria-label="Focus My District"')
    const fullscreenIndex = outbreakMapPageSrc.indexOf("aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}")
    // All three controls must be declared AFTER the group's own opening
    // tag (i.e. genuinely inside it), not just present anywhere on the page.
    expect(fitIndex).toBeGreaterThan(groupStart)
    expect(districtIndex).toBeGreaterThan(groupStart)
    expect(fullscreenIndex).toBeGreaterThan(groupStart)
  })

  it('GEO-UI-TIMELINE-01 Part 1: Focus My District tooltip names the real vet district when known, without changing its stable aria-label', () => {
    expect(outbreakMapPageSrc).toContain('`Center on ${vetDistrict}`')
    // The stable, already-tested screen-reader identity is untouched --
    // only the sighted-user hover/focus tooltip becomes dynamic.
    expect(outbreakMapPageSrc).toContain('aria-label="Focus My District"')
  })

  it('GEO-UI-TIMELINE-01 Part 1: Fit Sri Lanka keeps its real aria-label/title -- traced behavior is a fixed national bounds reset, not a "visible data" fit', () => {
    // handleFitSriLanka calls resetView() with no explicit bounds, which
    // MapLibreCanvas.jsx resolves to the fixed SRI_LANKA_BOUNDS constant,
    // never the current marker/data extent -- so this control must keep
    // wording that describes THAT real behavior, not an invented one.
    const body = extractFunctionBody(outbreakMapPageSrc, 'handleFitSriLanka')
    expect(body).toContain('resetView()')
    expect(outbreakMapPageSrc).toContain('aria-label="Fit Sri Lanka"')
    expect(outbreakMapPageSrc).toContain('title="Fit Sri Lanka"')
  })
})
