import { describe, expect, it } from 'vitest'

import { CLINICAL_CIRCLE_ICON_ID, CLINICAL_DIAMOND_ICON_ID, CLINICAL_MARKER_COLOR_HEX } from '../components/operationalIcons'
import {
  OPERATIONAL_MARKERS_HALO_LAYER_ID,
  OPERATIONAL_MARKERS_LAYER_ID,
  OPERATIONAL_MARKERS_SOURCE_ID,
  buildOperationalMarkerFeatureCollection,
  operationalMarkerHaloPaint,
  operationalMarkerIconLayout,
  operationalMarkerPaint,
} from '../components/operationalMarkerLayer'

const LSD_FARM_GROUP = {
  farmId: 'F1',
  disease: 'LSD',
  latitude: 6.9271,
  longitude: 79.8612,
  locationDistrict: 'Colombo',
  caseCount: 2,
  caseIds: ['C1', 'C2'],
  verificationTimes: ['2026-01-02 10:00:00', '2026-01-01 09:00:00'],
  latestVerificationTime: '2026-01-02 10:00:00',
  recencyTier: 'recent',
}

const FMD_FARM_GROUP = { ...LSD_FARM_GROUP, disease: 'FMD', caseCount: 1, caseIds: ['C3'] }

describe('GEO-INT-03-LAYER-01 / GEO26B: buildOperationalMarkerFeatureCollection', () => {
  it('builds one Point feature per farm+disease aggregate, in [lon, lat] order', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_FARM_GROUP])
    expect(fc.type).toBe('FeatureCollection')
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].geometry.coordinates).toEqual([79.8612, 6.9271])
  })

  it('never fabricates a coordinate -- it only wraps the caller-supplied lat/lon verbatim', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_FARM_GROUP, FMD_FARM_GROUP])
    for (const feature of fc.features) {
      expect(feature.geometry.coordinates[0]).toBe(LSD_FARM_GROUP.longitude)
      expect(feature.geometry.coordinates[1]).toBe(LSD_FARM_GROUP.latitude)
    }
  })

  it('carries the real caseCount/caseIds/latestVerificationTime through verbatim, never recomputed here', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_FARM_GROUP])
    expect(fc.features[0].properties.caseCount).toBe(2)
    expect(fc.features[0].properties.caseIds).toEqual(['C1', 'C2'])
    expect(fc.features[0].properties.latestVerificationTime).toBe('2026-01-02 10:00:00')
  })

  it('promotes a stable farmDiseaseKey so a farm marker can be targeted by feature-state across refreshes', () => {
    const fc = buildOperationalMarkerFeatureCollection([LSD_FARM_GROUP])
    expect(fc.features[0].properties.farmDiseaseKey).toBe('F1::LSD')
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

  it('carries no color property, and its icon-size is a step expression keyed on the real caseCount', () => {
    const layout = operationalMarkerIconLayout()
    expect(Object.keys(layout).sort()).toEqual(['icon-allow-overlap', 'icon-ignore-placement', 'icon-image', 'icon-size'])
    expect(layout['icon-size'][0]).toBe('step')
    expect(layout['icon-size'][1]).toEqual(['get', 'caseCount'])
  })
})

describe('GEO26B: operationalMarkerPaint -- opacity only, never color, by real recencyTier/feature-state', () => {
  it('has no color/paint property besides icon-opacity(-transition)', () => {
    expect(Object.keys(operationalMarkerPaint(false)).sort()).toEqual(['icon-opacity', 'icon-opacity-transition'])
  })

  it('disables the opacity transition when reduced motion is requested', () => {
    expect(operationalMarkerPaint(true)['icon-opacity-transition']).toEqual({ duration: 0 })
    expect(operationalMarkerPaint(false)['icon-opacity-transition']).toEqual({ duration: 300 })
  })
})

describe('GEO-INT-03-LAYER-03: stable source/layer ids', () => {
  it('ids are non-empty, distinct from every existing source/layer id family', () => {
    expect(OPERATIONAL_MARKERS_SOURCE_ID).toBeTruthy()
    expect(OPERATIONAL_MARKERS_LAYER_ID).toBeTruthy()
    expect(OPERATIONAL_MARKERS_SOURCE_ID).not.toBe(OPERATIONAL_MARKERS_LAYER_ID)
    expect(OPERATIONAL_MARKERS_HALO_LAYER_ID).toBeTruthy()
    expect(OPERATIONAL_MARKERS_HALO_LAYER_ID).not.toBe(OPERATIONAL_MARKERS_LAYER_ID)
  })
})

describe('GEO31A/GEO33A Section 2/3/20/26: operationalMarkerHaloPaint -- the pulse/selection ring', () => {
  it('always paints the same clinical red color, never a data-driven/risk expression', () => {
    const paint = operationalMarkerHaloPaint(false)
    expect(paint['circle-color']).toBe(CLINICAL_MARKER_COLOR_HEX)
  })

  it('is fully invisible (opacity 0) when neither selected nor pulsing -- "settle to steady" leaves no ring', () => {
    const paint = operationalMarkerHaloPaint(false)
    // The final fallback branch of the opacity `case` expression.
    const opacityExpr = paint['circle-opacity']
    expect(opacityExpr[opacityExpr.length - 1]).toBe(0)
  })

  it('a selected farm gets a steady, non-zero ring opacity independent of any pulse state', () => {
    const paint = operationalMarkerHaloPaint(false)
    expect(paint['circle-opacity']).toContain(0.28)
    expect(paint['circle-radius']).toContain(13)
  })

  it('a pulse cycle alternates a small/bright ring and a large/faded one via feature-state, never a fixed value', () => {
    const paint = operationalMarkerHaloPaint(false)
    expect(paint['circle-radius']).toContain(26) // pulseExpanded: true -> large
    expect(paint['circle-radius']).toContain(9) // resting/base radius
    expect(paint['circle-opacity']).toContain(0.5) // pulseActive && !pulseExpanded -> small bright ring
  })

  it('GEO31A Section 2 (reduced motion): both transitions collapse to 0ms, never a longer real value', () => {
    expect(operationalMarkerHaloPaint(true)['circle-radius-transition']).toEqual({ duration: 0 })
    expect(operationalMarkerHaloPaint(true)['circle-opacity-transition']).toEqual({ duration: 0 })
    expect(operationalMarkerHaloPaint(false)['circle-radius-transition']).toEqual({ duration: 700 })
    expect(operationalMarkerHaloPaint(false)['circle-opacity-transition']).toEqual({ duration: 700 })
  })

  it('carries no icon-*/color-by-disease property -- shape/disease identity stays on the icon layer only', () => {
    const paint = operationalMarkerHaloPaint(false)
    expect(Object.keys(paint).every((k) => k.startsWith('circle-'))).toBe(true)
  })
})
