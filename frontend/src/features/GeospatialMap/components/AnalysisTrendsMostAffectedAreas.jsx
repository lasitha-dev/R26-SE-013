import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'

/**
 * PAGE-3-NATIONAL-KPI: "Most Affected Areas" -- top real districts by
 * real, deduplicated observed-record count (`adapters/
 * nationalAreaBreakdown.js::buildMostAffectedAreas`). `rows` already
 * arrives sorted/capped; this component only renders what it is given,
 * never pads a short real list with filler rows.
 */
export default function AnalysisTrendsMostAffectedAreas({ rows, status }) {
  if (status === 'loading') {
    return <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">Resolving district geometry…</div>
  }
  if (status === 'unavailable') {
    return <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">District geometry unavailable.</div>
  }
  if (!rows || rows.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">
        No district-attributable observed records are available in the current dataset.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2 font-medium">District</th>
            <th className="px-3 py-2 font-medium">Records</th>
            <th className="px-3 py-2 font-medium">Last Observed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.district} className="border-b border-white/5 last:border-0">
              <td className="px-3 py-2 font-medium text-slate-200">{row.district}</td>
              <td className="px-3 py-2 text-emerald-300">{row.records}</td>
              <td className="px-3 py-2 text-slate-400">{row.lastObserved ? formatDisplayDate(row.lastObserved) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 pb-2 pt-1 text-[10px] text-slate-600">
        District is resolved from each record's real source coordinate; date is the most recent real origin t0 whose window covers it (no
        per-record date is exposed by the current data contract).
      </p>
    </div>
  )
}
