// @vitest-environment jsdom
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { buildMyAreaTimelineView } from '../adapters/spatialTimelineView'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'
import { buildRiskFieldModel } from '../adapters/riskFieldModel'
import { buildRiskOutlookRows } from '../adapters/riskOutlook'
import { DISTRICT, RISK_TIMELINE } from './fixtures/riskRasterTimeline'
import galleTimeline from './fixtures/spatialTimeline.galleRaster.json'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'

// Real Phase 2 engine output for two FICTIONAL test farms (see fixtures/README).
describe('Page-2 synchronized components driven by one backend frame', () => {
  it('highlights the active chart bar from activeIndex and emits the clicked frame index', () => {
    const rows = buildRiskOutlookRows(buildRiskFieldModel(RISK_TIMELINE), DISTRICT)
    const onSelectIndex = vi.fn()
    render(<MyAreaTemporalOutlook areaLabel="Testshire" activeIndex={7} onSelectIndex={onSelectIndex} rows={rows} />)
    expect(screen.getByText('Future Risk Outlook — Testshire')).toBeTruthy()
    const active = screen.getAllByRole('button').find((button) => button.getAttribute('aria-current') === 'date')
    expect(active.getAttribute('aria-label')).toMatch(/^24 Oct 2026 - .* km² \(.*% of Testshire\) coloured/)
    fireEvent.click(screen.getAllByRole('button')[3])
    expect(onSelectIndex).toHaveBeenCalledWith(3)
    fireEvent.click(screen.getAllByRole('button')[14])
    expect(onSelectIndex).toHaveBeenCalledWith(14)
  })

  it('the chart, district risk and reach come from the same selected frame', () => {
    const view = buildMyAreaTimelineView(mataraTimeline, 3, 'Matara')
    const frame = mataraTimeline.frames[3]
    const summary = frame.district_summaries.find((s) => s.district === 'Matara')
    expect(view.date).toBe(frame.date)
    expect(view.reachKm).toBe(frame.reach.nominal_reach_km)
    expect(view.areaWithinReachKm2).toBe(summary.area_within_reach_km2)
    expect(view.outlook[3].areaKm2).toBe(summary.area_within_reach_km2)
    expect(view.districtTier).toBe(summary.highest_tier_within_reach)
  })

  it('influence cards follow the selected frame and View on Map emits only the real source identity', () => {
    const onFocusCase = vi.fn()
    const asOf = buildMyAreaTimelineView(galleTimeline, 0, 'Galle')
    const { rerender } = render(<MyAreaOutbreaksInfluencing influences={asOf.influences} day={0} districtLabel="Galle" focusedCaseId={null} onFocusCase={onFocusCase} />)
    expect(screen.getByText(/reaches the district on Day 3/)).toBeTruthy()

    const day10 = buildMyAreaTimelineView(galleTimeline, 10, 'Galle')
    rerender(<MyAreaOutbreaksInfluencing influences={day10.influences} day={10} districtLabel="Galle" focusedCaseId={null} onFocusCase={onFocusCase} />)
    expect(screen.queryByText(/reaches the district on Day 3/)).toBeNull()
    expect(screen.getAllByText(/influence on Day 10/)).toHaveLength(3)
    fireEvent.click(screen.getAllByRole('button', { name: 'View on Map →' })[0])
    expect(onFocusCase).toHaveBeenCalledWith('case-1')
  })
})
