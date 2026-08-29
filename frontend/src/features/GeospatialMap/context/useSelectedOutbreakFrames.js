/**
 * LSD-UI-04: once an outbreak is selected (focus mode, plan Section 20),
 * fetches its real summary + sources + cells ONCE and exposes them, plus
 * the real available forecast-day horizon derived by the disease
 * adapter (`getAvailableForecastDays`) -- never a hardcoded 14/15 day
 * count. Re-fetches only when `outbreakId` itself changes, never on a
 * timeline day change (day 0..7 are all served from this one fetch).
 */
import { useEffect, useState } from 'react'

import { fetchAnalysisCells, fetchAnalysisSources, fetchAnalysisSummary } from '../api/geospatialApi'
import { getOutbreakAdapter } from '../adapters'
import { CAPABILITY, hasCapability } from '../disease/diseaseRegistry'

export const FOCUS_STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  UNAVAILABLE: 'unavailable',
  ERROR: 'error',
}

/** `refreshToken` (plan Section 9's "Check for newer snapshot") forces a
 * real re-fetch of the same real endpoints for the currently selected
 * outbreak; never auto-bumped by a timer. */
export function useSelectedOutbreakFrames(diseaseCode, outbreakId, refreshToken = 0) {
  const [state, setState] = useState({ status: FOCUS_STATUS.IDLE, summary: null, sources: null, cells: null, error: null })

  useEffect(() => {
    if (!outbreakId) {
      setState({ status: FOCUS_STATUS.IDLE, summary: null, sources: null, cells: null, error: null })
      return undefined
    }
    // FMD-10C: gated on the `spatialCells` capability, not the coarse
    // `ready` flag -- this hook fetches the LSD-shaped summary/cells/
    // sources snapshot specifically, which stays 409
    // ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY for FMD even now that
    // FMD has real historical origins + a real scalar risk score
    // (neither of which this hook touches).
    if (!hasCapability(diseaseCode, CAPABILITY.SPATIAL_CELLS)) {
      setState({ status: FOCUS_STATUS.UNAVAILABLE, summary: null, sources: null, cells: null, error: null })
      return undefined
    }

    let cancelled = false
    setState({ status: FOCUS_STATUS.LOADING, summary: null, sources: null, cells: null, error: null })

    Promise.all([fetchAnalysisSummary(outbreakId), fetchAnalysisSources(outbreakId), fetchAnalysisCells(outbreakId)])
      .then(([summary, sources, cells]) => {
        if (cancelled) return
        setState({ status: FOCUS_STATUS.READY, summary, sources, cells, error: null })
      })
      .catch((err) => {
        if (cancelled) return
        setState({ status: FOCUS_STATUS.ERROR, summary: null, sources: null, cells: null, error: err.message })
      })

    return () => {
      cancelled = true
    }
  }, [diseaseCode, outbreakId, refreshToken])

  return state
}

/** Pure helper (no hook) so `OutbreakMapPage` and tests can derive the
 * real available-days list the same way regardless of load state. */
export function deriveAvailableForecastDays(diseaseCode, summary) {
  if (!summary) return [0]
  return getOutbreakAdapter(diseaseCode).getAvailableForecastDays(summary)
}
