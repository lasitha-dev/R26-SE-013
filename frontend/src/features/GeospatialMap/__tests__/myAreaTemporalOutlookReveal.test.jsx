// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AREA_FORECAST_OUTLOOK } from '../adapters/myAreaPresentationForecast'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'

const CHART_SOURCE = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'components', 'MyAreaTemporalOutlook.jsx'), 'utf8')
const RISK_HEIGHT_RANGE = { low: [28, 34], moderate: [42, 50], elevated: [56, 64], high: [68, 76] }

function renderOutlook(activeIndex) {
  return render(<MyAreaTemporalOutlook areaLabel="Matara" activeIndex={activeIndex} onSelectIndex={() => {}} frames={AREA_FORECAST_OUTLOOK} />)
}

describe('Future Risk Outlook progressive reveal', () => {
  it('renders exactly 14 chart slots, one per Sep date', () => {
    renderOutlook(0)
    expect(screen.getAllByRole('button')).toHaveLength(14)
  })

  it('active index 0 reveals exactly the first risk bar', () => {
    renderOutlook(0)
    expect(screen.getByRole('button', { name: '1 Sep 2026 - LOW district risk' })).toBeTruthy()
    expect(screen.getAllByRole('button', { name: /not yet revealed/ })).toHaveLength(13)
  })

  it('active index 4 reveals exactly five risk bars', () => {
    renderOutlook(4)
    expect(screen.getAllByRole('button', { name: /district risk$/ })).toHaveLength(5)
    expect(screen.getAllByRole('button', { name: /not yet revealed/ })).toHaveLength(9)
  })

  it('future bars expose no risk label or color', () => {
    renderOutlook(4)
    for (const frame of AREA_FORECAST_OUTLOOK.slice(5)) {
      const button = screen.getByRole('button', { name: new RegExp(`${frame.date.slice(-2).replace(/^0/, '')} Sep 2026 - not yet revealed`) })
      expect(button.textContent).not.toMatch(/LOW|MODERATE|ELEVATED|HIGH/)
    }
  })

  it('seeking backward hides later bars again', () => {
    const { rerender } = renderOutlook(10)
    expect(screen.getAllByRole('button', { name: /district risk$/ })).toHaveLength(11)
    rerender(<MyAreaTemporalOutlook areaLabel="Matara" activeIndex={3} onSelectIndex={() => {}} frames={AREA_FORECAST_OUTLOOK} />)
    expect(screen.getAllByRole('button', { name: /district risk$/ })).toHaveLength(4)
    expect(screen.getAllByRole('button', { name: /not yet revealed/ })).toHaveLength(10)
  })

  it('final Sep 14 reveals all fourteen bars', () => {
    renderOutlook(13)
    expect(screen.getAllByRole('button', { name: /district risk$/ })).toHaveLength(14)
    expect(screen.queryAllByRole('button', { name: /not yet revealed/ })).toHaveLength(0)
  })

  it('keeps bar heights restrained within the requested practical ranges (never near 100%)', () => {
    const match = CHART_SOURCE.match(/RISK_HEIGHT = \{ low: (\d+), moderate: (\d+), elevated: (\d+), high: (\d+) \}/)
    expect(match).toBeTruthy()
    const [, low, moderate, elevated, high] = match.map(Number)
    const heights = { low, moderate, elevated, high }
    for (const [level, height] of Object.entries(heights)) {
      const [min, max] = RISK_HEIGHT_RANGE[level]
      expect(height).toBeGreaterThanOrEqual(min)
      expect(height).toBeLessThanOrEqual(max)
    }
  })
})
