// @vitest-environment jsdom
// Task 4: "Outbreaks influencing my area" cards, from real engine output for
// three FICTIONAL farms (Galle district view; fixtures/spatialTimeline.galleRaster.json):
// two sources inside Galle and one 10 km outside whose first modelled
// influence on Galle land is Day 3 (no direction: isolated case).
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { INFLUENCE_KIND, buildMyAreaTimelineView } from '../adapters/spatialTimelineView'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import galle from './fixtures/spatialTimeline.galleRaster.json'

const clone = (value) => JSON.parse(JSON.stringify(value))
const cardsOn = (timeline, day) => Object.fromEntries(buildMyAreaTimelineView(timeline, day, 'Galle').influences.map((i) => [i.sourceId, i.card]))
const EXTERNAL = 'TEST-FICTIONAL-3'

/** The external source first influences Galle on Day 13 (scores zeroed before). */
function firstInfluenceOnDay13() {
  const timeline = clone(galle)
  const entry = timeline.district_influence.sources.find((e) => e.source_id === EXTERNAL)
  entry.first_influence_day = 13
  for (const d of entry.by_day) if (d.day < 13) Object.assign(d, { area_km2: 0, max_score: null })
  return timeline
}

describe('influence card model (backend district influence per day)', () => {
  it('local sources are LOCAL SOURCE, the outside one APPROACHING AREA, with distance, direction and age', () => {
    const day0 = cardsOn(galle, 0)
    expect(day0['TEST-FICTIONAL-1'].kind).toBe(INFLUENCE_KIND.LOCAL)
    expect(day0['TEST-FICTIONAL-2'].kind).toBe(INFLUENCE_KIND.LOCAL)
    expect(day0[EXTERNAL].kind).toBe(INFLUENCE_KIND.APPROACHING)
    expect(day0['TEST-FICTIONAL-1'].whereText).toBe('Inside Galle (local source)')
    expect(day0['TEST-FICTIONAL-1'].dayStatusText).toBe('Elevated influence on Day 0')
    expect(day0['TEST-FICTIONAL-1'].directionText).toBe('heading SW 217°') // the heading it starts on
    expect(day0[EXTERNAL].whereText).toBe('10.0 km from Galle')
    expect(day0[EXTERNAL].directionText).toBe('direction unavailable')
    expect(day0[EXTERNAL].ageDays).toBe(0)
    expect(day0[EXTERNAL].firstInfluenceDay).toBe(3)
    expect(day0[EXTERNAL].series).toHaveLength(15)
  })

  it('the selected day changes the status; the direction is that day\'s path heading', () => {
    expect(cardsOn(galle, 2)[EXTERNAL]).toMatchObject({ influencingToday: false, dayStatusText: 'reaches the district on Day 3' })
    expect(cardsOn(galle, 3)[EXTERNAL]).toMatchObject({ influencingToday: true, dayStatusText: 'Low influence on Day 3' })
    expect(cardsOn(galle, 13)[EXTERNAL].dayStatusText).toBe('Moderate influence on Day 13')
    const day3 = galle.frames[3].source_paths.find((p) => p.source_id === 'TEST-FICTIONAL-1').front_bearing_deg
    expect(cardsOn(galle, 3)['TEST-FICTIONAL-1'].directionText).toBe(`heading SW ${Math.round(day3)}°`)
  })

  it('a source first influencing on Day 13 is never shown as arrived on Days 0-12', () => {
    const timeline = firstInfluenceOnDay13()
    for (let day = 0; day <= 12; day += 1) {
      const card = cardsOn(timeline, day)[EXTERNAL]
      expect(card.influencingToday).toBe(false)
      expect(card.dayStatusText).toBe('reaches the district on Day 13')
      expect(card.series.slice(0, 13).every((v) => v === 0)).toBe(true)
    }
    expect(cardsOn(timeline, 13)[EXTERNAL].influencingToday).toBe(true)
    expect(cardsOn(timeline, 13)[EXTERNAL].kind).toBe(INFLUENCE_KIND.APPROACHING)
  })

  it('names the possible new cases a source triggers, before and after their day', () => {
    const timeline = clone(galle)
    timeline.possible_new_cases = [{ id: 'POSSIBLE:F9', farm_id: 'F9', latitude: 6.1, longitude: 80.3, seed_day: 5, seed_score: 0.42, generation: 1, triggered_by: [EXTERNAL] }]
    expect(cardsOn(timeline, 4)[EXTERNAL].possibleText).toBe('Could start a new outbreak in Galle on Day 5 (modelled)')
    expect(cardsOn(timeline, 6)[EXTERNAL].possibleText).toBe('Started a new outbreak in Galle on Day 5 (modelled)')
    expect(cardsOn(timeline, 6)['TEST-FICTIONAL-1'].possibleText).toBeNull()
  })

  it('uses the real case number when the backend sends one, and no model data without district influence', () => {
    const timeline = clone(galle)
    timeline.sources[0].case_refs = ['REC-FICTIONAL-9']
    expect(cardsOn(timeline, 0)['TEST-FICTIONAL-1'].caseRef).toBe('REC-FICTIONAL-9')
    expect(cardsOn(timeline, 0)['TEST-FICTIONAL-2'].caseRef).toBeNull()
    delete timeline.district_influence
    const view = buildMyAreaTimelineView(timeline, 0, 'Galle')
    expect(view.influenceDataAvailable).toBe(false)
    expect(view.influences.every((i) => i.card.kind === null && i.card.modelData === false)).toBe(true)
  })
})

describe('Outbreaks influencing my area (component)', () => {
  const props = (timeline, day, extra = {}) => {
    const view = buildMyAreaTimelineView(timeline, day, 'Galle')
    return { influences: view.influences, day, districtLabel: 'Galle', influenceDataAvailable: view.influenceDataAvailable, onFocusCase: vi.fn(), ...extra }
  }

  it('renders the two card kinds with place, sentence, sparkline and View on Map focusing that source', () => {
    const onViewOnMap = vi.fn()
    const { container } = render(<MyAreaOutbreaksInfluencing {...props(galle, 0, { onViewOnMap, locationFor: (i) => ({ place: i.sourceId === EXTERNAL ? 'Fictional Town' : null, district: i.sourceId === EXTERNAL ? 'Matara' : 'Galle' }) })} />)
    expect(screen.getAllByText(INFLUENCE_KIND.LOCAL)).toHaveLength(2)
    expect(screen.getAllByText(INFLUENCE_KIND.APPROACHING)).toHaveLength(1)
    expect(screen.getByText('10.0 km from Galle · direction unavailable · reaches the district on Day 3.')).toBeTruthy()
    expect(screen.getByText('· Fictional Town, Matara')).toBeTruthy()
    expect(container.querySelectorAll('[data-chart="influence-series"]')).toHaveLength(3)
    const external = [...container.querySelectorAll('li')].find((li) => li.dataset.kind === INFLUENCE_KIND.APPROACHING)
    fireEvent.click(external.querySelector('button'))
    expect(onViewOnMap).toHaveBeenCalledWith(expect.objectContaining({ sourceId: EXTERNAL }))
  })

  it('a nearby source with no modelled influence is not listed but counted', () => {
    const timeline = clone(galle)
    const entry = timeline.district_influence.sources.find((e) => e.source_id === EXTERNAL)
    entry.first_influence_day = null
    for (const d of entry.by_day) Object.assign(d, { area_km2: 0, max_score: null })
    const { container } = render(<MyAreaOutbreaksInfluencing {...props(timeline, 5)} />)
    expect(screen.queryByText(INFLUENCE_KIND.APPROACHING)).toBeNull()
    expect(container.querySelector('[data-state="nearby-no-influence"]').textContent).toContain('1 nearby source')
  })

  it('handles no sources, a pending model and a snapshot without influence data', () => {
    const { container, rerender } = render(<MyAreaOutbreaksInfluencing influences={[]} districtLabel="Galle" />)
    expect(container.querySelector('[data-state="no-influence"]').textContent).toContain('No eligible source reaches Galle')
    rerender(<MyAreaOutbreaksInfluencing influences={[]} districtLabel="Galle" statusText="Waiting for the backend spatial timeline." />)
    expect(container.querySelector('[data-state="model-status"]')).toBeTruthy()
    const timeline = clone(galle)
    delete timeline.district_influence
    rerender(<MyAreaOutbreaksInfluencing {...props(timeline, 0)} />)
    expect(container.querySelector('[data-state="insufficient-model-data"]')).toBeTruthy()
    expect(screen.getAllByText('NO MODEL DATA')).toHaveLength(3)
  })
})

describe('source district from the real polygons', () => {
  it('names the district containing the GPS and nothing for a point in none', async () => {
    const { districtNameAtPoint } = await import('../adapters/districtGeometry')
    const box = (name, w, s) => ({ type: 'Feature', properties: { shapeName: name }, geometry: { type: 'Polygon', coordinates: [[[w, s], [w + 1, s], [w + 1, s + 1], [w, s + 1], [w, s]]] } })
    const collection = { type: 'FeatureCollection', features: [box('Testshire District', 80, 6), box('Otherland District', 81, 6)] }
    expect(districtNameAtPoint(collection, [80.5, 6.5])).toBe('Testshire')
    expect(districtNameAtPoint(collection, [81.5, 6.5])).toBe('Otherland')
    expect(districtNameAtPoint(collection, [79.5, 6.5])).toBeNull()
    expect(districtNameAtPoint(null, [80.5, 6.5])).toBeNull()
  })
})

describe('privacy-reduced sources (another vet\'s case)', () => {
  it('show only the one-way source key, never a record id, using the backend detail_access value', () => {
    const timeline = clone(galle)
    timeline.sources[2].detail_access = 'PRIVACY_REDUCED_EXTERNAL_FARM'
    timeline.sources[2].source_id = 'OP:LSD:Fda372bb0123456789'
    timeline.district_influence.sources[2].source_id = 'OP:LSD:Fda372bb0123456789'
    const view = buildMyAreaTimelineView(timeline, 0, 'Galle')
    expect(view.influences.find((i) => i.sourceId.startsWith('OP:')).privacyReduced).toBe(true)
    render(<MyAreaOutbreaksInfluencing influences={view.influences} day={0} districtLabel="Galle" onFocusCase={vi.fn()} />)
    expect(screen.getByText('OP:LSD:Fda372bb')).toBeTruthy()
    expect(screen.queryByText('case-3')).toBeNull()
    expect(screen.getByText('case-1')).toBeTruthy() // the vet's own case: its record id
  })
})
