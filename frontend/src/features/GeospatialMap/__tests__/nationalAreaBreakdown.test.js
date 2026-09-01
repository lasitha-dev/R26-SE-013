import { describe, expect, it } from 'vitest'

import {
  buildDeduplicatedNationalSources,
  buildMostAffectedAreas,
  deriveAffectedAreas,
  resolveDistrictForFeature,
} from '../adapters/nationalAreaBreakdown'

const MATARA_DISTRICT = {
  type: 'Feature',
  properties: { shapeName: 'Matara District' },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [80.4, 5.9],
        [80.7, 5.9],
        [80.7, 6.1],
        [80.4, 6.1],
        [80.4, 5.9],
      ],
    ],
  },
}

const JAFFNA_DISTRICT = {
  type: 'Feature',
  properties: { shapeName: 'Jaffna District' },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [79.9, 9.5],
        [80.2, 9.5],
        [80.2, 9.8],
        [79.9, 9.8],
        [79.9, 9.5],
      ],
    ],
  },
}

const DISTRICTS = { type: 'FeatureCollection', features: [MATARA_DISTRICT, JAFFNA_DISTRICT] }

function origin({ outbreakId, t0, points }) {
  return {
    outbreakId,
    t0,
    sourcesFeatureCollection: {
      type: 'FeatureCollection',
      features: points.map(([lng, lat], i) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: { source_id: `${outbreakId}:${i}` },
      })),
    },
  }
}

describe('resolveDistrictForFeature', () => {
  it('resolves a real coordinate to the district polygon that contains it', () => {
    const feature = { geometry: { coordinates: [80.5, 6.0] } }
    expect(resolveDistrictForFeature(feature, DISTRICTS)).toBe('Matara')
  })

  it('returns null for a coordinate outside every real district polygon', () => {
    const feature = { geometry: { coordinates: [1, 1] } }
    expect(resolveDistrictForFeature(feature, DISTRICTS)).toBeNull()
  })
})

describe('buildDeduplicatedNationalSources', () => {
  it('collapses two origins sharing one real coordinate into a single record', () => {
    const origins = [
      origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0]] }),
      origin({ outbreakId: 'B', t0: '2020-09-09', points: [[80.5, 6.0]] }),
    ]
    const deduped = buildDeduplicatedNationalSources(origins)
    expect(deduped.features).toHaveLength(1)
    expect(deduped.features[0].properties.outbreakIds).toEqual(['A', 'B'])
  })

  it('never double-counts distinct real coordinates', () => {
    const origins = [origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0], [80.55, 6.02]] })]
    expect(buildDeduplicatedNationalSources(origins).features).toHaveLength(2)
  })
})

describe('deriveAffectedAreas', () => {
  it('counts only real districts with at least one real observed record', () => {
    const origins = [
      origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0]] }),
      origin({ outbreakId: 'B', t0: '2020-09-09', points: [[80.0, 9.6]] }),
    ]
    const result = deriveAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS)
    expect(result.count).toBe(2)
    expect(result.districts).toEqual(['Jaffna', 'Matara'])
  })

  it('excludes a real record whose coordinate falls outside every district polygon', () => {
    const origins = [origin({ outbreakId: 'A', t0: '2020-09-07', points: [[1, 1]] })]
    const result = deriveAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS)
    expect(result.count).toBe(0)
  })
})

describe('buildMostAffectedAreas', () => {
  it('sorts districts descending by real record count', () => {
    const origins = [
      origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0], [80.55, 6.02]] }),
      origin({ outbreakId: 'B', t0: '2020-09-09', points: [[80.0, 9.6]] }),
    ]
    const rows = buildMostAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS, origins)
    expect(rows.map((r) => r.district)).toEqual(['Matara', 'Jaffna'])
    expect(rows[0].records).toBe(2)
    expect(rows[1].records).toBe(1)
  })

  it('lastObserved is the latest real origin t0 covering that district', () => {
    const origins = [
      origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0]] }),
      origin({ outbreakId: 'B', t0: '2020-10-28', points: [[80.55, 6.02]] }),
    ]
    const rows = buildMostAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS, origins)
    expect(rows[0]).toEqual({ district: 'Matara', records: 2, lastObserved: '2020-10-28' })
  })

  it('never pads a short real result with filler rows', () => {
    const origins = [origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0]] })]
    const rows = buildMostAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS, origins, { topN: 5 })
    expect(rows).toHaveLength(1)
  })

  it('respects topN', () => {
    const origins = [
      origin({ outbreakId: 'A', t0: '2020-09-07', points: [[80.5, 6.0]] }),
      origin({ outbreakId: 'B', t0: '2020-09-09', points: [[80.0, 9.6]] }),
    ]
    const rows = buildMostAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS, origins, { topN: 1 })
    expect(rows).toHaveLength(1)
  })

  it('returns an empty list when no district contains any real record', () => {
    const origins = [origin({ outbreakId: 'A', t0: '2020-09-07', points: [[1, 1]] })]
    expect(buildMostAffectedAreas(buildDeduplicatedNationalSources(origins), DISTRICTS, origins)).toEqual([])
  })
})
