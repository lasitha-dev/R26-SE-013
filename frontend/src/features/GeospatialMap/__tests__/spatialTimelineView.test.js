import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import {
  anchorIdForSource,
  buildPossibleCases,
  buildMyAreaTimelineView,
  buildNationalTimelineLayers,
  clampFrameIndex,
  frameDates,
  horizonLabel,
  isTimelineRenderable,
  TIER_TO_RISK_LEVEL,
} from '../adapters/spatialTimelineView'
import fmdNotReady from './fixtures/spatialTimeline.fmdNotReady.json'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'
import nationalTimeline from './fixtures/spatialTimeline.national.json'
import noSources from './fixtures/spatialTimeline.noSources.json'

// Fixtures: real Phase 2 engine output for two FICTIONAL test farms (see fixtures/README).
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const read = (...parts) => readFileSync(join(ROOT, ...parts), 'utf8')
// Code only: comments may legitimately cite past verification dates.
const readCode = (...parts) => read(...parts).replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

describe('national layers are the backend geometry, unchanged', () => {
  it('Day 0..14 dates come from the backend frames', () => {
    const dates = frameDates(nationalTimeline)
    expect(dates).toHaveLength(15)
    expect(dates[0]).toBe(nationalTimeline.as_of)
    expect(dates).toEqual(nationalTimeline.frames.map((f) => f.date))
    expect(clampFrameIndex(nationalTimeline, 99)).toBe(14)
    expect(clampFrameIndex(nationalTimeline, -3)).toBe(0)
  })

  it('risk zones are the STATIC backend relative-score tiers (as-of date), identical on every day', () => {
    const backend = nationalTimeline.risk_zones.features
    const day1 = buildNationalTimelineLayers(nationalTimeline, 1).riskZones
    for (const day of [0, 7, 14]) expect(buildNationalTimelineLayers(nationalTimeline, day).riskZones).toEqual(day1)
    expect(day1.features).toHaveLength(backend.length)
    for (const feature of day1.features) {
      const source = backend.find((f) => f.properties.tier === feature.properties.tier)
      expect(feature.geometry).toEqual(source.geometry) // coordinates untouched
      expect(feature.properties.riskLevel).toBe(TIER_TO_RISK_LEVEL[feature.properties.tier])
      expect(feature.properties.layerRole).toBe('STATIC_RELATIVE_SCORE_TIER')
      expect(feature.properties.asOf).toBe(nationalTimeline.as_of)
    }
    expect(TIER_TO_RISK_LEVEL).toEqual({ lower: 'green', moderate: 'yellow', high: 'orange', highest: 'red' })
  })

  it('the only day-dependent layer is the backend nominal-reach outline (none on Day 0)', () => {
    expect(buildNationalTimelineLayers(nationalTimeline, 0).contextZones.features).toHaveLength(0)
    for (const day of [1, 7, 14]) {
      const [outline, ...rest] = buildNationalTimelineLayers(nationalTimeline, day).contextZones.features
      expect(rest).toHaveLength(0)
      expect(outline.geometry).toEqual(nationalTimeline.frames[day].reach_envelope) // backend geometry verbatim
      expect(outline.properties).toMatchObject({ riskLevel: 'reach', layerRole: 'NOMINAL_REACH_OUTLINE', day, nominalReachKm: nationalTimeline.frames[day].reach.nominal_reach_km })
    }
  })

  it('direction lines follow the timeline: none on Day 0, each later date draws its own backend corridors', () => {
    const sourceIds = new Set(nationalTimeline.sources.map((s) => s.source_id))
    expect(buildNationalTimelineLayers(nationalTimeline, 0).paths.features).toHaveLength(0)
    for (const day of [1, 5, 14]) {
      const layers = buildNationalTimelineLayers(nationalTimeline, day)
      const own = nationalTimeline.frames[day].source_corridors.filter((c) => Number.isFinite(c.bearing_deg))
      expect(layers.paths.features.map((f) => f.geometry)).toEqual(own.map((c) => c.geometry))
      for (const path of layers.paths.features) {
        expect(sourceIds.has(path.properties.sourceId)).toBe(true)
        expect(path.properties.day).toBe(day)
        expect(path.properties.pathLabel).toMatch(/^Day \d{1,2} · \d+ km$/)
      }
    }
    expect(buildNationalTimelineLayers(nationalTimeline, 5).paths.features[0].properties.lengthKm).toBe(nationalTimeline.frames[5].reach.nominal_reach_km)
    const research = buildNationalTimelineLayers(nationalTimeline, 5, { research: true })
    const corridors = nationalTimeline.frames[5].source_corridors
    expect(research.paths.features.map((f) => f.geometry)).toEqual(corridors.map((c) => c.geometry))
    expect(research.fronts.features[0].geometry.coordinates).toEqual(corridors[0].geometry.coordinates.at(-1))
    expect(buildNationalTimelineLayers(nationalTimeline, 0, { research: true }).paths.features).toHaveLength(0) // Day 0: no reach
  })

  it('never draws a corridor whose bearing is indeterminate', () => {
    const indeterminate = structuredClone(nationalTimeline)
    indeterminate.frames[3].source_corridors[0].bearing_deg = null
    expect(buildNationalTimelineLayers(indeterminate, 3).paths.features).toHaveLength(nationalTimeline.frames[3].source_corridors.length - 1)
  })
})

describe('status handling', () => {
  it('FMD (no frozen spatial model) and empty source sets never render layers', () => {
    expect(fmdNotReady.status).toBe('ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY')
    expect(noSources.status).toBe('NO_ELIGIBLE_SOURCES')
    for (const snapshot of [fmdNotReady, noSources, null, undefined]) {
      expect(isTimelineRenderable(snapshot)).toBe(false)
      const layers = buildNationalTimelineLayers(snapshot, 4)
      expect(layers.riskZones.features).toHaveLength(0)
      expect(layers.paths.features).toHaveLength(0)
      expect(buildMyAreaTimelineView(snapshot, 4, 'Galle').influences).toHaveLength(0)
    }
  })

  it('horizon labels mark Day 8-14 as the exploratory extension', () => {
    expect(nationalTimeline.frames.map((f) => horizonLabel(f.horizon_status))).toEqual([
      'As-of context (Day 0)', ...Array(7).fill('Day 1–7 nominal-reach horizon'), ...Array(7).fill('Exploratory extension (Day 8–14)'),
    ])
  })

  it('environment NOT_INTEGRATED is passed through for the panel', () => {
    expect(buildMyAreaTimelineView(mataraTimeline, 2, 'Matara').environmentStatus).toBe('NOT_INTEGRATED')
  })
})

describe('My Area view: one selected frame for every element', () => {
  it('district scope summaries drive risk, reach and chart; operational sources link to their case id', () => {
    const view = buildMyAreaTimelineView(mataraTimeline, 7, 'Matara')
    const frame = mataraTimeline.frames[7]
    expect(view.date).toBe(frame.date)
    expect(view.horizonStatus).toBe('WITHIN_D1_D7_REACH_HORIZON')
    expect(view.outlook[7].areaKm2).toBe(view.areaWithinReachKm2)
    const outlines = view.contextZones.features.filter((f) => f.properties.layerRole === 'NOMINAL_REACH_OUTLINE')
    expect(outlines).toHaveLength(1)
    expect(outlines[0].geometry).toEqual(frame.reach_envelope)
    expect(view.contextZones.features.filter((f) => f.properties.layerRole === 'STATIC_RELATIVE_SCORE_TIER')).toHaveLength(mataraTimeline.risk_zones.features.length)
    expect(view.riskZones.features.every((f) => f.properties.layerRole === 'SCORED_LAND_WITHIN_NOMINAL_REACH')).toBe(true)
    expect(view.riskZones.features.map((f) => f.geometry)).toEqual(frame.reach_limited_risk_zones.features.slice().sort((a, b) => ['lower', 'moderate', 'high', 'highest'].indexOf(a.properties.tier) - ['lower', 'moderate', 'high', 'highest'].indexOf(b.properties.tier)).map((f) => f.geometry))
    expect(view.paths.features.map((p) => p.properties.anchorId)).toEqual(['TEST-FICTIONAL-CASE-1', 'TEST-FICTIONAL-CASE-2'])
    expect(anchorIdForSource({ record_domain: 'HISTORICAL', source_id: 'HIST:X' })).toBe('HIST:X')
  })

  it('a different district name finds no summary instead of borrowing another district', () => {
    const view = buildMyAreaTimelineView(mataraTimeline, 7, 'Galle')
    expect(view.areaWithinReachKm2).toBeNull()
    expect(view.districtRisk).toBeNull()
  })
})

describe('no scripted progression in the active runtime path', () => {
  const runtimeFiles = [
    ['pages', 'OutbreakMapPage.jsx'], ['pages', 'MyAreaPage.jsx'], ['adapters', 'spatialTimelineView.js'],
    ['components', 'MyAreaForecastStrip.jsx'], ['components', 'MyAreaTemporalOutlook.jsx'], ['components', 'MyAreaKpiCards.jsx'],
    ['components', 'MyAreaIntelligencePanel.jsx'], ['components', 'MyAreaOutbreaksInfluencing.jsx'], ['components', 'CorridorPopup.jsx'],
  ]
  it.each(runtimeFiles)('%s/%s uses no fixed dates, scripted arrays, hashes or randomness', (...parts) => {
    const source = readCode(...parts)
    for (const forbidden of [
      'buildPage1ForecastVisualization', 'PAGE1_FORECAST_DATES', 'PAGE1_RISK_PHASE', 'PAGE1_SPREAD_PROGRESS',
      'buildMyAreaPresentationForecast', 'AREA_FORECAST_DATES', 'AREA_DISTRICT_RISK_LEVELS', 'AREA_SPREAD_PROGRESS',
      'stableForecastHash', 'stableAreaCaseHash', 'Math.random', '2026-09-',
    ]) {
      expect(source).not.toContain(forbidden)
    }
  })

  it('both pages fetch the backend timeline with the correct scope', () => {
    expect(read('pages', 'OutbreakMapPage.jsx')).toContain("scope: 'national',")
    const myArea = read('pages', 'MyAreaPage.jsx')
    expect(myArea).toContain("scope: 'district',")
    expect(myArea).toContain('district: authorizedDistrict,')
  })
})

describe('possible new cases on the My Area timeline', () => {
  const possible = (id, seedDay, extra = {}) => ({
    id: `POSSIBLE:${id}`, farm_id: id, longitude: 80.55, latitude: 6.02, seed_day: seedDay, seed_date: `2026-10-${17 + seedDay}`,
    seed_score: 0.45, seed_threshold: 0.4, generation: 1, triggered_by: ['S1'], has_path: true, ...extra,
  })
  const timeline = { possible_new_cases: [possible('F1', 3), possible('F2', 7, { generation: 2, triggered_by: ['POSSIBLE:F1'] }), possible('BAD', 2, { latitude: null })] }

  it('a possible case appears only from its first Elevated day and is flagged new on that day', () => {
    expect(buildPossibleCases(timeline, { day: 0 }).features).toHaveLength(0)
    expect(buildPossibleCases(timeline, { day: 2 }).features).toHaveLength(0) // missing GPS is never drawn
    const day3 = buildPossibleCases(timeline, { day: 3 }).features
    expect(day3.map((f) => f.properties.id)).toEqual(['POSSIBLE:F1'])
    expect(day3[0].properties.newToday).toBe(true)
    expect(day3[0].properties.label).toBe('New outbreak · Day 3')
    const day7 = buildPossibleCases(timeline, { day: 7 }).features
    expect(day7.map((f) => [f.properties.id, f.properties.newToday])).toEqual([['POSSIBLE:F1', false], ['POSSIBLE:F2', true]])
    expect(day7[1].properties.triggeredBy).toEqual(['POSSIBLE:F1'])
    expect(day7[1].properties.generation).toBe(2)
  })

  it('no possible cases without the backend list', () => {
    expect(buildPossibleCases({}, { day: 14 }).features).toHaveLength(0)
    expect(buildPossibleCases(timeline, null).features).toHaveLength(0)
  })
})
