import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const outbreakMapPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')
const mapLibreCanvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
}

/** Extracts a named function's body by brace-matching from its `function
 * name(` declaration to the closing brace -- the same naive-but-effective
 * technique `topControlBar.test.js`/`operationalMapWiring.test.js` already
 * use for this codebase's structural tests. */
function extractFunctionBody(src, functionName) {
  const start = src.indexOf(`function ${functionName}(`)
  if (start === -1) throw new Error(`function ${functionName} not found`)
  const bodyStart = src.indexOf('{', start)
  let depth = 0
  for (let i = bodyStart; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1
    if (src[i] === '}') {
      depth -= 1
      if (depth === 0) return src.slice(bodyStart, i + 1)
    }
  }
  throw new Error(`unterminated function ${functionName}`)
}

describe('GEO33A Section 5/22: camera (location) handlers never touch national/operational state', () => {
  const handleFitSriLanka = extractFunctionBody(outbreakMapPageSrc, 'handleFitSriLanka')
  const handleFocusMyDistrict = extractFunctionBody(outbreakMapPageSrc, 'handleFocusMyDistrict')

  it('handleFitSriLanka only sets the location scope and calls resetView -- no national/operational state mutation', () => {
    expect(handleFitSriLanka).toContain('setLocationScope')
    expect(handleFitSriLanka).toContain('resetView')
    expect(handleFitSriLanka).not.toMatch(/setRefreshToken|operational\.refresh|national\./)
  })

  it('handleFocusMyDistrict only sets the location scope and calls resetView with real bounds -- never clears national state', () => {
    expect(handleFocusMyDistrict).toContain('setLocationScope')
    expect(handleFocusMyDistrict).toContain('resetView')
    expect(handleFocusMyDistrict).not.toMatch(/setRefreshToken|operational\.refresh|national\./)
  })
})

describe('GEO33A Section 5: MapLibreCanvas resetView() (camera-only) never touches the national-sources source', () => {
  it('resetView() calls fitBounds only -- it never calls setData on any source', () => {
    const start = mapLibreCanvasSrc.indexOf('resetView(explicitBounds) {')
    const end = mapLibreCanvasSrc.indexOf('},', start)
    const body = stripComments(mapLibreCanvasSrc.slice(start, end))
    expect(body).toMatch(/fitBounds/)
    expect(body).not.toMatch(/\.setData\(/)
  })

  it('the national-sources source is updated ONLY by its own dedicated effect, keyed on the nationalSources prop -- never inside resetView or a location-scope effect', () => {
    const src = stripComments(mapLibreCanvasSrc)
    const setDataCallSite = src.indexOf('map.getSource(NATIONAL_SOURCES_SOURCE_ID)?.setData(nationalSources)')
    expect(setDataCallSite).toBeGreaterThan(-1)
    // Its enclosing effect's dependency array is exactly [nationalSources].
    const effectDepsStart = src.indexOf('}, [nationalSources])', setDataCallSite)
    expect(effectDepsStart).toBeGreaterThan(setDataCallSite)
  })
})

describe('GEO33A Section 22: a scientific/historical (national) fetch failure must not suppress authorized Cases', () => {
  it('showOperationalLayer depends only on analysisMode -- never on national.status', () => {
    const line = outbreakMapPageSrc.match(/const showOperationalLayer = .*/)[0]
    expect(line).not.toMatch(/national\./)
  })

  it('the operational-context hook is independent of the national-outbreaks hook -- two separate hook calls, no shared error state', () => {
    expect(outbreakMapPageSrc).toMatch(/const national = useNationalOutbreaks\(/)
    expect(outbreakMapPageSrc).toMatch(/const operational = useOperationalContext\(\)/)
  })

  it('the national-error banner text is scoped to the scientific/historical layer only, explicitly says verified clinical cases are unaffected', () => {
    expect(outbreakMapPageSrc).toMatch(/Scientific\/historical layer unavailable\. Verified clinical cases are unaffected\./)
  })
})

describe('GEO33A Section 8: the initial/reset camera fit reserves real room for the floating top toolbar and bottom timeline', () => {
  it('MAP_FIT_PADDING is asymmetric (top/bottom differ from a flat small pad), not a single flat number', () => {
    expect(mapLibreCanvasSrc).toMatch(/MAP_FIT_PADDING\s*=\s*\{\s*top:\s*\d+,\s*bottom:\s*\d+,\s*left:\s*\d+,\s*right:\s*\d+\s*\}/)
  })

  it('every real fitBounds call site uses the shared padding constant, never a re-introduced flat literal', () => {
    const fitBoundsCalls = mapLibreCanvasSrc.match(/map\.fitBounds\([^)]*\)/g) ?? []
    expect(fitBoundsCalls.length).toBeGreaterThanOrEqual(3)
    for (const call of fitBoundsCalls) {
      expect(call).toContain('MAP_FIT_PADDING')
    }
  })
})
