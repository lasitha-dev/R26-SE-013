import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SevenDayTriageScan from './SevenDayTriageScan'

describe('SevenDayTriageScan - URL Cattle Parameter & Daily Logs Hydration', () => {
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

  it('auto-selects cattle from ?cattle_id query param and populates table with recorded logs', async () => {
    render(
      <MemoryRouter initialEntries={['/health/7-day-triage-scan?cattle_id=c123']}>
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

    // Verify that at least one of the inputs in the table reflects the hydrated recorded values
    await waitFor(() => {
      const inputs = screen.getAllByRole('spinbutton')
      const values = inputs.map(i => parseFloat(i.value))
      expect(values).toContain(8.2)
      expect(values).toContain(380)
    })
  })
})
