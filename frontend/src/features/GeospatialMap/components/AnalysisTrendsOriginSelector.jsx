import React from 'react'

import { LABEL_ANALYSIS_ORIGIN_SELECTOR } from '../semanticLabels'

/**
 * GEO-ANALYSIS-02 Section 12: compact real Sri Lanka historical/model
 * origin picker -- `origins` is the already-fetched real
 * `/origins`-ledger list (`useDiseaseOriginLedger`), never a fabricated
 * list. Selecting one is explicit user intent only (Section 10 -- no
 * entry is ever pre-selected here). Entries are labelled by real `t0`
 * and "retrospective" wording only -- never "live outbreak"/"current
 * outbreak"/"active infection" (Section 12's explicit rule).
 */
export default function AnalysisTrendsOriginSelector({ origins, selectedOriginId, onSelect }) {
  if (!origins || origins.length === 0) return null

  return (
    <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
      <label htmlFor="analysis-trends-origin-select" className="font-mono uppercase tracking-wide text-emerald-300">
        {LABEL_ANALYSIS_ORIGIN_SELECTOR}
      </label>
      <select
        id="analysis-trends-origin-select"
        value={selectedOriginId ?? ''}
        onChange={(e) => onSelect(e.target.value || null)}
        className="mt-2 w-full rounded-md border border-white/10 bg-slate-950 px-2 py-1.5 text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <option value="">— none selected —</option>
        {origins.map((origin) => (
          <option key={origin.originId} value={origin.originId} title={origin.originId}>
            {origin.t0 ? `t0: ${origin.t0}` : origin.originId} · retrospective
          </option>
        ))}
      </select>
    </div>
  )
}
