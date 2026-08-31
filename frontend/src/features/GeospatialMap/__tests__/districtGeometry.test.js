import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  computeFeatureBounds,
  districtNameMatches,
  filterOriginsInsideDistrict,
  findDistrictFeature,
  isPointInsideDistrictFeature,
  normalizeDistrictDisplayName,
} from '../adapters/districtGeometry'

// GEO30B Section 16: loaded via real `fs.readFileSync`, NOT a hardcoded
// fixture -- these tests exercise the SAME real geoBoundaries dataset the
// app ships (`data/sri-lanka-districts-adm2.geojson`), so a regression in
// either the adapter or the dataset itself would be caught here.
const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const datasetPath = join(FEATURE_ROOT, 'data', 'sri-lanka-districts-adm2.geojson')
const realDistricts = JSON.parse(readFileSync(datasetPath, 'utf-8'))

describe('GEO30B Section 16: districtNameMatches', () => {
  it('matches a real vet district string against the real dataset shapeName convention', () => {
    expect(districtNameMatches('Matara', 'Matara District')).toBe(true)
  })

  it('is case-insensitive', () => {
    expect(districtNameMatches('matara', 'Matara District')).toBe(true)
    expect(districtNameMatches('MATARA', 'Matara District')).toBe(true)
  })

  it('does not match an unrelated district', () => {
    expect(districtNameMatches('Matara', 'Kandy District')).toBe(false)
  })

  it('returns false for missing input on either side, never guesses a match', () => {
    expect(districtNameMatches(null, 'Matara District')).toBe(false)
    expect(districtNameMatches('Matara', null)).toBe(false)
    expect(districtNameMatches('', 'Matara District')).toBe(false)
    expect(districtNameMatches('   ', 'Matara District')).toBe(false)
  })
})

describe('GEO30B Section 16: findDistrictFeature against the real dataset', () => {
  it('contains exactly 25 real districts (geoBoundaries LKA ADM2)', () => {
    expect(realDistricts.type).toBe('FeatureCollection')
    expect(realDistricts.features).toHaveLength(25)
  })

  it('resolves the real Matara District feature for vet district "Matara"', () => {
    const feature = findDistrictFeature(realDistricts, 'Matara')
    expect(feature).not.toBeNull()
    expect(feature.properties.shapeName).toBe('Matara District')
  })

  it('returns null for a district name with no real match', () => {
    expect(findDistrictFeature(realDistricts, 'Not A Real District')).toBeNull()
  })

  it('returns null when no vet district or no collection is given, never a guessed feature', () => {
    expect(findDistrictFeature(realDistricts, null)).toBeNull()
    expect(findDistrictFeature(null, 'Matara')).toBeNull()
    expect(findDistrictFeature({ features: 'not-an-array' }, 'Matara')).toBeNull()
  })
})

describe('GEO-MY-AREA-FINAL-PASS: normalizeDistrictDisplayName', () => {
  it('extracts the real district name out of the real, documented messy raw format', () => {
    // Exact real example from `host_operational_adapter.py::district_matches`'s
    // own docstring -- verified against the live host database, never a
    // guessed format.
    expect(normalizeDistrictDisplayName('8.4162, 80.0261 (Anuradhapura District)')).toBe('Anuradhapura')
  })

  it('extracts real Matara from the same messy shape', () => {
    expect(normalizeDistrictDisplayName('5.9478, 80.5483 (Matara District)')).toBe('Matara')
  })

  it('passes through an already-clean district name unchanged', () => {
    expect(normalizeDistrictDisplayName('Matara')).toBe('Matara')
  })

  it('strips a clean-but-suffixed "District" and normalizes casing', () => {
    expect(normalizeDistrictDisplayName('Matara District')).toBe('Matara')
    expect(normalizeDistrictDisplayName('MATARA DISTRICT')).toBe('Matara')
    expect(normalizeDistrictDisplayName('matara district')).toBe('Matara')
  })

  it('handles a real multi-word district name correctly', () => {
    expect(normalizeDistrictDisplayName('6.9497, 80.7891 (Nuwara Eliya District)')).toBe('Nuwara Eliya')
  })

  it('never fabricates a district from missing/empty input', () => {
    expect(normalizeDistrictDisplayName(null)).toBeNull()
    expect(normalizeDistrictDisplayName(undefined)).toBeNull()
    expect(normalizeDistrictDisplayName('')).toBeNull()
    expect(normalizeDistrictDisplayName('   ')).toBeNull()
  })

  it('REGRESSION: the messy raw format, once normalized, resolves the real district feature (previously silently never matched)', () => {
    const cleaned = normalizeDistrictDisplayName('5.9478, 80.5483 (Matara District)')
    const feature = findDistrictFeature(realDistricts, cleaned)
    expect(feature).not.toBeNull()
    expect(feature.properties.shapeName).toBe('Matara District')
  })

  it('REGRESSION: the raw messy format fed directly (unnormalized) never matches -- proves the bug this normalizer fixes was real', () => {
    const feature = findDistrictFeature(realDistricts, '5.9478, 80.5483 (Matara District)')
    expect(feature).toBeNull()
  })
})

describe('GEO30B Section 19: computeFeatureBounds', () => {
  it('derives real bounds directly from the real Matara polygon coordinates -- never a hardcoded box', () => {
    const feature = findDistrictFeature(realDistricts, 'Matara')
    const bounds = computeFeatureBounds(feature)
    expect(bounds).not.toBeNull()
    const [[minLng, minLat], [maxLng, maxLat]] = bounds
    // Sanity envelope only (Matara district sits within this range) --
    // the exact values come from the real dataset, not from this test.
    expect(minLng).toBeGreaterThan(80)
    expect(maxLng).toBeLessThan(81)
    expect(minLat).toBeGreaterThan(5.5)
    expect(maxLat).toBeLessThan(6.5)
    expect(minLng).toBeLessThan(maxLng)
    expect(minLat).toBeLessThan(maxLat)
  })

  it('handles a real MultiPolygon feature the same way as a Polygon', () => {
    const feature = {
      type: 'Feature',
      properties: { shapeName: 'Test MultiPolygon' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[80, 6], [80.5, 6], [80.5, 6.5], [80, 6.5], [80, 6]]],
          [[[81, 7], [81.2, 7], [81.2, 7.2], [81, 7.2], [81, 7]]],
        ],
      },
    }
    expect(computeFeatureBounds(feature)).toEqual([
      [80, 6],
      [81.2, 7.2],
    ])
  })

  it('returns null for a missing/empty geometry, never a fabricated box', () => {
    expect(computeFeatureBounds(null)).toBeNull()
    expect(computeFeatureBounds({})).toBeNull()
    expect(computeFeatureBounds({ geometry: { type: 'Polygon', coordinates: [] } })).toBeNull()
    expect(computeFeatureBounds({ geometry: { type: 'Point', coordinates: [80, 6] } })).toBeNull()
  })
})

describe('URGENT-MATARA-REAL-FILTER: isPointInsideDistrictFeature against the real Matara Polygon', () => {
  const matara = findDistrictFeature(realDistricts, 'Matara')

  it('the real Matara feature resolves as a Polygon or MultiPolygon (sanity check for the tests below)', () => {
    expect(['Polygon', 'MultiPolygon']).toContain(matara.geometry.type)
  })

  it('a real point inside Matara town is reported inside', () => {
    expect(isPointInsideDistrictFeature([80.554, 5.9549], matara)).toBe(true)
  })

  it('a real point far outside Matara (Colombo) is reported outside', () => {
    expect(isPointInsideDistrictFeature([79.8612, 6.9271], matara)).toBe(false)
  })

  it('returns false for missing/malformed input, never guesses containment', () => {
    expect(isPointInsideDistrictFeature(null, matara)).toBe(false)
    expect(isPointInsideDistrictFeature([80.5], matara)).toBe(false)
    expect(isPointInsideDistrictFeature([80.5, 6], null)).toBe(false)
    expect(isPointInsideDistrictFeature([80.5, 6], { geometry: null })).toBe(false)
  })

  it('supports MultiPolygon: a point inside either real ring is inside, a point inside neither is outside', () => {
    const feature = {
      type: 'Feature',
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[80, 6], [80.5, 6], [80.5, 6.5], [80, 6.5], [80, 6]]],
          [[[81, 7], [81.2, 7], [81.2, 7.2], [81, 7.2], [81, 7]]],
        ],
      },
    }
    expect(isPointInsideDistrictFeature([80.2, 6.2], feature)).toBe(true)
    expect(isPointInsideDistrictFeature([81.1, 7.1], feature)).toBe(true)
    expect(isPointInsideDistrictFeature([82, 8], feature)).toBe(false)
  })

  it('supports a plain single-ring Polygon', () => {
    const feature = {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [[[80, 6], [80.5, 6], [80.5, 6.5], [80, 6.5], [80, 6]]] },
    }
    expect(isPointInsideDistrictFeature([80.2, 6.2], feature)).toBe(true)
    expect(isPointInsideDistrictFeature([82, 8], feature)).toBe(false)
  })
})

describe('URGENT-MATARA-REAL-FILTER: filterOriginsInsideDistrict', () => {
  const matara = findDistrictFeature(realDistricts, 'Matara')

  function origin(id, coordinates) {
    return {
      outbreakId: id,
      country: 'Sri Lanka',
      t0: '2020-09-28',
      sourceCount: 1,
      sourcesFeatureCollection: coordinates
        ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates } }] }
        : { type: 'FeatureCollection', features: [] },
    }
  }

  it('keeps only origins with a real source point inside the district, in original order', () => {
    const insideMatara = origin('ORIGIN:Sri Lanka:2020-09-28', [80.554, 5.9549])
    const outsideMatara = origin('ORIGIN:Sri Lanka:2020-09-07', [79.8612, 6.9271])
    const result = filterOriginsInsideDistrict([insideMatara, outsideMatara], matara)
    expect(result).toEqual([insideMatara])
  })

  it('excludes an origin with no source geometry at all', () => {
    const noGeometry = origin('ORIGIN:Sri Lanka:2020-09-09', null)
    expect(filterOriginsInsideDistrict([noGeometry], matara)).toEqual([])
  })

  it('returns an empty list (never "all origins") when the district feature has not resolved yet', () => {
    const insideMatara = origin('ORIGIN:Sri Lanka:2020-09-28', [80.554, 5.9549])
    expect(filterOriginsInsideDistrict([insideMatara], null)).toEqual([])
  })

  it('returns an empty list for a non-array input, never throws', () => {
    expect(filterOriginsInsideDistrict(null, matara)).toEqual([])
    expect(filterOriginsInsideDistrict(undefined, matara)).toEqual([])
  })
})
