import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it, vi } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const mapLibreCanvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
const outbreakMapPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
}

/** `MapLibreCanvas.jsx` pulls in `maplibre-gl`, whose module has a
 * top-level `URL.createObjectURL` side effect jsdom does not implement --
 * same dynamic-import-after-polyfill pattern as
 * `initialCameraAndStatusCompaction.test.js`. */
let SRI_LANKA_BOUNDS, SRI_LANKA_CENTER, SRI_LANKA_INITIAL_ZOOM
beforeAll(async () => {
  if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
  if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
  ;({ SRI_LANKA_BOUNDS, SRI_LANKA_CENTER, SRI_LANKA_INITIAL_ZOOM } = await import('../components/MapLibreCanvas'))
})

describe('GEO33B Section 2: the map/data load order is genuinely independent (the real race fix)', () => {
  const stripped = stripComments(mapLibreCanvasSrc)

  it('every async-arriving prop is mirrored into a ref that the mount-only effect can read', () => {
    for (const ref of [
      'nationalSourcesRef.current = nationalSources',
      'operationalFeaturesRef.current = operationalFeatures',
      'districtFeatureRef.current = districtFeature',
      'cellFeaturesRef.current = cellFeatures',
      'sourceFeaturesRef.current = sourceFeatures',
    ]) {
      expect(stripped).toContain(ref)
    }
  })

  it("map.on('load') seeds every source from the LATEST ref value, never the mount effect's first-render closure", () => {
    const loadStart = stripped.indexOf("map.on('load'")
    expect(loadStart).toBeGreaterThan(-1)
    const loadBody = stripped.slice(loadStart, stripped.indexOf('} catch (err)', loadStart))
    // The refs are read...
    expect(loadBody).toContain('nationalSourcesRef.current')
    expect(loadBody).toContain('districtFeatureRef.current')
    expect(loadBody).toContain('operationalFeaturesRef.current')
    // ...and the stale closure props are NOT used to seed source data.
    expect(loadBody).not.toMatch(/data:\s*operationalFeatures\s*\?\?/)
    expect(loadBody).not.toMatch(/const nationalFC = nationalSources\s*\?\?/)
  })

  it('the API fetches start in their own mount effects, never gated on a map load event', () => {
    const nationalSrc = stripComments(readFileSync(join(FEATURE_ROOT, 'context', 'useNationalOutbreaks.js'), 'utf-8'))
    const operationalSrc = stripComments(readFileSync(join(FEATURE_ROOT, 'context', 'useOperationalContext.js'), 'utf-8'))
    const districtSrc = stripComments(readFileSync(join(FEATURE_ROOT, 'context', 'useDistrictGeometry.js'), 'utf-8'))
    for (const src of [nationalSrc, operationalSrc, districtSrc]) {
      expect(src).not.toContain("map.on('load'")
      expect(src).not.toContain('loadedRef')
      expect(src).not.toContain('maplibre')
    }
  })
})

describe('GEO33B Section 3: the map is constructed exactly once', () => {
  it('there is a single `new maplibregl.Map(` call and it sits in a mount-once ([]-deps) effect', () => {
    const stripped = stripComments(mapLibreCanvasSrc)
    expect(stripped.split('new maplibregl.Map(').length - 1).toBe(1)
    const ctorIndex = stripped.indexOf('new maplibregl.Map(')
    const effectStart = stripped.lastIndexOf('useEffect(() => {', ctorIndex)
    const effectEnd = stripped.indexOf('}, [])', ctorIndex)
    expect(effectStart).toBeGreaterThan(-1)
    expect(effectEnd).toBeGreaterThan(ctorIndex)
    // No other dependency array closes this effect before the empty one.
    expect(stripped.slice(ctorIndex, effectEnd)).not.toMatch(/\}, \[[^\]]+\]\)/)
  })

  it('every prop-driven change is applied through setData/setPaintProperty/setLayoutProperty/setFeatureState, never a remount', () => {
    const stripped = stripComments(mapLibreCanvasSrc)
    for (const method of ['.setData(', 'setPaintProperty(', 'setLayoutProperty(', 'setFeatureState(']) {
      expect(stripped).toContain(method)
    }
    // `map.remove()` exists exactly once, in the unmount cleanup only.
    expect(stripped.split('map?.remove()').length - 1).toBe(1)
  })
})

describe('GEO33B Section 4: a restrained loading state, never a blocking one', () => {
  it('renders a "Loading map…" overlay gated on the real style-load event', () => {
    expect(mapLibreCanvasSrc).toContain('Loading map')
    expect(mapLibreCanvasSrc).toContain('setStyleReady(true)')
    expect(mapLibreCanvasSrc).toMatch(/\{!styleReady && !failedRef\.current && \(/)
  })

  it('the overlay never blocks interaction and is not announced as content', () => {
    const overlayStart = mapLibreCanvasSrc.indexOf('{!styleReady && !failedRef.current && (')
    const overlay = mapLibreCanvasSrc.slice(overlayStart, overlayStart + 900)
    expect(overlay).toContain('pointer-events-none')
    expect(overlay).toContain('aria-hidden="true"')
  })

  it('it is scoped to the map card only -- the page header/toolbar/legend/timeline are siblings, not children, of the canvas', () => {
    // The overlay lives inside MapLibreCanvas; ModeToolbar/PageLegend/the
    // timeline are rendered by the page as siblings of <MapLibreCanvas/>.
    const canvasIndex = outbreakMapPageSrc.indexOf('<MapLibreCanvas')
    expect(outbreakMapPageSrc.indexOf('<ModeToolbar')).toBeGreaterThan(canvasIndex)
    expect(outbreakMapPageSrc.indexOf('<PageLegend')).toBeGreaterThan(canvasIndex)
  })
})

describe('GEO33B Section 5: Sri Lanka framing', () => {
  it('the bounds constant matches real mainland Sri Lanka, not a box reaching into southern India', () => {
    const [[minLng, minLat], [maxLng, maxLat]] = SRI_LANKA_BOUNDS
    // Real island extent is approximately lon 79.65--81.88, lat 5.92--9.84.
    // A small presentation margin is fine; a large western/southern
    // overhang is what pulled southern India into frame.
    expect(minLng).toBeGreaterThanOrEqual(79.4)
    expect(minLng).toBeLessThanOrEqual(79.65)
    expect(minLat).toBeGreaterThanOrEqual(5.8)
    expect(maxLng).toBeGreaterThanOrEqual(81.88)
    expect(maxLng).toBeLessThanOrEqual(82.1)
    expect(maxLat).toBeLessThanOrEqual(10.0)
    // The box must actually contain every real Sri Lanka LSD record.
    for (const [lng, lat] of [
      [80.0668497, 9.7151701],
      [80.6608048, 9.0621351],
      [80.0461103553, 8.888178931],
    ]) {
      expect(lng).toBeGreaterThan(minLng)
      expect(lng).toBeLessThan(maxLng)
      expect(lat).toBeGreaterThan(minLat)
      expect(lat).toBeLessThan(maxLat)
    }
  })

  it('the initial centre/zoom sit on the island itself', () => {
    const [lng, lat] = SRI_LANKA_CENTER
    expect(lng).toBeGreaterThan(79.6)
    expect(lng).toBeLessThan(81.9)
    expect(lat).toBeGreaterThan(5.9)
    expect(lat).toBeLessThan(9.9)
    expect(SRI_LANKA_INITIAL_ZOOM).toBeGreaterThanOrEqual(6.8)
  })

  it('the national-browse initial camera fits SRI_LANKA_BOUNDS, never the extent of whatever markers loaded', () => {
    const stripped = stripComments(mapLibreCanvasSrc)
    const loadStart = stripped.indexOf("map.on('load'")
    const loadBody = stripped.slice(loadStart, stripped.indexOf('} catch (err)', loadStart))
    expect(loadBody).toMatch(/latestNationalSources\s*\n?\s*\?\s*SRI_LANKA_BOUNDS/)
    // The pre-GEO33B marker-extent fit (every real LSD record sits in the
    // far north, so this opened the page on the Jaffna peninsula) is gone.
    expect(loadBody).not.toContain('computeCombinedLngLatBounds([], nationalFC.features)')
  })

  it('"Fit Sri Lanka" (resetView with no explicit bounds) fits Sri Lanka, not the national marker extent', () => {
    const start = mapLibreCanvasSrc.indexOf('resetView(explicitBounds) {')
    const body = stripComments(mapLibreCanvasSrc.slice(start, mapLibreCanvasSrc.indexOf('},', start)))
    expect(body).toContain('explicitBounds ?? SRI_LANKA_BOUNDS')
    expect(body).not.toContain('nationalBounds')
  })

  it('every camera fit is capped by a maxZoom so a small real geometry never zooms to street level', () => {
    const stripped = stripComments(mapLibreCanvasSrc)
    // Each `map.fitBounds(` occurrence, followed by enough characters to
    // cover its whole options object.
    const callSites = stripped.split('map.fitBounds(').slice(1)
    expect(callSites.length).toBeGreaterThanOrEqual(3)
    for (const site of callSites) {
      expect(site.slice(0, 220)).toContain('MAP_FIT_MAX_ZOOM')
    }
  })

  it('the camera padding still reserves real room for the floating top toolbar and the bottom timeline lane', () => {
    const padding = mapLibreCanvasSrc.match(/MAP_FIT_PADDING = \{ top: (\d+), bottom: (\d+)/)
    expect(padding).toBeTruthy()
    const [, top, bottom] = padding
    // ModeToolbar sits at top-4 and is ~40px tall; the timeline now sits at
    // bottom-7 and is ~70px tall with its new header row.
    expect(Number(top)).toBeGreaterThanOrEqual(60)
    expect(Number(bottom)).toBeGreaterThanOrEqual(100)
  })
})

describe('GEO33B Section 16: attribution is repositioned, never removed', () => {
  it('an AttributionControl is explicitly added away from the bottom-right timeline lane', () => {
    expect(mapLibreCanvasSrc).toMatch(/new maplibregl\.AttributionControl\([\s\S]{0,60}?\),\s*'bottom-left'/)
  })

  it('the default control is only disabled because an explicit one replaces it -- attribution is never suppressed', () => {
    expect(mapLibreCanvasSrc).toContain('attributionControl: false')
    expect(mapLibreCanvasSrc).toContain('maplibregl.AttributionControl')
    // The ODbL credit the district source itself declares is still set.
    expect(mapLibreCanvasSrc).toContain("attribution: '© OpenStreetMap contributors'")
  })

  it('the timeline lane clears the bottom-left attribution strip', () => {
    expect(outbreakMapPageSrc).toContain('absolute inset-x-0 bottom-7 flex justify-center')
  })
})

describe('GEO33B Section 15: MapLibre control theming is feature-owned and non-breaking', () => {
  const css = readFileSync(join(FEATURE_ROOT, 'components', 'geospatialMapChrome.css'), 'utf-8')

  it('every rule is scoped under this feature\'s own wrapper class -- nothing global/shared is restyled', () => {
    const selectors = css.match(/^[^@\s/][^{]*\{/gm) ?? []
    expect(selectors.length).toBeGreaterThan(0)
    for (const selector of selectors) {
      expect(selector).toContain('.geo-map-shell')
    }
  })

  it('the wrapper class is actually rendered by MapLibreCanvas', () => {
    expect(mapLibreCanvasSrc).toContain('geo-map-shell')
  })

  it('restyles the zoom control group and its buttons for the dark theme', () => {
    expect(css).toContain('.maplibregl-ctrl-group')
    expect(css).toContain('.maplibregl-ctrl-group button')
  })

  it('never disables interaction or hides a control -- colour/border only', () => {
    expect(css).not.toMatch(/pointer-events\s*:/)
    expect(css).not.toMatch(/display\s*:\s*none/)
    expect(css).not.toMatch(/visibility\s*:\s*hidden/)
    // Attribution must stay legible, never collapsed to zero size.
    expect(css).not.toMatch(/\.maplibregl-ctrl-attrib[^{]*\{[^}]*(width|height)\s*:\s*0/)
  })
})

describe('GEO33B Section 1: dev-only load-timing instrumentation', () => {
  it('marks every lifecycle boundary the checkpoint asks for', () => {
    const timingSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'loadTiming.js'), 'utf-8')
    for (const mark of [
      'PAGE_MOUNT',
      'MAP_CONSTRUCT_START',
      'STYLE_LOAD_START',
      'STYLE_LOAD_END',
      'FIRST_RENDER',
      'SOURCES_CREATED',
      'NATIONAL_FETCH_START',
      'NATIONAL_FETCH_END',
      'OPERATIONAL_FETCH_START',
      'OPERATIONAL_FETCH_END',
      'FIRST_SET_DATA',
      'FIRST_OUTBREAK_RENDER',
      'MAP_IDLE',
    ]) {
      expect(timingSrc).toContain(`${mark}:`)
    }
  })

  it('is gated on import.meta.env.DEV so it cannot affect production behaviour', () => {
    const timingSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'loadTiming.js'), 'utf-8')
    expect(timingSrc).toContain('import.meta.env?.DEV')
    expect(timingSrc).toContain('if (!isTimingEnabled()) return')
  })

  it('is write-only diagnostics -- no rendering decision anywhere reads a timing value back', () => {
    for (const relativePath of [
      'components/MapLibreCanvas.jsx',
      'pages/OutbreakMapPage.jsx',
      'context/useNationalOutbreaks.js',
      'context/useOperationalContext.js',
      'context/useDistrictGeometry.js',
    ]) {
      const src = stripComments(readFileSync(join(FEATURE_ROOT, relativePath), 'utf-8'))
      expect(src).not.toContain('buildTimingSummary')
      expect(src).not.toContain('durationBetween')
      expect(src).not.toContain('timingMarks(')
    }
  })
})
