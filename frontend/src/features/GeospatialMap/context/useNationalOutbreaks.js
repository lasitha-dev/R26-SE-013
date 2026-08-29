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
export function useNationalOutbreaks(diseaseCode, country, refreshToken = 0) {
  const [state, setState] = useState({ status: NATIONAL_STATUS.IDLE, originsWithSources: [], error: null })

  useEffect(() => {
    if (!hasCapability(diseaseCode, CAPABILITY.HISTORICAL_ORIGINS)) {
      setState({ status: NATIONAL_STATUS.UNAVAILABLE, originsWithSources: [], error: null })
      return undefined
    }

    let cancelled = false
    setState({ status: NATIONAL_STATUS.LOADING, originsWithSources: [], error: null })

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
      .then(async (originsResponse) => {
        if (cancelled) return
        const summaries = adapter.mapOriginsToOutbreakSummaries(originsResponse)
        const withSources = await Promise.all(
          summaries.map(async (summary) => {
            const sourcesFeatureCollection = canFetchLsdSourceGeometry
              ? await fetchAnalysisSources(summary.outbreakId)
              : canFetchHistoricalTriggerGeometry
                ? await fetchOriginTriggerSources(summary.outbreakId, { disease: apiValue })
                : null
            return { ...summary, sourcesFeatureCollection }
          }),
        )
        if (cancelled) return
        setState({
          status: withSources.length === 0 ? NATIONAL_STATUS.EMPTY : NATIONAL_STATUS.READY,
          originsWithSources: withSources,
          error: null,
        })
      })
      .catch((err) => {
        if (cancelled) return
        setState({ status: NATIONAL_STATUS.ERROR, originsWithSources: [], error: err.message })
      })

    return () => {
      cancelled = true
    }
  }, [diseaseCode, country, refreshToken])

  return state
}
