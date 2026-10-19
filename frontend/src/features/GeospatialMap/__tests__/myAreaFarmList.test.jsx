// @vitest-environment jsdom
// Task 6: Farms in my district. Statuses from the selected day's backend
// risk raster (fixtures/spatialTimeline.galleRaster.json: engine output for
// FICTIONAL farms, Galle view) at each farm's GPS. All farms are FICTIONAL.
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { buildFarmListRows, FARM_LIST_STATUS, validAnimalCount } from '../adapters/myAreaFarmList'
import { buildRiskFieldModel, rasterScoreAt } from '../adapters/riskFieldModel'
import MyAreaFarmList from '../components/MyAreaFarmList'
import galle from './fixtures/spatialTimeline.galleRaster.json'

const model = buildRiskFieldModel(galle)
const onSurface = (day, [lon, lat]) => rasterScoreAt(model.rasterFor(day), model.grid, lon, lat) >= model.grid.min_score
// A point the surface first reaches after Day 1, found on the real model
// (east of the first case, along the coast-inland line).
const LATER = (() => {
  for (let k = 1; k <= 80; k += 1) {
    const point = [80.30 + k * 0.004, 6.20 + k * 0.001]
    const first = Array.from({ length: model.frameCount }, (_, d) => onSurface(d, point)).indexOf(true)
    if (first >= 2) return { point, first }
  }
  return null
})()

const farm = (farmId, coordinates, extra = {}) => ({ farmId, label: `Fictional ${farmId}`, coordinates, personallyAssigned: true, outsideDistrict: false, totalAnimals: 20, diseaseCaseCount: 0, ...extra })
const ROSTER = {
  rows: [
    farm('F-CASE', [80.30, 6.20], { diseaseCaseCount: 2, totalAnimals: 64 }),
    farm('F-NEAR', [80.33, 6.24], { totalAnimals: 30 }),
    farm('F-LATER', LATER.point),
    farm('F-NOGPS', null, { totalAnimals: -5 }),
    farm('F-NEAR', [80.33, 6.24], { totalAnimals: 30 }), // duplicate record
    farm('F-OTHER-DISTRICT', [80.63, 7.29], { outsideDistrict: true }),
    farm('F-SURVEILLANCE', [80.31, 6.21], { personallyAssigned: false, totalAnimals: null }),
    farm('F-HALF', [80.31, 6.205], { totalAnimals: 12.5 }),
  ],
}
const rowsOn = (day, extra = {}) => buildFarmListRows({ roster: ROSTER, model, dayIndex: day, ...extra })
const byId = (list) => Object.fromEntries(list.rows.map((r) => [r.farmId, r]))

describe('farm list statuses follow the selected day footprint', () => {
  it('found a farm first reached after Day 1 on the real model', () => {
    expect(LATER).not.toBeNull()
  })

  it('verified, potentially affected, monitoring and location unavailable are separate', () => {
    const rows = byId(rowsOn(0))
    expect(rows['F-CASE'].status).toBe(FARM_LIST_STATUS.VERIFIED) // on the surface too, but a real report decides
    expect(rows['F-CASE'].caseCount).toBe(2)
    expect(rows['F-NEAR'].status).toBe(FARM_LIST_STATUS.AFFECTED)
    expect(rows['F-NEAR'].detail).toMatch(/risk zone on Day 0 .* modelled exposure, not infected/)
    expect(rows['F-NOGPS'].status).toBe(FARM_LIST_STATUS.NO_LOCATION)
    expect(rows['F-LATER'].status).toBe(FARM_LIST_STATUS.MONITORING)
  })

  it('a farm first on the surface on Day N is never potentially affected before Day N', () => {
    for (let day = 0; day < LATER.first; day += 1) {
      const row = byId(rowsOn(day))['F-LATER']
      expect(row.status).toBe(FARM_LIST_STATUS.MONITORING)
      expect(row.detail).toBe(`Risk zone reaches this farm on Day ${LATER.first}`)
    }
    expect(byId(rowsOn(LATER.first))['F-LATER'].status).toBe(FARM_LIST_STATUS.AFFECTED)
    expect(byId(rowsOn(LATER.first))['F-LATER'].firstSurfaceDay).toBe(LATER.first)
  })

  it('duplicates once, other districts never, invalid and withheld herd sizes flagged', () => {
    const list = rowsOn(0)
    expect(list.rows.filter((r) => r.farmId === 'F-NEAR')).toHaveLength(1)
    expect(list.rows.some((r) => r.farmId === 'F-OTHER-DISTRICT')).toBe(false)
    expect(list.summary.assignedOutsideDistrict).toBe(1)
    const rows = byId(list)
    expect(rows['F-NOGPS']).toMatchObject({ animals: null, animalCountStatus: 'INVALID', coordinates: null, locationText: 'Location unavailable' })
    expect(rows['F-HALF']).toMatchObject({ animals: null, animalCountStatus: 'INVALID' })
    expect(rows['F-SURVEILLANCE']).toMatchObject({ animals: null, animalCountStatus: 'NOT_SHARED' })
    expect(rows['F-NEAR'].animals).toBe(30)
    expect([validAnimalCount(0), validAnimalCount(250), validAnimalCount(-1), validAnimalCount(3.2), validAnimalCount(null)]).toEqual([0, 250, null, null, null])
    expect(list.summary).toMatchObject({ total: 6, verified: 1, noLocation: 1 }) // 8 records - 1 duplicate - 1 other district
  })

  it('Verified Cases mode has no modelled status; possible new cases are named on their farm', () => {
    expect(rowsOn(5, { futureMode: false }).rows.some((r) => r.status === FARM_LIST_STATUS.AFFECTED)).toBe(false)
    const withPossible = byId(rowsOn(5, { possibleNewCases: [{ id: 'POSSIBLE:F-NEAR', farm_id: 'F-NEAR', seed_day: 3 }] }))
    expect(withPossible['F-NEAR'].possibleNewCaseDay).toBe(3)
    expect(byId(rowsOn(2, { possibleNewCases: [{ id: 'POSSIBLE:F-NEAR', farm_id: 'F-NEAR', seed_day: 3 }] }))['F-NEAR'].possibleNewCaseDay).toBeNull()
  })
})

describe('farm list component', () => {
  it('shows name, herd, badge and location; a click focuses the farm; no-GPS rows cannot be clicked', () => {
    const onFocusFarm = vi.fn()
    const list = rowsOn(0, { placeFor: (id) => (id === 'F-NEAR' ? 'Fictional Town' : null) })
    const { container } = render(<MyAreaFarmList districtLabel="Galle" farmList={list} day={0} onFocusFarm={onFocusFarm} />)
    expect(screen.getByText('Farms in Galle')).toBeTruthy()
    expect(container.querySelector('[data-value="farm-total"]').textContent).toBe('6')
    expect(screen.getByText('2 ACTIVE CASES')).toBeTruthy()
    expect(screen.getByText('64 head')).toBeTruthy()
    expect(screen.getAllByText('COULD BE AFFECTED').length).toBeGreaterThan(0)
    expect(screen.getByText('LOCATION UNAVAILABLE')).toBeTruthy()
    expect(container.textContent).not.toContain('6.240, 80.330') // the detail line is not shown in the list
    expect(container.textContent).not.toContain('risk zone on Day')
    // "infected" appears only negated ("not infected", "not an infection").
    expect(container.textContent.replace(/not (an )?infect(ed|ion)/gi, '')).not.toMatch(/infect/i)
    const near = [...container.querySelectorAll('li')].find((li) => li.textContent.includes('Fictional F-NEAR')).querySelector('button')
    fireEvent.click(near)
    expect(onFocusFarm).toHaveBeenCalledWith(expect.objectContaining({ farmId: 'F-NEAR', coordinates: [80.33, 6.24] }))
    const noGps = [...container.querySelectorAll('li')].find((li) => li.dataset.status === FARM_LIST_STATUS.NO_LOCATION).querySelector('button')
    expect(noGps.disabled).toBe(true)
  })
})

describe('active cases are the last 30 days only', () => {
  const cases = (days) => days.map((d, i) => ({ caseId: `c${i}`, disease: 'LSD', verificationTime: `2026-10-${String(d).padStart(2, '0')}T09:00:00+05:30` }))
  const old = (n) => Array.from({ length: n }, (_, i) => ({ caseId: `o${i}`, disease: 'LSD', verificationTime: '2026-08-01T09:00:00+05:30' }))
  const roster = {
    rows: [
      farm('F-ACTIVE', [80.33, 6.24], { cases: [...cases([12]), ...old(2)], diseaseCaseCount: 3 }),
      farm('F-OLD-ON-SURFACE', [80.30, 6.20], { cases: old(3), diseaseCaseCount: 3 }),
      farm('F-OTHER-DISEASE', [80.31, 6.21], { cases: [{ caseId: 'f1', disease: 'FMD', verificationTime: '2026-10-12T09:00:00+05:30' }], diseaseCaseCount: 0 }),
    ],
  }
  it('counts only verified cases of the disease within 30 days; older ones are noted, not active', () => {
    const rows = byId(buildFarmListRows({ roster, model, dayIndex: 0, disease: 'LSD', referenceDateKey: '2026-10-13' }))
    expect(rows['F-ACTIVE']).toMatchObject({ status: FARM_LIST_STATUS.VERIFIED, caseCount: 1, olderCaseCount: 2 })
    expect(rows['F-ACTIVE'].detail).toContain('2 older cases (over 30 days)')
    // Only old cases: not active -- on the risk surface it could be affected.
    expect(rows['F-OLD-ON-SURFACE']).toMatchObject({ status: FARM_LIST_STATUS.AFFECTED, caseCount: 0, olderCaseCount: 3 })
    expect(rows['F-OTHER-DISEASE'].caseCount).toBe(0)
    expect(FARM_LIST_STATUS.AFFECTED).toBe('COULD BE AFFECTED')
  })
})

describe('a farm on a spread line is PENDING from the day the line reaches it', () => {
  const timeline = { ...galle, provenance: { ...galle.provenance, risk_field_rule: { ...galle.provenance.risk_field_rule, resolution_km: 2.5 } } }
  const path5 = galle.frames[5].source_paths.find((p) => p.geometry)
  const onLine = path5.front // where the line stands on Day 5
  const roster = { rows: [farm('F-ON-LINE', onLine), farm('F-ACTIVE-ON-LINE', onLine, { diseaseCaseCount: 1 })] }
  const rowsOn = (day) => byId(buildFarmListRows({ roster, model, dayIndex: day, timeline }))

  it('not pending before the line arrives, pending from then on; a real case still wins', () => {
    const first = rowsOn(14)['F-ON-LINE'].spreadLineDay
    expect(first).toBeGreaterThanOrEqual(1)
    expect(first).toBeLessThanOrEqual(5)
    expect(rowsOn(0)['F-ON-LINE'].status).not.toBe(FARM_LIST_STATUS.PENDING) // Day 0 has no line
    if (first > 1) expect(rowsOn(first - 1)['F-ON-LINE'].status).not.toBe(FARM_LIST_STATUS.PENDING)
    for (const day of [first, 5, 14]) {
      const row = rowsOn(day)['F-ON-LINE']
      expect(row.status).toBe(FARM_LIST_STATUS.PENDING)
      expect(row.detail).toMatch(/spread line since Day \d+ \(within 2.5 km\) · awaiting a check, not a case/)
    }
    expect(rowsOn(5)['F-ACTIVE-ON-LINE'].status).toBe(FARM_LIST_STATUS.VERIFIED)
  })

  it('without the model resolution no farm is marked pending (nothing assumed)', () => {
    expect(buildFarmListRows({ roster, model, dayIndex: 5, timeline: galle }).rows.some((r) => r.status === FARM_LIST_STATUS.PENDING)).toBe(false)
  })
})
