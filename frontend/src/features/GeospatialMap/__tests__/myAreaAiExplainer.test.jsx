// @vitest-environment jsdom
// Task 7: AI Explainer (rule-based) from the page's selected-day inputs, on
// real engine output for FICTIONAL farms (fixtures/spatialTimeline.galleRaster.json).
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ACTION_BASIS_KIND, buildAreaExplainer } from '../adapters/areaExplainer'
import { buildAreaIntelligenceSummary } from '../adapters/areaIntelligenceSummary'
import { findDistrictFeature } from '../adapters/districtGeometry'
import { buildFarmListRows } from '../adapters/myAreaFarmList'
import { buildRiskFieldModel } from '../adapters/riskFieldModel'
import { buildRiskOutlookRows } from '../adapters/riskOutlook'
import { buildMyAreaTimelineView } from '../adapters/spatialTimelineView'
import MyAreaAiExplainer from '../components/MyAreaAiExplainer'
import galle from './fixtures/spatialTimeline.galleRaster.json'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const GALLE = findDistrictFeature(JSON.parse(readFileSync(join(ROOT, 'data', 'sri-lanka-districts-adm2.geojson'), 'utf-8')), 'Galle')
const model = buildRiskFieldModel(galle)
const farm = (farmId, label, coordinates, extra = {}) => ({ farmId, label, coordinates, personallyAssigned: true, outsideDistrict: false, totalAnimals: 20, diseaseCaseCount: 0, ...extra })
const ROSTER = {
  summary: { total: 3, mapped: 2 },
  rows: [
    farm('F1', 'Fictional Case Farm', [80.30, 6.20], { diseaseCaseCount: 2 }),
    farm('F2', 'Fictional Near Farm', [80.33, 6.24]),
    farm('F3', 'Fictional No-GPS Farm', null),
  ],
}
const CASES = { reportCount: 2, uniqueFarmCount: 1, pending: [{}] }
const PLACES = { 'TEST-FICTIONAL-1': 'Fictional Town A', 'TEST-FICTIONAL-2': 'Fictional Town B', 'TEST-FICTIONAL-3': 'Fictional Town C' }
const rows = buildRiskOutlookRows(model, GALLE, { farms: ROSTER.rows.filter((r) => r.coordinates) })

function explainerOn(day, extra = {}) {
  const view = buildMyAreaTimelineView(galle, day, 'Galle')
  const farmList = buildFarmListRows({ roster: ROSTER, model, dayIndex: day })
  const summary = buildAreaIntelligenceSummary({ view, frame: view.frame, row: rows[day], roster: ROSTER, caseIntel: CASES })
  return buildAreaExplainer({
    districtName: 'Galle', disease: 'LSD', diseaseShortLabel: 'LSD', futureMode: true, timelineOk: true, summary,
    influences: view.influences, farmList, caseIntel: CASES, locationFor: (i) => ({ place: PLACES[i.sourceId] ?? null }), asOf: galle.as_of, ...extra,
  })
}
const DECISION = /must (quarantine|vaccinate|cull)|impose (a )?quarantine|\bcull\b|movement ban|diagnos(is|ed) (as|with)/i
const unnegated = (text) => text.replace(/not (an )?infect(ed|ion)|forecast of infection|predicted infections?/gi, '')

describe('AI Explainer content (selected-day inputs only)', () => {
  it('Day 0: district risk, the sources behind it, potentially affected farms, decisions left to authority', () => {
    const { text, paragraphs } = explainerOn(0)
    expect(paragraphs[0]).toMatch(new RegExp(`^On .* \\(Day 0\\) Galle is (HIGH|ELEVATED|MODERATE|LOW): peak relative score ${rows[0].maxScore.toFixed(2)} \\(not a probability\\)`))
    expect(text).toContain('3 verified sources influence the district — 2 inside (Fictional Town A and Fictional Town B) and 1 outside (Fictional Town C, from Day 3)')
    expect(text).toContain('Fictional Near Farm) is potentially affected on this day')
    expect(text).toContain('It is not infected.')
    expect(text).toContain('Fictional Case Farm is also on the surface and already has verified cases')
    expect(text).toContain('does not justify quarantine or vaccinating a specific farm')
    expect(unnegated(text)).not.toMatch(/infect/i)
    expect(text).not.toMatch(DECISION)
  })

  it('the outside source is named as arrived only from its first influence day', () => {
    expect(explainerOn(2).text).toContain('Fictional Town C, from Day 3')
    expect(explainerOn(5).text).toContain('1 outside (Fictional Town C)')
  })

  it('actions A-E carry their basis; vaccination and movement control stay advisory', () => {
    const { actions } = explainerOn(0)
    expect(actions.map((g) => g.id)).toEqual(['A', 'B', 'C', 'D', 'E'])
    expect(actions[0].items[0]).toMatchObject({ title: 'Visit potentially affected farms', basis: ACTION_BASIS_KIND.MODEL, farms: ['Fictional Near Farm'] })
    expect(actions[0].items.some((i) => i.title === 'Watch sources approaching from outside' && i.why.includes('Day 3'))).toBe(true)
    expect(actions[1].items[0]).toMatchObject({ basis: ACTION_BASIS_KIND.REPORTS, farms: ['Fictional Case Farm'] })
    expect(actions[2].items.map((i) => i.title)).toContain('Risk zones are not quarantine zones')
    expect(actions[3].items[0].basis).toBe(ACTION_BASIS_KIND.GUIDANCE)
    expect(actions[4].items.map((i) => i.title)).toEqual(['Review 1 pending report', 'Update farm locations', 'Encourage early reporting'])
    expect(JSON.stringify(actions)).not.toMatch(DECISION)
  })

  it('limitations follow the day; Verified Cases mode and a pending model are summarised honestly', () => {
    expect(explainerOn(3).limitations.some((l) => l.includes('exploratory'))).toBe(false)
    expect(explainerOn(10).limitations.some((l) => l.includes('exploratory'))).toBe(true)
    expect(explainerOn(0).limitations).toContain('1 farm without GPS cannot be evaluated.')
    expect(explainerOn(0, { futureMode: false }).text).toBe('Galle has 2 vet-verified LSD reports at 1 farm, and 1 report still pending verification. These are recorded reports only; nothing here is predicted.')
    expect(explainerOn(0, { timelineOk: false, statusText: 'Waiting for the backend spatial timeline.' }).text).toBe('Waiting for the backend spatial timeline.')
  })
})

describe('AI Explainer card and page layout', () => {
  it('renders the title and the collapsed suggested-action groups only (summary, limitations and footer trimmed)', () => {
    const { container } = render(<MyAreaAiExplainer explainer={explainerOn(0)} />)
    expect(container.textContent).toContain('AI Explainer')
    expect(container.textContent).toContain('ADVISORY')
    expect(container.querySelectorAll('[data-action-group]')).toHaveLength(5)
    expect([...container.querySelectorAll('[data-action-group]')].every((d) => !d.open)).toBe(true)
    expect(container.querySelector('[data-explainer="summary"]')).toBeNull()
    expect(container.querySelector('[data-explainer="limitations"]')).toBeNull()
  })

  it('page: map column first, compact panel beside it, farms + explainer stacked on narrow and side by side on wide screens', () => {
    const page = readFileSync(join(ROOT, 'pages', 'MyAreaPage.jsx'), 'utf-8')
    expect(page).toContain('lg:grid-cols-[minmax(0,2.15fr)_minmax(290px,0.85fr)]')
    expect(page).toContain('className="grid grid-cols-1 items-start gap-4 xl:grid-cols-2" aria-label="Area explanation and actions"')
    const row = page.slice(page.indexOf('aria-label="Area explanation and actions"'))
    expect(row.indexOf('<MyAreaFarmList')).toBeLessThan(row.indexOf('<MyAreaAiExplainer'))
    expect(page).toContain('farmsElsewhere')
  })
})
