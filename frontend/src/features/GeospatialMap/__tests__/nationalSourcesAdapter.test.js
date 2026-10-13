import { describe, expect, it } from 'vitest'

import { buildNationalSourcesFeatureCollection } from '../components/mapLibreAdapter'
import { REAL_SOURCES_20200928 } from './fixtures/realLsdOriginFixture'

describe('buildNationalSourcesFeatureCollection', () => {
  it('tags every feature with its origin outbreakId, preserving real coordinates/properties verbatim', () => {
    const fc = buildNationalSourcesFeatureCollection([
      { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', sourcesFeatureCollection: REAL_SOURCES_20200928 },
    ])
    expect(fc.type).toBe('FeatureCollection')
    expect(fc.features).toHaveLength(2)
    for (const feature of fc.features) {
      expect(feature.properties.outbreakId).toBe('ORIGIN:Sri Lanka:2020-09-28')
    }
    expect(fc.features[0].properties.source_id).toBe('WAHIS_PDF:Event_3473.pdf:002409')
    expect(fc.features[0].geometry.coordinates).toEqual([80.0290277, 9.6734908])
  })

  it('merges multiple origins into one collection', () => {
    const fc = buildNationalSourcesFeatureCollection([
      { outbreakId: 'ORIGIN:Sri Lanka:2020-09-07', sourcesFeatureCollection: { type: 'FeatureCollection', features: [REAL_SOURCES_20200928.features[0]] } },
      { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', sourcesFeatureCollection: REAL_SOURCES_20200928 },
    ])
    expect(fc.features).toHaveLength(3)
    expect(new Set(fc.features.map((f) => f.properties.outbreakId))).toEqual(new Set(['ORIGIN:Sri Lanka:2020-09-07', 'ORIGIN:Sri Lanka:2020-09-28']))
  })

  it('handles an origin with no sources gracefully (empty, not a crash)', () => {
    const fc = buildNationalSourcesFeatureCollection([{ outbreakId: 'x', sourcesFeatureCollection: null }])
    expect(fc.features).toEqual([])
  })

  it('handles an empty origin list', () => {
    expect(buildNationalSourcesFeatureCollection([])).toEqual({ type: 'FeatureCollection', features: [] })
  })
})
