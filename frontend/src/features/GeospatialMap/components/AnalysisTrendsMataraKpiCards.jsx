import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'

/**
 * URGENT-MATARA-REAL-FILTER: the Matara-scoped KPI row. Every value here
 * is derived from `mataraOrigins` (real database-backed origins whose
 * real source coordinates fall inside the real Matara polygon --
 * `AnalysisTrendsPage.jsx`'s own `districtGeometry.js::
 * filterOriginsInsideDistrict`) EXCEPT the third card, which is
 * genuinely national (Page 3's own `/analysis-trends` contract has no
 * district field to filter -- Section 3 of the spec) and is labelled
 * "National History" rather than silently mixed in as if it were
 * Matara-specific.
 */
export default function AnalysisTrendsMataraKpiCards({ mataraOriginCount, mataraPeriod, nationalHistoricalSourceCount, selectedOriginId, selectedOriginT0 }) {
  const periodValue = mataraPeriod ? `${formatDisplayDate(mataraPeriod.firstDate)} – ${formatDisplayDate(mataraPeriod.lastDate)}` : 'No Matara observations'

  const shortOriginId = selectedOriginId ? selectedOriginId.replace(/^ORIGIN:/, '') : null

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Card label="Matara Origins" value={mataraOriginCount} sublabel="Historical/model origins located in Matara" />
      <Card label="Observed Period" value={periodValue} compactValue sublabel="Matara origin date range" />
      <Card label="National History" value={nationalHistoricalSourceCount ?? '—'} sublabel="Sri Lanka historical source records" />
      <Card
        label="Selected Origin"
        value={selectedOriginId ? shortOriginId : 'Matara View'}
        valueTitle={selectedOriginId ?? undefined}
        compactValue
        sublabel={selectedOriginId ? `t0: ${selectedOriginT0 ?? '—'}` : 'No origin selected'}
      />
    </div>
  )
}

function Card({ label, value, sublabel, compactValue = false, valueTitle }) {
  return (
    <div className="flex flex-col justify-center gap-1 rounded-lg border border-white/5 bg-slate-950/40 px-3 py-3">
      <div className="font-mono text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={compactValue ? 'truncate text-sm font-semibold text-white' : 'text-xl font-semibold text-white'} title={valueTitle}>
        {value}
      </div>
      {sublabel && <div className="truncate text-[10px] text-slate-500">{sublabel}</div>}
    </div>
  )
}
