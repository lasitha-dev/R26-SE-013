// @vitest-environment jsdom
// Task 5: Area Intelligence + Future Risk Outlook read the SAME selected
// backend frame as the map. Real engine output for three FICTIONAL farms,
// Galle district view (fixtures/spatialTimeline.galleRaster.json), against
// the real Galle ADM2 polygon the app ships.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { buildAreaIntelligenceSummary } from '../adapters/areaIntelligenceSummary'
import { findDistrictFeature } from '../adapters/districtGeometry'
import { bandOfScore, buildRiskFieldModel } from '../adapters/riskFieldModel'
import { buildRiskOutlookRows } from '../adapters/riskOutlook'
import { buildMyAreaTimelineView } from '../adapters/spatialTimelineView'
import MyAreaIntelligencePanel from '../components/MyAreaIntelligencePanel'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'
import galle from './fixtures/spatialTimeline.galleRaster.json'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const districts = JSON.parse(readFileSync(join(ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8'))
const GALLE = findDistrictFeature(districts, 'Galle')
const S0 = 3.946
const CELL_DIAGONAL_KM = Math.hypot(0.015 * 110.6, 0.015 * 110.6)
// FICTIONAL district farms: one on the first case (40 animals), one without
// a herd size next to the second case, one far inland (outside colour).
const FARMS = [
  { coordinates: [80.30, 6.20], totalAnimals: 40 },
  { coordinates: [80.33, 6.24], totalAnimals: null },
  { coordinates: [80.42, 6.40], totalAnimals: 12 },
]
const ROSTER = { summary: { total: 4, mapped: 3, withoutGps: 1 }, rows: [] }
const CASES = { reportCount: 3, uniqueFarmCount: 2, pending: [] }

const model = buildRiskFieldModel(galle)
const rows = buildRiskOutlookRows(model, GALLE, { farms: FARMS })
const summaryOn = (day) => {
  const view = buildMyAreaTimelineView(galle, day, 'Galle')
  return { view, row: rows[view.activeIndex], summary: buildAreaIntelligenceSummary({ view, frame: view.frame, row: rows[view.activeIndex], roster: ROSTER, caseIntel: CASES }) }
}

describe('Area Intelligence metrics follow the selected backend frame', () => {
  it.each([0, 3, 7, 13, 14])('Day %i: frame, score, area, sources and farms come from that one frame', (day) => {
    const { view, row, summary } = summaryOn(day)
    expect(summary.frame).toMatchObject({ index: day, count: 15, day, date: galle.frames[day].date })
    expect(row.day).toBe(day)
    // Peak score / category = the day's raster on district land, and never
    // below any single case's own peak there (backend district influence).
    const ownPeaks = galle.district_influence.sources.map((e) => e.by_day[day]).filter((d) => d.area_km2 > 0).map((d) => d.max_score)
    expect(summary.risk.peakScore).toBe(row.maxScore)
    expect(summary.risk.peakScore + 1e-6).toBeGreaterThanOrEqual(Math.max(...ownPeaks) - 0.01)
    expect(summary.risk.band).toBe(bandOfScore(row.maxScore, model.bands))
    // Area: km² and share of the district are one quantity, one denominator.
    expect(summary.area.share).toBeCloseTo(summary.area.coloredKm2 / summary.area.districtKm2, 9)
    // Sources: the influence cards' kinds (2 local, 1 approaching from Day 3).
    expect(summary.sources).toMatchObject({ local: 2, external: 1, externalReachingNow: day >= 3 ? 1 : 0, basis: 'MODELLED_INFLUENCE' })
    // Spread: the day's backend paths.
    const paths = view.frame.source_paths.filter((p) => p.geometry && !p.possible_new_case)
    expect(summary.spread.activePaths).toBe(paths.length)
    // Farms on coloured land: the one on the first case is always counted.
    expect(summary.affected.farms).toBeGreaterThanOrEqual(1)
    expect(summary.affected.animals).toBe(rows[day].monitoredAnimals)
    expect(summary.farms).toEqual({ mapped: 3, total: 4 })
  })

  it('Day 0 has colour but no spread: explained as position uncertainty, never as a 0 km reach', () => {
    const { summary } = summaryOn(0)
    expect(summary.spread.activePaths).toBe(0)
    expect(summary.spread.travelledKm).toBe(0)
    expect(summary.spread.nominalReachKm).toBeNull()
    expect(summary.area.coloredKm2).toBeGreaterThan(0)
    expect(summary.spread.colourExtentKm).toBeGreaterThan(0)
    expect(summary.spread.colourExtentKm).toBeLessThanOrEqual(3.5 * 2.5 + CELL_DIAGONAL_KM)
  })

  it('travelled distance and colour extent stay within the model budget on every day', () => {
    for (let day = 1; day <= 14; day += 1) {
      const { summary } = summaryOn(day)
      expect(summary.spread.travelledKm).toBeLessThanOrEqual(Math.min(S0 * day, 25) + 0.01) // backend rounds to 1 m
      expect(summary.spread.nominalReachKm).toBeCloseTo(S0 * day, 0)
      expect(summary.spread.colourExtentKm).toBeLessThanOrEqual(46.3 + CELL_DIAGONAL_KM)
    }
  })
})

describe('panel and outlook render the selected frame without mixing quantities', () => {
  it('the panel rows show that frame', () => {
    const { summary } = summaryOn(3)
    const { container } = render(<MyAreaIntelligencePanel authorizedDistrict="Galle" mode="FUTURE_IMPACT" timelineOk diseaseShortLabel="LSD" asOf={galle.as_of} activeDate={galle.frames[3].date} activeDay={3} areaSummary={summary} />)
    const value = (name) => container.querySelector(`[data-value="${name}"]`)?.textContent
    expect(value('farm-coordinates')).toBe('3 of 4 mapped')
    expect(value('current-frame')).toBe('4 of 15 · Day 3')
    expect(value('peak-score')).toBe(summary.risk.peakScore.toFixed(2))
    expect(value('district-area')).toBe(`${Math.round(summary.area.share * 100)}% · ${Math.round(summary.area.coloredKm2).toLocaleString('en-US')} km²`)
    expect(value('influencing-origins')).toBe('3')
    expect(value('affected-farms')).toContain(`${summary.affected.animals} animals`)
  })

  it('outlook: bars carry area only and fill up to the selected day', () => {
    const { container } = render(<MyAreaTemporalOutlook areaLabel="Galle" activeIndex={7} onSelectIndex={() => {}} rows={rows} />)
    expect(container.querySelector('[title$="on coloured land"]')).toBeNull() // no farm badge on a bar
    expect(container.querySelector('[aria-current="date"]').getAttribute('aria-label')).toContain(`(${(rows[7].coloredShare * 100).toFixed(rows[7].coloredShare > 0 && rows[7].coloredShare < 0.1 ? 1 : 0)}% of Galle)`)
    const revealed = [...container.querySelectorAll('[data-bar="coloured-share"]')].map((bar) => bar.dataset.revealed)
    expect(revealed).toEqual(rows.map((_, i) => (i <= 7 ? 'true' : 'false')))
  })
})
