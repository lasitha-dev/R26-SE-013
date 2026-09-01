// @vitest-environment jsdom
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AREA_FORECAST_OUTLOOK, buildMyAreaPresentationForecast } from '../adapters/myAreaPresentationForecast'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'

const DISTRICT = {
  type: 'Feature',
  properties: { shapeName: 'Matara District' },
  geometry: { type: 'Polygon', coordinates: [[[80.4, 5.8], [80.8, 5.8], [80.8, 6.2], [80.4, 6.2], [80.4, 5.8]]] },
}

const CASES = [
  { type: 'Feature', geometry: { type: 'Point', coordinates: [80.53, 5.96] }, properties: { caseId: 'REAL-A', disease: 'LSD', locationDistrict: 'Matara' } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [80.58, 5.99] }, properties: { caseId: 'REAL-B', disease: 'LSD', locationDistrict: 'Matara' } },
]

describe('Page-2 synchronized presentation components', () => {
  it('highlights the active chart bar from activeIndex and emits the clicked Sep index', () => {
    const onSelectIndex = vi.fn()
    render(<MyAreaTemporalOutlook areaLabel="Matara" activeIndex={7} onSelectIndex={onSelectIndex} frames={AREA_FORECAST_OUTLOOK} />)
    expect(screen.getByText('Future Risk Outlook — Matara')).toBeTruthy()
    expect(screen.getByRole('button', { name: '8 Sep 2026 - HIGH district risk' })).toHaveAttribute('aria-current', 'date')
    // Index 3 (4 Sep) is already revealed at activeIndex 7, so its real risk label is exposed.
    fireEvent.click(screen.getByRole('button', { name: '4 Sep 2026 - MODERATE district risk' }))
    expect(onSelectIndex).toHaveBeenCalledWith(3)
    // Index 13 (14 Sep) is still in the future at activeIndex 7 -- direct seek stays possible,
    // but its risk label/color must not leak ahead of the timeline.
    fireEvent.click(screen.getByRole('button', { name: '14 Sep 2026 - not yet revealed' }))
    expect(onSelectIndex).toHaveBeenCalledWith(13)
  })

  it('updates influencing-card status with the same frame and View on Map only emits the real case identity', () => {
    const onFocusCase = vi.fn()
    const early = buildMyAreaPresentationForecast(CASES, 0, DISTRICT)
    const { rerender } = render(<MyAreaOutbreaksInfluencing influences={early.influences} focusedCaseId={null} onFocusCase={onFocusCase} />)
    expect(screen.getAllByText('APPROACHING AREA')).toHaveLength(2)

    const peak = buildMyAreaPresentationForecast(CASES, 9, DISTRICT)
    rerender(<MyAreaOutbreaksInfluencing influences={peak.influences} focusedCaseId={null} onFocusCase={onFocusCase} />)
    expect(screen.getAllByText(/AREA INFLUENCE|AFFECTS AREA/)).toHaveLength(2)
    fireEvent.click(screen.getAllByRole('button', { name: 'View on Map ->' })[0])
    expect(onFocusCase).toHaveBeenCalledWith(peak.influences[0].anchorId)
    expect(onFocusCase).toHaveBeenCalledTimes(1)
  })
})
