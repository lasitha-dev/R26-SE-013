import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

function collectSourceFiles(dir) {
  const files = []
  for (const entry of readdirSync(dir)) {
    if (entry === '__tests__' || entry === 'node_modules') continue
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      files.push(...collectSourceFiles(full))
    } else if (/\.(js|jsx)$/.test(entry)) {
      files.push(full)
    }
  }
  return files
}

const SOURCE_FILES = collectSourceFiles(FEATURE_ROOT)

// Strips block and line comments before a structural code scan --
// without this, a comment that legitimately DOCUMENTS a forbidden token
// (explaining what the code deliberately does NOT do) false-positives
// the same way a blunt string search over prose does. This is the same
// class of bug fixed by the negation-aware wording check in
// semanticLabels.test.js -- fix the checker, not the vocabulary.
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
}

describe('11B-STATE-01/02: the map consumes ONLY the committed snapshot, never the in-flight buffer', () => {
  it('no visual/map component file ever references incomingSnapshotBuffer', () => {
    const visualFiles = SOURCE_FILES.filter((f) => /(MapView|MapLibreCanvas|MapCanvas|MapLegend|CellDetailPanel|GeospatialMapFeature)\.(jsx?)$/.test(f))
    expect(visualFiles.length).toBeGreaterThanOrEqual(6)
    for (const file of visualFiles) {
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('incomingSnapshotBuffer')).toBe(false)
    }
  })

  it('GeospatialMapFeature only ever passes state.currentCommittedSnapshot into the map view', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'GeospatialMapFeature.jsx'), 'utf-8')
    expect(src).toMatch(/currentCommittedSnapshot/)
    expect(src).toMatch(/<MapView snapshot=\{snapshot\}/)
  })

  it('MapView never fetches or opens a second snapshot transport -- it only reads props', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'MapView.jsx'), 'utf-8')
    expect(src).not.toMatch(/fetch\(/)
    expect(src).not.toMatch(/new WebSocket/)
  })
})

describe('11B-POLL-01: no automatic scientific refresh timer exists anywhere in the visual layer', () => {
  // GEO-HYBRID-LIVE-SYNC-08 Phase 5: `setInterval` stays banned everywhere,
  // no exception. `setTimeout` is now intentionally used as the single
  // operational-reconciliation scheduler in `context/useOperationalContext.js`
  // only (never a scientific refresh) -- see that file and
  // `noAutoPolling.test.js` for its own dedicated safety assertions. Every
  // OTHER file in the visual layer, scientific included, still has none.
  const OPERATIONAL_SCHEDULER_FILE = join('context', 'useOperationalContext.js')

  it('no source file under GeospatialMap/ (excluding tests) calls setInterval', () => {
    expect(SOURCE_FILES.length).toBeGreaterThan(0)
    for (const file of SOURCE_FILES) {
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('setInterval(')).toBe(false)
    }
  })

  it('no source file OTHER than the operational reconciliation scheduler calls setTimeout', () => {
    for (const file of SOURCE_FILES) {
      if (file === join(FEATURE_ROOT, OPERATIONAL_SCHEDULER_FILE)) continue
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('setTimeout('), `${file} unexpectedly calls setTimeout(`).toBe(false)
    }
  })
})

describe('11B-FALLBACK-01: a map-rendering failure preserves scientific snapshot data via a distinct status', () => {
  it('MapView classifies map failure as VISUAL_MAP_UNAVAILABLE_SNAPSHOT_DATA_PRESERVED, never ANALYSIS_UNAVAILABLE', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'MapView.jsx'), 'utf-8')
    expect(src).toMatch(/VISUAL_MAP_UNAVAILABLE_SNAPSHOT_DATA_PRESERVED/)
    expect(src).not.toMatch(/ANALYSIS_UNAVAILABLE/)
  })

  it('the fallback path still renders MapCanvas (the SVG view) with the same snapshot data', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'MapView.jsx'), 'utf-8')
    expect(src).toMatch(/<MapCanvas cellFeatures=\{snapshot\.cells\} sourceFeatures=\{snapshot\.sources\.features\}/)
  })
})

describe('11B1-GLYPH-01: neutral scientific overlays contain no text-field/glyph dependency', () => {
  it('MapLibreCanvas.jsx never uses text-field/text-font for the source or direction overlays', () => {
    const src = stripComments(readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8'))
    expect(src).not.toMatch(/text-field/)
    expect(src).not.toMatch(/text-font/)
  })

  it('MapLibreCanvas.jsx registers LOCAL images via addImage, never a remote icon URL', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
    expect(src).toMatch(/map\.addImage\(/)
    expect(src).not.toMatch(/loadImage\(/) // the URL-based MapLibre alternative -- deliberately not used
  })

  it('the source/direction layer specs use icon-image/icon-rotate (mapLibreAdapter.js), never text-field', () => {
    const raw = readFileSync(join(FEATURE_ROOT, 'components', 'mapLibreAdapter.js'), 'utf-8')
    expect(raw).toMatch(/icon-image/)
    expect(raw).toMatch(/icon-rotate/)
    expect(stripComments(raw)).not.toMatch(/text-field/)
  })

  it('the neutral fallback style itself declares no glyphs URL and no remote sources', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'basemapConfig.js'), 'utf-8')
    expect(src).not.toMatch(/glyphs\s*:/)
  })
})

describe('Part 20: no frontend scientific recomputation in the visual layer', () => {
  const FORBIDDEN_SUBSTRINGS = [
    'Math.exp(', // C0 formula signature (SUM exp(-d/25))
    'haversine',
    'geodesic',
    'resultant',
    'bootstrap',
    'raw_c0_score.toFixed', // formatting-then-storing back would indicate mutation, not just display
  ]
  // A real ASSIGNMENT ("foo = value"), never a comparison ("===", "==",
  // "!==") -- the negative lookahead excludes any "=" immediately
  // followed by another "=".
  const ASSIGNMENT_PATTERN = (field) => new RegExp(`${field}\\s*=(?!=)`)

  it('no visual-layer source file contains a scientific-recomputation signature', () => {
    for (const file of SOURCE_FILES) {
      const src = readFileSync(file, 'utf-8')
      for (const token of FORBIDDEN_SUBSTRINGS) {
        expect(src.includes(token), `${token} found in ${file}`).toBe(false)
      }
    }
  })

  it('raw_c0_score is only ever READ, never assigned/mutated', () => {
    for (const file of SOURCE_FILES) {
      const src = readFileSync(file, 'utf-8')
      expect(ASSIGNMENT_PATTERN('raw_c0_score').test(src), `assignment found in ${file}`).toBe(false)
    }
  })

  it('bearing_deg is only ever READ (via property access or MapLibre get expression), never written back', () => {
    for (const file of SOURCE_FILES) {
      const src = readFileSync(file, 'utf-8')
      expect(ASSIGNMENT_PATTERN('bearing_deg').test(src), `assignment found in ${file}`).toBe(false)
    }
  })
})

describe('GEO-OWNED-FINAL-08 Section 15: host-layout safety -- map resizes with its container, not only on fullscreen', () => {
  const mapLibreCanvasSrc = stripComments(readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8'))

  it('observes its own container with a ResizeObserver (catches a host sidebar toggle/window resize, not only fullscreenchange)', () => {
    expect(mapLibreCanvasSrc).toContain('new ResizeObserver(')
    expect(mapLibreCanvasSrc).toContain('resizeObserver.observe(containerRef.current)')
  })

  it('calls the real MapLibre resize() from the observer callback, never a fabricated layout recalculation', () => {
    const observerStart = mapLibreCanvasSrc.indexOf('new ResizeObserver(')
    const observerCallback = mapLibreCanvasSrc.slice(observerStart, mapLibreCanvasSrc.indexOf('resizeObserver.observe', observerStart))
    expect(observerCallback).toContain('mapRef.current?.resize()')
  })

  it('disconnects the ResizeObserver on unmount -- no leaked observer across remounts', () => {
    // The mount effect's own cleanup is the one that also calls
    // `map?.remove()` -- MapLibreCanvas.jsx has several OTHER effects
    // with their own unrelated `return () => {...}` cleanups (reach-ring
    // animation, etc.), so this must not just grab the LAST one in the file.
    const cleanupStart = mapLibreCanvasSrc.lastIndexOf('return () => {', mapLibreCanvasSrc.indexOf('map?.remove()'))
    const cleanupEnd = mapLibreCanvasSrc.indexOf('map?.remove()') + 'map?.remove()'.length
    const cleanupBody = mapLibreCanvasSrc.slice(cleanupStart, cleanupEnd)
    expect(cleanupBody).toContain('resizeObserver?.disconnect()')
  })

  it('the map container carries an explicit height/min-height class -- never an unbounded 0-height flex child', () => {
    expect(mapLibreCanvasSrc).toMatch(/className="[^"]*min-h-\[[0-9]+px\][^"]*"/)
  })
})

describe('GEO-PAGE1-FINAL Section 5.2/6: the map never wraps into a duplicate world copy and never pans outside a real, fixed Sri Lanka region', () => {
  const mapLibreCanvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')

  it('disables wrapped world copies on the real map instance', () => {
    expect(mapLibreCanvasSrc).toContain('renderWorldCopies: false')
  })

  it('constrains panning/zooming with a real, fixed maxBounds constant', () => {
    expect(mapLibreCanvasSrc).toContain('maxBounds: SRI_LANKA_MAX_PAN_BOUNDS')
    expect(mapLibreCanvasSrc).toMatch(/export const SRI_LANKA_MAX_PAN_BOUNDS = \[/)
  })
})

describe('GEO-PAGE1-FINAL Section 10/24: an auto-focused default origin never triggers the camera-fly or the selection halo/ripple/dim -- only a real click does', () => {
  const mapLibreCanvasSrc = stripComments(readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8'))

  it('derives a distinct visuallySelectedOutbreakId that is null whenever autoFocusOutbreak is true', () => {
    expect(mapLibreCanvasSrc).toMatch(/const visuallySelectedOutbreakId = autoFocusOutbreak \? null : selectedOutbreakId/)
  })

  it('the camera-fit effect gates on visuallySelectedOutbreakId, never the raw selectedOutbreakId prop', () => {
    const start = mapLibreCanvasSrc.indexOf('const cellsFC = buildCellsFeatureCollection(cellFeatures)')
    const end = mapLibreCanvasSrc.indexOf('}, [cellFeatures, sourceFeatures])')
    const body = mapLibreCanvasSrc.slice(start, end)
    expect(body).toContain('if (nationalSources && visuallySelectedOutbreakId && visuallySelectedOutbreakId !== lastFitOutbreakIdRef.current)')
    // The raw prop is never read for this decision -- only for building
    // the (unrelated) `cellFeatures`/`sourceFeatures` sources above it.
    expect(body).not.toMatch(/if \([^)]*\bselectedOutbreakId\b[^)]*\)/)
  })

  it('the halo/dim/ripple effect reads visuallySelectedOutbreakId exclusively, and re-runs whenever it changes', () => {
    const start = mapLibreCanvasSrc.indexOf('for (const feature of nationalSources.features) {')
    const end = mapLibreCanvasSrc.indexOf('}, [visuallySelectedOutbreakId, nationalSources])') + '}, [visuallySelectedOutbreakId, nationalSources])'.length
    const body = mapLibreCanvasSrc.slice(start, end)
    expect(body).toContain('featureBelongsToOutbreak(feature, visuallySelectedOutbreakId)')
    expect(body).toContain('if (visuallySelectedOutbreakId != null)')
    expect(body).not.toMatch(/featureBelongsToOutbreak\(f(eature)?, selectedOutbreakId\)/)
  })
})

describe('GEO-VISUAL-POLISH-01 Section 6: the ambient outbreak-marker pulse is cheap, leak-free, and motion-honest', () => {
  const mapLibreCanvasSrc = stripComments(readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8'))
  const pulseEffectStart = mapLibreCanvasSrc.indexOf('const HALF_CYCLE_MS = NATIONAL_SOURCES_PULSE_CYCLE_MS')
  // The effect's own dependency array closes it -- same brace-free
  // slicing technique already used elsewhere in this file/describe block.
  const pulseEffectEnd = mapLibreCanvasSrc.indexOf('}, [reduceMotion])', pulseEffectStart) + '}, [reduceMotion])'.length
  const pulseEffectBody = mapLibreCanvasSrc.slice(pulseEffectStart, pulseEffectEnd)

  it('the pulse clock actually exists and is scoped to the effect this test extracts', () => {
    expect(pulseEffectStart).toBeGreaterThan(-1)
    expect(pulseEffectBody).toContain('requestAnimationFrame(tick)')
  })

  it('is skipped entirely under prefers-reduced-motion -- never starts the RAF loop at all', () => {
    const windowBefore = mapLibreCanvasSrc.slice(Math.max(0, pulseEffectStart - 200), pulseEffectStart)
    expect(windowBefore).toContain('useEffect(() => {')
    expect(windowBefore).toContain('if (reduceMotion) return undefined')
  })

  it('drives MapLibre paint directly (setPaintProperty) -- never a React state update inside the per-frame tick, so a running pulse causes zero extra React re-renders', () => {
    expect(pulseEffectBody).toContain('map.setPaintProperty(')
    // Any "setXxx(" call NOT prefixed by "map." would be a React state
    // setter in this codebase's convention (e.g. `setStyleReady`,
    // `setSelectedCellFeature`) -- none may appear inside this effect.
    expect(pulseEffectBody).not.toMatch(/(?<!map\.)\bset[A-Z]\w*\(/)
  })

  it('never calls setFeatureState per-feature -- the whole-layer paint-property toggle is what keeps this cost independent of real marker count', () => {
    expect(pulseEffectBody).not.toContain('setFeatureState')
  })

  it('cancels its own animation frame on cleanup -- no leaked RAF loop across remounts/prop changes', () => {
    const cleanupStart = pulseEffectBody.lastIndexOf('return () => {')
    expect(cleanupStart).toBeGreaterThan(-1)
    const cleanupBody = pulseEffectBody.slice(cleanupStart)
    expect(cleanupBody).toContain('cancelAnimationFrame(frame)')
  })

  it('ticks against performance.now(), never setInterval/setTimeout (this feature bans both outside the one documented operational scheduler)', () => {
    expect(pulseEffectBody).toContain('performance.now()')
    expect(pulseEffectBody).not.toContain('setInterval(')
    expect(pulseEffectBody).not.toContain('setTimeout(')
  })
})
