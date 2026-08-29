/**
 * GEO-INT-03: pure GeoJSON FeatureCollection + layout builders for the
 * Verified Clinical Context overlay -- same pattern as
 * `mapLibreAdapter.js` (Section 3: reuse, don't duplicate the map
 * lifecycle; extracted so it's unit-testable without WebGL/DOM, same as
 * every other builder module in this feature). `MapLibreCanvas.jsx`
 * calls these exact functions.
 *
 * Section 9: never uses the risk red/orange/amber/yellow/green family or
 * any pulsing/glow/reach-ring treatment -- a single restrained hollow
 * neutral-mint marker (`operationalIcons.js`), identical treatment for
 * every clinical context regardless of disease. Disease identity is
 * SHAPE only (diamond=LSD, circle=FMD, `disease/diseaseRegistry.js`'s
 * existing `markerShape` convention), never color.
 */
import { CLINICAL_CIRCLE_ICON_ID, CLINICAL_DIAMOND_ICON_ID } from './operationalIcons'

export const OPERATIONAL_MARKERS_SOURCE_ID = 'geo-operational-clinical-contexts'
export const OPERATIONAL_MARKERS_LAYER_ID = 'operational-clinical-symbol'

/**
 * One feature per normalized clinical context. The caller
 * (`operationalContextAdapter.js`) has already dropped anything without
 * a valid, mapped farm location (Section 26) -- this function never
 * re-derives or guesses a coordinate, it only wraps validated input.
 */
export function buildOperationalMarkerFeatureCollection(clinicalContexts) {
  return {
    type: 'FeatureCollection',
    features: clinicalContexts.map((c) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [c.longitude, c.latitude] },
      properties: {
        caseId: c.caseId,
        farmId: c.farmId,
        disease: c.disease,
        semanticClass: c.semanticClass,
        verificationTime: c.verificationTime,
        timestampBasis: c.timestampBasis,
        locationDistrict: c.locationDistrict,
      },
    })),
  }
}

/**
 * Data-driven icon-image expression: diamond for LSD, circle for FMD --
 * shape only, matching `diseaseRegistry.js`'s `markerShape` convention.
 * No color or size varies by disease (Section 9).
 */
export function operationalMarkerIconLayout() {
  return {
    'icon-image': ['case', ['==', ['get', 'disease'], 'LSD'], CLINICAL_DIAMOND_ICON_ID, CLINICAL_CIRCLE_ICON_ID],
    'icon-allow-overlap': true,
    'icon-ignore-placement': true,
    'icon-size': 1,
  }
}
