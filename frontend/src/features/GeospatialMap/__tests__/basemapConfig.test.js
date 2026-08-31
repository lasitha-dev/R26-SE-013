import { describe, expect, it } from 'vitest'
import {
  BASEMAP_MODE_NEUTRAL_FALLBACK,
  BASEMAP_MODE_OPEN_RASTER_DEFAULT,
  BASEMAP_MODE_OPEN_VECTOR_DARK_DEFAULT,
  BASEMAP_MODE_OPEN_VECTOR_LIBERTY_DEFAULT,
  BASEMAP_MODE_REMOTE_STYLE,
  OPEN_FREE_MAP_DARK_STYLE_URL,
  OPEN_FREE_MAP_LIBERTY_STYLE_URL,
  neutralFallbackStyle,
  openRasterDefaultStyle,
  resolveBasemapConfig,
} from '../components/basemapConfig'

describe('Checkpoint 11B Part 3 / GEO33A: basemap configuration boundary', () => {
  // GEO33A Section 0/6: a real browser screenshot proved the previous
  // "dark" default was too close to black to read -- Liberty (the
  // checkpoint's own explicit first choice) is now the default.
  it('falls back to the real, key-free OpenFreeMap LIBERTY vector basemap when no URL is configured', () => {
    for (const value of [undefined, '', '   ']) {
      const config = resolveBasemapConfig(value)
      expect(config.mode).toBe(BASEMAP_MODE_OPEN_VECTOR_LIBERTY_DEFAULT)
      expect(config.style).toBe(OPEN_FREE_MAP_LIBERTY_STYLE_URL)
    }
  })

  it('never falls back to the too-dark "dark" style by default any more', () => {
    const config = resolveBasemapConfig(undefined)
    expect(config.mode).not.toBe(BASEMAP_MODE_OPEN_VECTOR_DARK_DEFAULT)
    expect(config.style).not.toBe(OPEN_FREE_MAP_DARK_STYLE_URL)
  })

  it('the default vector style URL requires no API key/token and is a plain string MapLibre fetches itself', () => {
    expect(OPEN_FREE_MAP_LIBERTY_STYLE_URL.toLowerCase()).not.toMatch(/token|api_key|apikey|secret|key=/)
    expect(OPEN_FREE_MAP_LIBERTY_STYLE_URL).toMatch(/^https:\/\//)
  })

  it('the retired "dark" style URL is still exported for reference/opt-in only, still key-free', () => {
    expect(OPEN_FREE_MAP_DARK_STYLE_URL.toLowerCase()).not.toMatch(/token|api_key|apikey|secret|key=/)
    expect(OPEN_FREE_MAP_DARK_STYLE_URL).toMatch(/^https:\/\//)
  })

  // GEO29A: a prior CARTO-based default passed this exact assertion shape
  // while the ACTUAL tiles rendered an "API KEY REQUIRED" watermark in a
  // real browser -- a style-JSON-only test can never catch that class of
  // failure (the watermark is baked into the tile image the third party
  // returns, not into anything this repo's config text contains). This
  // test still checks the config is honest (no credential field), but
  // Part 13's real basemap PASS requires actual browser Network evidence,
  // never this test alone.
  it('the open raster default requires no API key/token and uses a real OSM tile source', () => {
    const style = openRasterDefaultStyle()
    expect(JSON.stringify(style).toLowerCase()).not.toMatch(/token|api_key|apikey|secret/)
    const source = style.sources.osm
    expect(source.type).toBe('raster')
    expect(source.tiles.length).toBeGreaterThan(0)
    for (const url of source.tiles) {
      expect(url).toMatch(/^https:\/\/[a-c]\.tile\.openstreetmap\.org\//)
    }
    expect(style.layers.some((l) => l.type === 'raster' && l.source === 'osm')).toBe(true)
  })

  it('the neutral (flat, sourceless) fallback style remains available for an explicit zero-network context', () => {
    const style = neutralFallbackStyle()
    expect(JSON.stringify(style).toLowerCase()).not.toMatch(/token|api_key|apikey|secret/)
    expect(Object.keys(style.sources)).toHaveLength(0)
  })

  it('uses the configured remote style URL verbatim when present, never the open-raster default', () => {
    const config = resolveBasemapConfig('https://example.com/style.json')
    expect(config.mode).toBe(BASEMAP_MODE_REMOTE_STYLE)
    expect(config.style).toBe('https://example.com/style.json')
    expect(config.note).toMatch(/(not|never) scientific evidence/i)
    expect(config.note).toMatch(/availability is not guaranteed/i)
  })

  it('BASEMAP_MODE_NEUTRAL_FALLBACK is still exported (for callers that explicitly want it) even though it is no longer the resolver default', () => {
    expect(BASEMAP_MODE_NEUTRAL_FALLBACK).toBe('NEUTRAL_FALLBACK')
  })
})
