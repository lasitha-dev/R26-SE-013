import React, { useEffect, useMemo, useRef, useState } from 'react'

import AnalysisTrendsChart from '../components/AnalysisTrendsChart'
import AnalysisTrendsDiseaseToggle from '../components/AnalysisTrendsDiseaseToggle'
import AnalysisTrendsEvidencePanel from '../components/AnalysisTrendsEvidencePanel'
import AnalysisTrendsOriginAnalyticsPanel from '../components/AnalysisTrendsOriginAnalyticsPanel'
import AnalysisTrendsOriginSelector from '../components/AnalysisTrendsOriginSelector'
import AnalysisTrendsSummaryPanel from '../components/AnalysisTrendsSummaryPanel'
import { ANALYSIS_TRENDS_FETCH_STATUS } from '../api/analysisTrendsApi'
import { useGeospatialContext } from '../context/GeospatialContext'
import { ANALYSIS_TRENDS_REQUEST_STATE, useAnalysisTrends } from '../context/useAnalysisTrends'
import { ORIGIN_LEDGER_STATUS, useDiseaseOriginLedger } from '../context/useDiseaseOriginLedger'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import {
  ANALYSIS_TRENDS_PAGE_TAGLINE,
  ANALYSIS_TRENDS_PAGE_TITLE,
  LABEL_ANALYSIS_TRENDS_FORBIDDEN,
  LABEL_ANALYSIS_TRENDS_HOST_NOT_CONNECTED,
  LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR,
  LABEL_ANALYSIS_TRENDS_INVALID_REQUEST,
  LABEL_ANALYSIS_TRENDS_NETWORK_ERROR,
  LABEL_ANALYSIS_TRENDS_ORIGIN_NOT_FOUND,
  LABEL_ANALYSIS_TRENDS_SESSION_REQUIRED,
  LABEL_ANALYSIS_TRENDS_UNSUPPORTED_DISEASE,
  LABEL_HISTORICAL_TREND,
  LABEL_NO_HISTORICAL_DATA,
  LABEL_SCOPE_RETROSPECTIVE_SUFFIX,
} from '../semanticLabels'

const ERROR_LABEL_BY_FETCH_STATUS = {
  [ANALYSIS_TRENDS_FETCH_STATUS.SESSION_REQUIRED]: LABEL_ANALYSIS_TRENDS_SESSION_REQUIRED,
  [ANALYSIS_TRENDS_FETCH_STATUS.FORBIDDEN]: LABEL_ANALYSIS_TRENDS_FORBIDDEN,
  [ANALYSIS_TRENDS_FETCH_STATUS.HOST_COMPOSITION_REQUIRED]: LABEL_ANALYSIS_TRENDS_HOST_NOT_CONNECTED,
  [ANALYSIS_TRENDS_FETCH_STATUS.ORIGIN_NOT_FOUND]: LABEL_ANALYSIS_TRENDS_ORIGIN_NOT_FOUND,
  [ANALYSIS_TRENDS_FETCH_STATUS.UNSUPPORTED_DISEASE]: LABEL_ANALYSIS_TRENDS_UNSUPPORTED_DISEASE,
  [ANALYSIS_TRENDS_FETCH_STATUS.INVALID_REQUEST]: LABEL_ANALYSIS_TRENDS_INVALID_REQUEST,
  [ANALYSIS_TRENDS_FETCH_STATUS.ANALYSIS_INTERNAL_ERROR]: LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR,
  [ANALYSIS_TRENDS_FETCH_STATUS.SERVICE_UNAVAILABLE]: LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR,
  [ANALYSIS_TRENDS_FETCH_STATUS.NETWORK_ERROR]: LABEL_ANALYSIS_TRENDS_NETWORK_ERROR,
}

/**
 * GEO-ANALYSIS-02: Page 3 -- Analysis & Trends. Real Sri Lanka
 * historical/model evidence only; never a generic KPI dashboard filled
 * with unavailable/invented numbers (Section 1).
 *
 * Section 10: the initial request never auto-selects an origin --
 * `selectedOriginId` starts `null` and only Section 11's explicit
 * cross-page-continuity check, or an explicit user click
 * (`AnalysisTrendsOriginSelector`), ever sets it.
 *
 * Section 11: a Page-1/Page-2-selected `ctx.selectedOutbreakId` may be
 * adopted ONCE as this page's initial origin -- but ONLY after it is
 * verified present in this disease's real Sri Lanka origin ledger
 * (`useDiseaseOriginLedger`), never trusted by its string shape alone.
 * Mirrors `MyAreaPage.jsx`'s own `seededFromPage1Ref` "adopt once, never
 * re-apply" pattern exactly.
 *
 * Section 9/39: a disease change clears the selected origin (a
 * different disease has a different real ledger) via the existing
 * shared `outbreakSelectionReducer` semantics where applicable, and
 * locally otherwise -- and `useAnalysisTrends`'s own request-id guard
 * (Section 37) guarantees a slow stale response for the OLD disease/
 * origin can never overwrite the new selection's data.
 */
export default function AnalysisTrendsPage() {
  const ctx = useGeospatialContext()
  const reduceMotion = usePrefersReducedMotion()

  const [selectedOriginId, setSelectedOriginId] = useState(null)
  const [retryToken, setRetryToken] = useState(0)

  // Section 9: disease change clears any origin selection that may not
  // belong to the new disease's real ledger.
  const prevDiseaseRef = useRef(ctx.selectedDisease)
  useEffect(() => {
    if (prevDiseaseRef.current !== ctx.selectedDisease) {
      prevDiseaseRef.current = ctx.selectedDisease
      setSelectedOriginId(null)
    }
  }, [ctx.selectedDisease])

  const ledger = useDiseaseOriginLedger(ctx.selectedDisease)

  // Section 11: adopt a Page-1/Page-2 selection ONCE, only if it is a
  // real member of this disease's own Sri Lanka origin ledger -- never
  // trusted by its id string shape alone, never re-applied after an
  // explicit later choice/reset.
  const seededFromSharedSelectionRef = useRef(false)
  useEffect(() => {
    if (seededFromSharedSelectionRef.current) return
    if (ledger.status !== ORIGIN_LEDGER_STATUS.READY) return
    seededFromSharedSelectionRef.current = true
    if (ctx.selectedOutbreakId && ledger.origins.some((o) => o.originId === ctx.selectedOutbreakId)) {
      setSelectedOriginId(ctx.selectedOutbreakId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ledger.status])

  const analysisTrends = useAnalysisTrends({ disease: ctx.selectedDisease, originId: selectedOriginId, retryToken })

  function handleSelectOrigin(originId) {
    setSelectedOriginId(originId)
    if (originId) {
      ctx.selectOutbreak(originId)
    }
  }

  const data = analysisTrends.data

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto">
      <div className="flex shrink-0 flex-col gap-2">
        <div>
          <h2 className="text-lg font-semibold text-white">{ANALYSIS_TRENDS_PAGE_TITLE}</h2>
          <p className="text-xs text-slate-400">{ANALYSIS_TRENDS_PAGE_TAGLINE}</p>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <AnalysisTrendsDiseaseToggle selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
          {data?.scopeCountry && (
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-300">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>
                {data.scopeCountry} · {LABEL_SCOPE_RETROSPECTIVE_SUFFIX}
              </span>
            </div>
          )}
        </div>
      </div>

      {analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.ERROR && (
        <div className="flex shrink-0 items-center justify-between gap-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
          <span>{ERROR_LABEL_BY_FETCH_STATUS[analysisTrends.errorStatus] ?? LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR}</span>
          <button
            type="button"
            onClick={() => setRetryToken((t) => t + 1)}
            className="shrink-0 rounded border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20"
          >
            Retry
          </button>
        </div>
      )}

      {analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.LOADING && !data && (
        <div className="shrink-0 rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400">Loading Analysis &amp; Trends…</div>
      )}

      {analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.READY && data && (
        <>
          <AnalysisTrendsSummaryPanel historicalSummary={data.historicalSummary} historicalTrend={data.historicalTrend} />

          <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3">
            <div className="font-mono text-[10px] uppercase tracking-wide text-slate-500">{LABEL_HISTORICAL_TREND}</div>
            {data.historicalTrend?.points?.length > 0 ? (
              <AnalysisTrendsChart points={data.historicalTrend.points} periodBasis={data.historicalTrend.periodBasis} reduceMotion={reduceMotion} />
            ) : (
              <div className="mt-2 text-xs text-slate-500">{LABEL_NO_HISTORICAL_DATA}</div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="flex flex-col gap-3">
              <AnalysisTrendsOriginSelector
                origins={ledger.origins}
                selectedOriginId={selectedOriginId}
                onSelect={handleSelectOrigin}
              />
              <AnalysisTrendsOriginAnalyticsPanel selectedOriginAnalytics={data.selectedOriginAnalytics} />
            </div>
            <AnalysisTrendsEvidencePanel
              modelEvaluation={data.modelEvaluation}
              modelRunComparison={data.modelRunComparison}
              confidence={data.confidence}
              drivers={data.drivers}
            />
          </div>

          <div className="rounded-lg border border-white/10 bg-slate-900/50 p-3 text-[11px] text-slate-500">
            <div>Historical retrospective replay context -- not live operational surveillance.</div>
            {data.generatedAt && <div className="mt-1">Generated {data.generatedAt}</div>}
          </div>
        </>
      )}
    </div>
  )
}
