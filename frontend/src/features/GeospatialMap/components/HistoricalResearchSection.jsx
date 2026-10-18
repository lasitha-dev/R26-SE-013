import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import { ANALYSIS_TRENDS_REQUEST_STATE, useAnalysisTrends } from '../context/useAnalysisTrends'
import AnalysisTrendsChart from './AnalysisTrendsChart'

const PERIOD_WORD = { WEEK: 'week', MONTH: 'month', DAY: 'day' }

const EVIDENCE_ROWS = [
  ['modelEvaluation', 'Model evaluation metrics', { EVALUATION_METRICS_NOT_AVAILABLE: 'Not available from the backend' }],
  ['modelRunComparison', 'Model run comparison', { MODEL_RUN_COMPARISON_UNAVAILABLE: 'Not available' }],
  ['confidence', 'Confidence / uncertainty bands', { CONFIDENCE_NOT_AVAILABLE: 'Not available — none are shown' }],
  ['drivers', 'Driver (factor) decomposition', { DRIVER_DECOMPOSITION_NOT_AVAILABLE: 'Not available — no drivers are claimed' }],
]

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/40 p-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-white">{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>}
    </div>
  )
}

/**
 * Retrospective research record for the selected disease in Sri Lanka,
 * from the existing `GET /api/geospatial/analysis-trends` contract.
 * Explicitly historical: these are research source records with their own
 * observation dates, never current incidents, and kept visually separate
 * from the current verified-case sections above.
 */
export default function HistoricalResearchSection({ disease, diseaseShortLabel = '', reduceMotion = false }) {
  const trends = useAnalysisTrends({ disease, originId: null })
  const data = trends.data
  const summary = data?.historicalSummary
  const trend = data?.historicalTrend
  const available = summary?.status === 'AVAILABLE'
  const periodWord = PERIOD_WORD[trend?.periodBasis] ?? 'period'

  return (
    <section className="rounded-xl border border-slate-500/30 bg-slate-900/40" aria-labelledby="historical-research-title">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/5 p-3 sm:p-4">
        <div>
          <h3 id="historical-research-title" className="text-sm font-semibold text-white">Historical research record — {diseaseShortLabel}, Sri Lanka</h3>
          <p className="mt-0.5 text-xs text-slate-500">Retrospective source records used for model development. Not current incidents and not a forecast.</p>
        </div>
        <span className="rounded-full border border-slate-400/30 bg-slate-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">Retrospective</span>
      </div>
      <div className="flex flex-col gap-4 p-3 sm:p-4">
        {trends.status === ANALYSIS_TRENDS_REQUEST_STATE.LOADING && !data && <div className="text-xs text-slate-500">Loading historical research summary…</div>}
        {trends.status === ANALYSIS_TRENDS_REQUEST_STATE.ERROR && <div className="text-xs text-red-200">Historical research summary unavailable right now.</div>}
        {data && !available && <div className="text-xs text-slate-400">No historical {diseaseShortLabel} research records are available for Sri Lanka.</div>}
        {data && available && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Stat label="Historical source records" value={summary.historicalSourceCount ?? '—'} sub="Counted as research records, not cases" />
              <Stat
                label="Observation period"
                value={summary.firstObservedDate && summary.lastObservedDate ? `${formatDisplayDate(summary.firstObservedDate)} – ${formatDisplayDate(summary.lastObservedDate)}` : '—'}
                sub="Dates recorded in the source data"
              />
              <Stat label="Research forecast origins" value={summary.forecastOriginCount ?? '—'} sub="Analysis starting points in the research set" />
            </div>
            {trend?.status === 'AVAILABLE' && Array.isArray(trend.points) && trend.points.length > 0 && (
              <div>
                <div className="mb-1 text-xs font-semibold text-slate-300">Historical source records per {periodWord}</div>
                <AnalysisTrendsChart points={trend.points} periodBasis={trend.periodBasis} reduceMotion={reduceMotion} />
                <p className="mt-1 text-[11px] text-slate-500">Y axis: number of historical source records per {periodWord} (ISO {periodWord} labels). Only {periodWord}s with records are listed.</p>
              </div>
            )}
          </>
        )}
        {data && (
          <div>
            <div className="mb-1 text-xs font-semibold text-slate-300">Evidence availability</div>
            <ul className="divide-y divide-white/5 rounded-lg border border-white/10">
              {EVIDENCE_ROWS.map(([key, label, words]) => (
                <li key={key} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                  <span className="text-slate-300">{label}</span>
                  <span className="text-right text-slate-500">{words[data[key]?.status] ?? data[key]?.status ?? 'Unknown'}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}
