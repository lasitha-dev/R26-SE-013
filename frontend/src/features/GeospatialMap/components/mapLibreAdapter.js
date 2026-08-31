/**
 * Checkpoint 11B: pure, framework-independent MapLibre GeoJSON-source
 * and paint-expression builders. Extracted so they are unit-testable
 * without a real WebGL/browser context -- this repo's Vitest
 * environment is Node with no DOM at all, matching every other module
 * in this feature (`mapProjection.js`, `directionGeometry.js`,
 * `snapshotAssembly.js`).
 *
 * `MapLibreCanvas.jsx` calls these EXACT functions; nothing here
 * duplicates a scientific formula -- every function only derives
 * display geometry/color from values the backend already computed.
 * `raw_c0_score` (and every other backend field) is never read into a
 * JS variable and written back to the feature -- functions either pass
 * features through verbatim or return a MapLibre GL EXPRESSION (an
 * array MapLibre evaluates per-feature at render time), never a
 * precomputed per-feature value.
 */
import { shouldDrawArrow } from './directionGeometry.js'
import { DIRECTION_ICON_ID, SOURCE_ICON_ID } from './presentationIcons.js'

export const UNAVAILABLE_RISK_COLOR = '#9ca3af' // neutral gray -- never implies low risk
export const NEUTRAL_SINGLE_COLOR = '#60a5fa' // used when no within-snapshot gradient exists
// GEO-STITCH-PAGE1-14: exported (previously module-private) so
// `PageLegend.jsx`'s Risk Zones gradient swatch can read the SAME two real
// hex values this file's own `riskCircleColorExpression` paints the map
// with -- never a second, hand-copied approximation that could drift.
export const LOW_COLOR_HEX = '#3b82f6' // blue (low raw_c0_score)
export const HIGH_COLOR_HEX = '#dc2626' // red (high raw_c0_score)

/** MapLibre expression reading `feature.properties.risk.raw_c0_score`
 * verbatim -- a nested `get`, never a flattened/duplicated copy of the
 * scientific payload. */
const RAW_C0_SCORE_EXPR = ['get', 'raw_c0_score', ['get', 'risk']]
/** MapLibre expression reading `feature.properties.direction.bearing_deg`
 * verbatim. */
export const BEARING_DEG_EXPR = ['get', 'bearing_deg', ['get', 'direction']]

/** Wraps committed cell features as a FeatureCollection -- a pure
 * pass-through, never mutates or rewrites any property. */
export function buildCellsFeatureCollection(cells) {
  return { type: 'FeatureCollection', features: cells }
}

/** Passes the committed sources FeatureCollection through unchanged. */
export function buildSourcesFeatureCollection(sourceCollection) {
  return sourceCollection
}

/** Checkpoint 11B Part 10: only cells with a DEFINED bearing become
 * direction-arrow features (null/undefined -> no arrow, reusing the
 * same `shouldDrawArrow` null-vs-0.0 rule the SVG fallback uses --
 * never a second, divergent implementation of this check). */
export function buildDirectionFeatureCollection(cells) {
  return {
    type: 'FeatureCollection',
    features: cells.filter((c) => shouldDrawArrow(c.properties?.direction?.bearing_deg)),
  }
}

/**
 * Checkpoint 11B Part 8: presentation-only min/max over `raw_c0_score`,
 * EXCLUDING null/undefined scores from the range -- a missing score is
 * never treated as 0 or "low". Returns enough information for both the
 * paint expression and the on-map legend text.
 */
export function computeRiskColorStats(cells) {
  const scores = []
  let hasUnavailable = false
  for (const c of cells) {
    const s = c.properties?.risk?.raw_c0_score
    if (s === null || s === undefined) {
      hasUnavailable = true
    } else {
      scores.push(s)
    }
  }
  if (scores.length === 0) {
    return { min: null, max: null, hasVariation: false, hasUnavailable, allUnavailable: cells.length > 0 }
  }
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  return { min, max, hasVariation: max > min, hasUnavailable, allUnavailable: false }
}

/**
 * MapLibre GL data-driven paint-property EXPRESSION (evaluated by
 * MapLibre per-feature at render time) -- this function itself never
 * reads or writes a single feature's `raw_c0_score`. A null/undefined
 * score always resolves to `UNAVAILABLE_RISK_COLOR`, never interpolated
 * into the gradient as a low value (Part 8).
 */
export function riskCircleColorExpression(stats) {
  const unavailableCase = ['case', ['==', RAW_C0_SCORE_EXPR, null], UNAVAILABLE_RISK_COLOR]
  if (stats.allUnavailable) {
    return UNAVAILABLE_RISK_COLOR
  }
  if (!stats.hasVariation) {
    // Part 8: all valid scores equal -- one neutral color, no gradient implied.
    return [...unavailableCase, NEUTRAL_SINGLE_COLOR]
  }
  return [
    ...unavailableCase,
    ['interpolate', ['linear'], RAW_C0_SCORE_EXPR, stats.min, LOW_COLOR_HEX, stats.max, HIGH_COLOR_HEX],
  ]
}

// GEO-VISUAL-POLISH-03: discrete, SNAPSHOT-RELATIVE risk tiers -- the
// visually distinct red/orange/yellow/green the design reference calls
// for, WITHOUT claiming a fixed absolute threshold the backend does not
// define. `raw_c0_score` is documented (`risk.semantics` on every real
// cell, and this file's own `computeRiskColorStats` above) as a
// within-snapshot-normalized RELATIVE spatial ranking, not an infection
// probability -- a fixed cutoff like ">= 0.70 = red" would be a fabricated
// medical claim this codebase's existing risk-honesty tests explicitly
// forbid (`operationalScientificFirewall.test.js` and friends). Instead,
// each tier boundary is a REAL QUANTILE of the CURRENT snapshot's own
// valid-score distribution (top quartile / upper-middle / lower-middle /
// bottom quartile) -- "highest among today's real cells", never "high in
// any absolute sense". A null/unavailable score is NEVER classified into
// a tier (stays the same `UNAVAILABLE_RISK_COLOR` the continuous gradient
// already uses) -- it is never forced into "lower"/green just because
// green happens to be the bottom of the scale.
export const RISK_TIER = { HIGHEST: 'highest', HIGH: 'high', MODERATE: 'moderate', LOWER: 'lower' }
export const RISK_TIER_COLOR = {
  [RISK_TIER.HIGHEST]: '#EF4444',
  [RISK_TIER.HIGH]: '#F97316',
  [RISK_TIER.MODERATE]: '#FACC15',
  [RISK_TIER.LOWER]: '#22C55E',
}
// Legend/UI wording -- deliberately RELATIVE, never an absolute medical
// claim ("infection probability", "confirmed risk %", "confidence %").
export const RISK_TIER_LABEL = {
  [RISK_TIER.HIGHEST]: 'Highest relative risk',
  [RISK_TIER.HIGH]: 'Elevated relative risk',
  [RISK_TIER.MODERATE]: 'Moderate relative risk',
  [RISK_TIER.LOWER]: 'Lower relative risk',
}
// Rendering order, lowest tier first -- matches the `step` expression's
// own ascending-threshold structure in `riskTierColorExpression` below.
export const RISK_TIER_ORDER = [RISK_TIER.LOWER, RISK_TIER.MODERATE, RISK_TIER.HIGH, RISK_TIER.HIGHEST]

/** Standard linear-interpolation quantile (matches NumPy's default
 * 'linear' method) over an ALREADY-SORTED-ASCENDING numeric array.
 * Pure/deterministic; never reads a feature. */
function quantileOfSorted(sortedValues, q) {
  if (sortedValues.length === 1) return sortedValues[0]
  const pos = (sortedValues.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  const upper = sortedValues[base + 1]
  return upper === undefined ? sortedValues[base] : sortedValues[base] + rest * (upper - sortedValues[base])
}

function classifyTier(score, q1, median, q3) {
  if (score >= q3) return RISK_TIER.HIGHEST
  if (score >= median) return RISK_TIER.HIGH
  if (score >= q1) return RISK_TIER.MODERATE
  return RISK_TIER.LOWER
}

/**
 * Presentation-only quartile stats over `raw_c0_score`, EXCLUDING null/
 * undefined (same exclusion rule as `computeRiskColorStats` -- a missing
 * score is never treated as 0/low). `hasVariation` is `true` only when
 * the three quartile breakpoints are STRICTLY increasing -- a real
 * safeguard, not just a cosmetic one: MapLibre's `step` expression
 * requires strictly-ascending stops, so a degenerate distribution (too
 * few distinct real values -- e.g. every valid score identical, or so
 * few valid cells that quartiles collapse onto each other) must fall back
 * to the existing honest single-neutral-color presentation rather than
 * ever risk handing MapLibre a non-increasing `step` expression.
 * `counts` are REAL per-tier cell counts for the legend (never a
 * percentage, never fabricated) -- all zero when `hasVariation` is false,
 * since no cell is classified into a tier that was never actually drawn.
 */
export function computeRiskTierStats(cells) {
  const scores = []
  let hasUnavailable = false
  for (const c of cells) {
    const s = c.properties?.risk?.raw_c0_score
    if (s === null || s === undefined) {
      hasUnavailable = true
    } else {
      scores.push(s)
    }
  }
  if (scores.length === 0) {
    return {
      q1: null,
      median: null,
      q3: null,
      hasVariation: false,
      hasUnavailable,
      allUnavailable: cells.length > 0,
      validCount: 0,
      counts: { [RISK_TIER.HIGHEST]: 0, [RISK_TIER.HIGH]: 0, [RISK_TIER.MODERATE]: 0, [RISK_TIER.LOWER]: 0 },
    }
  }
  const sorted = [...scores].sort((a, b) => a - b)
  const q1 = quantileOfSorted(sorted, 0.25)
  const median = quantileOfSorted(sorted, 0.5)
  const q3 = quantileOfSorted(sorted, 0.75)
  const hasVariation = q1 < median && median < q3

  const counts = { [RISK_TIER.HIGHEST]: 0, [RISK_TIER.HIGH]: 0, [RISK_TIER.MODERATE]: 0, [RISK_TIER.LOWER]: 0 }
  if (hasVariation) {
    for (const s of scores) counts[classifyTier(s, q1, median, q3)] += 1
  }

  return { q1, median, q3, hasVariation, hasUnavailable, allUnavailable: false, validCount: scores.length, counts }
}

/**
 * MapLibre GL data-driven paint-property EXPRESSION for the discrete
 * relative-tier presentation -- same null-safety contract as
 * `riskCircleColorExpression` (null always resolves to
 * `UNAVAILABLE_RISK_COLOR`, checked first, never overridden by the tier
 * `step`). Falls back to `NEUTRAL_SINGLE_COLOR` -- the SAME honest
 * "no meaningful within-snapshot variation" presentation the continuous
 * gradient already uses -- whenever `stats.hasVariation` is false, never
 * a fabricated four-tier split over a distribution that cannot honestly
 * support one.
 */
export function riskTierColorExpression(stats) {
  const unavailableCase = ['case', ['==', RAW_C0_SCORE_EXPR, null], UNAVAILABLE_RISK_COLOR]
  if (stats.allUnavailable) {
    return UNAVAILABLE_RISK_COLOR
  }
  if (!stats.hasVariation) {
    return [...unavailableCase, NEUTRAL_SINGLE_COLOR]
  }
  return [
    ...unavailableCase,
    [
      'step',
      RAW_C0_SCORE_EXPR,
      RISK_TIER_COLOR[RISK_TIER.LOWER],
      stats.q1,
      RISK_TIER_COLOR[RISK_TIER.MODERATE],
      stats.median,
      RISK_TIER_COLOR[RISK_TIER.HIGH],
      stats.q3,
      RISK_TIER_COLOR[RISK_TIER.HIGHEST],
    ],
  ]
}

/**
 * Checkpoint 11B.1 Part 3/5: the eligible-source overlay's `layout`,
 * built entirely from a LOCALLY REGISTERED image (`map.addImage(...)`,
 * see `presentationIcons.js`) -- no font-glyph text-symbol layer, no
 * dependency of any kind on glyphs/sprites. Pure -- returns the same
 * object regardless of environment/network state.
 */
/** FMD-10C1: `iconId` is optional (defaults to the existing LSD diamond,
 * `SOURCE_ICON_ID`) so every pre-existing caller is unaffected -- pass
 * `FMD_SOURCE_ICON_ID` for the FMD-shaped circle marker layer instead. */
export function sourceIconLayout(iconId = SOURCE_ICON_ID) {
  return { 'icon-image': iconId, 'icon-allow-overlap': true, 'icon-ignore-placement': true, 'icon-size': 1 }
}

/**
 * Checkpoint 11B.1 Part 4/5: the direction overlay's `layout` -- a
 * locally registered north-facing icon rotated by `icon-rotate` using
 * the backend's `bearing_deg` VERBATIM (no arithmetic performed here).
 * No font-glyph text-symbol dependency of any kind.
 */
export function directionIconLayout() {
  return {
    'icon-image': DIRECTION_ICON_ID,
    'icon-rotate': BEARING_DEG_EXPR,
    'icon-rotation-alignment': 'map',
    'icon-allow-overlap': true,
    'icon-ignore-placement': true,
    'icon-size': 1,
  }
}

// GEO-VISUAL-POLISH-01: a continuous, gentle "this is a live outbreak
// marker" breathing ring for EVERY national source marker, not only the
// selected one -- distinct from the existing one-shot selection ripple
// (`national-sources-ripple`, fires once per selection change) and the
// steady selection halo (`national-sources-halo`). Same red family as the
// marker itself (`presentationIcons.js`'s `SOURCE_FILL`) -- never a
// second color, and never implies anything about risk. `expanded` is a
// plain boolean the caller (`MapLibreCanvas.jsx`) flips on a fixed RAF
// clock; MapLibre's own paint `-transition` (set once, alongside this
// paint object) performs the actual smooth interpolation between the two
// endpoint values this function returns -- this function itself never
// computes an in-between frame.
export const NATIONAL_SOURCES_PULSE_CYCLE_MS = 1800
const PULSE_BASE_RADIUS = 8
const PULSE_EXPANDED_RADIUS = 15
const PULSE_SELECTED_EXPANDED_RADIUS = 19
const PULSE_DIMMED_EXPANDED_RADIUS = 11
const PULSE_BASE_OPACITY = 0.4
const PULSE_SELECTED_BASE_OPACITY = 0.55
const PULSE_DIMMED_BASE_OPACITY = 0.12

/**
 * A currently-SELECTED marker pulses with a larger amplitude/opacity than
 * an ordinary one; a DIMMED marker (a different origin is selected) pulses
 * at a visibly reduced amplitude, matching its already-reduced icon
 * opacity -- never hidden entirely (Section 5: "unselected outbreaks:
 * still visible"). Radius always shrinks back to the SAME base value
 * regardless of state; only the expanded/faded endpoint differs.
 */
export function nationalSourceAmbientPulsePaint(expanded) {
  return {
    'circle-color': '#ef4444',
    'circle-radius': [
      'case',
      ['boolean', ['feature-state', 'selected'], false],
      expanded ? PULSE_SELECTED_EXPANDED_RADIUS : PULSE_BASE_RADIUS,
      ['boolean', ['feature-state', 'dimmed'], false],
      expanded ? PULSE_DIMMED_EXPANDED_RADIUS : PULSE_BASE_RADIUS,
      expanded ? PULSE_EXPANDED_RADIUS : PULSE_BASE_RADIUS,
    ],
    'circle-opacity': [
      'case',
      ['boolean', ['feature-state', 'selected'], false],
      expanded ? 0 : PULSE_SELECTED_BASE_OPACITY,
      ['boolean', ['feature-state', 'dimmed'], false],
      expanded ? 0 : PULSE_DIMMED_BASE_OPACITY,
      expanded ? 0 : PULSE_BASE_OPACITY,
    ],
  }
}

/**
 * LSD-UI-03: merges every real Sri Lanka LSD origin's `sources` response
 * into ONE FeatureCollection for the national browsing layer, tagging
 * each feature with `outbreakId` (its `forecast_origin_id`) so a click
 * handler can identify which origin was selected, and promoting each
 * feature's real `source_id` to the GeoJSON top-level `id` (via
 * `promoteId` when the source is added in `MapLibreCanvas.jsx`) so
 * MapLibre feature-state (selection halo/dim) can be set per feature.
 * Pure pass-through of real coordinates/properties -- adds no
 * scientific value, only the `outbreakId` tag needed for UI selection.
 */
export function buildNationalSourcesFeatureCollection(originsWithSources) {
  const features = []
  for (const origin of originsWithSources) {
    for (const feature of origin.sourcesFeatureCollection?.features ?? []) {
      features.push({
        ...feature,
        properties: { ...feature.properties, outbreakId: origin.outbreakId },
      })
    }
  }
  return { type: 'FeatureCollection', features }
}

/**
 * Checkpoint 11B Part 6: derives the camera fit bounds ONLY from the
 * committed cell + eligible-source coordinates -- never a favorable or
 * outcome-informed viewport, never a fabricated forecast-origin point.
 * Returns `null` for zero geometries (honest no-geometry state) and a
 * padded single-point box for exactly one geometry (a documented
 * conservative default, not a scientific value).
 */
export function computeCombinedLngLatBounds(cellFeatures, sourceFeatures) {
  const points = [...cellFeatures, ...sourceFeatures].map((f) => f.geometry.coordinates)
  if (points.length === 0) return null
  let minLon = Infinity
  let maxLon = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity
  for (const [lon, lat] of points) {
    if (lon < minLon) minLon = lon
    if (lon > maxLon) maxLon = lon
    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
  }
  if (points.length === 1) {
    // Single geometry: a fixed, documented presentation padding -- not
    // derived from any risk/outcome value.
    const PAD_DEG = 0.15
    return [
      [minLon - PAD_DEG, minLat - PAD_DEG],
      [maxLon + PAD_DEG, maxLat + PAD_DEG],
    ]
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ]
}
