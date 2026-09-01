import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Regression test for the reported bug: on Sri Lanka Overview the master
 * Page-1 "Forecast risk · 01 SEP 2026 ... 14 SEP 2026" presentation
 * timeline is showing correctly, but clicking the existing "Focus My
 * District" (GPS/district-focus) control reverts the bottom dock back to
 * the legacy "Observed cases" timeline whenever the focused district
 * happens to have zero currently loaded outbreaks inside its polygon --
 * a real, common, honest case (most districts have no active outbreak at
 * any given moment).
 *
 * Root cause: the previous render logic picked which timeline COMPONENT
 * to mount from a location-scope-FILTERED anchor count
 * (`page1ForecastAnchorFeatures.length > 0`), so narrowing to a district
 * with no local outbreaks unmounted the master timeline entirely.
 * `OutbreakMapPage.jsx` now decides that from the full, UNFILTERED
 * national outbreak collection (`isPage1MasterTimelineActive`,
 * `page1ForecastVisualization.js`) -- camera/location scope must never
 * own the master timeline.
 *
 * Reuses the exact jsdom/fetch-mocking approach already proven in
 * `outbreakMapPageAutoFocus.test.jsx` (MapLibre's real `Map` constructor
 * fails gracefully in jsdom and is caught by `MapLibreCanvas.jsx`).
 */
describe('Page 1: district/GPS focus keeps the master forecast timeline mounted', () => {
  let OutbreakMapPage
  let GeospatialProvider

  const ORIGIN_ID = 'ORIGIN:Sri Lanka:2020-09-07'
  // Real outbreak coordinate is far north (Jaffna-ish); the mocked
  // "Matara" district polygon below is a small box far in the south, so
  // the district-scoped filter legitimately yields ZERO anchors -- the
  // exact condition that reproduced the bug.
  const OUTBREAK_COORDINATE = [80.1, 9.1]

  function originsResponse() {
    return { origins: [{ forecast_origin_id: ORIGIN_ID, country: 'Sri Lanka', t0: '2020-09-07', trigger_source_count: 1 }], n_origins: 1 }
  }

  function sourcesResponse() {
    return {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: OUTBREAK_COORDINATE }, properties: { source_id: `${ORIGIN_ID}::S1` } }],
    }
  }

  function summaryResponse() {
    return {
      analysis_metadata: { forecast_origin_id: ORIGIN_ID, t0: '2020-09-07', country: 'Sri Lanka' },
      nominal_reach_by_day: [1, 2, 3].map((day) => ({ day, nominal_reach_km: day * 5, derived_interval_lower_km: null, derived_interval_upper_km: null })),
      n_eligible_sources: 1,
      apparent_rate_context: null,
      snapshot_id: 'snap-1',
      generated_at_utc: '2026-08-31T00:00:00Z',
    }
  }

  function cellsResponse() {
    return { type: 'FeatureCollection', features: [] }
  }

  function operationalContextResponse() {
    return {
      vet_district: 'Matara',
      farms: [],
      clinical_contexts: [],
      surveillance_farms: [],
      surveillance_contexts: [],
      generated_at: '2026-09-01T00:00:00Z',
      vet: { role: 'VET' },
    }
  }

  function matariaDistrictFeatureCollection() {
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { shapeName: 'Matara District' },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [80.4, 5.9],
                [80.7, 5.9],
                [80.7, 6.2],
                [80.4, 6.2],
                [80.4, 5.9],
              ],
            ],
          },
        },
      ],
    }
  }

  beforeAll(async () => {
    if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
    ;({ GeospatialProvider } = await import('../context/GeospatialContext'))
    OutbreakMapPage = (await import('../pages/OutbreakMapPage')).default
  })

  beforeEach(() => {
    global.fetch = vi.fn((url) => {
      const href = String(url)
      if (href.includes('/api/geospatial/origins')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(originsResponse()) })
      }
      if (href.includes('/api/geospatial/operational-context')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(operationalContextResponse()) })
      }
      if (href.match(/\/analysis\/([^/]+)\/summary/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(summaryResponse()) })
      }
      if (href.match(/\/analysis\/([^/]+)\/sources/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(sourcesResponse()) })
      }
      if (href.match(/\/analysis\/([^/]+)\/cells/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(cellsResponse()) })
      }
      if (href.includes('.geojson')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(matariaDistrictFeatureCollection()) })
      }
      return Promise.reject(new Error(`unmocked url in test: ${href}`))
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('stays on the Sep 01-14 master timeline after focusing a district with zero local outbreaks', async () => {
    render(
      <GeospatialProvider>
        <OutbreakMapPage />
      </GeospatialProvider>,
    )

    // National/Sri Lanka Overview: the master presentation timeline
    // appears automatically as soon as the real outbreak coordinate loads.
    await waitFor(
      () => {
        expect(screen.getByText(/Forecast risk · 01 SEP 2026/i)).toBeTruthy()
      },
      { timeout: 3000 },
    )

    // Now click the existing GPS/district-focus control -- camera-only by
    // design, must never own the timeline.
    const focusButton = await screen.findByRole('button', { name: 'Focus My District' })
    focusButton.click()

    // The master timeline must still be showing the fixed presentation
    // date -- never fall back to the legacy Observed-cases timeline, and
    // never reset back to today/D0.
    await waitFor(() => {
      expect(screen.getByText(/Forecast risk · 01 SEP 2026/i)).toBeTruthy()
    })
    expect(screen.queryByText(/Observed cases/i)).toBeNull()
    expect(screen.queryByText(/30 Aug/i)).toBeNull()
  })
})
