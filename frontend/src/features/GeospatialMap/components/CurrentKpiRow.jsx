import React from 'react'

const UNAVAILABLE_NOTE = 'National case records unavailable'

/**
 * The Analysis & Trends KPI row -- Recorded cases / Affected areas /
 * Clusters / Forecast horizon. Every number is a real prop computed by the
 * page from the API response (never here). Loading shows "—"; a failed
 * request shows "N/A" with the reason; a genuine zero is shown as 0.
 * `loadStatus` / `clusterStatus` are `'loading' | 'ready' | 'unavailable'`.
 */
export default function CurrentKpiRow({
  loadStatus,
  currentRecordsCount,
  recordsSublabel = null,
  affectedAreasCount,
  affectedAreasSublabel = null,
  clusterStatus = 'unavailable',
  clusterCount = null,
  clusterSublabel = null,
}) {
  const isReady = loadStatus === 'ready'
  const isLoading = loadStatus === 'loading'

  const currentRecordsValue = isReady ? currentRecordsCount : isLoading ? '—' : 'N/A'
  const affectedAreasValue = isReady ? affectedAreasCount : isLoading ? '—' : 'N/A'
  const dynamicSublabel = isReady ? undefined : isLoading ? 'Loading national case records…' : UNAVAILABLE_NOTE
  const clusterValue = clusterStatus === 'ready' && Number.isFinite(clusterCount) ? clusterCount : clusterStatus === 'loading' ? '—' : 'N/A'
  const clusterNote = clusterStatus === 'ready'
    ? clusterSublabel ?? 'Exploratory ST-DBSCAN output'
    : clusterStatus === 'loading'
      ? 'Computing exploratory clusters…'
      : 'Current cluster output unavailable'

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <KpiCard label="Recorded Cases" value={currentRecordsValue} sublabel={dynamicSublabel ?? recordsSublabel ?? 'ADRS case reports, all dates'} />
      <KpiCard label="Affected Areas" value={affectedAreasValue} sublabel={dynamicSublabel ?? affectedAreasSublabel ?? 'Districts with at least one report'} />
      <KpiCard label="Space-time Clusters" value={clusterValue} sublabel={clusterNote} />
      <KpiCard label="Forecast Horizon" value="Not available" sublabel="History only · exploratory 14-day outlook on Map / My Area" />
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
      {sublabel && (
        <div className="truncate text-[10px] text-slate-500" title={sublabel}>
          {sublabel}
        </div>
      )}
    </div>
  )
}
