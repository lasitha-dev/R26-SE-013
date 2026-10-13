import { cleanup, render } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * GEO28A "blank app" root cause: every other test file in this feature is
 * structural/pure-function only (this repo's own documented reason:
 * WebGL/MapLibre needs a real browser). That is exactly why a fatal
 * render-time bug -- `showOperationalLayer` was read by an earlier
 * `useMemo` before its own `const` declaration further down the
 * component, a temporal-dead-zone `ReferenceError` thrown on EVERY
 * render -- shipped with 54/54 test files green: nothing in the suite
 * ever actually rendered this component.
 *
 * `jsdom` + `@testing-library/react` (both already project dependencies)
 * ARE enough to catch this class of bug without a real browser, but
 * `maplibre-gl`'s own module has a top-level side effect
 * (`maplibregl.setWorkerUrl(window.URL.createObjectURL(...))`) that jsdom
 * does not implement by default -- `OutbreakMapPage`/`GeospatialProvider`
 * are therefore imported DYNAMICALLY inside `beforeAll`, after installing
 * a minimal `URL.createObjectURL`/`revokeObjectURL` stub, so that
 * side effect runs against a jsdom that can tolerate it. Once past that,
 * MapLibre's actual `Map` constructor still fails gracefully in jsdom (no
 * WebGL context) and is already caught by `MapLibreCanvas.jsx`'s own
 * try/catch -> `onMapUnavailable`, so this test never needs to mock
 * MapLibre's rendering itself.
 *
 * `fetch` is mocked to reject for every call -- this test asserts only
 * that a total backend outage renders SOME UI without throwing, not any
 * particular real data.
 */
describe('GEO28A: OutbreakMapPage renders without a fatal exception', () => {
  let OutbreakMapPage
  let GeospatialProvider

  beforeAll(async () => {
    if (!global.URL.createObjectURL) global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = vi.fn()
    ;({ GeospatialProvider } = await import('../context/GeospatialContext'))
    OutbreakMapPage = (await import('../pages/OutbreakMapPage')).default
  })

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
          <OutbreakMapPage />
        </GeospatialProvider>,
      ),
    ).not.toThrow()
  })

  it('renders the real page title text (proves the component tree actually committed, not just "did not throw")', () => {
    const { getByText } = render(
      <GeospatialProvider>
        <OutbreakMapPage />
      </GeospatialProvider>,
    )
    expect(getByText('Geospatial Disease Intelligence')).toBeTruthy()
  })
})
