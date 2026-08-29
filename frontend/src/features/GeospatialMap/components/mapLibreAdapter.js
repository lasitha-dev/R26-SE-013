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
const LOW_COLOR_HEX = '#3b82f6' // blue (low raw_c0_score)
const HIGH_COLOR_HEX = '#dc2626' // red (high raw_c0_score)

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
