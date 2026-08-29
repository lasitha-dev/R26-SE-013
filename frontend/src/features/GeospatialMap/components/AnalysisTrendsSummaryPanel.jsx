import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import {
  LABEL_FORECAST_ORIGINS,
  LABEL_HISTORICAL_SOURCE_RECORDS,
  LABEL_NO_HISTORICAL_DATA,
  LABEL_OBSERVATION_COVERAGE,
  LABEL_TREND_BASIS,
} from '../semanticLabels'

/**
 * GEO-ANALYSIS-02 Section 15/16/17: the KPI row -- ONLY the four real
 * values `historical_summary` actually supplies. No score/rate/count
 * this component does not itself receive as a real prop is ever
 * rendered or derived here; `historical_source_
 * count` and `forecast_origin_count` are always two SEPARATE cards,
 * never summed (Section 16).
 */
export default function AnalysisTrendsSummaryPanel({ historicalSummary, historicalTrend }) {
  if (!historicalSummary || historicalSummary.status !== 'AVAILABLE') {
    return (
      <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs text-slate-400">{LABEL_NO_HISTORICAL_DATA}</div>
    )
  }

  const coverage =
    historicalSummary.firstObservedDate && historicalSummary.lastObservedDate
      ? `${formatDisplayDate(historicalSummary.firstObservedDate)} – ${formatDisplayDate(historicalSummary.lastObservedDate)}`
      : '—'

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Card label={LABEL_HISTORICAL_SOURCE_RECORDS} value={historicalSummary.historicalSourceCount ?? '—'} />
      <Card label={LABEL_FORECAST_ORIGINS} value={historicalSummary.forecastOriginCount ?? '—'} />
      <Card label={LABEL_OBSERVATION_COVERAGE} value={coverage} compactValue />
      <Card label={LABEL_TREND_BASIS} value={historicalTrend?.periodBasis ?? '—'} />
    </div>
  )
}

function Card({ label, value, compactValue = false }) {
  return (
    <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3">
      <div className="font-mono text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={compactValue ? 'mt-1 text-sm font-semibold text-white' : 'mt-1 text-2xl font-semibold text-white'}>{value}</div>
    </div>
  )
}
