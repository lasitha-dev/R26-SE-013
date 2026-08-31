import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const outbreakMapPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')
const myAreaPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'MyAreaPage.jsx'), 'utf-8')
const hookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useVerifiedClinicalEvents.js'), 'utf-8')

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

describe('GEO-LIVE-05-WIRING-01: no automatic timer anywhere (also covered globally by noAutoPolling.test.js)', () => {
  it('useVerifiedClinicalEvents.js uses requestAnimationFrame, never setInterval/setTimeout', () => {
    expect(hookSrc).toContain('requestAnimationFrame')
    expect(hookSrc.includes('setInterval(')).toBe(false)
    expect(hookSrc.includes('setTimeout(')).toBe(false)
  })

  it('aborts the in-flight stream and cancels the RAF loop on unmount', () => {
    const cleanupStart = hookSrc.lastIndexOf('return () => {')
    const cleanupBody = hookSrc.slice(cleanupStart)
    expect(cleanupBody).toContain('cancelAnimationFrame')
    expect(cleanupBody).toContain('.abort()')
  })
})

describe('GEO-LIVE-05-WIRING-02: Page 1 -- a clinical event refetches operational-context, never mutates markers directly', () => {
  it('the clinical-events effect calls operational.refresh(), not a direct state mutation', () => {
    expect(outbreakMapPageSrc).toContain('operational.refresh()')
    expect(outbreakMapPageSrc).toContain('clinicalEvents.lastEvent')
  })

  it('handleViewClinicalUpdate never calls ctx.selectOutbreak / sets selectedOutbreakId to a case id', () => {
    const handlerBody = extractFunctionBody(outbreakMapPageSrc, 'handleViewClinicalUpdate')
    expect(handlerBody).not.toContain('selectOutbreak')
    expect(handlerBody).not.toContain('selectedOutbreakId')
  })

  it('handleViewClinicalUpdate opens the operational popup via the dedicated clinical-case state, not the historical popup', () => {
    const handlerBody = extractFunctionBody(outbreakMapPageSrc, 'handleViewClinicalUpdate')
    expect(handlerBody).toContain('setOperationalPopupCase')
    expect(handlerBody).not.toContain('setPopupFeature')
  })

  it('handleViewClinicalUpdate never touches playback/timeline controls', () => {
    const handlerBody = extractFunctionBody(outbreakMapPageSrc, 'handleViewClinicalUpdate')
    for (const forbidden of ['ctx.play', 'ctx.pause', 'selectDay']) {
      expect(handlerBody).not.toContain(forbidden)
    }
  })

  // GEO26C Section 6: "View update" now brings the real farm this event
  // belongs to into view -- by reusing the SAME `resetView(explicitBounds)`
  // primitive the Location control's "My assigned farms" option uses,
  // never a second/new camera-fit call site (`fitBounds(`/`flyTo(` still
  // never appear directly in this handler).
  it('focuses the real farm via the shared resetView(bounds) primitive, never a new fitBounds/flyTo call site', () => {
    const handlerBody = extractFunctionBody(outbreakMapPageSrc, 'handleViewClinicalUpdate')
    expect(handlerBody).toContain('resetView(bounds)')
    expect(handlerBody).not.toContain('fitBounds')
    expect(handlerBody).not.toContain('flyTo')
  })

  it('only fits the camera when the event farm has a real, valid location -- never a guessed coordinate', () => {
    const handlerBody = extractFunctionBody(outbreakMapPageSrc, 'handleViewClinicalUpdate')
    expect(handlerBody).toContain("farm?.locationStatus === 'VALID'")
  })
})

describe('GEO-LIVE-05-WIRING-03: Page 2 -- relevance-gated refetch, never an unrelated farm refresh', () => {
  it('the relevance check is the real pure function, not an inline farm_id guess', () => {
    expect(myAreaPageSrc).toContain('isEventRelevantToMyArea(event, { selectedAreaId: ctx.selectedAreaId })')
  })

  it('retryToken is bumped only inside the relevance-gated branch', () => {
    const guardIndex = myAreaPageSrc.indexOf('isEventRelevantToMyArea(event, { selectedAreaId: ctx.selectedAreaId })')
    const afterGuard = myAreaPageSrc.slice(guardIndex, guardIndex + 200)
    expect(afterGuard).toContain('setRetryToken')
  })

  it('handleViewClinicalUpdate never overwrites selectedOriginId/selectedDay directly', () => {
    const handlerBody = extractFunctionBody(myAreaPageSrc, 'handleViewClinicalUpdate')
    expect(handlerBody).not.toContain('setSelectedOriginId')
    expect(handlerBody).not.toContain('setSelectedDay')
  })
})

describe('GEO-LIVE-05-WIRING-04: both pages render the alert banner, never a hardcoded/fake count', () => {
  it('OutbreakMapPage renders GeospatialAlertBanner backed by real notifications', () => {
    expect(outbreakMapPageSrc).toContain('<GeospatialAlertBanner')
    expect(outbreakMapPageSrc).toContain('notifications={clinicalEvents.notifications}')
  })

  it('MyAreaPage renders GeospatialAlertBanner backed by real notifications', () => {
    expect(myAreaPageSrc).toContain('<GeospatialAlertBanner')
    expect(myAreaPageSrc).toContain('notifications={clinicalEvents.notifications}')
  })
})
