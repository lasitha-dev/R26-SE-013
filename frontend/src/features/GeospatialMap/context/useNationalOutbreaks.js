/**
 * LSD-UI-03: loads every real forecast origin for the selected disease/
 * country plus each origin's own real geometry, for Page 1's national
 * browsing layer (plan Section 16 -- "render every real available Sri
 * Lanka LSD source/origin... if the dataset is sparse, show it
 * honestly. Do NOT invent additional points").
 *
 * The real `/origins` endpoint returns metadata only (no geometry), so
 * showing real markers nationally needs one extra geometry fetch per
 * origin -- cheap for the real Sri Lanka corpus (5 LSD / 16 FMD origins
 * today). No polling: this only re-fetches when `diseaseCode`/`country`
 * change, matching the rest of this feature's no-auto-polling
 * discipline.
 *
 * FMD-10C1: which geometry endpoint backs that per-origin fetch depends
 * on the disease's capabilities -- a disease with the LSD-shaped
 * `spatialCells` capability uses `/analysis/{id}/sources` unchanged
 * (LSD, non-regression); a disease WITHOUT it but WITH `historicalOrigins`
 * (FMD today) uses the new disease-neutral, real
 * `/origins/{id}/trigger-sources` route instead (`fmdOutbreakAdapter.js`'s
 * old "no coordinate-bearing endpoint exists for FMD" limitation no
 * longer applies -- see `api/router.py::get_origin_trigger_sources`).
 * Neither path is ever both-called for the same origin.
 */
import { useEffect, useState } from 'react'

import { fetchAnalysisSources, fetchOrigins, fetchOriginTriggerSources } from '../api/geospatialApi'
import { getOutbreakAdapter } from '../adapters'
import { GEO_TIMING, markTiming } from '../adapters/loadTiming'
import { CAPABILITY, getDiseaseConfig, hasCapability } from '../disease/diseaseRegistry'

export const NATIONAL_STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  EMPTY: 'empty',
  UNAVAILABLE: 'unavailable', // disease not API-ready (e.g. FMD, HTTP 409)
  ERROR: 'error',
}

/** `refreshToken` is not compared for meaning, only for change -- bump it
 * (e.g. from a "Check for newer snapshot" button, plan Section 9) to
 * force a real re-fetch of the same real endpoints. Never auto-bumped
 * by a timer -- see the no-auto-polling structural tests. */
// GEO-VISUAL-POLISH-02 Section 1/2: honest per-stage counts for the
// database -> forecast-origin -> per-origin-geometry -> rendered-marker
// pipeline -- exposed as real hook state (read by `StatusDiagnosticsMenu`
// via `OutbreakMapPage.jsx`), never a console.log. `expectedOriginCount`
// is stage A (how many real forecast origins `/origins` returned for this
// disease/country -- NOT the same thing as the underlying trigger/source
// RECORD count, since one origin can bundle several real records on the
// same day). `expectedSourceRecordCount` sums each origin's own real
// `trigger_source_count` -- stage B. `resolvedOriginCount`/
// `failedOriginCount` are stage-A-shaped: how many of those origins'
// OWN per-origin geometry requests actually settled successfully vs.
// failed (a slow/failed request, e.g. the real >30s backend defect this
// hook's own module docstring already documents, is counted here rather
// than silently vanishing). Stage C (resolved real geometries) and stage
// D (rendered map features, after co-location aggregation) are derived
// from `originsWithSources` itself by the caller -- this hook never
// duplicates that computation.
const ZERO_RESOLUTION_STATS = { expectedOriginCount: 0, resolvedOriginCount: 0, failedOriginCount: 0, expectedSourceRecordCount: 0 }

export function useNationalOutbreaks(diseaseCode, country, refreshToken = 0) {
  const [state, setState] = useState({ status: NATIONAL_STATUS.IDLE, originsWithSources: [], error: null, ...ZERO_RESOLUTION_STATS })

  useEffect(() => {
    if (!hasCapability(diseaseCode, CAPABILITY.HISTORICAL_ORIGINS)) {
      setState({ status: NATIONAL_STATUS.UNAVAILABLE, originsWithSources: [], error: null, ...ZERO_RESOLUTION_STATS })
      return undefined
    }

    let cancelled = false
    // GEO-VIVA-USER-VISIBLE-RECOVERY-05: a real switch AWAY from a disease
    // previously only set a local `cancelled` flag -- the actual HTTP
    // requests already in flight (`fetchOrigins`/the per-origin geometry
    // calls) kept running to completion on the network/server side
    // regardless, their responses just silently discarded on arrival.
    // Observed live: switching FMD -> LSD while FMD's real requests were
    // still stuck mid-flight (the backend latency condition documented
    // above) left LSD's own fresh request queued behind that same
    // backend, so the page never actually recovered. `AbortController`
    // actually cancels the outstanding network requests at the browser
    // level the moment a NEWER selection supersedes them -- a real,
    // Geospatial-local mitigation for a real, previously-unhandled resource
    // pile-up, not merely a client-side "ignore the answer" flag (which is
    // kept below too, for a response that already started decoding before
    // abort could take effect).
    const abortController = new AbortController()
    setState({ status: NATIONAL_STATUS.LOADING, originsWithSources: [], error: null, ...ZERO_RESOLUTION_STATS })
    // GEO33B Section 1/2: this effect runs on MOUNT, in parallel with (and
    // completely independent of) MapLibre's own construction/style load --
    // it never waits for `map.on('load')`. The marks make that provable
    // from a real browser session rather than only from reading the code.
    // `{ repeat: true }` (GEO-VIVA-USER-VISIBLE-RECOVERY-05) so a REAL
    // disease switch after initial load marks its own start/end too, not
    // only the very first page-load fetch.
    markTiming(GEO_TIMING.NATIONAL_FETCH_START, { repeat: true })

    const adapter = getOutbreakAdapter(diseaseCode)
    const apiValue = getDiseaseConfig(diseaseCode).apiValue
    // FMD-10C1: `/analysis/{id}/sources` shares FMD's own 409
    // ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY gate with `/summary`/
    // `/cells` (`spatialCells` capability) -- a disease without it never
    // even attempts that doomed-to-409 request. Instead, a disease with
    // `historicalOrigins` but not `spatialCells` (FMD today) fetches its
    // real geometry from the new `trigger-sources` route.
    const canFetchLsdSourceGeometry = hasCapability(diseaseCode, CAPABILITY.SPATIAL_CELLS)
    const canFetchHistoricalTriggerGeometry = !canFetchLsdSourceGeometry && hasCapability(diseaseCode, CAPABILITY.HISTORICAL_ORIGINS)

    fetchOrigins({ disease: apiValue, country })
      .then((originsResponse) => {
        if (cancelled) return
        const summaries = adapter.mapOriginsToOutbreakSummaries(originsResponse)
        markTiming(GEO_TIMING.NATIONAL_FETCH_END, { repeat: true })

        // Stage A/B: known the instant the (lightweight, geometry-free)
        // `/origins` response itself resolves -- real counts from the
        // real backend response, never derived from anything that could
        // still be pending.
        const expectedOriginCount = summaries.length
        const expectedSourceRecordCount = summaries.reduce((sum, s) => sum + (s.sourceCount ?? 0), 0)

        if (summaries.length === 0) {
          setState({ status: NATIONAL_STATUS.EMPTY, originsWithSources: [], error: null, ...ZERO_RESOLUTION_STATS })
          return
        }

        // GEO-VISUAL-POLISH-02: stage A/B are reported the instant they
        // are genuinely known -- BEFORE any per-origin geometry request
        // has even been dispatched, let alone settled. Without this, a
        // vet watching the diagnostics panel during the real documented
        // slow-origin window would see "0 expected" (a false "nothing is
        // happening yet") right up until the first geometry request
        // settles, even though the real forecast-origin count was already
        // known from the lightweight `/origins` response alone.
        setState({
          status: NATIONAL_STATUS.LOADING,
          originsWithSources: [],
          error: null,
          expectedOriginCount,
          expectedSourceRecordCount,
          resolvedOriginCount: 0,
          failedOriginCount: 0,
        })

        // GEO-VIVA-TOP-UI-AND-INTERACTION-LATENCY-04: each real origin's
        // geometry request is revealed INDEPENDENTLY as it resolves,
        // instead of the whole national layer waiting on `Promise.all`
        // (i.e. on the single SLOWEST of N parallel requests) -- measured
        // live against the real running backend: fetching FMD's real
        // origins, 15 of 16 `/trigger-sources` calls resolved in well
        // under a second while one real origin
        // (`ORIGIN:Sri Lanka:2009-09-09`) took ~19.5s (and, on a later
        // measurement, ~38.8s while the other 15 requests never completed
        // at all until it did -- looks like the backend serializes on
        // this handler; a real, reported, backend-only defect, never
        // touched here). `resultsBySlot` keeps the array positionally
        // stable as results trickle in -- a still-pending slot is simply
        // absent (`filter(Boolean)`), never a placeholder/fabricated
        // entry. A single origin's request failing now excludes only
        // that one real origin (never fabricated) instead of discarding
        // every OTHER already-succeeded real origin too, which is what
        // the previous single `Promise.all` rejection did.
        //
        // GEO-VIVA-USER-VISIBLE-RECOVERY-05: `status` itself only becomes
        // READY/EMPTY once EVERY origin has settled (`settledCount ===
        // summaries.length`) -- while any are still pending it stays
        // LOADING (keeping the page's "Updating…" indicator honestly
        // visible), even though `originsWithSources` -- and therefore the
        // map's real markers -- already grows with each real arrival
        // underneath it. A PARTIAL result is real data, never fabricated,
        // but it is not yet the FINAL answer for this selection, so it
        // must not be reported as such.
        const resultsBySlot = new Array(summaries.length).fill(null)
        let settledCount = 0
        // GEO-VISUAL-POLISH-02 Section 2: the real count of per-origin
        // geometry requests that failed (rejected, or -- once a caller
        // applies a real timeout via `signal` -- aborted) rather than
        // resolving. Previously this was silently discarded entirely
        // (`.catch(() => {})`); it is still excluded from the rendered
        // map exactly as before (never fabricated), but is now an honest,
        // visible number instead of an invisible one.
        let failedCount = 0

        function revealSettled(isFinal) {
          if (cancelled) return
          const revealed = resultsBySlot.filter(Boolean)
          if (isFinal) markTiming(GEO_TIMING.NATIONAL_ALL_SETTLED, { repeat: true })
          setState({
            status: isFinal ? (revealed.length === 0 ? NATIONAL_STATUS.EMPTY : NATIONAL_STATUS.READY) : NATIONAL_STATUS.LOADING,
            originsWithSources: revealed,
            error: null,
            expectedOriginCount,
            expectedSourceRecordCount,
            resolvedOriginCount: revealed.length,
            failedOriginCount: failedCount,
          })
        }

        summaries.forEach((summary, index) => {
          const geometryPromise = canFetchLsdSourceGeometry
            ? fetchAnalysisSources(summary.outbreakId, { signal: abortController.signal })
            : canFetchHistoricalTriggerGeometry
              ? fetchOriginTriggerSources(summary.outbreakId, { disease: apiValue, signal: abortController.signal })
              : Promise.resolve(null)

          geometryPromise
            .then((sourcesFeatureCollection) => {
              if (cancelled) return
              resultsBySlot[index] = { ...summary, sourcesFeatureCollection }
            })
            .catch(() => {
              // Excludes only this one real origin -- see comment above.
              // Never fabricated as "resolved"; counted honestly instead.
              if (!cancelled) failedCount += 1
            })
            .finally(() => {
              settledCount += 1
              revealSettled(settledCount === summaries.length)
            })
        })
      })
      .catch((err) => {
        if (cancelled) return
        setState({ status: NATIONAL_STATUS.ERROR, originsWithSources: [], error: err.message, ...ZERO_RESOLUTION_STATS })
      })

    return () => {
      cancelled = true
      abortController.abort()
    }
  }, [diseaseCode, country, refreshToken])

  return state
}
