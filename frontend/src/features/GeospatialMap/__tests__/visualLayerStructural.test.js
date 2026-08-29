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
  it('no source file under GeospatialMap/ (excluding tests) calls setInterval or setTimeout', () => {
    expect(SOURCE_FILES.length).toBeGreaterThan(0)
    for (const file of SOURCE_FILES) {
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('setInterval(')).toBe(false)
      expect(src.includes('setTimeout(')).toBe(false)
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
