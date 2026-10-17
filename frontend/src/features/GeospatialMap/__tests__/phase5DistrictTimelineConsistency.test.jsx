import { cleanup, render, screen, within, waitFor } from '@testing-library/react'
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import {
  areaPlateauStartIndex,
  buildMyAreaTimelineView,
  buildNationalTimelineLayers,
  HORIZON_STATUS,
  plateauNote,
  plateauStartIndex,
} from '../adapters/spatialTimelineView'
import galleTimeline from './fixtures/spatialTimeline.galle.json'
import kandyTimeline from './fixtures/spatialTimeline.kandy.json'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'
import nationalTimeline from './fixtures/spatialTimeline.national.json'

// Fixtures: real backend output (router -> service -> engine) for FICTIONAL
// test farms only -- see fixtures/README_SPATIAL_TIMELINE_FIXTURES.md.
const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const realDistrictsText = readFileSync(join(FEATURE_ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8')
const DISTRICTS = [['Matara', mataraTimeline], ['Galle', galleTimeline], ['Kandy', kandyTimeline]]
const TIER_RANK = ['lower', 'moderate', 'high', 'highest']
const staticZoneGeometries = (timeline) => timeline.risk_zones.features.slice()
  .sort((a, b) => TIER_RANK.indexOf(a.properties.tier) - TIER_RANK.indexOf(b.properties.tier)).map((f) => f.geometry)
// Order-independent geometry comparison (each zone is one backend polygon).
const geometrySet = (geometries) => geometries.map((g) => JSON.stringify(g)).sort()
const reachZoneGeometries = (frame) => (frame.reach_limited_risk_zones?.features ?? []).map((f) => f.geometry)

describe('Day 0-14: every view value is the selected backend frame', () => {
  it.each(DISTRICTS)('%s: date, sources, zones, reach, corridors, chart, summary and status agree on every frame', (district, timeline) => {
    expect(timeline.frames).toHaveLength(15)
    for (let index = 0; index <= 14; index += 1) {
      const frame = timeline.frames[index]
      const view = buildMyAreaTimelineView(timeline, index, district)
      const summary = frame.district_summaries.find((s) => s.district === district)
      // Day 0 is the as-of context: no reach yet, so the backend sends no district summary.
      if (index === 0) {
        expect(frame.district_summaries).toEqual([])
        expect(view.areaWithinReachKm2).toBeNull()
        expect(view.outlook[0].areaKm2).toBe(0)
        // The static relative-score tiers (faint context) and direction
        // indicators exist from Day 0; no reach yet, so no bright zone and no
        // reach outline (reach starts on Day 1).
        expect(geometrySet(view.riskZones.features.map((f) => f.geometry))).toEqual(geometrySet(reachZoneGeometries(frame)))
        expect(geometrySet(view.contextZones.features.map((f) => f.geometry))).toEqual(geometrySet(staticZoneGeometries(timeline)))
        expect(view.paths.features).toHaveLength(0) // direction appears with the timeline (Day 1+)
        continue
      }
      expect(view.date).toBe(frame.date)
      expect(view.day).toBe(index)
      expect(view.horizonStatus).toBe(frame.horizon_status)
      expect(view.horizonStatus).toBe(index === 0 ? HORIZON_STATUS.AS_OF : index <= 7 ? HORIZON_STATUS.EVALUATED : HORIZON_STATUS.EXPLORATORY)
      expect(view.reachKm).toBe(index === 0 ? null : frame.reach.nominal_reach_km)
      expect(view.areaWithinReachKm2).toBe(summary.area_within_reach_km2)
      expect(view.outlook[index].areaKm2).toBe(summary.area_within_reach_km2)
      expect(view.outlook[index].tier).toBe(summary.highest_tier_within_reach)
      expect(view.districtTier).toBe(summary.highest_tier_within_reach)
      // Context: the static tiers on every day plus that day's reach outline.
      // Bright zones: the backend's scored land within that day's reach.
      expect(geometrySet(view.riskZones.features.map((f) => f.geometry))).toEqual(geometrySet(reachZoneGeometries(frame)))
      expect(geometrySet(view.contextZones.features.map((f) => f.geometry))).toEqual(geometrySet([...staticZoneGeometries(timeline), frame.reach_envelope]))
      const active = new Set(frame.active_source_ids)
      expect(view.paths.features).toHaveLength(frame.source_corridors.filter((c) => Number.isFinite(c.bearing_deg)).length)
      // Each date draws its own backend corridor (grows with the reach).
      expect(view.paths.features.map((f) => f.geometry)).toEqual(frame.source_corridors.filter((c) => Number.isFinite(c.bearing_deg)).map((c) => c.geometry))
      for (const path of view.paths.features) {
        expect(active.has(path.properties.sourceId)).toBe(true)
        expect(path.properties.lengthKm).toBe(frame.source_corridors.find((c) => c.source_id === path.properties.sourceId).length_km)
        expect(path.properties.date).toBe(frame.date)
      }
      expect(view.influences.map((i) => i.sourceId).sort()).toEqual(timeline.sources.map((s) => s.source_id).sort())
    }
  })

  it('national layers follow the same frames (dates, zones, corridors)', () => {
    for (let index = 0; index <= 14; index += 1) {
      const layers = buildNationalTimelineLayers(nationalTimeline, index)
      const frame = nationalTimeline.frames[index]
      expect(layers.date).toBe(frame.date)
      expect(layers.riskZones.features.map((f) => f.geometry)).toEqual(staticZoneGeometries(nationalTimeline))
      expect(layers.contextZones.features.map((f) => f.geometry)).toEqual(index === 0 ? [] : [frame.reach_envelope])
      const own = index === 0 ? [] : frame.source_corridors.filter((c) => Number.isFinite(c.bearing_deg))
      expect(layers.paths.features.map((f) => f.geometry)).toEqual(own.map((c) => c.geometry))
    }
  })
})

describe('district isolation', () => {
  it('each district snapshot only carries its own district and sources', () => {
    for (const [district, timeline] of DISTRICTS) {
      expect(timeline.scope.district).toBe(district)
      for (const frame of timeline.frames.slice(1)) expect(frame.district_summaries.map((s) => s.district)).toEqual([district])
      const others = DISTRICTS.filter(([name]) => name !== district).map(([name]) => name.toUpperCase())
      const text = JSON.stringify(timeline.sources)
      for (const other of others) expect(text).not.toContain(other)
    }
  })

  it('reading a snapshot with another district name never borrows its numbers', () => {
    const view = buildMyAreaTimelineView(galleTimeline, 9, 'Matara')
    expect(view.areaWithinReachKm2).toBeNull()
    expect(view.districtRisk).toBeNull()
    expect(view.outlook.every((row) => row.areaKm2 === 0 && row.tier === null)).toBe(true)
  })
})

describe('two different plateaus are labelled separately and honestly', () => {
  it('the reach covers the scored area from Day 7; the district area within reach keeps growing until its own plateau', () => {
    expect(DISTRICTS.map(([, t]) => plateauStartIndex(t))).toEqual([7, 7, 7])
    const areaPlateaus = DISTRICTS.map(([d, t]) => areaPlateauStartIndex(buildMyAreaTimelineView(t, 0, d).outlook))
    expect(areaPlateaus).toEqual([10, 10, 11])
    // Between the two plateaus the zone note is shown but the area is still changing.
    const day8 = buildMyAreaTimelineView(mataraTimeline, 8, 'Matara')
    const day9 = buildMyAreaTimelineView(mataraTimeline, 9, 'Matara')
    expect(day8.plateauNote).toBe('Reach covers scored area from Day 7')
    expect(day9.areaWithinReachKm2).toBeGreaterThan(day8.areaWithinReachKm2)
    expect(plateauNote(mataraTimeline, 6)).toBeNull()
    expect(areaPlateauStartIndex([{ areaKm2: 1, tier: 'high' }, { areaKm2: 2, tier: 'high' }, { areaKm2: 3, tier: 'high' }])).toBeNull()
  })
})

describe('no scripted forecast reaches the runtime path', () => {
  // Live code takes colours, playback intervals and the case normaliser from
  // `timelinePresentation.js`; importing anything from the legacy scripted
  // modules would ship their fixed date/risk arrays in the production bundle.
  const LEGACY_MODULES = ['page1ForecastVisualization', 'myAreaPresentationForecast']
  const files = ['components', 'pages', 'context', 'api'].flatMap((dir) => readdirSync(join(FEATURE_ROOT, dir)).filter((f) => /\.jsx?$/.test(f)).map((f) => [dir, f]))
  it.each(files)('%s/%s never imports the legacy presentation modules', (dir, file) => {
    const source = readFileSync(join(FEATURE_ROOT, dir, file), 'utf-8')
    for (const module of LEGACY_MODULES) {
      expect(source).not.toMatch(new RegExp(`from\\s*'[./]*(adapters/)?${module}'`))
    }
  })
  it('the shared presentation module carries no dates, spread arrays or hashes', () => {
    const source = readFileSync(join(FEATURE_ROOT, 'adapters', 'timelinePresentation.js'), 'utf-8')
    for (const forbidden of ['2026-', 'SPREAD_PROGRESS', 'FORECAST_DATES', 'RISK_LEVELS', 'Hash', 'Math.random', 'fetch(']) {
      expect(source).not.toContain(forbidden)
    }
  })
})

function jsonResponse(body) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

function fictionalContext(district, timeline) {
  const farms = timeline.sources.map((source) => ({
    farm_id: source.farm_id, latitude: source.latitude, longitude: source.longitude, location_status: 'VALID',
    location_district: district, total_animals: 10, personally_assigned: false,
  }))
  const contexts = timeline.sources.map((source) => ({
    case_id: source.member_record_ids[0], farm_id: source.farm_id, disease: 'LSD', semantic_class: 'VERIFIED_CLINICAL_CONTEXT',
    verification_time: `${source.observation_date} 09:00:00`, timestamp_basis: 'VERIFICATION_TIME',
  }))
  return {
    status: 'OK', vet: { role: 'vet' }, farms: [], clinical_contexts: [], vet_district: district, surveillance_status: 'DISTRICT_RESOLVED',
    surveillance_farms: farms, surveillance_contexts: contexts,
  }
}

describe('My Area page follows the logged-in vet district (Galle, Kandy) with no Matara leakage', () => {
  let GeospatialProvider
  let MyAreaPage
  beforeAll(async () => {
    if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
    ;({ GeospatialProvider } = await import('../context/GeospatialContext'))
    MyAreaPage = (await import('../pages/MyAreaPage')).default
  })
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  function mock(district, timeline) {
    global.fetch = vi.fn((url) => {
      const target = String(url)
      if (target.includes('sri-lanka-districts-adm2')) return Promise.resolve(new Response(realDistrictsText, { status: 200 }))
      if (target.includes('/operational-context')) return jsonResponse(fictionalContext(district, timeline))
      if (target.includes('/spatial-timeline')) return jsonResponse(timeline)
      return Promise.reject(new Error(`unmocked request in test: ${target}`))
    })
  }

  it.each([['Galle', galleTimeline], ['Kandy', kandyTimeline]])('%s vet: district-scoped request, own sources, synced panels on Day 1/4/7/10/14', async (district, timeline) => {
    mock(district, timeline)
    render(<MemoryRouter><GeospatialProvider><MyAreaPage /></GeospatialProvider></MemoryRouter>)
    expect(within(await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })).getAllByRole('button')).toHaveLength(15)
    expect(screen.getByText(`Future Risk Outlook — ${district}`)).toBeTruthy()
    const call = global.fetch.mock.calls.find(([url]) => String(url).includes('/spatial-timeline'))
    expect(new URL(String(call[0]), 'http://localhost').searchParams.get('district')).toBe(district)
    const panel = screen.getByLabelText('Area Intelligence')
    for (const day of [1, 4, 7, 10, 14]) {
      const frame = timeline.frames[day]
      const label = new Date(`${frame.date}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      screen.getByRole('button', { name: `Select ${label}` }).click()
      // Area Intelligence reads the same frame (Task 5 summary rows).
      expect(await within(panel).findByText(`${day + 1} of 15 · Day ${day}`)).toBeTruthy()
      // Coloured land (the day's risk raster inside the district): same value on the selected chart bar and in the panel.
      const bar = screen.getByRole('group', { name: /share of the district coloured by the risk surface/ }).querySelector('[aria-current="date"]')
      const area = bar.getAttribute('aria-label').match(/([\d,]+ km²)/)[1]
      expect(panel.querySelector('[data-value="district-area"]').textContent).toContain(area)
    }
    expect(document.body.textContent).not.toMatch(/matara/i)
    expect(document.body.textContent).toContain(timeline.sources[0].member_record_ids[0])
  })

  it.each([['Galle', galleTimeline], ['Kandy', kandyTimeline]])('%s vet: Future Impact offers Cases / Risk Zones / Trajectory; switching keeps the selected day', async (district, timeline) => {
    mock(district, timeline)
    render(<MemoryRouter><GeospatialProvider><MyAreaPage /></GeospatialProvider></MemoryRouter>)
    expect(within(await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })).getAllByRole('button')).toHaveLength(15)
    const views = screen.getByRole('group', { name: 'Future Impact view' })
    const [cases, risk, trajectory] = ['Cases', 'Risk Zones', 'Trajectory'].map((name) => within(views).getByRole('button', { name }))
    expect(risk.getAttribute('aria-pressed')).toBe('true')
    screen.getByRole('button', { name: /^Select 20 Oct 2026$/ }).click()
    trajectory.click()
    await waitFor(() => expect(trajectory.getAttribute('aria-pressed')).toBe('true'))
    const selectedDay = () => screen.getByRole('group', { name: /share of the district coloured by the risk surface/ }).querySelector('[aria-current="date"]').getAttribute('aria-label')
    expect(selectedDay()).toMatch(/^20 Oct 2026/)
    cases.click()
    await waitFor(() => expect(cases.getAttribute('aria-pressed')).toBe('true'))
    expect(selectedDay()).toMatch(/^20 Oct 2026/) // switching views keeps the selected day
    // Verified Cases mode has no Future Impact view switch.
    screen.getByRole('button', { name: 'Verified cases' }).click()
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Future Impact view' })).toBeNull())
  })

  it('selecting a chart bar moves the whole page (map/strip/panel) to that frame', async () => {
    mock('Galle', galleTimeline)
    render(<MemoryRouter><GeospatialProvider><MyAreaPage /></GeospatialProvider></MemoryRouter>)
    expect(within(await screen.findByRole('group', { name: /share of the district coloured by the risk surface/ })).getAllByRole('button')).toHaveLength(15)
    const chart = screen.getByRole('group', { name: /Galle: share of the district coloured by the risk surface/ })
    const bars = within(chart).getAllByRole('button')
    expect(bars).toHaveLength(15)
    bars[10].click()
    const panel = screen.getByLabelText('Area Intelligence')
    expect(await within(panel).findByText('11 of 15 · Day 10')).toBeTruthy()
    expect(screen.getAllByText('Reach covers scored area from Day 7').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /^Select 23 Oct 2026$/ }).getAttribute('aria-current')).toBe('date')
  })
})
