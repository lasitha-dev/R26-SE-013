import React, { useMemo, useState } from 'react'

import {
  DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS,
  buildCurrentMostAffectedAreas,
  buildRecentActivityBuckets,
  deriveCurrentAffectedAreas,
  deriveCurrentRecordCount,
  filterCurrentContextsByDisease,
} from '../adapters/currentSurveillance'
import AnalysisTrendsChart from '../components/AnalysisTrendsChart'
import AnalysisTrendsDiseaseToggle from '../components/AnalysisTrendsDiseaseToggle'
import CurrentActivityWindowToggle from '../components/CurrentActivityWindowToggle'
import CurrentKpiRow from '../components/CurrentKpiRow'
import CurrentMostAffectedAreas from '../components/CurrentMostAffectedAreas'
import { useGeospatialContext } from '../context/GeospatialContext'
import { OPERATIONAL_STATE, useOperationalContext } from '../context/useOperationalContext'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import {
  LABEL_OPERATIONAL_STATUS_FORBIDDEN,
  LABEL_OPERATIONAL_STATUS_HOST_COMPOSITION_REQUIRED,
  LABEL_OPERATIONAL_STATUS_SESSION_REQUIRED,
  LABEL_OPERATIONAL_STATUS_UNAVAILABLE,
} from '../semanticLabels'

const PAGE_TITLE = 'Analysis & Trends'
const PAGE_TAGLINE = 'Current outbreak patterns and spatial intelligence'
const SCOPE_BADGE = 'Sri Lanka · Current surveillance'
const ACTIVITY_TITLE = 'Recent Outbreak Activity'
const ACTIVITY_SUBTITLE = 'Current verified outbreak records'
const MOST_AFFECTED_AREAS_TITLE = 'Most Affected Areas'

const UNAVAILABLE_LABEL_BY_STATE = {
  [OPERATIONAL_STATE.SESSION_REQUIRED]: LABEL_OPERATIONAL_STATUS_SESSION_REQUIRED,
  [OPERATIONAL_STATE.FORBIDDEN]: LABEL_OPERATIONAL_STATUS_FORBIDDEN,
  [OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED]: LABEL_OPERATIONAL_STATUS_HOST_COMPOSITION_REQUIRED,
  [OPERATIONAL_STATE.OPERATIONAL_UNAVAILABLE]: LABEL_OPERATIONAL_STATUS_UNAVAILABLE,
  [OPERATIONAL_STATE.ERROR]: LABEL_OPERATIONAL_STATUS_UNAVAILABLE,
}

/**
 * PAGE-3-CURRENT-DASHBOARD: Analysis & Trends, rebuilt to a small
 * CURRENT-surveillance dashboard -- header, disease toggle, four real KPI
 * cards, one real recent-activity chart, one real most-affected-areas
 * table. Nothing below reads the retrospective/historical `/origins` or
 * `/analysis-trends` ledgers (those research-era modules still exist
 * under `adapters/`/`components/` for any future workflow that needs
 * them, but this page's render path no longer depends on their output).
 *
 * The one real, current, DB-backed collection every value on this page
 * derives from is `useOperationalContext()`'s `surveillanceContexts` --
 * the SAME Verified Clinical Context data Page 1's `OutbreakMapPage.jsx`
 * already renders as solid red confirmed-case markers
 * (`operationalMarkerLayer.js` / `operationalIcons.js`'s
 * `CLINICAL_MARKER_COLOR_HEX`). This page fetches its own independent
 * instance of that hook (its own ~2s reconciliation cycle, its own SSE
 * fallback semantics) -- mirroring every other page in this feature,
 * which each own their own data-fetching hook instance; only UI
 * selection state (`ctx.selectedDisease`) is shared via
 * `GeospatialContext`.
 */
export default function AnalysisTrendsPage() {
  const ctx = useGeospatialContext()
  const reduceMotion = usePrefersReducedMotion()
  const operational = useOperationalContext()

  const [windowDays, setWindowDays] = useState(DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS)

  // Section 6/7: the real current, DB-backed collection -- never the
  // retrospective historical/model ledger, never Page 1's presentation-
  // only forecast/spread visuals (those are never part of this data).
  const currentContexts = useMemo(
    () => filterCurrentContextsByDisease(operational.data?.surveillanceContexts, ctx.selectedDisease),
    [operational.data, ctx.selectedDisease],
  )

  const loadStatus =
    operational.state === OPERATIONAL_STATE.CONNECTED || operational.state === OPERATIONAL_STATE.STALE
      ? 'ready'
      : operational.state === OPERATIONAL_STATE.IDLE || operational.state === OPERATIONAL_STATE.LOADING
        ? 'loading'
        : 'unavailable'

  const currentRecordsCount = useMemo(() => deriveCurrentRecordCount(currentContexts), [currentContexts])
  const affectedAreas = useMemo(() => deriveCurrentAffectedAreas(currentContexts), [currentContexts])
  const mostAffectedAreas = useMemo(() => buildCurrentMostAffectedAreas(currentContexts, { topN: 5 }), [currentContexts])
  const activity = useMemo(() => buildRecentActivityBuckets(currentContexts, windowDays), [currentContexts, windowDays])

  const hasAnyActivity = activity.points.some((p) => p.count > 0)
  const unavailableNote = UNAVAILABLE_LABEL_BY_STATE[operational.state]

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto">
      <div className="flex shrink-0 flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold text-white">{PAGE_TITLE}</h2>
            <p className="mt-0.5 text-sm text-slate-400">{PAGE_TAGLINE}</p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-300">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span>{SCOPE_BADGE}</span>
          </div>
        </div>
        <AnalysisTrendsDiseaseToggle selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
      </div>

      <CurrentKpiRow loadStatus={loadStatus} currentRecordsCount={currentRecordsCount} affectedAreasCount={affectedAreas.count} />

      <section className="rounded-xl border border-white/10 bg-slate-900/60">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/5 p-3 sm:p-4">
          <div>
            <h3 className="text-sm font-semibold text-white">{ACTIVITY_TITLE}</h3>
            <p className="mt-0.5 text-xs text-slate-500">{ACTIVITY_SUBTITLE}</p>
          </div>
          <CurrentActivityWindowToggle selectedDays={windowDays} onSelect={setWindowDays} />
        </div>
        <div className="p-3 sm:p-4">
          {loadStatus === 'unavailable' ? (
            <div className="flex h-32 items-center justify-center px-3 text-center text-xs text-slate-500">{unavailableNote}</div>
          ) : loadStatus === 'loading' ? (
            <div className="flex h-32 items-center justify-center px-3 text-center text-xs text-slate-500">Loading current surveillance data…</div>
          ) : hasAnyActivity ? (
            <AnalysisTrendsChart points={activity.points} periodBasis="DAY" reduceMotion={reduceMotion} />
          ) : (
            <div className="flex h-32 items-center justify-center px-3 text-center text-xs text-slate-500">
              No current outbreak activity in this period.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-slate-900/60">
        <div className="border-b border-white/5 p-3 sm:p-4">
          <h3 className="text-sm font-semibold text-white">{MOST_AFFECTED_AREAS_TITLE}</h3>
        </div>
        <CurrentMostAffectedAreas rows={mostAffectedAreas} status={loadStatus} />
      </section>
    </div>
  )
}
