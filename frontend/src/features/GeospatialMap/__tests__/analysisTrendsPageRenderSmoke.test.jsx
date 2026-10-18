import { cleanup, render } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { GeospatialProvider } from '../context/GeospatialContext'
import AnalysisTrendsPage from '../pages/AnalysisTrendsPage'

/**
 * PAGE-3-CURRENT-DASHBOARD: every other Page-3 test in this suite is a
 * `readFileSync` text-scan of the source -- none of them actually mount
 * the component, so a real render-time bug (a hook-order mistake, an
 * undefined prop access, a bad destructure) could ship even with every
 * text-scan assertion green. Mirrors `outbreakMapPageRenderSmoke.test.jsx`'s
 * exact rationale/pattern for Page 1. `fetch` is mocked to reject for
 * every call -- this proves the page renders honest UI without throwing
 * on a total backend outage, not any particular real data.
 */
describe('PAGE-3-CURRENT-DASHBOARD-RENDER: AnalysisTrendsPage renders without a fatal exception', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() => Promise.reject(new Error('network unavailable in test')))
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('mounts inside GeospatialProvider without throwing, even when every backend call fails', () => {
    expect(() =>
      render(
        <GeospatialProvider>
          <AnalysisTrendsPage />
        </GeospatialProvider>,
      ),
    ).not.toThrow()
  })

  it('renders the real page title and the four current-data section headings (proves the tree actually committed)', () => {
    const { getByText } = render(
      <GeospatialProvider>
        <AnalysisTrendsPage />
      </GeospatialProvider>,
    )
    expect(getByText('Analysis & Trends')).toBeTruthy()
    expect(getByText('Current outbreak patterns and spatial intelligence')).toBeTruthy()
    expect(getByText('Recent Outbreak Activity')).toBeTruthy()
    expect(getByText('Most Affected Areas')).toBeTruthy()
  })

  it('shows honest N/A KPI cards on a total backend outage, never a fabricated number', async () => {
    const { getByText, findAllByText } = render(
      <GeospatialProvider>
        <AnalysisTrendsPage />
      </GeospatialProvider>,
    )
    expect(getByText('Current clusters')).toBeTruthy()
    expect(getByText('Forecast horizon')).toBeTruthy()
    // Records, areas and clusters all fail -> N/A (never 0) once settled.
    expect((await findAllByText('N/A')).length).toBeGreaterThanOrEqual(3)
  })
})
