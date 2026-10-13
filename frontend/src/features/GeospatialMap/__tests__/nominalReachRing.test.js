import { describe, expect, it } from 'vitest'

import {
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
