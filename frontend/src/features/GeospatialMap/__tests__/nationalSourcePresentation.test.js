import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  aggregateNationalSourcesByLocation,
  coordinateKey,
  featureBelongsToOutbreak,
  nationalStackIndicatorPaint,
} from '../adapters/nationalSourcePresentation'
import { buildNationalSourcesFeatureCollection } from '../components/mapLibreAdapter'
import SourcePopup from '../components/SourcePopup'

/**
 * GEO33B Section 7.
 *
 * REAL DATA, not invented. The six records below are the complete real Sri
 * Lanka LSD model-candidate set, read (read-only) out of the development
 * `historical_outbreak_records` store on 2026-08-30 -- same `source_id`s,
 * same coordinates, same `proxy_availability_date`s. The per-origin
 * eligibility expansion is the backend's own documented rule
 * (`services/source_selector.py`: `t0 - active_window_days <= date <= t0`,
 * with `ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT = 14` from `config.py`),
 * applied here to the real dates to reproduce exactly what the frontend
 * receives after merging every origin's `/analysis/{id}/sources` response.
 *
 * That expansion is what produces the "9 LSD features but only 6 visible
 * markers" observation: 9 rows, 6 distinct real records/locations, 3
 * records returned twice because two origins' 14-day windows both contain
 * them. Six markers was always the correct picture of reality.
 */
const REAL_LSD_RECORDS = [
  { id: 'WAHIS_PDF:Event_3473.pdf:002407', date: '2020-09-07', lon: 80.0668497, lat: 9.7151701 },
  { id: 'WAHIS_PDF:Event_3473.pdf:002408', date: '2020-09-09', lon: 80.1643076, lat: 9.6579014 },
  { id: 'WAHIS_PDF:Event_3473.pdf:002409', date: '2020-09-28', lon: 80.0290277, lat: 9.6734908 },
  { id: 'WAHIS_PDF:Event_3473.pdf:002410', date: '2020-09-28', lon: 80.08333, lat: 9.75 },
  { id: 'WAHIS_PDF:Event_3473.pdf:002411', date: '2020-09-29', lon: 80.0461103553, lat: 8.888178931 },
  { id: 'WAHIS_PDF:Event_3473.pdf:002412', date: '2020-10-28', lon: 80.6608048, lat: 9.0621351 },
]
const ACTIVE_SOURCE_WINDOW_DAYS = 14
const DAY_MS = 24 * 60 * 60 * 1000

/** Reproduces the real per-origin `/analysis/{id}/sources` responses, then
 * merges them exactly as `OutbreakMapPage.jsx` does. */
function buildRealMergedNationalSources() {
  const originDates = Array.from(new Set(REAL_LSD_RECORDS.map((r) => r.date))).sort()
  const originsWithSources = originDates.map((t0) => {
    const t0Ms = Date.parse(`${t0}T00:00:00Z`)
    const eligible = REAL_LSD_RECORDS.filter((r) => {
      const ms = Date.parse(`${r.date}T00:00:00Z`)
      return ms <= t0Ms && ms >= t0Ms - ACTIVE_SOURCE_WINDOW_DAYS * DAY_MS
    })
    return {
      outbreakId: `ORIGIN:Sri Lanka:${t0}`,
      sourcesFeatureCollection: {
        type: 'FeatureCollection',
        features: eligible.map((r) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [r.lon, r.lat] },
          properties: { source_id: r.id, availability_quality: 'EVENT_DATE_PROXY', gps_quality: 'EXACT' },
        })),
      },
    }
  })
  return buildNationalSourcesFeatureCollection(originsWithSources)
}

describe('GEO33B Section 7: the real 9-row / 6-location national LSD collection', () => {
  const merged = buildRealMergedNationalSources()

  it('reproduces the reported 9 merged features from the real 6-record corpus', () => {
    expect(merged.features).toHaveLength(9)
  })

  it('those 9 rows cover only 6 distinct real coordinates -- the other 3 are the same records under a second origin', () => {
    const distinctCoordinates = new Set(merged.features.map((f) => coordinateKey(...f.geometry.coordinates)))
    expect(distinctCoordinates.size).toBe(6)
    const distinctSourceIds = new Set(merged.features.map((f) => f.properties.source_id))
    expect(distinctSourceIds.size).toBe(6)
  })

  it('aggregates to exactly 6 presentation markers -- one per real location, none invented, none dropped', () => {
    const aggregated = aggregateNationalSourcesByLocation(merged)
    expect(aggregated.features).toHaveLength(6)
    const aggregatedIds = new Set(aggregated.features.map((f) => f.properties.source_id))
    expect(aggregatedIds).toEqual(new Set(REAL_LSD_RECORDS.map((r) => r.id)))
  })

  it('every aggregate keeps a REAL record coordinate verbatim -- never a centroid/average of the merged rows', () => {
    const aggregated = aggregateNationalSourcesByLocation(merged)
    const realCoordinates = new Set(REAL_LSD_RECORDS.map((r) => coordinateKey(r.lon, r.lat)))
    for (const feature of aggregated.features) {
      expect(realCoordinates.has(coordinateKey(...feature.geometry.coordinates))).toBe(true)
    }
  })

  it('stackCount counts DISTINCT REAL RECORDS, never repeated eligibility rows -- so it is 1 everywhere in this real corpus', () => {
    const aggregated = aggregateNationalSourcesByLocation(merged)
    for (const feature of aggregated.features) {
      expect(feature.properties.stackCount).toBe(1)
    }
    // The raw row count still shows which records were returned twice --
    // diagnostics only, never presented as an observation count.
    const doubleCounted = aggregated.features.filter((f) => f.properties.mergedFeatureCount === 2)
    expect(doubleCounted).toHaveLength(3)
  })

  it('records eligible under several real origins keep EVERY real origin id, so selection can match any of them', () => {
    const aggregated = aggregateNationalSourcesByLocation(merged)
    const record002407 = aggregated.features.find((f) => f.properties.source_id.endsWith('002407'))
    expect(record002407.properties.outbreakIds).toEqual(['ORIGIN:Sri Lanka:2020-09-07', 'ORIGIN:Sri Lanka:2020-09-09'])
    // The pre-GEO33B equality check (`properties.outbreakId === selected`)
    // matched only whichever origin happened to be first.
    expect(featureBelongsToOutbreak(record002407, 'ORIGIN:Sri Lanka:2020-09-09')).toBe(true)
    expect(featureBelongsToOutbreak(record002407, 'ORIGIN:Sri Lanka:2020-09-07')).toBe(true)
    expect(featureBelongsToOutbreak(record002407, 'ORIGIN:Sri Lanka:2020-10-28')).toBe(false)
  })

  it('the promoted feature id (source_id) is unique after aggregation -- the feature-state collision is gone', () => {
    const aggregated = aggregateNationalSourcesByLocation(merged)
    const ids = aggregated.features.map((f) => f.properties.source_id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

describe('GEO33B Section 7: the aggregation never fabricates or repairs geometry', () => {
  it('drops a feature with a missing/non-finite coordinate rather than guessing one', () => {
    const aggregated = aggregateNationalSourcesByLocation({
      type: 'FeatureCollection',
      features: [
        { type: 'Feature', geometry: { type: 'Point', coordinates: [80.1, 9.1] }, properties: { source_id: 'a' } },
        { type: 'Feature', geometry: { type: 'Point', coordinates: [null, 9.1] }, properties: { source_id: 'b' } },
        { type: 'Feature', geometry: null, properties: { source_id: 'c' } },
      ],
    })
    expect(aggregated.features).toHaveLength(1)
    expect(aggregated.features[0].properties.source_id).toBe('a')
  })

  it('two genuinely DIFFERENT real records at one coordinate produce one marker with a real stackCount of 2', () => {
    const aggregated = aggregateNationalSourcesByLocation({
      type: 'FeatureCollection',
      features: [
        { type: 'Feature', geometry: { type: 'Point', coordinates: [80.1, 9.1] }, properties: { source_id: 'a', outbreakId: 'o1' } },
        { type: 'Feature', geometry: { type: 'Point', coordinates: [80.1, 9.1] }, properties: { source_id: 'b', outbreakId: 'o2' } },
      ],
    })
    expect(aggregated.features).toHaveLength(1)
    expect(aggregated.features[0].properties.stackCount).toBe(2)
    expect(aggregated.features[0].properties.sourceIds).toEqual(['a', 'b'])
  })

  it('an empty/absent collection aggregates to an empty collection, never a crash', () => {
    expect(aggregateNationalSourcesByLocation(null)).toEqual({ type: 'FeatureCollection', features: [] })
    expect(aggregateNationalSourcesByLocation({ type: 'FeatureCollection', features: [] }).features).toEqual([])
  })
})

describe('GEO33B Section 7: the stack indicator is invisible unless a real stack exists', () => {
  const paint = nationalStackIndicatorPaint()

  it('resolves to radius 0 and stroke-width 0 at stackCount 1 -- a single record is never decorated', () => {
    // `['step', ['get', 'stackCount'], <base>, 2, <at>=2 ...]` -- the base
    // is what a stackCount of 1 gets.
    expect(paint['circle-radius'][2]).toBe(0)
    expect(paint['circle-stroke-width'][2]).toBe(0)
    expect(paint['circle-stroke-opacity'][2]).toBe(0)
  })

  it('is a plain step on the real stackCount property -- never a text/glyph-dependent badge', () => {
    expect(JSON.stringify(paint)).toContain('stackCount')
    expect(JSON.stringify(paint)).not.toContain('text-field')
  })
})

describe('GEO33B Section 7: SourcePopup states the real count, and only when there really is one', () => {
  it('a single real record never shows a fabricated "1 record" count', () => {
    const html = renderToStaticMarkup(
      React.createElement(SourcePopup, {
        feature: {
          geometry: { type: 'Point', coordinates: [80.0290277, 9.6734908] },
          properties: { source_id: 'WAHIS_PDF:Event_3473.pdf:002409', gps_quality: 'EXACT', availability_quality: 'EVENT_DATE_PROXY', stackCount: 1, sourceIds: ['WAHIS_PDF:Event_3473.pdf:002409'] },
        },
        onViewSpatialContext: () => {},
        onClose: () => {},
      }),
    )
    expect(html).not.toContain('distinct historical source records')
  })

  it('two real records at one coordinate show the real count of 2 and both real ids', () => {
    const html = renderToStaticMarkup(
      React.createElement(SourcePopup, {
        feature: {
          geometry: { type: 'Point', coordinates: [80.1, 9.1] },
          properties: { source_id: 'a', gps_quality: 'EXACT', availability_quality: 'EVENT_DATE_PROXY', stackCount: 2, sourceIds: ['a', 'b'] },
        },
        onViewSpatialContext: () => {},
        onClose: () => {},
      }),
    )
    expect(html).toContain('2 distinct historical source records')
    expect(html).toContain('a, b')
  })
})
