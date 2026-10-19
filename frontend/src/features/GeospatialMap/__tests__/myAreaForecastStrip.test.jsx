// @vitest-environment jsdom
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { frameDates } from '../adapters/spatialTimelineView'
import MyAreaForecastStrip from '../components/MyAreaForecastStrip'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'

// Backend frame dates (Phase 2 engine output, fictional test farms): 13-27 Oct 2026, Day 0..14.
const DATES = frameDates(mataraTimeline)

function renderStrip(overrides = {}) {
  const props = {
    dates: DATES,
    activeIndex: 6,
    onSelectIndex: vi.fn(),
    isPlaying: false,
    onTogglePlayback: vi.fn(),
    playbackSpeed: 1,
    onPlaybackSpeedChange: vi.fn(),
    currentRisk: 'high',
    disabled: false,
    ...overrides,
  }
  render(<MyAreaForecastStrip {...props} />)
  return props
}

describe('My Area backend-frame master timeline', () => {
  it('renders all 15 backend dates (Day 0..14) with first / Day-7 / last labels and no D+ notation', () => {
    renderStrip()
    expect(DATES).toHaveLength(15)
    expect(screen.getAllByRole('button', { name: /^Select / })).toHaveLength(15)
    expect(screen.getByRole('button', { name: 'Select 13 Oct 2026' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Select 27 Oct 2026' })).toBeTruthy()
    expect(screen.getByText('13 OCT')).toBeTruthy()
    expect(screen.getByText('20 OCT')).toBeTruthy()
    expect(screen.getByText('27 OCT')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/D\+\d|SEP/)
  })

  it('flags Day 8-14 frames as exploratory', () => {
    renderStrip({ activeIndex: 9, horizonStatus: 'EXPLORATORY_BEYOND_D7_REACH_HORIZON' })
    expect(screen.getByText('Exploratory')).toBeTruthy()
  })

  it('previous and next update the one controlled activeIndex', () => {
    const props = renderStrip()
    fireEvent.click(screen.getByRole('button', { name: 'Previous area forecast date' }))
    expect(props.onSelectIndex).toHaveBeenCalledWith(5)
    fireEvent.click(screen.getByRole('button', { name: 'Next area forecast date' }))
    expect(props.onSelectIndex).toHaveBeenCalledWith(7)
  })

  it('play/pause and speed are explicit controlled actions', () => {
    const props = renderStrip()
    fireEvent.click(screen.getByRole('button', { name: 'Play area forecast playback' }))
    expect(props.onTogglePlayback).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: '2x' }))
    expect(props.onPlaybackSpeedChange).toHaveBeenCalledWith(2)
  })

  it('direct date interaction selects the matching index', () => {
    const props = renderStrip()
    fireEvent.click(screen.getByRole('button', { name: 'Select 23 Oct 2026' }))
    expect(props.onSelectIndex).toHaveBeenCalledWith(10)
  })

  it('the final backend frame (Day 14) disables Play and remains the active date', () => {
    renderStrip({ activeIndex: 14 })
    expect(screen.getByRole('button', { name: 'Timeline complete at 27 Oct 2026' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Select 27 Oct 2026' })).toHaveAttribute('aria-current', 'date')
  })
})
