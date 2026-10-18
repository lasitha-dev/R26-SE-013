// @vitest-environment jsdom
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { buildRiskFieldModel } from '../adapters/riskFieldModel'
import { buildRiskOutlookRows, districtAreaKm2 } from '../adapters/riskOutlook'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'
import { DISTRICT, RISK_TIMELINE } from './fixtures/riskRasterTimeline'

// FICTIONAL snapshot with backend-format day rasters (fixtures/riskRasterTimeline.js).
const MODEL = buildRiskFieldModel(RISK_TIMELINE)
const ROWS = buildRiskOutlookRows(MODEL, DISTRICT, { farms: [[80.5, 6.0], [80.9, 6.0]] })

function renderOutlook(activeIndex) {
  return render(<MyAreaTemporalOutlook areaLabel="Testshire" activeIndex={activeIndex} onSelectIndex={() => {}} rows={ROWS} />)
}

describe('Future Risk Outlook: the same day rasters as the Risk Zones map', () => {
  it('renders one chart slot per backend frame (Day 0..14)', () => {
    renderOutlook(0)
    expect(ROWS.map((r) => r.day)).toEqual([...Array(15).keys()])
    expect(screen.getAllByRole('button')).toHaveLength(15)
  })

  it('bar = coloured land inside the district by band, over ONE fixed district-area denominator', () => {
    const km2 = districtAreaKm2(DISTRICT)
    expect(km2).toBeGreaterThan(170)
    expect(km2).toBeLessThan(180) // 0.12 x 0.12 deg at 6 N
    for (const row of ROWS) {
      expect(row.districtKm2).toBe(km2)
      expect(row.coloredKm2).toBeCloseTo(Object.values(row.bandAreas).reduce((a, b) => a + b, 0), 6)
      expect(row.coloredShare).toBeCloseTo(row.coloredKm2 / km2, 9)
      expect(row.coloredShare).toBeLessThanOrEqual(1.000001)
    }
    expect(ROWS[0].coloredKm2).toBeGreaterThan(0) // Day 0: the case's own zone
    // The block grows past the district square: only cells inside are counted.
    expect(ROWS[14].coloredKm2).toBeLessThan(ROWS[14].districtKm2 * 1.01)
  })

  it('reports the highest band, the change since the previous day and farms on coloured land', () => {
    expect(ROWS[0].deltaKm2).toBeNull()
    expect(ROWS[3].deltaKm2).toBeCloseTo(ROWS[3].coloredKm2 - ROWS[2].coloredKm2, 9)
    expect(ROWS[14].maxBand).toBe('high')
    expect(ROWS[0].maxBand).toBe('elevated')
    expect(ROWS[0].monitoredFarms).toBe(1) // the farm at the case, not the one 44 km away
  })

  it('every bar is visible and the selected day reports its own values', () => {
    renderOutlook(7)
    expect(screen.getAllByRole('button', { name: /of Testshire\) coloured/ })).toHaveLength(15)
    expect(screen.getByRole('button', { name: /of Testshire\) coloured/, current: 'date' })).toBeTruthy()
  })

  it('scales bars to the largest daily share and marks Day 8-14 as exploratory', () => {
    const { container } = renderOutlook(14)
    const bars = [...container.querySelectorAll('[data-bar="coloured-share"]')]
    expect(bars).toHaveLength(15)
    expect(Math.max(...bars.map((el) => parseFloat(el.style.height)))).toBeLessThanOrEqual(100)
    expect(bars.map((el) => el.className.includes('border-dashed'))).toEqual(ROWS.map((r) => r.exploratory))
  })

  it('no model -> no rows (nothing invented)', () => {
    expect(buildRiskOutlookRows(null, DISTRICT)).toEqual([])
    expect(buildRiskOutlookRows(MODEL, null)).toEqual([])
  })
})
