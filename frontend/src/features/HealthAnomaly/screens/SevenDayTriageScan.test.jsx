import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SevenDayTriageScan from './SevenDayTriageScan'

describe('SevenDayTriageScan - Date-Matched Auto-Fetch, Input Locking & Validation', () => {
  const mockCattleList = [
    {
      id: 'c123',
      identifier: 'kiri katiya',
      breed: 'Jersey',
      calving_date: '2026-05-01',
      dob: '2022-01-01'
    }
  ]

  const mockDailyLogs = [
    {
      id: 'log1',
      cattle_id: 'c123',
      date: '2026-10-10',
      milk_yield: 9.8,
      weight: 382.5,
      water_intake: 50.0,
      feed_intake: 12.0,
      body_temp: 38.6
    },
    {
      id: 'log2',
      cattle_id: 'c123',
      date: '2026-10-14',
      milk_yield: 8.2,
      weight: 380.0,
      water_intake: 52.0,
      feed_intake: 11.5,
      body_temp: 38.7
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn((url) => {
      if (url.includes('/api/cattle/c123/daily-logs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockDailyLogs),
        })
      }
      if (url.includes('/api/cattle')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockCattleList),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      })
    })
  })

  it('anchors 7 days to currentDate, auto-populates & locks matched dates, and leaves unmatched dates at 0 & editable', async () => {
    render(
      <MemoryRouter initialEntries={['/health/7-day-triage-scan?cattle_id=c123&date=2026-10-15']}>
        <SevenDayTriageScan />
      </MemoryRouter>
    )

    // Verify cattle dropdown value gets set
    await waitFor(() => {
      const select = screen.getByRole('combobox')
      expect(select.value).toBe('c123')
    })

    // Verify daily logs API was called for c123
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/cattle/c123/daily-logs',
        expect.anything()
      )
    })

    // Verify day labels with formatted dates
    expect(screen.getByText('D1')).toBeInTheDocument()
    expect(screen.getByText('(10-09)')).toBeInTheDocument()
    expect(screen.getByText('D2')).toBeInTheDocument()
    expect(screen.getByText('(10-10)')).toBeInTheDocument()
    expect(screen.getByText('D6')).toBeInTheDocument()
    expect(screen.getByText('(10-14)')).toBeInTheDocument()
    expect(screen.getByText('D7')).toBeInTheDocument()
    expect(screen.getByText('(10-15)')).toBeInTheDocument()

    // Verify values populated in inputs
    await waitFor(() => {
      const inputs = screen.getAllByRole('spinbutton')
      const values = inputs.map(i => parseFloat(i.value))
      expect(values).toContain(9.8)
      expect(values).toContain(382.5)
      expect(values).toContain(8.2)
      expect(values).toContain(380)
    })

    // Verify that matched date rows (D2: 10-10, D6: 10-14) have disabled (locked) milk and weight inputs
    const allInputs = screen.getAllByRole('spinbutton')
    // There are 7 rows * 5 inputs = 35 spinbuttons: [milk, water, feed, temp, weight] per row
    // D2 is row index 1: inputs 5 (milk), 6 (water), 7 (feed), 8 (temp), 9 (weight)
    const d2MilkInput = allInputs[5]
    const d2WaterInput = allInputs[6]
    const d2WeightInput = allInputs[9]

    expect(d2MilkInput).toBeDisabled()
    expect(parseFloat(d2MilkInput.value)).toBe(9.8)
    expect(d2WeightInput).toBeDisabled()
    expect(parseFloat(d2WeightInput.value)).toBe(382.5)
    // Water, feed, temp should stay editable
    expect(d2WaterInput).not.toBeDisabled()

    // D1 is row index 0 (10-09, missing from DB): inputs 0 (milk), 4 (weight)
    const d1MilkInput = allInputs[0]
    const d1WeightInput = allInputs[4]
    expect(d1MilkInput).not.toBeDisabled()
    expect(parseFloat(d1MilkInput.value)).toBe(0)
    expect(d1WeightInput).not.toBeDisabled()
    expect(parseFloat(d1WeightInput.value)).toBe(0)
  })

  it('shows clear validation error banner when attempting to run diagnostics with missing (0) milk/weight', async () => {
    render(
      <MemoryRouter initialEntries={['/health/7-day-triage-scan?cattle_id=c123&date=2026-10-15']}>
        <SevenDayTriageScan />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('combobox').value).toBe('c123')
    })

    // Click Run Diagnostics while missing days (D1, D3, D4, D5, D7) still have 0 milk & weight
    const runBtn = screen.getByRole('button', { name: /run multi-modal ai diagnostics/i })
    fireEvent.click(runBtn)

    // Should display validation banner
    await waitFor(() => {
      const banners = screen.getAllByTestId(/triage-validation-banner/)
      expect(banners.length).toBeGreaterThan(0)
      expect(banners[0].textContent).toMatch(/Missing milk yield or weight/i)
    })
  })
})
