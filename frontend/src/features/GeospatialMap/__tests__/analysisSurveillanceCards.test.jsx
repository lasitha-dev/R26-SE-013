// @vitest-environment jsdom
// Analysis & Trends cards render the adapter rows (FICTIONAL values).
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ActivityChart, AffectedAreasTable, ClusterTable, compass16, KpiCard } from '../components/AnalysisSurveillanceCards'

describe('Analysis & Trends cards', () => {
  it('chart stacks verified under pending per day', () => {
    const { container } = render(<ActivityChart days={[{ date: '2026-10-16', verified: 0, pending: 2 }, { date: '2026-10-17', verified: 6, pending: 1 }]} />)
    const day = container.querySelector('[data-day="2026-10-17"]')
    expect(day.querySelector('[data-bar="verified"]')).toBeTruthy()
    expect(day.querySelector('[data-bar="pending"]')).toBeTruthy()
    expect(container.querySelector('[data-day="2026-10-16"] [data-bar="verified"]')).toBeNull()
    expect(screen.getByText('Verified')).toBeTruthy()
  })

  it('affected areas: MY chip, change arrows, empty state', () => {
    const rows = [
      { district: 'Testshire', records: 2, verified: 1, pending: 1, lastObserved: '2026-10-17', previous: 3, delta: -1, mine: true, nearestKm: null },
      { district: 'Otherland', records: 8, verified: 7, pending: 1, lastObserved: '2026-10-17', previous: 0, delta: 8, mine: false, nearestKm: 12 },
    ]
    const { container, rerender } = render(<AffectedAreasTable rows={rows} windowDays={14} emptyText="none" />)
    expect(screen.getByText('MY')).toBeTruthy()
    expect(screen.getByText('vs previous 14 d')).toBeTruthy()
    expect(container.querySelector('[data-district="Testshire"] [data-delta="-1"]').textContent).toBe('▼ 1')
    expect(container.querySelector('[data-district="Otherland"] [data-delta="8"]').textContent).toBe('▲ 8')
    expect(screen.getByText('12 km away')).toBeTruthy()
    rerender(<AffectedAreasTable rows={[]} windowDays={14} emptyText="No LSD records in this window." />)
    expect(screen.getByText('No LSD records in this window.')).toBeTruthy()
  })

  it('clusters: id, cases, districts, radius, drift and a 16-point direction', () => {
    const rows = [{ clusterId: 'x', label: 'C1', cases: 8, farms: 5, districts: ['Jaffna', 'Kilinochchi'], radiusKm: 23.2, driftKm: 17.4, bearingDeg: 111, startDate: '2026-10-05', endDate: '2026-10-16' }]
    const { container } = render(<ClusterTable rows={rows} emptyText="none" />)
    expect(container.querySelector('[data-cluster="C1"]').textContent).toContain('Jaffna, Kilinochchi')
    expect(container.textContent).toContain('23 km')
    expect(container.textContent).toContain('ESE 111°')
    expect(compass16(0)).toBe('N 0°')
    expect(compass16(225)).toBe('SW 225°')
  })

  it('KPI card shows the value and its basis, or a loading state', () => {
    const { rerender, container } = render(<KpiCard name="records" label="Current records" value={24} sub="20 verified · 4 pending · last 14 days" />)
    expect(container.querySelector('[data-value="records"]').textContent).toBe('24')
    rerender(<KpiCard name="records" label="Current records" value={24} sub="x" loading />)
    expect(container.textContent).toContain('Loading current surveillance data')
  })
})
