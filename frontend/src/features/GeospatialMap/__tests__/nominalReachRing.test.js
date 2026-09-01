import { describe, expect, it } from 'vitest'

import {
  REACH_GRADIENT_BAND_COUNT,
  REACH_GRADIENT_BAND_OPACITY,
  buildReachGradientFeatureCollectionForCenters,
  buildReachRingFeatureCollectionForCenters,
  buildReachRingPolygon,
  emptyReachRingFeatureCollection,
  reachRingFeatureCollection,
} from '../components/nominalReachRing'

describe('nominalReachRing', () => {
  it('returns null for a non-positive radius (D0 has no forward reach)', () => {
    expect(buildReachRingPolygon([80.1, 9.6], 0)).toBeNull()
    expect(buildReachRingPolygon([80.1, 9.6], -1)).toBeNull()
  })

  it('builds a closed polygon ring around the given center', () => {
    const feature = buildReachRingPolygon([80.1, 9.6], 10, 8)
    expect(feature.type).toBe('Feature')
    expect(feature.geometry.type).toBe('Polygon')
    const ring = feature.geometry.coordinates[0]
    expect(ring).toHaveLength(9) // steps + 1 (closed)
    expect(ring[0]).toEqual(ring[ring.length - 1]) // closed ring
  })

  it('carries the real radiusKm and center verbatim on the feature (never recomputed by a reader)', () => {
    const feature = buildReachRingPolygon([80.1, 9.6], 19.73)
    expect(feature.properties.radiusKm).toBe(19.73)
    expect(feature.properties.centerLonLat).toEqual([80.1, 9.6])
  })

  it('a larger radius produces a ring further from the center', () => {
    const small = buildReachRingPolygon([80.0, 9.0], 5)
    const large = buildReachRingPolygon([80.0, 9.0], 20)
    const smallPoint = small.geometry.coordinates[0][0]
    const largePoint = large.geometry.coordinates[0][0]
    const smallDelta = Math.abs(smallPoint[0] - 80.0) + Math.abs(smallPoint[1] - 9.0)
    const largeDelta = Math.abs(largePoint[0] - 80.0) + Math.abs(largePoint[1] - 9.0)
    expect(largeDelta).toBeGreaterThan(smallDelta)
  })

  it('emptyReachRingFeatureCollection is a valid empty FeatureCollection', () => {
    expect(emptyReachRingFeatureCollection()).toEqual({ type: 'FeatureCollection', features: [] })
  })

  it('reachRingFeatureCollection wraps a real radius as one feature, and a zero radius as none', () => {
    const withRadius = reachRingFeatureCollection([80.1, 9.6], 12)
    expect(withRadius.features).toHaveLength(1)

    const withoutRadius = reachRingFeatureCollection([80.1, 9.6], 0)
    expect(withoutRadius.features).toHaveLength(0)
  })

  it('buildReachRingFeatureCollectionForCenters draws the SAME real radius around every real source, never picking just one', () => {
    const centers = [
      [80.0290277, 9.6734908],
      [80.08333, 9.75],
    ]
    const fc = buildReachRingFeatureCollectionForCenters(centers, 15)
    expect(fc.features).toHaveLength(2)
    expect(fc.features[0].properties.radiusKm).toBe(15)
    expect(fc.features[1].properties.radiusKm).toBe(15)
    expect(fc.features[0].properties.centerLonLat).toEqual(centers[0])
    expect(fc.features[1].properties.centerLonLat).toEqual(centers[1])
  })

  it('buildReachRingFeatureCollectionForCenters returns no features for a non-positive radius or no centers', () => {
    expect(buildReachRingFeatureCollectionForCenters([[80, 9]], 0).features).toHaveLength(0)
    expect(buildReachRingFeatureCollectionForCenters([], 10).features).toHaveLength(0)
    expect(buildReachRingFeatureCollectionForCenters(null, 10).features).toHaveLength(0)
  })
})

describe('GEO-REACH-GRADIENT-01: concentric-disk radial gradient -- same real radius, layered opacity only', () => {
  it('emits REACH_GRADIENT_BAND_COUNT bands per real center, largest radius first', () => {
    const fc = buildReachGradientFeatureCollectionForCenters([[80.1, 9.6]], 20)
    expect(fc.features).toHaveLength(REACH_GRADIENT_BAND_COUNT)
    // Largest band (fraction 1) first, so smaller/more-opaque bands paint
    // on top of it -- required for the compositing gradient to look right.
    expect(fc.features[0].properties.bandFraction).toBe(1)
    expect(fc.features[fc.features.length - 1].properties.bandFraction).toBeCloseTo(1 / REACH_GRADIENT_BAND_COUNT)
    // Monotonically decreasing fraction -> monotonically decreasing radius.
    for (let i = 1; i < fc.features.length; i += 1) {
      expect(fc.features[i].properties.radiusKm).toBeLessThan(fc.features[i - 1].properties.radiusKm)
    }
  })

  it('every band is a real fraction of the SAME real radiusKm -- never a second/independent radius value', () => {
    const radiusKm = 19.732107215773755 // real day-5 value observed live against the backend
    const fc = buildReachGradientFeatureCollectionForCenters([[80.1, 9.6]], radiusKm)
    for (const feature of fc.features) {
      expect(feature.properties.radiusKm).toBeCloseTo(radiusKm * feature.properties.bandFraction, 10)
    }
  })

  it('draws the same band set around EVERY real center, never just one', () => {
    const centers = [
      [80.0290277, 9.6734908],
      [80.08333, 9.75],
    ]
    const fc = buildReachGradientFeatureCollectionForCenters(centers, 15)
    expect(fc.features).toHaveLength(centers.length * REACH_GRADIENT_BAND_COUNT)
  })

  it('returns no features for a non-positive radius or no centers -- same honesty rule as the ring/outline', () => {
    expect(buildReachGradientFeatureCollectionForCenters([[80, 9]], 0).features).toHaveLength(0)
    expect(buildReachGradientFeatureCollectionForCenters([], 10).features).toHaveLength(0)
    expect(buildReachGradientFeatureCollectionForCenters(null, 10).features).toHaveLength(0)
  })

  it('the equal per-band opacity composites to roughly the intended ~25% peak at the origin, ~0% at the edge (alpha-over math)', () => {
    const centerComposite = 1 - (1 - REACH_GRADIENT_BAND_OPACITY) ** REACH_GRADIENT_BAND_COUNT
    expect(centerComposite).toBeGreaterThan(0.2)
    expect(centerComposite).toBeLessThan(0.3)
    // The outermost sliver is covered by exactly one band.
    expect(REACH_GRADIENT_BAND_OPACITY).toBeLessThan(0.05)
  })
})
