/**
 * FMD-10C: fetches the real FMD-only scalar risk score
 * (`GET /analysis/{id}/fmd-risk`) for the currently selected origin --
 * and ONLY when the selected disease actually has the `scalarOriginRisk`
 * capability (FMD today; LSD has no such endpoint at all). Mirrors
 * `useSelectedOutbreakFrames.js`'s "refetch on dependency change only"
 * convention -- no polling.
 *
 * Explicit states, never collapsed into a single boolean: a selected
 * origin can be genuinely SCORED, genuinely UNAVAILABLE (zero eligible
 * sources / scientific-domain construction failed -- a real backend
 * answer, not a transport failure), NOT_FOUND (bad/foreign origin id),
 * or ERROR (network/internal failure) -- each means something different
 * to a vet reading this panel.
 */
import { useEffect, useState } from 'react'

import { fetchFmdRiskAnalysis } from '../api/geospatialApi'
import { CAPABILITY, hasCapability } from '../disease/diseaseRegistry'

export const FMD_RISK_STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  UNAVAILABLE: 'unavailable',
  NOT_FOUND: 'not_found',
  ERROR: 'error',
}

const UNAVAILABLE_ERROR_STATUSES = new Set([
  'ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE',
  'ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN',
])

export function useFmdOriginRisk(diseaseCode, originId, refreshToken = 0) {
  const [state, setState] = useState({ status: FMD_RISK_STATUS.IDLE, data: null, error: null })

  useEffect(() => {
    if (!originId || !hasCapability(diseaseCode, CAPABILITY.SCALAR_ORIGIN_RISK)) {
      setState({ status: FMD_RISK_STATUS.IDLE, data: null, error: null })
      return undefined
    }

    let cancelled = false
    setState({ status: FMD_RISK_STATUS.LOADING, data: null, error: null })

    fetchFmdRiskAnalysis(originId)
      .then((data) => {
        if (cancelled) return
        // `data.status` is the backend's own SCORED/UNAVAILABLE verdict
        // (`ANALYSIS_STATUS_SCORED_9`/`ANALYSIS_STATUS_UNAVAILABLE_9`) --
        // never re-derived from `risk_score` here.
        setState({
          status: data.status === 'SCORED' ? FMD_RISK_STATUS.READY : FMD_RISK_STATUS.UNAVAILABLE,
          data,
          error: null,
        })
      })
      .catch((err) => {
        if (cancelled) return
        if (err.status === 'ORIGIN_NOT_FOUND') {
          setState({ status: FMD_RISK_STATUS.NOT_FOUND, data: null, error: err.message })
        } else if (UNAVAILABLE_ERROR_STATUSES.has(err.status)) {
          setState({ status: FMD_RISK_STATUS.UNAVAILABLE, data: null, error: err.message })
        } else {
          setState({ status: FMD_RISK_STATUS.ERROR, data: null, error: err.message })
        }
      })

    return () => {
      cancelled = true
    }
  }, [diseaseCode, originId, refreshToken])

  return state
}
