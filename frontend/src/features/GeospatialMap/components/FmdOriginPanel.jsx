import React from 'react'

import { FMD_RISK_STATUS } from '../context/useFmdOriginRisk'
import {
  DISCLAIMER_RELATIVE_ORIGIN_SPATIAL_SCORE,
  LABEL_FMD_HISTORICAL_ORIGINS,
  LABEL_FMD_ORIGIN_PANEL_SUBTITLE,
  LABEL_FMD_RISK_ERROR,
  LABEL_FMD_RISK_LOADING,
  LABEL_FMD_RISK_NOT_FOUND,
  LABEL_FMD_RISK_UNAVAILABLE,
  LABEL_RELATIVE_ORIGIN_SPATIAL_SCORE,
} from '../semanticLabels'

/**
 * FMD-10C1: Page 1's FMD-only real-origin picker + scalar risk panel.
 * FMD-10C1 added real circle-marker points on the map itself
 * (`/origins/{id}/trigger-sources`, rendered by `MapLibreCanvas.jsx`'s
 * `national-sources-symbol` layer) -- this panel is now a SECONDARY,
 * accessible/selectable list over the same real `/origins` ledger, not
 * the only representation of FMD historical origins (that was FMD-10C's
 * honest-but-incomplete fallback while no coordinate-bearing endpoint
 * existed). Once an origin is selected (from either the map or this
 * list), its real scalar `risk_score` (`GET /analysis/{id}/fmd-risk`)
 * is shown verbatim -- a raw number, never `%`, never reclassified
 * against the backend's own threshold.
 */
export default function FmdOriginPanel({ origins, selectedOriginId, onSelect, risk }) {
  if (!origins || origins.length === 0) return null

  return (
    <div className="pointer-events-auto w-72 rounded-lg border border-white/10 bg-slate-900/85 p-3 text-xs text-slate-300 shadow-xl backdrop-blur">
      <div className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_FMD_HISTORICAL_ORIGINS}</div>
      <div className="mt-1 text-slate-500">{LABEL_FMD_ORIGIN_PANEL_SUBTITLE}</div>

      <select
        className="mt-2 w-full rounded-md border border-white/10 bg-slate-950 px-2 py-1.5 text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
        value={selectedOriginId ?? ''}
        onChange={(e) => onSelect(e.target.value || null)}
        aria-label={LABEL_FMD_HISTORICAL_ORIGINS}
      >
        <option value="">— none selected —</option>
        {origins.map((origin) => (
          <option key={origin.outbreakId} value={origin.outbreakId} title={origin.outbreakId}>
            {origin.t0 ? `t0: ${origin.t0}` : origin.outbreakId} · {origin.country}
          </option>
        ))}
      </select>

      {selectedOriginId && risk && (
        <div className="mt-3 border-t border-white/10 pt-2">
          <div className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_RELATIVE_ORIGIN_SPATIAL_SCORE}</div>
          {risk.status === FMD_RISK_STATUS.LOADING && <div className="mt-1 text-slate-400">{LABEL_FMD_RISK_LOADING}</div>}
          {risk.status === FMD_RISK_STATUS.READY && (
            <>
              <div className="mt-1 text-lg font-semibold text-slate-100">{risk.data.risk_score?.toFixed(4)}</div>
              <div className="mt-1 text-slate-500">{DISCLAIMER_RELATIVE_ORIGIN_SPATIAL_SCORE}</div>
              <div className="mt-1 text-slate-500">Eligible sources: {risk.data.n_eligible_sources}</div>
            </>
          )}
          {risk.status === FMD_RISK_STATUS.UNAVAILABLE && <div className="mt-1 text-slate-400">{LABEL_FMD_RISK_UNAVAILABLE}</div>}
          {risk.status === FMD_RISK_STATUS.NOT_FOUND && <div className="mt-1 text-slate-400">{LABEL_FMD_RISK_NOT_FOUND}</div>}
          {risk.status === FMD_RISK_STATUS.ERROR && <div className="mt-1 text-red-300">{LABEL_FMD_RISK_ERROR}</div>}
        </div>
      )}
    </div>
  )
}
