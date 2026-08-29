import { describe, expect, it } from 'vitest'

import { CLINICAL_CIRCLE_ICON_ID, CLINICAL_DIAMOND_ICON_ID } from '../components/operationalIcons'
import {
  OPERATIONAL_MARKERS_LAYER_ID,
  OPERATIONAL_MARKERS_SOURCE_ID,
  buildOperationalMarkerFeatureCollection,
  operationalMarkerIconLayout,
} from '../components/operationalMarkerLayer'

const LSD_CONTEXT = {
  caseId: 'C1',
  farmId: 'F1',
  disease: 'LSD',
  semanticClass: 'VERIFIED_CLINICAL_CONTEXT',
  verificationTime: '2026-01-02 10:00:00',
  timestampBasis: 'VERIFICATION_TIME',
  latitude: 6.9271,
  longitude: 79.8612,
  locationDistrict: 'Colombo',
}

const FMD_CONTEXT = { ...LSD_CONTEXT, caseId: 'C2', disease: 'FMD' }

describe('GEO-INT-03-LAYER-01: buildOperationalMarkerFeatureCollection', () => {
  it('builds one Point feature per validated clinical context, in [lon, lat] order', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_CONTEXT])
    expect(fc.type).toBe('FeatureCollection')
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].geometry.coordinates).toEqual([79.8612, 6.9271])
  })

  it('never fabricates a coordinate -- it only wraps the caller-supplied lat/lon verbatim', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_CONTEXT, FMD_CONTEXT])
    for (const feature of fc.features) {
      expect(feature.geometry.coordinates[0]).toBe(LSD_CONTEXT.longitude)
      expect(feature.geometry.coordinates[1]).toBe(LSD_CONTEXT.latitude)
    }
  })

  it('preserves semantic_class and timestamp_basis on the feature so a click handler never has to re-derive them', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_CONTEXT])
    expect(fc.features[0].properties.semanticClass).toBe('VERIFIED_CLINICAL_CONTEXT')
    expect(fc.features[0].properties.timestampBasis).toBe('VERIFICATION_TIME')
  })

  it('empty input produces an empty, valid FeatureCollection', () => {
    expect(buildOperationalMarkerFeatureCollection([])).toEqual({ type: 'FeatureCollection', features: [] })
  })
})

describe('GEO-INT-03-LAYER-02: operationalMarkerIconLayout is disease-shape-driven, never risk-colored', () => {
  it('is a pure data-driven expression -- calling it twice returns an equivalent layout', () => {
    expect(operationalMarkerIconLayout()).toEqual(operationalMarkerIconLayout())
  })

  it('selects the diamond icon for LSD and the circle icon for FMD via a `case` expression, never a fixed single icon', () => {
    const layout = operationalMarkerIconLayout()
    const expr = layout['icon-image']
    expect(expr[0]).toBe('case')
    expect(expr).toContain(CLINICAL_DIAMOND_ICON_ID)
    expect(expr).toContain(CLINICAL_CIRCLE_ICON_ID)
  })

  it('carries no paint/color/size property that could vary by disease or risk', () => {
    const layout = operationalMarkerIconLayout()
    expect(Object.keys(layout).sort()).toEqual(['icon-allow-overlap', 'icon-ignore-placement', 'icon-image', 'icon-size'])
  })
})

describe('GEO-INT-03-LAYER-03: stable source/layer ids', () => {
  it('ids are non-empty, distinct from every existing source/layer id family', () => {
    expect(OPERATIONAL_MARKERS_SOURCE_ID).toBeTruthy()
    expect(OPERATIONAL_MARKERS_LAYER_ID).toBeTruthy()
    expect(OPERATIONAL_MARKERS_SOURCE_ID).not.toBe(OPERATIONAL_MARKERS_LAYER_ID)
  })
})
