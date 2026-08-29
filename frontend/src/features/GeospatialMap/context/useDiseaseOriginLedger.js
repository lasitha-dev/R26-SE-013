/**
 * GEO-ANALYSIS-02 Section 11/12: disease-agnostic real Sri Lanka
 * forecast-origin listing, reusing the SAME `/origins` endpoint Page 1's
 * `useNationalOutbreaks.js` already calls (`fetchOrigins`,
 * `geospatialApi.js`, verified read-only) -- never a second/invented
 * origin dataset.
 *
 * Deliberately NOT going through `getOutbreakAdapter(disease)
 * .mapOriginsToOutbreakSummaries` (`adapters/index.js`): that dispatch
 * reaches `fmdOutbreakAdapter.js`, which intentionally THROWS
 * `FmdModelNotReadyError` from that exact function -- a Page-1-specific
 * "fail loud, never fabricate a national FMD forecast-frame view"
 * safeguard for FMD's forecast-frame pipeline (a genuine limitation:
 * FMD has no real summary/cells/sources yet). The raw `/origins`
 * metadata fields themselves (`forecast_origin_id`/`t0`/
 * `trigger_source_count`) carry no scientific computation at all and are
 * exactly what GEO-AREA-01S already proved safe to list for FMD (My
 * Area's own real `relevant_origins`, backed by the same `/origins`
 * ledger) -- so this hook reads them directly, disease-neutral, never
 * touching the FMD-adapter landmine.
 *
 * `COUNTRY` mirrors `OutbreakMapPage.jsx`'s own hardcoded
 * `const COUNTRY = 'Sri Lanka'` verbatim (not exported from that file,
 * so duplicated here as a small, identically-valued, clearly-justified
 * local constant -- the same "prefer one source of truth; a small local
 * duplicate is acceptable when moving would create churn" judgment call
 * GEO-AREA-01S's own report already applied to `ANALYSIS_TRENDS_COUNTRY`
 * on the backend). This is NOT a second country the frontend invents --
 * it is the identical, already-audited, non-user-controllable value
 * Page 1 already sends to this same endpoint.
 */
import { useEffect, useState } from 'react'

import { fetchOrigins } from '../api/geospatialApi'
import { getDiseaseConfig } from '../disease/diseaseRegistry'

const COUNTRY = 'Sri Lanka'

export const ORIGIN_LEDGER_STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
}

export function useDiseaseOriginLedger(diseaseCode) {
  const [state, setState] = useState({ status: ORIGIN_LEDGER_STATUS.IDLE, origins: [] })

  useEffect(() => {
    if (!diseaseCode) {
      setState({ status: ORIGIN_LEDGER_STATUS.IDLE, origins: [] })
      return undefined
    }

    let cancelled = false
    setState({ status: ORIGIN_LEDGER_STATUS.LOADING, origins: [] })

    const apiValue = getDiseaseConfig(diseaseCode).apiValue
    fetchOrigins({ disease: apiValue, country: COUNTRY })
      .then((response) => {
        if (cancelled) return
        const origins = (response.origins ?? []).map((o) => ({
          originId: o.forecast_origin_id,
          country: o.country,
          t0: o.t0,
          sourceCount: o.trigger_source_count,
        }))
        setState({ status: ORIGIN_LEDGER_STATUS.READY, origins })
      })
      .catch(() => {
        if (cancelled) return
        setState({ status: ORIGIN_LEDGER_STATUS.ERROR, origins: [] })
      })

    return () => {
      cancelled = true
    }
  }, [diseaseCode])

  return state
}
