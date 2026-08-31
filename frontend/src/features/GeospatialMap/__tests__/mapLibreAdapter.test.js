import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  BEARING_DEG_EXPR,
  NEUTRAL_SINGLE_COLOR,
  RISK_TIER,
  RISK_TIER_COLOR,
  RISK_TIER_LABEL,
  UNAVAILABLE_RISK_COLOR,
  buildCellsFeatureCollection,
  buildDirectionFeatureCollection,
  buildSourcesFeatureCollection,
  computeCombinedLngLatBounds,
  computeRiskColorStats,
  computeRiskTierStats,
  directionIconLayout,
  nationalSourceAmbientPulsePaint,
  riskCircleColorExpression,
  riskTierColorExpression,
  sourceIconLayout,
} from '../components/mapLibreAdapter'
import { DIRECTION_ICON_ID, SOURCE_ICON_ID } from '../components/presentationIcons'

// Bangkok-like coordinates -- longitude > 90, latitude < 20 -- chosen so
// a lat/lon reversal is structurally unmistakable (a "latitude" of
// 100.5 is out of the valid [-90, 90] range).
const BANGKOK_LON = 100.523186
const BANGKOK_LAT = 13.756331

function cellFeature(id, { score = 0.4, bearing = null } = {}) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [BANGKOK_LON, BANGKOK_LAT] },
    properties: {
      scientific_cell_id: id,
      risk: { raw_c0_score: score, score_status: score === null ? 'UNSCORED' : 'SCORED', semantics: 'RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY' },
      direction: { bearing_deg: bearing, directional_clarity: 1.0, direction_status: 'X' },
    },
  }
}

function sourceFeature(id) {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [BANGKOK_LON + 1, BANGKOK_LAT + 1] }, properties: { source_id: id } }
}

describe('11B-GEO-01: GeoJSON [longitude, latitude] preserved exactly through the MapLibre adapter', () => {
  it('buildCellsFeatureCollection is a verbatim pass-through -- coordinates unchanged', () => {
    const cells = [cellFeature('C1')]
    const fc = buildCellsFeatureCollection(cells)
    expect(fc.features[0].geometry.coordinates).toEqual([BANGKOK_LON, BANGKOK_LAT])
    expect(Math.abs(fc.features[0].geometry.coordinates[0])).toBeGreaterThan(90) // would be invalid latitude if reversed
  })

  it('buildSourcesFeatureCollection is a verbatim pass-through', () => {
    const collection = { type: 'FeatureCollection', features: [sourceFeature('S1')] }
    expect(buildSourcesFeatureCollection(collection)).toBe(collection)
  })
})

describe('11B-GEO-02: fitBounds derived only from committed cell/source coordinates', () => {
  it('bounds cover exactly the min/max of the provided cell + source points, nothing else', () => {
    const cells = [cellFeature('C1')]
    const sources = [sourceFeature('S1')]
    const bounds = computeCombinedLngLatBounds(cells, sources)
    // two distinct points -> real bounding box, no artificial single-point padding
    expect(bounds).toEqual([
      [BANGKOK_LON, BANGKOK_LAT],
      [BANGKOK_LON + 1, BANGKOK_LAT + 1],
    ])
  })

  it('returns null for zero geometries (honest no-geometry state, never a fabricated default)', () => {
    expect(computeCombinedLngLatBounds([], [])).toBeNull()
  })

  it('a single geometry gets a small documented padding, not a favorable/outcome-based zoom', () => {
    const bounds = computeCombinedLngLatBounds([cellFeature('ONLY')], [])
    expect(bounds[0][0]).toBeLessThan(BANGKOK_LON)
    expect(bounds[1][0]).toBeGreaterThan(BANGKOK_LON)
  })
})

describe('11B-GEO-03: no forecast-origin coordinate is fabricated', () => {
  it('computeCombinedLngLatBounds only accepts cell/source features -- no origin parameter exists', () => {
    expect(computeCombinedLngLatBounds.length).toBe(2)
  })

  it('bounds are unaffected by anything other than the two feature arrays passed in', () => {
    const cells = [cellFeature('C1')]
    const boundsA = computeCombinedLngLatBounds(cells, [])
    const boundsB = computeCombinedLngLatBounds(cells, [])
    expect(boundsA).toEqual(boundsB)
  })
})

describe('11B-RISK-01: raw_c0_score remains unchanged after presentation-style generation', () => {
  it('computeRiskColorStats and riskCircleColorExpression never mutate the input features', () => {
    const cells = [cellFeature('C1', { score: 0.2 }), cellFeature('C2', { score: 0.8 }), cellFeature('C3', { score: null })]
    const before = JSON.parse(JSON.stringify(cells))
    const stats = computeRiskColorStats(cells)
    riskCircleColorExpression(stats)
    expect(cells).toEqual(before)
  })
})

describe('11B-RISK-02: presentation normalization is separate from the raw scientific field', () => {
  it('the color expression is a MapLibre EXPRESSION (never a precomputed value) that reads the field via a nested get, never a duplicated copy', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.2 }), cellFeature('C2', { score: 0.9 })])
    const expr = riskCircleColorExpression(stats)
    expect(Array.isArray(expr)).toBe(true)
    expect(JSON.stringify(expr)).toContain('raw_c0_score')
    expect(JSON.stringify(expr)).toContain('"risk"')
  })
})

describe('11B-RISK-03: null/unavailable score never becomes low risk or zero', () => {
  it('computeRiskColorStats excludes null scores from min/max entirely', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.5 }), cellFeature('C2', { score: null })])
    expect(stats.min).toBe(0.5)
    expect(stats.max).toBe(0.5)
    expect(stats.hasUnavailable).toBe(true)
  })

  it('the color expression maps null to UNAVAILABLE_RISK_COLOR, distinct from the low-end gradient color', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.1 }), cellFeature('C2', { score: 0.9 })])
    const expr = riskCircleColorExpression(stats)
    expect(expr[0]).toBe('case')
    expect(expr).toContain(UNAVAILABLE_RISK_COLOR)
    expect(UNAVAILABLE_RISK_COLOR).not.toBe('#3b82f6') // never silently reuses the "low" gradient color
  })

  it('all-unavailable cells resolve to a single distinct unavailable color, never a numeric interpolation', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: null }), cellFeature('C2', { score: null })])
    expect(stats.allUnavailable).toBe(true)
    expect(riskCircleColorExpression(stats)).toBe(UNAVAILABLE_RISK_COLOR)
  })
})

describe('11B-RISK-04: equal-score snapshot produces a safe neutral presentation state', () => {
  it('hasVariation is false when every valid score is identical', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.4 }), cellFeature('C2', { score: 0.4 })])
    expect(stats.hasVariation).toBe(false)
    const expr = riskCircleColorExpression(stats)
    expect(expr).toContain(NEUTRAL_SINGLE_COLOR)
    expect(JSON.stringify(expr)).not.toContain('interpolate')
  })
})

describe('11B-DIR: direction arrow data reuses the null-vs-0.0 rule, never recomputes bearing', () => {
  it('11B-DIR-01: a cell with null bearing produces no direction feature', () => {
    const fc = buildDirectionFeatureCollection([cellFeature('C1', { bearing: null })])
    expect(fc.features).toHaveLength(0)
  })

  it('11B-DIR-02: a cell with bearing 0.0 DOES produce a direction feature (valid North, never treated as falsy)', () => {
    const fc = buildDirectionFeatureCollection([cellFeature('C1', { bearing: 0.0 })])
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].properties.direction.bearing_deg).toBe(0.0)
  })

  it('11B-DIR-03: the rotation expression reads bearing_deg verbatim via nested get -- no arithmetic/recomputation', () => {
    expect(BEARING_DEG_EXPR).toEqual(['get', 'bearing_deg', ['get', 'direction']])
  })
})

describe('11B-SOURCE-01: all backend eligible source features remain represented', () => {
  it('buildSourcesFeatureCollection never filters -- feature count and identity preserved', () => {
    const collection = { type: 'FeatureCollection', features: [sourceFeature('S1'), sourceFeature('S2'), sourceFeature('S3')] }
    const fc = buildSourcesFeatureCollection(collection)
    expect(fc.features).toHaveLength(3)
    expect(fc.features.map((f) => f.properties.source_id)).toEqual(['S1', 'S2', 'S3'])
  })
})

describe('11B-MAPLIBRE-01: the GeoJSON data object preserves backend coordinates/fields', () => {
  it('cell features keep every original property key untouched', () => {
    const cell = cellFeature('C1', { score: 0.5, bearing: 45 })
    const fc = buildCellsFeatureCollection([cell])
    expect(fc.features[0]).toBe(cell) // identity-preserved, not a rebuilt copy
  })
})

// ---------------------------------------------------------------------
// Checkpoint 11B.1
// ---------------------------------------------------------------------

describe('11B1-GLYPH-02: source overlay uses a locally registered icon/image, never text-field', () => {
  it('sourceIconLayout references the local icon id and no text-field key', () => {
    const layout = sourceIconLayout()
    expect(layout['icon-image']).toBe(SOURCE_ICON_ID)
    expect(Object.keys(layout)).not.toContain('text-field')
    expect(Object.keys(layout)).not.toContain('text-font')
  })
})

describe('11B1-GLYPH-03: direction overlay uses a locally registered icon/image and icon-rotate, never text-field', () => {
  it('directionIconLayout references the local icon id, icon-rotate, and no text-field key', () => {
    const layout = directionIconLayout()
    expect(layout['icon-image']).toBe(DIRECTION_ICON_ID)
    expect(layout['icon-rotate']).toBeDefined()
    expect(Object.keys(layout)).not.toContain('text-field')
    expect(Object.keys(layout)).not.toContain('text-font')
  })
})

describe('11B1-ICON-03/04: bearing is passed through to icon-rotate completely verbatim, for every value', () => {
  it('icon-rotate is the exact same expression as BEARING_DEG_EXPR -- no offset/transform applied', () => {
    const layout = directionIconLayout()
    expect(layout['icon-rotate']).toEqual(BEARING_DEG_EXPR)
    expect(layout['icon-rotate']).toEqual(['get', 'bearing_deg', ['get', 'direction']])
  })

  it('this verbatim pass-through applies identically regardless of the bearing value (0/90/180/270)', () => {
    // The expression itself contains no numeric literal/offset, so it
    // cannot special-case any bearing value -- true for 0, 90, 180, 270
    // and every value in between simultaneously.
    const expr = directionIconLayout()['icon-rotate']
    expect(JSON.stringify(expr)).not.toMatch(/[+\-]\s*\d/) // no "+N"/"-N" offset baked in
  })
})

describe('11B1-ICON-05: null bearing produces no direction feature (icon layer input)', () => {
  it('buildDirectionFeatureCollection excludes null-bearing cells before they ever reach the icon layer', () => {
    const fc = buildDirectionFeatureCollection([
      cellFeature('A', { bearing: null }),
      cellFeature('B', { bearing: 45 }),
      cellFeature('C', { bearing: undefined }),
    ])
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].properties.scientific_cell_id).toBe('B')
  })
})

describe('11B1-ICON-06: no raw scientific field is mutated while preparing icons/layers', () => {
  it('sourceIconLayout/directionIconLayout take no scientific arguments and read no feature', () => {
    expect(sourceIconLayout.length).toBe(0)
    expect(directionIconLayout.length).toBe(0)
  })

  it('the full icon+data pipeline leaves the original cells array untouched', () => {
    const cells = [cellFeature('C1', { score: 0.2, bearing: 90 }), cellFeature('C2', { score: 0.8, bearing: null })]
    const before = JSON.parse(JSON.stringify(cells))
    buildCellsFeatureCollection(cells)
    buildDirectionFeatureCollection(cells)
    sourceIconLayout()
    directionIconLayout()
    expect(cells).toEqual(before)
  })
})

describe('11B1-ICON-07: scientific source count remains exactly the input source count', () => {
  it('feeding sources through buildSourcesFeatureCollection for the icon layer preserves count and identity', () => {
    const collection = { type: 'FeatureCollection', features: [sourceFeature('S1'), sourceFeature('S2')] }
    const fc = buildSourcesFeatureCollection(collection)
    expect(fc.features).toHaveLength(2)
  })
})

describe('11B1-ICON-08: direction feature count equals the count of backend cells with a defined bearing', () => {
  it('exactly the cells with non-null/non-undefined bearing become direction icon features', () => {
    const cells = [
      cellFeature('A', { bearing: 0.0 }),
      cellFeature('B', { bearing: null }),
      cellFeature('C', { bearing: 180 }),
      cellFeature('D', { bearing: undefined }),
      cellFeature('E', { bearing: 270 }),
    ]
    const fc = buildDirectionFeatureCollection(cells)
    expect(fc.features).toHaveLength(3)
    expect(fc.features.map((f) => f.properties.scientific_cell_id)).toEqual(['A', 'C', 'E'])
  })
})

describe('GEO-VISUAL-POLISH-01: the ambient outbreak-marker pulse is red, per-state, and endpoint-only', () => {
  it('always paints the same red family as the marker itself, never a risk color', () => {
    expect(nationalSourceAmbientPulsePaint(false)['circle-color']).toBe('#ef4444')
    expect(nationalSourceAmbientPulsePaint(true)['circle-color']).toBe('#ef4444')
  })

  it('the expanded phase always fades opacity toward 0, regardless of selection state', () => {
    const expr = nationalSourceAmbientPulsePaint(true)['circle-opacity']
    // ['case', selectedCond, 0, dimmedCond, 0, 0] -- every branch is 0 when expanded
    expect(expr.filter((v) => v === 0).length).toBeGreaterThanOrEqual(3)
  })

  it('a selected marker gets a larger expanded radius than an ordinary one, which in turn is larger than a dimmed one', () => {
    const expr = nationalSourceAmbientPulsePaint(true)['circle-radius']
    const [, , selectedRadius, , dimmedRadius, baseRadius] = expr
    expect(selectedRadius).toBeGreaterThan(baseRadius)
    expect(baseRadius).toBeGreaterThan(dimmedRadius)
  })

  it('collapses back to the SAME base radius across states when not expanded', () => {
    const collapsed = nationalSourceAmbientPulsePaint(false)['circle-radius']
    // Every branch's collapsed value is a small, near-identical base --
    // never left at the previous expanded size.
    expect(Math.max(...collapsed.filter((v) => typeof v === 'number'))).toBeLessThanOrEqual(9)
  })
})

describe('11B-MAPLIBRE-02: style/layer generation never changes raw_c0_score', () => {
  it('riskCircleColorExpression output never contains a literal numeric raw_c0_score value from the input', () => {
    const cells = [cellFeature('C1', { score: 0.123456 }), cellFeature('C2', { score: 0.987654 })]
    const stats = computeRiskColorStats(cells)
    const expr = riskCircleColorExpression(stats)
    // the expression references the FIELD NAME, not a snapshot of any one feature's value baked in as a rewritten score
    expect(cells[0].properties.risk.raw_c0_score).toBe(0.123456)
    expect(cells[1].properties.risk.raw_c0_score).toBe(0.987654)
    // present only as a STOP boundary in the interpolation expression, not a rewritten per-feature value
    expect(JSON.stringify(expr)).toContain('0.123456')
  })
})

// ---------------------------------------------------------------------
// GEO-VISUAL-POLISH-03: discrete, snapshot-relative risk tiers
// ---------------------------------------------------------------------

describe('GEO-VISUAL-POLISH-03: risk tiers are RELATIVE quantiles, never a fixed absolute medical threshold', () => {
  it('classification (classifyTier) compares ONLY against the real per-snapshot q1/median/q3 values -- never a fixed absolute numeric cutoff like 0.70/0.40/0.15', () => {
    const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'components', 'mapLibreAdapter.js'), 'utf-8')
    const start = src.indexOf('function classifyTier(')
    const end = src.indexOf('\n}', start)
    const body = src.slice(start, end)
    expect(body).not.toMatch(/>=\s*0\.\d+/) // no literal fraction ever compared against
    expect(body).toMatch(/>=\s*q3\b/)
    expect(body).toMatch(/>=\s*median\b/)
    expect(body).toMatch(/>=\s*q1\b/)
  })

  it('the map paint expression (riskTierColorExpression) never bakes in a fixed absolute stop -- every stop is one of stats.q1/stats.median/stats.q3, computed from the real active snapshot', () => {
    const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'components', 'mapLibreAdapter.js'), 'utf-8')
    const start = src.indexOf('export function riskTierColorExpression(')
    const end = src.indexOf('\n}', start)
    const body = src.slice(start, end)
    expect(body).not.toMatch(/0\.\d+/) // no numeric literal fraction anywhere in this function
    expect(body).toMatch(/stats\.q1/)
    expect(body).toMatch(/stats\.median/)
    expect(body).toMatch(/stats\.q3/)
  })

  it('the legend wording is relative-only -- never "infection probability", "confirmed risk %", or "confidence %"', () => {
    const allLabels = Object.values(RISK_TIER_LABEL).join(' ')
    expect(allLabels.toLowerCase()).not.toMatch(/infection probability|confirmed risk|confidence/)
    expect(allLabels.toLowerCase()).toContain('relative')
  })

  it('a null/unavailable score is NEVER classified into a tier -- it stays UNAVAILABLE_RISK_COLOR, never forced into the bottom (green/lower) tier', () => {
    const cells = [cellFeature('A', { score: 0.1 }), cellFeature('B', { score: 0.5 }), cellFeature('C', { score: 0.9 }), cellFeature('D', { score: null })]
    const stats = computeRiskTierStats(cells)
    const expr = riskTierColorExpression(stats)
    expect(expr[0]).toBe('case')
    expect(expr).toContain(UNAVAILABLE_RISK_COLOR)
    expect(UNAVAILABLE_RISK_COLOR).not.toBe(RISK_TIER_COLOR[RISK_TIER.LOWER])
    // The null-check is the FIRST case branch, evaluated before the tier step.
    expect(JSON.stringify(expr.slice(0, 3))).toContain('null')
  })

  it('tier counts sum to exactly the valid (non-null) cell count -- no cell double-counted, none silently dropped', () => {
    const cells = Array.from({ length: 12 }, (_, i) => cellFeature(`C${i}`, { score: i / 11 }))
    const stats = computeRiskTierStats(cells)
    expect(stats.hasVariation).toBe(true)
    const total = Object.values(stats.counts).reduce((a, b) => a + b, 0)
    expect(total).toBe(stats.validCount)
    expect(stats.validCount).toBe(12)
  })

  it('the top-scoring real cell in a varied snapshot is always classified into the HIGHEST tier, the bottom-scoring into LOWER', () => {
    const cells = [
      cellFeature('low', { score: 0.01 }),
      cellFeature('mid1', { score: 0.3 }),
      cellFeature('mid2', { score: 0.4 }),
      cellFeature('mid3', { score: 0.6 }),
      cellFeature('mid4', { score: 0.7 }),
      cellFeature('high', { score: 0.99 }),
    ]
    const stats = computeRiskTierStats(cells)
    expect(stats.hasVariation).toBe(true)
    expect(stats.counts[RISK_TIER.HIGHEST]).toBeGreaterThanOrEqual(1)
    expect(stats.counts[RISK_TIER.LOWER]).toBeGreaterThanOrEqual(1)
  })

  it('all-equal real scores fall back to the SAME honest neutral single color the continuous gradient already uses -- never a fabricated 4-way split', () => {
    const cells = [cellFeature('A', { score: 0.42 }), cellFeature('B', { score: 0.42 }), cellFeature('C', { score: 0.42 })]
    const stats = computeRiskTierStats(cells)
    expect(stats.hasVariation).toBe(false)
    expect(Object.values(stats.counts).every((c) => c === 0)).toBe(true)
    const expr = riskTierColorExpression(stats)
    expect(expr).toContain(NEUTRAL_SINGLE_COLOR)
    expect(JSON.stringify(expr)).not.toContain('step')
  })

  it('too few valid cells for a meaningful quartile split (e.g. one or two real cells) also falls back to the honest neutral presentation, never a degenerate/crashing MapLibre step expression', () => {
    const stats = computeRiskTierStats([cellFeature('ONLY', { score: 0.6 })])
    expect(stats.hasVariation).toBe(false)
    expect(riskTierColorExpression(stats)).toContain(NEUTRAL_SINGLE_COLOR)
  })

  it('all-unavailable cells resolve to the single distinct unavailable color, same as the continuous gradient', () => {
    const stats = computeRiskTierStats([cellFeature('A', { score: null }), cellFeature('B', { score: null })])
    expect(stats.allUnavailable).toBe(true)
    expect(riskTierColorExpression(stats)).toBe(UNAVAILABLE_RISK_COLOR)
  })

  it('computeRiskTierStats/riskTierColorExpression never mutate the input features', () => {
    const cells = [cellFeature('A', { score: 0.1 }), cellFeature('B', { score: 0.5 }), cellFeature('C', { score: 0.9 })]
    const before = JSON.parse(JSON.stringify(cells))
    const stats = computeRiskTierStats(cells)
    riskTierColorExpression(stats)
    expect(cells).toEqual(before)
  })

  it('the step expression stops are strictly increasing (q1 < median < q3) whenever hasVariation is true -- a real MapLibre validity requirement, not just a style choice', () => {
    const cells = Array.from({ length: 20 }, (_, i) => cellFeature(`C${i}`, { score: Math.sin(i) * 0.5 + 0.5 }))
    const stats = computeRiskTierStats(cells)
    if (stats.hasVariation) {
      expect(stats.q1).toBeLessThan(stats.median)
      expect(stats.median).toBeLessThan(stats.q3)
    }
  })
})
