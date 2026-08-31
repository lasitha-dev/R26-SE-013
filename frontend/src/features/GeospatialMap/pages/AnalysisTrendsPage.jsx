import React, { useEffect, useMemo, useRef, useState } from 'react'

import { filterOriginsInsideDistrict } from '../adapters/districtGeometry'
import { buildMataraOriginActivityPoints, mataraObservedPeriod } from '../adapters/mataraOriginActivity'
import AnalysisTrendsChart from '../components/AnalysisTrendsChart'
import AnalysisTrendsDiseaseToggle from '../components/AnalysisTrendsDiseaseToggle'
import AnalysisTrendsEvidencePanel from '../components/AnalysisTrendsEvidencePanel'
import AnalysisTrendsKeySpatialInsights from '../components/AnalysisTrendsKeySpatialInsights'
import AnalysisTrendsMataraKpiCards from '../components/AnalysisTrendsMataraKpiCards'
import AnalysisTrendsMataraOriginTable from '../components/AnalysisTrendsMataraOriginTable'
import AnalysisTrendsOriginAnalyticsPanel from '../components/AnalysisTrendsOriginAnalyticsPanel'
import AnalysisTrendsOriginSelector from '../components/AnalysisTrendsOriginSelector'
import AnalysisTrendsSummaryPanel from '../components/AnalysisTrendsSummaryPanel'
import { ANALYSIS_TRENDS_FETCH_STATUS } from '../api/analysisTrendsApi'
import { useGeospatialContext } from '../context/GeospatialContext'
import { ANALYSIS_TRENDS_REQUEST_STATE, useAnalysisTrends } from '../context/useAnalysisTrends'
import { useDistrictGeometry } from '../context/useDistrictGeometry'
import { NATIONAL_STATUS, useNationalOutbreaks } from '../context/useNationalOutbreaks'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { getDiseaseConfig } from '../disease/diseaseRegistry'
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

// Page-3-local section copy -- navigational/structural text, not a
// scientific claim, so it stays local rather than in the shared wording
// firewall (`semanticLabels.js`).
const MATARA_ACTIVITY_TITLE = 'Matara Origin Activity'
const MATARA_ACTIVITY_SUBTITLE = 'Historical/model origin occurrences inside Matara district'
const MATARA_ORIGIN_TABLE_TITLE = 'Matara Origin History'
const NATIONAL_COVERAGE_TITLE = 'Analysis Coverage'
const NATIONAL_COVERAGE_SUBTITLE = 'Sri Lanka National Scientific Context'
const ORIGIN_ANALYSIS_TITLE = 'Origin Analysis'
const ORIGIN_ANALYSIS_SUBTITLE = 'Select a Matara-located historical/model origin to inspect available origin-level evidence.'
const KEY_INSIGHTS_TITLE = 'Key Spatial Insights'
const PROVENANCE_SENTENCE = 'Historical retrospective replay context -- not live operational surveillance.'

// URGENT-MATARA-REAL-FILTER: this page's national `/analysis-trends`
// evidence (KPI "National History", the "Analysis Coverage" card) has no
// district field at all -- it is never re-labelled Matara. Matara values
// (the KPI row's Matara cards, the activity chart, the origin table/
// selector/insights) are instead derived by real point-in-polygon
// filtering of `useNationalOutbreaks`' real per-origin source geometry
// against the real Matara polygon (`districtGeometry.js`) -- never a
// district field the backend does not have, never a relabel of national
// counts.
//
// A stable module-level constant, never component state -- there is
// nothing to reset on refresh/remount/route navigation.
//
// TODO: Replace fixed Matara demo scope with authenticated vet district
// after host profile integration is finalized.
const DEFAULT_ANALYSIS_DISTRICT = 'Matara'

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
 * verified present in `mataraOrigins` (this page's real, point-in-
 * polygon-filtered Matara origin set), never trusted by its string shape
 * alone. Mirrors `MyAreaPage.jsx`'s own `seededFromPage1Ref` "adopt once,
 * never re-apply" pattern exactly.
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

  // Resolves the SAME real geoBoundaries polygon
  // (`data/sri-lanka-districts-adm2.geojson`) every other Geospatial page
  // already uses -- never a fabricated shape. Used ONLY for real
  // point-in-polygon filtering below, never rendered as a map on this
  // page (Section 17: Page 3 must not gain a map).
  const districtGeometry = useDistrictGeometry(DEFAULT_ANALYSIS_DISTRICT)

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

  // URGENT-MATARA-REAL-FILTER: the SAME real national-origin fetch (with
  // real per-origin source geometry) Page 1's `OutbreakMapPage.jsx`
  // already uses -- never a second/duplicated network call, and never a
  // district query parameter (the real `/origins` endpoint has none).
  // Real geometry is fetched for BOTH diseases (LSD via `/analysis/{id}
  // /sources`, FMD via the disease-neutral `/origins/{id}/trigger-
  // sources`), so Matara filtering works honestly for either disease.
  const national = useNationalOutbreaks(ctx.selectedDisease, 'Sri Lanka', retryToken)

  // The one real derived collection every Matara-labelled value on this
  // page reads from (Section 19: KPI/chart/table/selector/insights must
  // never disagree by using different sources) -- real source coordinates
  // inside the real Matara polygon, nothing else.
  const mataraOrigins = useMemo(
    () => filterOriginsInsideDistrict(national.originsWithSources, districtGeometry.feature),
    [national.originsWithSources, districtGeometry.feature],
  )
  const mataraActivity = useMemo(() => buildMataraOriginActivityPoints(mataraOrigins), [mataraOrigins])
  const mataraPeriod = useMemo(() => mataraObservedPeriod(mataraOrigins), [mataraOrigins])
  const mataraPeakActivity = useMemo(
    () => mataraActivity.points.reduce((peak, p) => (!peak || p.count > peak.count ? p : peak), null),
    [mataraActivity],
  )
  const mataraOriginOptions = useMemo(() => mataraOrigins.map((o) => ({ originId: o.outbreakId, t0: o.t0 })), [mataraOrigins])

  // Section 11 (adapted): adopt a Page-1/Page-2 selection ONCE, only if
  // it is a real member of the Matara-filtered set this page's selector
  // actually offers -- never trusted by its id string shape alone, never
  // re-applied after an explicit later choice/reset. Fires once the real
  // national fetch has settled into any terminal state (never only
  // READY -- an EMPTY/UNAVAILABLE/ERROR national result must still let
  // this "adopt once" gate close, rather than retry forever).
  const seededFromSharedSelectionRef = useRef(false)
  useEffect(() => {
    if (seededFromSharedSelectionRef.current) return
    if (national.status === NATIONAL_STATUS.IDLE || national.status === NATIONAL_STATUS.LOADING) return
    seededFromSharedSelectionRef.current = true
    if (ctx.selectedOutbreakId && mataraOrigins.some((o) => o.outbreakId === ctx.selectedOutbreakId)) {
      setSelectedOriginId(ctx.selectedOutbreakId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [national.status, mataraOrigins])

  const analysisTrends = useAnalysisTrends({ disease: ctx.selectedDisease, originId: selectedOriginId, retryToken })

  function handleSelectOrigin(originId) {
    setSelectedOriginId(originId)
    if (originId) {
      ctx.selectOutbreak(originId)
    }
  }

  const data = analysisTrends.data
  const isRefreshing = analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.LOADING
  const diseaseShortLabel = getDiseaseConfig(ctx.selectedDisease)?.shortLabel

  const selectedOrigin = useMemo(() => mataraOrigins.find((o) => o.outbreakId === selectedOriginId) ?? null, [mataraOrigins, selectedOriginId])

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto">
      <div className="flex shrink-0 flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold text-white">{ANALYSIS_TRENDS_PAGE_TITLE}</h2>
            <p className="mt-0.5 text-sm text-slate-400">{ANALYSIS_TRENDS_PAGE_TAGLINE}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="flex flex-wrap items-center justify-end gap-2">
              {data?.scopeCountry && (
                <div className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-300">
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  <span>
                    {data.scopeCountry} · {LABEL_SCOPE_RETROSPECTIVE_SUFFIX}
                  </span>
                </div>
              )}
              <div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-300">
                Area Scope · {DEFAULT_ANALYSIS_DISTRICT}
              </div>
            </div>
            <p className="text-[11px] text-slate-500">District origin activity · National scientific context</p>
          </div>
        </div>
        <AnalysisTrendsDiseaseToggle selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
      </div>

      {/* URGENT-MATARA-REAL-FILTER: real Matara KPIs/chart/table/insights,
          rendered unconditionally -- derived from `mataraOrigins` only
          (`useNationalOutbreaks` + real point-in-polygon filtering), never
          from the national `analysisTrends` fetch, so neither "no origin
          selected" nor a national fetch error/loading state ever blocks
          this section from appearing (Section 16's explicit "no data !=
          no page" rule). */}
      <AnalysisTrendsMataraKpiCards
        mataraOriginCount={mataraOrigins.length}
        mataraPeriod={mataraPeriod}
        nationalHistoricalSourceCount={data?.historicalSummary?.historicalSourceCount ?? null}
        selectedOriginId={selectedOriginId}
        selectedOriginT0={selectedOrigin?.t0 ?? null}
      />

      <section className="rounded-xl border border-white/10 bg-slate-900/60">
        <div className="border-b border-white/5 p-3 sm:p-4">
          <h3 className="text-sm font-semibold text-white">{MATARA_ACTIVITY_TITLE}</h3>
          <p className="mt-0.5 text-xs text-slate-500">{MATARA_ACTIVITY_SUBTITLE}</p>
        </div>
        <div className="p-3 sm:p-4">
          {mataraActivity.points.length > 0 ? (
            <AnalysisTrendsChart points={mataraActivity.points} periodBasis={mataraActivity.periodBasis} reduceMotion={reduceMotion} />
          ) : (
            <div className="flex h-32 items-center justify-center px-3 text-center text-xs text-slate-500">
              No {diseaseShortLabel ?? ''} historical/model origins are located inside Matara district in the available dataset.
            </div>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-2">
        <section className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60">
          <div className="border-b border-white/5 p-3 sm:p-4">
            <h3 className="text-sm font-semibold text-white">{MATARA_ORIGIN_TABLE_TITLE}</h3>
          </div>
          <AnalysisTrendsMataraOriginTable mataraOrigins={mataraOrigins} diseaseShortLabel={diseaseShortLabel} />
        </section>

        <section className="rounded-xl border border-white/10 bg-slate-900/60 p-3 sm:p-4">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">{NATIONAL_COVERAGE_TITLE}</h3>
            <span className="shrink-0 rounded-full border border-white/10 bg-slate-950/50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              National
            </span>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">{NATIONAL_COVERAGE_SUBTITLE}</p>
          <div className="mt-3">
            {data ? (
              <AnalysisTrendsSummaryPanel historicalSummary={data.historicalSummary} historicalTrend={data.historicalTrend} />
            ) : (
              <div className="text-xs text-slate-500">{analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.LOADING ? 'Loading national context…' : 'National context unavailable'}</div>
            )}
          </div>
        </section>
      </div>

      {analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.ERROR && (
        <div className="flex shrink-0 items-center justify-between gap-3 rounded-xl border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
          <span>{ERROR_LABEL_BY_FETCH_STATUS[analysisTrends.errorStatus] ?? LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR}</span>
          <button
            type="button"
            onClick={() => setRetryToken((t) => t + 1)}
            className="shrink-0 rounded-md border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20"
          >
            Retry
          </button>
        </div>
      )}

      {analysisTrends.status === ANALYSIS_TRENDS_REQUEST_STATE.LOADING && !data && (
        <div className="shrink-0 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400">Loading Analysis &amp; Trends…</div>
      )}

      {data && (
        <div
          className={[
            'flex flex-col gap-4',
            reduceMotion ? '' : 'transition-opacity duration-200',
            isRefreshing ? 'opacity-60' : 'opacity-100',
          ].join(' ')}
        >
          <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-2 xl:grid-cols-12">
            <section className="flex flex-col gap-3 rounded-xl border border-white/10 bg-slate-900/60 p-3 sm:p-4 xl:col-span-7">
              <div>
                <div className="flex items-baseline gap-2">
                  <h3 className="text-sm font-semibold text-white">{ORIGIN_ANALYSIS_TITLE}</h3>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-300">District context · Matara</span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">{ORIGIN_ANALYSIS_SUBTITLE}</p>
              </div>
              <AnalysisTrendsOriginSelector origins={mataraOriginOptions} selectedOriginId={selectedOriginId} onSelect={handleSelectOrigin} />
              <AnalysisTrendsOriginAnalyticsPanel selectedOriginAnalytics={data.selectedOriginAnalytics} />
            </section>

            <section className="xl:col-span-5">
              <AnalysisTrendsEvidencePanel
                modelEvaluation={data.modelEvaluation}
                modelRunComparison={data.modelRunComparison}
                confidence={data.confidence}
                drivers={data.drivers}
              />
            </section>
          </div>

          <section className="rounded-xl border border-white/10 bg-slate-900/60 p-3 sm:p-4">
            <h3 className="text-sm font-semibold text-white">{KEY_INSIGHTS_TITLE}</h3>
            <div className="mt-3">
              <AnalysisTrendsKeySpatialInsights
                mataraOriginCount={mataraOrigins.length}
                mataraPeriod={mataraPeriod}
                peakActivity={mataraPeakActivity}
                selectedOriginAnalytics={data.selectedOriginAnalytics}
              />
            </div>
          </section>

          <div className="rounded-xl border border-white/10 bg-slate-900/40 px-3 py-2.5 text-[11px] text-slate-500">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="font-medium text-slate-400">{LABEL_SCOPE_RETROSPECTIVE_SUFFIX}</span>
              <span>{PROVENANCE_SENTENCE}</span>
            </div>
            {data.generatedAt && <div className="mt-1 text-slate-600">Generated {data.generatedAt}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
