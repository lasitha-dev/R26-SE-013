/**
 * GEO-INT-03 / GEO26B Section 8/9: pure GeoJSON FeatureCollection +
 * layout/paint builders for the Verified Clinical Context overlay --
 * same pattern as `mapLibreAdapter.js` (reuse, don't duplicate the map
 * lifecycle; extracted so it's unit-testable without WebGL/DOM, same as
 * every other builder module in this feature). `MapLibreCanvas.jsx`
 * calls these exact functions.
 *
 * GEO26B: one Feature per real FARM+disease aggregate
 * (`operationalFarmAggregation.js`'s output), never one per individual
 * case -- multiple verified cases at the same farm collapse into a
 * single marker carrying a real `caseCount`, never several overlapping
 * markers at an identical coordinate.
 *
 * Section 9: never uses the risk red/orange/amber/yellow/green family or
 * any pulsing/glow/reach-ring treatment -- a single restrained hollow
 * neutral-mint marker (`operationalIcons.js`), identical treatment for
 * every clinical context regardless of disease. Disease identity is
 * SHAPE only (diamond=LSD, circle=FMD, `disease/diseaseRegistry.js`'s
 * existing `markerShape` convention), never color. Visual weight (size)
 * varies only with the real `caseCount`; opacity varies only with the
 * real `recencyTier` -- never with disease or risk.
 */
import { CLINICAL_CIRCLE_ICON_ID, CLINICAL_DIAMOND_ICON_ID, CLINICAL_MARKER_COLOR_HEX } from './operationalIcons'

export const OPERATIONAL_MARKERS_SOURCE_ID = 'geo-operational-clinical-contexts'
export const OPERATIONAL_MARKERS_LAYER_ID = 'operational-clinical-symbol'
// GEO31A Section 2: the soft expanding halo/ring layer -- a SEPARATE
// `circle` layer under the icon symbol layer above, never baked into the
// icon raster itself, so the steady core (the icon) never has to animate
// to get a pulsing ring around it.
export const OPERATIONAL_MARKERS_HALO_LAYER_ID = 'operational-clinical-halo'
export const OPERATIONAL_MARKERS_PROMOTE_ID = 'farmDiseaseKey'

/**
 * One feature per real farm+disease aggregate. The caller
 * (`operationalFarmAggregation.js`) has already grouped/validated the
 * input -- this function never re-derives a coordinate or count, it only
 * wraps validated input into GeoJSON.
 *
 * `farmDiseaseKey` is promoted as the GeoJSON feature id (see
 * `MapLibreCanvas.jsx`'s `promoteId: OPERATIONAL_MARKERS_PROMOTE_ID`) so
 * MapLibre feature-state (the transient "just arrived" highlight, Section
 * 12) can target one specific farm marker across `setData` refreshes.
 */
export function buildOperationalMarkerFeatureCollection(farmGroups) {
  return {
    type: 'FeatureCollection',
    features: farmGroups.map((g) => ({
      type: 'Feature',
      properties: {
        farmDiseaseKey: `${g.farmId}::${g.disease}`,
        farmId: g.farmId,
        disease: g.disease,
        locationDistrict: g.locationDistrict,
        personallyAssigned: g.personallyAssigned,
        caseCount: g.caseCount,
        caseIds: g.caseIds,
        verificationTimes: g.verificationTimes,
        latestVerificationTime: g.latestVerificationTime,
        recencyTier: g.recencyTier,
      },
      geometry: { type: 'Point', coordinates: [g.longitude, g.latitude] },
    })),
  }
}

/**
 * Data-driven icon-image expression: diamond for LSD, circle for FMD --
 * shape only, matching `diseaseRegistry.js`'s `markerShape` convention.
 * No color varies by disease (Section 9). `icon-size` steps up with the
 * real `caseCount` (Section 9: visual hierarchy by real case volume, not
 * a fabricated density) -- this codebase's basemap has no glyph/sprite
 * URL (Checkpoint 11B.1), so a numeric count badge is not rendered as
 * text on the map itself; the exact count is shown in the popup instead
 * (`OperationalContextPopup.jsx`).
 */
export function operationalMarkerIconLayout() {
  return {
    'icon-image': ['case', ['==', ['get', 'disease'], 'LSD'], CLINICAL_DIAMOND_ICON_ID, CLINICAL_CIRCLE_ICON_ID],
    'icon-allow-overlap': true,
    'icon-ignore-placement': true,
    'icon-size': ['step', ['get', 'caseCount'], 0.85, 2, 1.0, 4, 1.2, 10, 1.45],
  }
}

/**
 * GEO26B Section 9: opacity-only visual hierarchy --
 *  - a farm marker mid transient "just arrived" highlight (MapLibre
 *    `feature-state`, set/cleared by `MapLibreCanvas.jsx`) is always
 *    full opacity, regardless of recency tier;
 *  - otherwise a farm whose most recent verified case is 'older' than
 *    the fixed recent-threshold renders slightly quieter than a 'recent'
 *    one.
 * Never touches color -- disease/risk color rules are untouched.
 */
export function operationalMarkerPaint(reduceMotion) {
  return {
    'icon-opacity': [
      'case',
      ['boolean', ['feature-state', 'justArrived'], false],
      1,
      ['==', ['get', 'recencyTier'], 'older'],
      0.55,
      1,
    ],
    'icon-opacity-transition': { duration: reduceMotion ? 0 : 300 },
  }
}

/**
 * GEO31A Section 2/3: the halo/ring `circle` layer's paint. Three
 * independent feature-states drive it (never color -- always the same
 * translucent red, `CLINICAL_MARKER_COLOR_HEX`):
 *  - `selected` (Section 2 "Selected outbreak: additional distinct
 *    halo"): a STEADY ring, set/cleared by `OutbreakMapPage.jsx` while
 *    that farm's popup is open -- independent of arrival.
 *  - `pulseActive` + `pulseExpanded` together (Section 2/3 "stronger
 *    outer pulse... ring expands and fades... repeat only for a short
 *    meaningful arrival sequence, then settle to steady"): while
 *    `pulseActive` is true (a SHORT ~2.4s window -- shorter than the
 *    longer-lived `justArrived` icon-opacity-boost state, which this
 *    layer never reads), `MapLibreCanvas.jsx`'s RAF loop repeatedly flips
 *    `pulseExpanded` false->true, and each flip's paint-transition
 *    (`-transition` below) animates a small/bright ring smoothly
 *    expanding into a large/faded one -- one visible "pulse" per flip.
 *    When the pulse sequence ends, both feature-states are cleared, and
 *    the layer falls through to the final `0`-opacity case: no ring at
 *    all, i.e. "settle to steady" -- the marker icon itself (a SEPARATE
 *    layer, `operationalMarkerPaint`) is the only thing left visible,
 *    and its own opacity never reaches 0 (Section 2: "the center dot
 *    MUST remain visible at all times").
 */
export function operationalMarkerHaloPaint(reduceMotion) {
  return {
    'circle-color': CLINICAL_MARKER_COLOR_HEX,
    'circle-radius': [
      'case',
      ['boolean', ['feature-state', 'selected'], false],
      13,
      ['boolean', ['feature-state', 'pulseExpanded'], false],
      26,
      9,
    ],
    'circle-opacity': [
      'case',
      ['boolean', ['feature-state', 'selected'], false],
      0.28,
      ['all', ['boolean', ['feature-state', 'pulseActive'], false], ['!', ['boolean', ['feature-state', 'pulseExpanded'], false]]],
      0.5,
      0,
    ],
    'circle-radius-transition': { duration: reduceMotion ? 0 : 700 },
    'circle-opacity-transition': { duration: reduceMotion ? 0 : 700 },
  }
}
