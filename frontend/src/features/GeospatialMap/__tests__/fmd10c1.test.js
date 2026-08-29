import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchOriginTriggerSources, fetchOrigins } from '../api/geospatialApi'
import { buildNationalSourcesFeatureCollection } from '../components/mapLibreAdapter'
import {
  FMD_SOURCE_ICON_ID,
  SOURCE_ICON_ID,
  SOURCE_ICON_SIZE,
  buildFmdSourceMarkerImage,
  buildSourceMarkerImage,
} from '../components/presentationIcons'
import { sourceIconLayout } from '../components/mapLibreAdapter'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

function readSource(relativePath) {
  return readFileSync(join(FEATURE_ROOT, relativePath), 'utf-8')
}

/**
 * FMD-10C1: this repo's Vitest environment is Node-only (no DOM/`act`,
 * see `MapLibreCanvas.jsx`'s own header comment), so `MapLibreCanvas`
 * itself and the `useNationalOutbreaks`/`useFmdOriginRisk` hooks cannot
 * be rendered here. The tests below verify:
 *  - the pure geometry/adapter functions those hooks and that component
 *    actually call (real assertions, not a browser/E2E stand-in), and
 *  - the WIRING that connects them, via a structural source-text check
 *    (the same technique this repo's own `noAutoPolling.test.js` already
 *    uses) -- these are guard-clause/wiring-presence checks, explicitly
 *    NOT claimed as end-to-end evidence that a marker renders on screen.
 */

describe('FMD-10C1: real FMD historical geometry maps to valid MapLibre point features', () => {
  const REAL_FMD_TRIGGER_SOURCES_RESPONSE = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [81.684662, 7.122427] },
        properties: {
          source_id: 'FAO_EMPRESI_BIGQUERY_CSV:EMPRES-i_FMD_events_2002-2026.csv:008964',
          forecast_origin_id: 'ORIGIN:Sri Lanka:2009-09-09',
          geometry_semantics:
            'OBSERVED_HISTORICAL_TRIGGER_SOURCE_ONLY_NOT_A_RISK_CELL_FORECAST_POINT_DISEASE_BOUNDARY_NOMINAL_REACH_OR_TRAJECTORY_POINT',
        },
      },
    ],
    forecast_origin_id: 'ORIGIN:Sri Lanka:2009-09-09',
    country: 'Sri Lanka',
    t0: '2009-09-09',
    disease: 'Foot and mouth disease',
    n_points: 1,
    geometry_semantics:
      'OBSERVED_HISTORICAL_TRIGGER_SOURCE_ONLY_NOT_A_RISK_CELL_FORECAST_POINT_DISEASE_BOUNDARY_NOMINAL_REACH_OR_TRAJECTORY_POINT',
  }

  it('a real trigger-sources response merges into a valid MapLibre FeatureCollection, tagged with its real outbreakId', () => {
    const fc = buildNationalSourcesFeatureCollection([
      { outbreakId: 'ORIGIN:Sri Lanka:2009-09-09', sourcesFeatureCollection: REAL_FMD_TRIGGER_SOURCES_RESPONSE },
    ])
    expect(fc.type).toBe('FeatureCollection')
    expect(fc.features).toHaveLength(1)
    const [feature] = fc.features
    expect(feature.type).toBe('Feature')
    expect(feature.geometry.type).toBe('Point')
    expect(feature.geometry.coordinates).toEqual([81.684662, 7.122427])
    expect(feature.properties.outbreakId).toBe('ORIGIN:Sri Lanka:2009-09-09')
    // marker -> origin ID identity preserved
    expect(feature.properties.source_id).toBe('FAO_EMPRESI_BIGQUERY_CSV:EMPRES-i_FMD_events_2002-2026.csv:008964')
  })

  it('every point is a real coordinate copied verbatim from the backend response -- no fallback/default/centroid value exists in the adapter', () => {
    const fc = buildNationalSourcesFeatureCollection([
      { outbreakId: 'ORIGIN:Sri Lanka:2009-09-09', sourcesFeatureCollection: REAL_FMD_TRIGGER_SOURCES_RESPONSE },
    ])
    // Exact byte-for-byte pass-through, never rounded/recomputed/defaulted.
    expect(fc.features[0].geometry.coordinates).toEqual(
      REAL_FMD_TRIGGER_SOURCES_RESPONSE.features[0].geometry.coordinates,
    )
  })

  it('multiple real trigger sources for one origin become multiple real map points, each with its own real source_id', () => {
    const multiSourceResponse = {
      ...REAL_FMD_TRIGGER_SOURCES_RESPONSE,
      features: [
        REAL_FMD_TRIGGER_SOURCES_RESPONSE.features[0],
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [81.7, 7.2] },
          properties: { source_id: 'SOURCE:B', forecast_origin_id: 'ORIGIN:Sri Lanka:2009-09-09', geometry_semantics: 'X' },
        },
      ],
    }
    const fc = buildNationalSourcesFeatureCollection([{ outbreakId: 'ORIGIN:Sri Lanka:2009-09-09', sourcesFeatureCollection: multiSourceResponse }])
    expect(fc.features).toHaveLength(2)
    expect(new Set(fc.features.map((f) => f.properties.source_id))).toEqual(
      new Set(['FAO_EMPRESI_BIGQUERY_CSV:EMPRES-i_FMD_events_2002-2026.csv:008964', 'SOURCE:B']),
    )
  })

  it('an origin with no resolvable geometry (sourcesFeatureCollection: null) contributes zero fabricated points', () => {
    const fc = buildNationalSourcesFeatureCollection([{ outbreakId: 'ORIGIN:X', sourcesFeatureCollection: null }])
    expect(fc.features).toEqual([])
  })
})

describe('FMD-10C1: fetchOriginTriggerSources builds the correct disease-neutral request', () => {
  const realFetch = global.fetch

  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ type: 'FeatureCollection', features: [], forecast_origin_id: 'x', country: 'Sri Lanka', t0: '2020-01-01', disease: 'Foot and mouth disease', n_points: 0, geometry_semantics: 'X' }),
    })
  })

  afterEach(() => {
    global.fetch = realFetch
  })

  it('calls GET /origins/{id}/trigger-sources -- never /analysis/{id}/sources', async () => {
    await fetchOriginTriggerSources('ORIGIN:Sri Lanka:2009-09-09', { disease: 'fmd' })
    expect(global.fetch).toHaveBeenCalledTimes(1)
    const url = global.fetch.mock.calls[0][0]
    expect(url).toContain('/origins/ORIGIN%3ASri%20Lanka%3A2009-09-09/trigger-sources')
    expect(url).toContain('disease=fmd')
    expect(url).not.toContain('/analysis/')
    expect(url).not.toContain('/sources?')
  })

  it('omitting disease sends no disease param (server defaults to LSD, same convention as every other route)', async () => {
    await fetchOriginTriggerSources('ORIGIN:Sri Lanka:2009-09-09')
    const url = global.fetch.mock.calls[0][0]
    expect(url).not.toContain('disease=')
  })
})

describe('FMD-10C1: Sri Lanka scope is preserved end-to-end in the request path', () => {
  const realFetch = global.fetch

  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ origins: [], n_origins: 0 }) })
  })

  afterEach(() => {
    global.fetch = realFetch
  })

  it('fetchOrigins forwards an explicit country filter verbatim -- never silently dropped, never a wider default', async () => {
    await fetchOrigins({ disease: 'fmd', country: 'Sri Lanka' })
    const url = global.fetch.mock.calls[0][0]
    expect(url).toContain('country=Sri+Lanka')
    expect(url).toContain('disease=fmd')
  })

  it('OutbreakMapPage.jsx hardcodes the Sri Lanka study-country scope and threads it into useNationalOutbreaks -- a Page-1 FMD request can never silently become the unrestricted global query', () => {
    const src = readSource('pages/OutbreakMapPage.jsx')
    expect(src).toMatch(/const COUNTRY = 'Sri Lanka'/)
    expect(src).toMatch(/useNationalOutbreaks\(ctx\.selectedDisease,\s*COUNTRY,\s*refreshToken\)/)
  })

  it('useNationalOutbreaks.js always forwards its country argument to fetchOrigins -- never omits or overrides it', () => {
    const src = readSource('context/useNationalOutbreaks.js')
    expect(src).toMatch(/fetchOrigins\(\{\s*disease:\s*apiValue,\s*country\s*\}\)/)
  })
})

describe('FMD-10C1: FMD marker shape (circle) is wired distinctly from LSD (diamond), color unchanged', () => {
  it('sourceIconLayout defaults to the LSD diamond icon id (non-regression)', () => {
    expect(sourceIconLayout()['icon-image']).toBe(SOURCE_ICON_ID)
  })

  it('sourceIconLayout accepts the FMD circle icon id explicitly', () => {
    expect(sourceIconLayout(FMD_SOURCE_ICON_ID)['icon-image']).toBe(FMD_SOURCE_ICON_ID)
  })

  it('the FMD circle icon is presentation-pixels-only, same size, no network/DOM/canvas dependency', () => {
    const image = buildFmdSourceMarkerImage()
    expect(image.data).toBeInstanceOf(Uint8ClampedArray)
    expect(image.width).toBe(SOURCE_ICON_SIZE)
    expect(image.height).toBe(SOURCE_ICON_SIZE)
  })

  it('the FMD circle icon is pixel-different from the LSD diamond icon -- a real shape distinction, not a relabeled copy', () => {
    const circle = buildFmdSourceMarkerImage()
    const diamond = buildSourceMarkerImage()
    expect(Array.from(circle.data)).not.toEqual(Array.from(diamond.data))
  })

  it('both icons use the identical fill color (shape differs, color never varies by disease)', () => {
    const circle = buildFmdSourceMarkerImage()
    const diamond = buildSourceMarkerImage()
    const size = SOURCE_ICON_SIZE
    const cx = Math.round((size - 1) / 2)
    const circleCenterRGBA = [circle.data[(cx * size + cx) * 4], circle.data[(cx * size + cx) * 4 + 1], circle.data[(cx * size + cx) * 4 + 2]]
    const diamondCenterRGBA = [diamond.data[(cx * size + cx) * 4], diamond.data[(cx * size + cx) * 4 + 1], diamond.data[(cx * size + cx) * 4 + 2]]
    expect(circleCenterRGBA).toEqual(diamondCenterRGBA)
  })

  it('OutbreakMapPage.jsx wires the selected disease marker shape into MapLibreCanvas', () => {
    const src = readSource('pages/OutbreakMapPage.jsx')
    expect(src).toMatch(/nationalMarkerShape=\{diseaseConfig\.markerShape\}/)
  })

  it('MapLibreCanvas.jsx defaults nationalMarkerShape to "diamond" (LSD non-regression when the prop is omitted)', () => {
    const src = readSource('components/MapLibreCanvas.jsx')
    expect(src).toMatch(/nationalMarkerShape\s*=\s*'diamond'/)
  })
})

describe('FMD-10C1: marker selection wiring preserves real origin identity and the scalar-risk path', () => {
  it('MapLibreCanvas.jsx\'s national-sources click handler resolves outbreakId from the real clicked feature, never a fabricated id', () => {
    const src = readSource('components/MapLibreCanvas.jsx')
    expect(src).toMatch(/onSelectSource\?\.\(feature\.properties\.outbreakId, feature\.properties\.source_id\)/)
  })

  it('OutbreakMapPage.jsx\'s handleSelectSource dispatches the real outbreakId into ctx.selectOutbreak -- the same path a Page-1 FMD circle-marker click reaches', () => {
    const src = readSource('pages/OutbreakMapPage.jsx')
    expect(src).toMatch(/function handleSelectSource\(outbreakId, sourceId\)/)
    expect(src).toMatch(/ctx\.selectOutbreak\(outbreakId\)/)
  })

  it('OutbreakMapPage.jsx wires the selected outbreak into useFmdOriginRisk -- a selected FMD marker/origin still drives the real /fmd-risk request', () => {
    const src = readSource('pages/OutbreakMapPage.jsx')
    expect(src).toMatch(/useFmdOriginRisk\(ctx\.selectedDisease,\s*ctx\.selectedOutbreakId,\s*refreshToken\)/)
  })
})

describe('FMD-10C1: disease switching removes stale geometry before the new disease renders (wiring, not a scientific claim)', () => {
  it('useNationalOutbreaks.js re-fetches (and its LOADING state clears prior originsWithSources) whenever diseaseCode changes', () => {
    const src = readSource('context/useNationalOutbreaks.js')
    expect(src).toMatch(/\},\s*\[diseaseCode, country, refreshToken\]\)/)
    expect(src).toMatch(/setState\(\{ status: NATIONAL_STATUS\.LOADING, originsWithSources: \[\], error: null \}\)/)
  })
})
