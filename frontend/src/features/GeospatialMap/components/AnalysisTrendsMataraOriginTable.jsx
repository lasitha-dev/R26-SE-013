import React from 'react'

/**
 * URGENT-MATARA-REAL-FILTER Section 9: "Matara Origin History" -- real
 * `mataraOrigins` rows only (never a fabricated district-subdivision
 * table, since this codebase's real data contract has no genuine Matara
 * DS/GN aggregation to show). "Scientific mode" is only ever known once
 * a SPECIFIC origin is selected (`selected_origin_analytics.
 * scientific_mode`, a different real endpoint) -- it is not present on
 * the lightweight `/origins` ledger this table is built from, so the
 * real, genuinely-available `sourceCount` (trigger source count) is
 * shown instead rather than a fabricated "scientific mode" column.
 */
export default function AnalysisTrendsMataraOriginTable({ mataraOrigins, diseaseShortLabel }) {
  if (!mataraOrigins || mataraOrigins.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">
        No {diseaseShortLabel ?? ''} historical/model origins are located inside Matara district in the available dataset.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2 font-medium">Origin</th>
            <th className="px-3 py-2 font-medium">Observed (t0)</th>
            <th className="px-3 py-2 font-medium">Disease</th>
            <th className="px-3 py-2 font-medium">Trigger Sources</th>
          </tr>
        </thead>
        <tbody>
          {mataraOrigins.map((origin) => (
            <tr key={origin.outbreakId} className="border-b border-white/5 last:border-0">
              <td className="max-w-[220px] truncate px-3 py-2 font-mono text-slate-200" title={origin.outbreakId}>
                {origin.outbreakId}
              </td>
              <td className="px-3 py-2 text-slate-300">{origin.t0 ?? '—'}</td>
              <td className="px-3 py-2 text-slate-300">{diseaseShortLabel ?? '—'}</td>
              <td className="px-3 py-2 text-slate-300">{typeof origin.sourceCount === 'number' ? origin.sourceCount : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
