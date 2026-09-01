import React from 'react'

/**
 * PAGE-3-NATIONAL-KPI: the top-of-page KPI row -- Observed Records /
 * Affected Areas / Observed Clusters / Forecast Horizon. Every value is
 * a prop this component receives verbatim; it never computes a
 * scientific number itself (that lives in `pages/AnalysisTrendsPage.jsx`
 * and the pure adapters it calls). A value this page cannot honestly
 * support renders "Not available"/"N/A" here, never a fabricated number
 * -- there is deliberately no fallback branch that substitutes a sample
 * value.
 */
export default function AnalysisTrendsKpiRow({ observedRecordsCount, affectedAreas, forecastHorizon }) {
  const affectedAreasValue =
    affectedAreas.status === 'ready' ? affectedAreas.count : affectedAreas.status === 'loading' ? '—' : 'Not available'
  const affectedAreasSublabel =
    affectedAreas.status === 'ready'
      ? 'Unique districts with a real observed record'
      : affectedAreas.status === 'loading'
        ? 'Resolving district geometry…'
        : 'District geometry unavailable'

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <KpiCard label="Observed Records" value={typeof observedRecordsCount === 'number' ? observedRecordsCount : '—'} sublabel="Historical source records · Sri Lanka" />
      <KpiCard label="Affected Areas" value={affectedAreasValue} sublabel={affectedAreasSublabel} />
      <KpiCard label="Observed Clusters" value="N/A" sublabel="No ST-DBSCAN cluster output is exposed by the runtime API yet." />
      <KpiCard
        label="Forecast Horizon"
        value={forecastHorizon.available ? `${forecastHorizon.days} day${forecastHorizon.days === 1 ? '' : 's'}` : 'Not available'}
        sublabel={forecastHorizon.note}
      />
    </div>
  )
}

function KpiCard({ label, value, sublabel }) {
  return (
    <div className="flex flex-col justify-center gap-1 rounded-lg border border-white/5 bg-slate-950/40 px-3 py-3">
      <div className="font-mono text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className="truncate text-xl font-semibold text-white" title={typeof value === 'string' ? value : undefined}>
        {value}
      </div>
      {sublabel && <div className="truncate text-[10px] text-slate-500" title={sublabel}>{sublabel}</div>}
    </div>
  )
}
