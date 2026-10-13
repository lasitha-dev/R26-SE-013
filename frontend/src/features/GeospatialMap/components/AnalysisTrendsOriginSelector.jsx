import React from 'react'

import { LABEL_ANALYSIS_ORIGIN_SELECTOR } from '../semanticLabels'

/**
 * GEO-ANALYSIS-02 Section 12 (URGENT-MATARA-REAL-FILTER: caller-scoped
 * to Matara): compact real historical/model origin picker -- `origins`
 * is `AnalysisTrendsPage.jsx`'s own real, point-in-polygon-filtered
 * `mataraOrigins` (never the full national ledger, never a fabricated
 * list). Selecting one is explicit user intent only (Section 10 -- no
 * entry is ever pre-selected here). Entries are labelled by real `t0`
 * and "retrospective" wording only -- never "live outbreak"/"current
 * outbreak"/"active infection" (Section 12's explicit rule).
 *
 * A genuinely empty list renders an honest inline statement instead of
 * silently disappearing -- zero Matara-located origins is real
 * evidence-availability state, not an error to hide.
 */
export default function AnalysisTrendsOriginSelector({ origins, selectedOriginId, onSelect }) {
  const hasOrigins = Array.isArray(origins) && origins.length > 0

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
      <span className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-slate-500">{LABEL_ANALYSIS_ORIGIN_SELECTOR}</span>
      {hasOrigins ? (
        <select
          aria-label={LABEL_ANALYSIS_ORIGIN_SELECTOR}
          value={selectedOriginId ?? ''}
          onChange={(e) => onSelect(e.target.value || null)}
          className="h-9 w-full min-w-0 rounded-md border border-white/10 bg-slate-950 px-2 text-xs text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 sm:max-w-xs"
        >
          <option value="">Select a Matara origin</option>
          {origins.map((origin) => (
            <option key={origin.originId} value={origin.originId} title={origin.originId}>
              {origin.t0 ? `t0: ${origin.t0}` : origin.originId} · retrospective
            </option>
          ))}
        </select>
      ) : (
        <span className="text-xs text-slate-500">No Matara-located historical/model origins are available for this disease</span>
      )}
    </div>
  )
}
