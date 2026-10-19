import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import { sriLankaDateKey } from '../adapters/verificationTime'

/**
 * PAGE-3-CURRENT-DASHBOARD: "Most Affected Areas" -- real districts by
 * real current-case count (`adapters/currentSurveillance.js::
 * buildCurrentMostAffectedAreas`). `rows` already arrives sorted/capped;
 * this component only renders what it is given, never pads a short real
 * list with filler rows -- if only one district has current cases, only
 * one row is shown.
 */
export default function CurrentMostAffectedAreas({ rows, status }) {
  if (status === 'loading') {
    return <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">Loading national case records…</div>
  }
  if (status === 'unavailable') {
    return <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">National case records unavailable.</div>
  }
  if (!rows || rows.length === 0) {
    return <div className="flex h-24 items-center justify-center px-3 text-center text-xs text-slate-500">No current affected areas for the selected disease.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2 font-medium">District</th>
            <th className="px-3 py-2 font-medium">Records</th>
            <th className="px-3 py-2 font-medium">Verified · pending</th>
            <th className="px-3 py-2 font-medium">Last Reported</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.district} className="border-b border-white/5 last:border-0">
              <td className="px-3 py-2 font-medium text-slate-200">{row.district}</td>
              <td className="px-3 py-2 text-emerald-300">{row.records}</td>
              <td className="px-3 py-2 text-slate-400">{Number.isFinite(row.verified) ? `${row.verified} · ${row.pending}` : '—'}</td>
              <td className="px-3 py-2 text-slate-400">{formatLastObserved(row.lastReported ?? row.lastObserved)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** `'YYYY-MM-DD HH:MM:SS'` (the real `verification_time` shape,
 * `adapters/verificationTime.js`) -> `'2 Sep 2026'`, reusing the same
 * locale-independent formatter every other Geospatial page already uses.
 * A missing/malformed value renders '—', never a guessed date. */
function formatLastObserved(verificationTime) {
  const date = sriLankaDateKey(verificationTime) // Asia/Colombo calendar date of the instant
  return date ? formatDisplayDate(date) : '—'
}
