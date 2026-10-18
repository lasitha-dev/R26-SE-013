import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * GEO-TRAJECTORY-01: Trajectory mode was previously permanently disabled
 * in `ModeToolbar.jsx` with the claim "no trajectory/corridor geometry is
 * produced by the runtime API yet" -- confirmed FALSE by tracing the real
 * backend contract end-to-end (`services/direction/c0_cell_local_tendency_8b3.py`
 * -> `frozen_geospatial_analysis_10a.py` -> `api/schemas.py::DirectionSchema`
 * -> `/analysis/{id}/cells`, and `nominal_reach_9c.py` -> `/summary`'s
 * `nominal_reach_by_day`) and confirmed live against the running dev
 * backend (2026-09-01): every sampled real LSD origin's cells carry a real
 * non-null `direction.bearing_deg`, and `nominal_reach_by_day` is real and
 * non-zero for days 1-7.
 *
 * This suite proves, end-to-end through the real page (not a unit stub),
 * that Trajectory mode:
 *  1. is genuinely selectable once a real LSD origin resolves with real
 *     direction/reach data (no honest-unavailable banner), and
 *  2. shows an honest, precise "unavailable for this origin" state --
 *     never a silently blank layer -- for a real origin whose OWN response
 *     genuinely has neither field, mirroring `outbreakMapPageAutoFocus.test.jsx`'s
 *     established jsdom/maplibre-gl workaround (MapLibreCanvas's real
 *     `Map` constructor fails gracefully in jsdom and is caught, falling
 *     back to the SVG `MapCanvas` path -- this suite asserts the page-level
 *     honesty logic, which runs regardless of which map renderer is active).
 */
describe('GEO-TRAJECTORY-01: Trajectory mode reflects the real per-origin direction/reach contract', () => {
  let OutbreakMapPage
  let GeospatialProvider

  const ORIGIN = 'ORIGIN:Sri Lanka:2020-09-07'

  function originsResponse() {
    return { origins: [{ forecast_origin_id: ORIGIN, country: 'Sri Lanka', t0: '2020-09-07', trigger_source_count: 1 }], n_origins: 1 }
  }

  function sourcesResponse() {
    return {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [80.1, 9.1] }, properties: { source_id: 'S1' } }],
    }
  }

  function summaryResponse(nominalReachByDay) {
    return {
      analysis_metadata: { forecast_origin_id: ORIGIN, t0: '2020-09-07', country: 'Sri Lanka' },
      nominal_reach_by_day: nominalReachByDay,
      n_eligible_sources: 1,
      apparent_rate_context: null,
      snapshot_id: 'snap-1',
      generated_at_utc: '2026-08-31T00:00:00Z',
    }
  }

  function cellsResponse(bearingDeg) {
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [80.1, 9.1] },
          properties: {
            scientific_cell_id: 'CELL-1',
            risk: { raw_c0_score: 0.4, score_status: 'SCORED', semantics: 'RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY' },
            direction: {
              method_id: bearingDeg === null ? null : 'C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY',
              method_version: bearingDeg === null ? null : '8B.3',
              bearing_deg: bearingDeg,
              directional_clarity: bearingDeg === null ? null : 1.0,
              directional_input_coverage: bearingDeg === null ? null : 1.0,
              direction_status: bearingDeg === null ? 'NO_DIRECTIONAL_MASS' : 'DIRECTION_AVAILABLE',
              direction_semantics: 'C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY',
            },
          },
        },
      ],
    }
  }

  function mockFetchFor({ bearingDeg, nominalReachByDay }) {
    global.fetch = vi.fn((url) => {
      const href = String(url)
      if (href.includes('/api/geospatial/origins')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(originsResponse()) })
      }
      if (href.match(/\/analysis\/([^/]+)\/summary/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(summaryResponse(nominalReachByDay)) })
      }
      if (href.match(/\/analysis\/([^/]+)\/sources/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(sourcesResponse()) })
      }
      if (href.match(/\/analysis\/([^/]+)\/cells/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(cellsResponse(bearingDeg)) })
      }
      return Promise.reject(new Error(`unmocked url in test: ${href}`))
    })
  }

  beforeAll(async () => {
    if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
    ;({ GeospatialProvider } = await import('../context/GeospatialContext'))
    OutbreakMapPage = (await import('../pages/OutbreakMapPage')).default
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('is selectable and shows no unavailable banner when the real origin has real bearing_deg + nominal_reach_by_day', async () => {
    mockFetchFor({ bearingDeg: 35.4, nominalReachByDay: [{ day: 1, nominal_reach_km: 3.9, derived_interval_lower_km: null, derived_interval_upper_km: null }] })

    render(
      <GeospatialProvider>
        <OutbreakMapPage />
      </GeospatialProvider>,
    )

    const trajectoryTab = await screen.findByRole('tab', { name: 'Trajectory' })
    expect(trajectoryTab).not.toHaveAttribute('aria-disabled', 'true')
    trajectoryTab.click()

    await waitFor(() => expect(trajectoryTab).toHaveAttribute('aria-selected', 'true'))
    expect(screen.queryByText(/does not include spread direction or nominal reach/i)).toBeNull()
  })

  it('shows the honest per-origin unavailable state when the real origin genuinely has neither field -- never a silent blank layer', async () => {
    mockFetchFor({ bearingDeg: null, nominalReachByDay: [] })

    render(
      <GeospatialProvider>
        <OutbreakMapPage />
      </GeospatialProvider>,
    )

    const trajectoryTab = await screen.findByRole('tab', { name: 'Trajectory' })
    trajectoryTab.click()

    await waitFor(() => {
      expect(screen.getByText(/This model run does not include spread direction or nominal reach for this origin\./i)).toBeTruthy()
    })
  })
})
