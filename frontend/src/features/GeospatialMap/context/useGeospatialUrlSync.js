/**
 * LSD-UI-01: the deep-link contract (plan Section K/J) --
 * `?disease=&outbreak=&day=&modelRun=` <-> shared selection state.
 *
 * Deliberately router-agnostic (plan Section N decision (b)): this
 * branch has no `react-router-dom` yet (only `origin/main` does, via
 * `VetLayout`). Rather than adding a throwaway router just for
 * standalone dev, this hook takes an injected `[searchParams,
 * setSearchParams]` pair shaped exactly like react-router-dom's
 * `useSearchParams()` return value (a `URLSearchParams`-like reader +
 * a setter). At real integration time, swap the injected pair for the
 * real `useSearchParams()` call in the page component -- this hook's
 * internals don't change.
 *
 * The pure `buildGeospatialSearchParams`/`parseGeospatialSearchParams`
 * functions are exported separately so the URL round-trip is testable
 * without React at all.
 */
import { useEffect, useRef } from 'react'

export function buildGeospatialSearchParams(selection) {
  const params = new URLSearchParams()
  if (selection.selectedDisease) params.set('disease', selection.selectedDisease)
  if (selection.selectedOutbreakId) params.set('outbreak', selection.selectedOutbreakId)
  if (selection.selectedForecastDay != null) params.set('day', String(selection.selectedForecastDay))
  if (selection.selectedModelRunId) params.set('modelRun', selection.selectedModelRunId)
  if (selection.selectedAreaId) params.set('area', selection.selectedAreaId)
  return params
}

export function parseGeospatialSearchParams(searchParams) {
  const day = searchParams.get('day')
  return {
    disease: searchParams.get('disease') || null,
    outbreakId: searchParams.get('outbreak') || null,
    day: day != null && day !== '' ? Number(day) : null,
    modelRunId: searchParams.get('modelRun') || null,
    areaId: searchParams.get('area') || null,
  }
}

/** Builds the path+query string for a Page1<->Page2<->Page3 deep link,
 * preserving whatever of the current selection isn't overridden --
 * the one helper every "View on Map" / "Impact on My Area" / "Analyze
 * trend" link in the spec is required to share (plan Section K). */
export function buildGeospatialUrl(basePath, selection, overrides = {}) {
  const params = buildGeospatialSearchParams({ ...selection, ...overrides })
  const query = params.toString()
  return query ? `${basePath}?${query}` : basePath
}

/**
 * One-way-in-at-mount, one-way-out-on-change sync: reads the URL once
 * when a page mounts (so a notification deep link or a pasted URL
 * restores context), then keeps the URL in sync with subsequent
 * selection changes. Does not fight the user by re-reading the URL on
 * every render.
 */
export function useGeospatialUrlSync({ selection, selectDisease, selectOutbreak, selectDay, setModelRun, selectArea }, [searchParams, setSearchParams]) {
  const hydratedRef = useRef(false)

  useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    const parsed = parseGeospatialSearchParams(searchParams)
    if (parsed.disease) selectDisease(parsed.disease)
    if (parsed.areaId) selectArea(parsed.areaId)
    if (parsed.outbreakId) selectOutbreak(parsed.outbreakId)
    if (parsed.modelRunId) setModelRun(parsed.modelRunId)
    if (parsed.day != null) selectDay(parsed.day)
    // Intentionally runs once per mount only -- URL is the source of
    // truth for the *initial* value, not re-applied on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!hydratedRef.current) return
    setSearchParams(buildGeospatialSearchParams(selection), { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection.selectedDisease, selection.selectedOutbreakId, selection.selectedForecastDay, selection.selectedModelRunId, selection.selectedAreaId])
}
