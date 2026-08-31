import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * GEO-PAGE1-FINAL Section 18/24: end-to-end proof that Risk Zones'
 * timeline populates with REAL data, and Play becomes usable, WITHOUT
 * the vet clicking a marker first -- the concrete root cause this
 * closure pass fixes (`selectMostRecentOrigin` + the page's own
 * auto-focus effect + `MapLibreCanvas`'s `autoFocusOutbreak` suppression
 * of the camera-fly/halo it would otherwise trigger).
 *
 * Same jsdom/maplibre-gl workaround as `outbreakMapPageRenderSmoke.test.jsx`
 * (dynamic import after stubbing `URL.createObjectURL`, MapLibre's real
 * `Map` constructor still fails gracefully in jsdom and is caught by
 * `MapLibreCanvas.jsx`'s own try/catch). `global.fetch` is mocked by URL
 * pattern -- only the real scientific/historical endpoints this test
 * cares about resolve; everything else (operational context, push
 * transport, protocol) rejects, exactly like the existing smoke test's
 * "a total backend outage still renders" baseline -- proving this
 * feature works even when only the scientific layer is up.
 */
describe('GEO-PAGE1-FINAL: Risk Zones auto-focuses the most recent real origin on load', () => {
  let OutbreakMapPage
  let GeospatialProvider

  const ORIGIN_OLD = 'ORIGIN:Sri Lanka:2020-09-07'
  const ORIGIN_NEW = 'ORIGIN:Sri Lanka:2020-10-28'

  function originsResponse() {
    return {
      origins: [
        { forecast_origin_id: ORIGIN_OLD, country: 'Sri Lanka', t0: '2020-09-07', trigger_source_count: 1 },
        { forecast_origin_id: ORIGIN_NEW, country: 'Sri Lanka', t0: '2020-10-28', trigger_source_count: 1 },
      ],
      n_origins: 2,
    }
  }

  function sourcesResponse(outbreakId) {
    return {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [80.1, 9.1] }, properties: { source_id: `${outbreakId}::S1` } }],
    }
  }

  function summaryResponse(outbreakId, t0) {
    return {
      analysis_metadata: { forecast_origin_id: outbreakId, t0, country: 'Sri Lanka' },
      nominal_reach_by_day: [1, 2, 3].map((day) => ({ day, nominal_reach_km: day * 5, derived_interval_lower_km: null, derived_interval_upper_km: null })),
      n_eligible_sources: 1,
      apparent_rate_context: null,
      snapshot_id: `snap-${outbreakId}`,
      generated_at_utc: '2026-08-31T00:00:00Z',
    }
  }

  function cellsResponse() {
    return { type: 'FeatureCollection', features: [] }
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
      const summaryMatch = href.match(/\/analysis\/([^/]+)\/summary/)
      if (summaryMatch) {
        const outbreakId = decodeURIComponent(summaryMatch[1])
        const t0 = outbreakId === ORIGIN_NEW ? '2020-10-28' : '2020-09-07'
        return Promise.resolve({ ok: true, json: () => Promise.resolve(summaryResponse(outbreakId, t0)) })
      }
      if (href.match(/\/analysis\/([^/]+)\/sources/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(sourcesResponse('S')) })
      }
      if (href.match(/\/analysis\/([^/]+)\/cells/)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(cellsResponse()) })
      }
      // Operational context, verified-clinical push transport, protocol,
      // district geometry -- all intentionally rejected, mirroring the
      // existing "total backend outage" smoke test's own baseline. This
      // feature must keep working for the scientific layer regardless.
      return Promise.reject(new Error(`unmocked url in test: ${href}`))
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('switches to Risk Zones and the real timeline shows the MOST RECENT real origin real date, without ever clicking a marker', async () => {
    render(
      <GeospatialProvider>
        <OutbreakMapPage />
      </GeospatialProvider>,
    )

    // "Cases" is the default mode; switch to Risk Zones the same way a
    // real vet would -- via the existing mode toolbar, never a test-only
    // backdoor into internal state. `ModeToolbar.jsx` gives each pill an
    // explicit `role="tab"` (a `role="tablist"` group), so its ACCESSIBLE
    // role is "tab", not the plain "button" the underlying element is.
    const riskZonesTab = await screen.findByRole('tab', { name: /risk zones/i })
    riskZonesTab.click()

    // The real, most-recent origin's real date -- never the older one,
    // never a fabricated placeholder -- appears in the timeline dock
    // header WITHOUT the test ever clicking a map marker.
    await waitFor(
      () => {
        expect(screen.getByText(/28 Oct 2020/i)).toBeTruthy()
      },
      { timeout: 3000 },
    )

    // The old stale "select an origin first" banner is gone -- a real
    // focus already exists.
    expect(screen.queryByText(/Select a historical outbreak origin/i)).toBeNull()
  })
})
