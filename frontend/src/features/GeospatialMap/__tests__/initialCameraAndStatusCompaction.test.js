import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it, vi } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

// `MapLibreCanvas.jsx` imports `maplibre-gl`, which has a top-level side
// effect (`maplibregl.setWorkerUrl(window.URL.createObjectURL(...))`) that
// jsdom does not implement by default -- see `outbreakMapPageRenderSmoke
// .test.jsx` for the same pattern/explanation. The module is imported
// dynamically, after the polyfill, so this file can import the real
// `SRI_LANKA_*` constants rather than duplicating them.
let SRI_LANKA_CENTER, SRI_LANKA_INITIAL_ZOOM, SRI_LANKA_BOUNDS

beforeAll(async () => {
  if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
  if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
  ;({ SRI_LANKA_CENTER, SRI_LANKA_INITIAL_ZOOM, SRI_LANKA_BOUNDS } = await import('../components/MapLibreCanvas'))
})

describe('GEO29A Phase 11/21 item 12: initial camera is Sri Lanka, never the whole world', () => {
  it('exposes a real, fixed Sri Lanka center/zoom/bounds -- never [0,0]/zoom 0', () => {
    expect(SRI_LANKA_CENTER).toHaveLength(2)
    const [lng, lat] = SRI_LANKA_CENTER
    expect(lng).toBeGreaterThan(79)
    expect(lng).toBeLessThan(82)
    expect(lat).toBeGreaterThan(5)
    expect(lat).toBeLessThan(10)
    expect(SRI_LANKA_INITIAL_ZOOM).toBeGreaterThan(3)

    const [[minLng, minLat], [maxLng, maxLat]] = SRI_LANKA_BOUNDS
    expect(minLng).toBeLessThan(maxLng)
    expect(minLat).toBeLessThan(maxLat)
  })

  it('the map constructor is given a real center/zoom directly, not left to the library default', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
    const ctorStart = src.indexOf('new maplibregl.Map({')
    const ctorEnd = src.indexOf('})', ctorStart)
    const ctorBody = src.slice(ctorStart, ctorEnd)
    expect(ctorBody).toContain('center: SRI_LANKA_CENTER')
    expect(ctorBody).toContain('zoom: SRI_LANKA_INITIAL_ZOOM')
  })

  it('"Fit Sri Lanka" (resetView with no explicit/national bounds) falls back to the real Sri Lanka bounds constant, never a silent no-op', () => {
    const src = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
    const resetViewStart = src.indexOf('resetView(explicitBounds) {')
    const resetViewEnd = src.indexOf('},', resetViewStart)
    const body = src.slice(resetViewStart, resetViewEnd)
    expect(body).toContain('SRI_LANKA_BOUNDS')
    expect(body).toMatch(/map\.fitBounds\(bounds/)
  })
})

describe('GEO29A Phase 10/14/15/21 item 14: status chips are compacted, never inline (the real overlap regression)', () => {
  const outbreakMapPageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')

  it('OutbreakMapPage no longer renders SnapshotStatusChip/OperationalStatusChip directly -- only via the collapsed StatusDiagnosticsMenu', () => {
    expect(outbreakMapPageSrc).not.toContain('<SnapshotStatusChip')
    expect(outbreakMapPageSrc).not.toContain('<OperationalStatusChip')
    expect(outbreakMapPageSrc).toContain('<StatusDiagnosticsMenu')
  })

  it('StatusDiagnosticsMenu keeps both chips real and functional, just collapsed behind one toggle', () => {
    const menuSrc = readFileSync(join(FEATURE_ROOT, 'components', 'StatusDiagnosticsMenu.jsx'), 'utf-8')
    expect(menuSrc).toContain('<SnapshotStatusChip')
    expect(menuSrc).toContain('<OperationalStatusChip')
    expect(menuSrc).toContain('useState')
  })
})
