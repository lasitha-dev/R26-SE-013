// @vitest-environment jsdom
import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AREA_FORECAST_DATES } from '../adapters/myAreaPresentationForecast'
import MyAreaForecastStrip from '../components/MyAreaForecastStrip'

function renderStrip(overrides = {}) {
  const props = {
    dates: AREA_FORECAST_DATES,
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

describe('My Area Sep 01-14 master timeline', () => {
  it('renders all 14 actual Sep dates with the requested major labels and no D+ notation', () => {
    renderStrip()
    expect(screen.getByRole('button', { name: 'Select 1 Sep 2026' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Select 14 Sep 2026' })).toBeTruthy()
    expect(screen.getByText('01 SEP')).toBeTruthy()
    expect(screen.getByText('07 SEP')).toBeTruthy()
    expect(screen.getByText('14 SEP')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/D\+\d/)
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
    fireEvent.click(screen.getByRole('button', { name: 'Select 11 Sep 2026' }))
    expect(props.onSelectIndex).toHaveBeenCalledWith(10)
  })

  it('final Sep 14 disables Play and remains the active date', () => {
    renderStrip({ activeIndex: 13 })
    expect(screen.getByRole('button', { name: 'Forecast complete at 14 Sep 2026' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Select 14 Sep 2026' })).toHaveAttribute('aria-current', 'date')
  })
})
