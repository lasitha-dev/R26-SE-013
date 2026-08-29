import { describe, expect, it } from 'vitest'
import { BASEMAP_MODE_NEUTRAL_FALLBACK, BASEMAP_MODE_REMOTE_STYLE, neutralFallbackStyle, resolveBasemapConfig } from '../components/basemapConfig'

describe('Checkpoint 11B Part 3: basemap configuration boundary', () => {
  it('falls back to a neutral, token-free style when no URL is configured', () => {
    for (const value of [undefined, '', '   ']) {
      const config = resolveBasemapConfig(value)
      expect(config.mode).toBe(BASEMAP_MODE_NEUTRAL_FALLBACK)
      expect(config.style).toEqual(neutralFallbackStyle())
    }
  })

  it('the neutral fallback style requires no API key/token field anywhere', () => {
    const style = neutralFallbackStyle()
    expect(JSON.stringify(style).toLowerCase()).not.toMatch(/token|api_key|apikey|secret/)
    expect(Object.keys(style.sources)).toHaveLength(0)
  })

  it('uses the configured remote style URL verbatim when present', () => {
    const config = resolveBasemapConfig('https://example.com/style.json')
    expect(config.mode).toBe(BASEMAP_MODE_REMOTE_STYLE)
    expect(config.style).toBe('https://example.com/style.json')
    expect(config.note).toMatch(/(not|never) scientific evidence/i)
    expect(config.note).toMatch(/availability is not guaranteed/i)
  })
})
