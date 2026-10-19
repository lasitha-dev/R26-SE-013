import React, { useMemo, useState } from 'react'

import {
  buildAffectedAreas,
  buildClusterRows,
  buildDailyActivity,
  forecastHorizon,
  prepareRecords,
  scopeRecords,
  summarizeWindow,
} from '../adapters/analysisSurveillance'
import { CURRENT_ACTIVITY_WINDOW_OPTIONS, DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS } from '../adapters/currentSurveillance'
import { formatDisplayDate } from '../adapters/forecastDate'
import { normalizeDistrictDisplayName } from '../adapters/districtGeometry'
import { ActivityChart, AffectedAreasTable, Card, ClusterTable, KpiCard, SegmentedControl, shortDay } from '../components/AnalysisSurveillanceCards'
import { getDiseaseConfig, listDiseaseCodes } from '../disease/diseaseRegistry'
import { useGeospatialContext } from '../context/GeospatialContext'
import { NATIONAL_CASES_STATE, nationalCasesEventKey, useNationalCases } from '../context/useNationalCases'
import { eligibleSourceSignature } from '../adapters/liveSourceSignature'
import { useSourceChangeToken } from '../context/useSourceChangeToken'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { useOperationalContext } from '../context/useOperationalContext'
import { useDistrictGeometry } from '../context/useDistrictGeometry'
import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'
import { useSpatialTimeline } from '../context/useSpatialTimeline'
import { useStClusters } from '../context/useStClusters'

const PAGE_TITLE = 'Analysis & Trends'
const PAGE_TAGLINE = 'Current outbreak patterns and spatial intelligence'
const ACTIVITY_TITLE = 'Recent Outbreak Activity'
const MOST_AFFECTED_AREAS_TITLE = 'Most Affected Areas'

const UNAVAILABLE_LABEL_BY_STATE = {
  [NATIONAL_CASES_STATE.SESSION_REQUIRED]: 'Sign-in required: case records were not loaded.',
  [NATIONAL_CASES_STATE.ERROR]: 'Case records could not be loaded (request failed).',
}

/**
 * Analysis & Trends: current surveillance for the logged-in vet's district
 * (default) or Sri Lanka, from real ADRS case reports (`/national-cases`,
 * vet-verified + pending, privacy-reduced), the runtime ST-DBSCAN clusters
 * (`/st-clusters`) and the backend spatial timeline (forecast horizon).
 * Counts are for the selected window ending today; the change column
 * compares with the window just before it. Historical WAHIS/EMPRES research
 * records are a different population and are not shown on this page.
 */
export default function AnalysisTrendsPage() {
  const ctx = useGeospatialContext()
  const operational = useOperationalContext()
  const clinicalEvents = useVerifiedClinicalEvents()
  const nationalCases = useNationalCases({ heartbeat: operational.lastRefreshedAt, eventKey: nationalCasesEventKey(clinicalEvents) })
  const stClusters = useStClusters({ disease: ctx.selectedDisease, enabled: Boolean(ctx.selectedDisease), refreshToken: clinicalEvents.dataChangeToken })

  const [windowDays, setWindowDays] = useState(DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS)
  const [analysisScope, setAnalysisScope] = useState('district')
  const districtName = normalizeDistrictDisplayName(operational.data?.vetDistrict)
  const districtResolved = Boolean(districtName) && districtName.toUpperCase().replace(/[^A-Z]/g, '') !== 'ALLDISTRICTS'
  const { feature: districtFeature, status: districtGeometryStatus, featureCollection: districtCollection } = useDistrictGeometry(districtName)
  const national = analysisScope === 'national'
  const scopeLabel = national ? 'Sri Lanka' : districtName ?? 'Your authorised district'
  const diseaseShortLabel = getDiseaseConfig(ctx.selectedDisease).shortLabel
  // Forecast horizon from the same backend spatial timeline the maps use.
  const sourceSignature = useMemo(() => eligibleSourceSignature(nationalCases.data?.records, ctx.selectedDisease), [nationalCases.data, ctx.selectedDisease])
  const sourceChangeToken = useSourceChangeToken(sourceSignature)
  const timeline = useSpatialTimeline({
    disease: ctx.selectedDisease, scope: national ? 'national' : 'district', district: national ? null : districtName,
    enabled: Boolean(ctx.selectedDisease) && (national || districtResolved), refreshToken: `${clinicalEvents.dataChangeToken}:${sourceChangeToken}`,
  })

  const prepared = useMemo(() => prepareRecords(nationalCases.data?.records, ctx.selectedDisease, districtCollection), [nationalCases.data, ctx.selectedDisease, districtCollection])
  const records = useMemo(() => scopeRecords(prepared, { scope: analysisScope, districtName }), [prepared, analysisScope, districtName])
  const summary = useMemo(() => summarizeWindow(records, { windowDays, scope: analysisScope }), [records, windowDays, analysisScope])
  const activity = useMemo(() => buildDailyActivity(records, { windowDays }), [records, windowDays])
  const horizon = forecastHorizon(timeline.data)
  const areas = useMemo(() => buildAffectedAreas(prepared, {
    windowDays, scope: analysisScope, districtName, districtFeature, nearbyKm: horizon?.relevanceKm ?? null, topN: 10,
  }), [prepared, windowDays, analysisScope, districtName, districtFeature, horizon?.relevanceKm])
  const clusterRows = useMemo(() => buildClusterRows(stClusters.data, { districtCollection, districtFeature, scope: analysisScope }), [stClusters.data, districtCollection, districtFeature, analysisScope])

  const districtPending = !national && !operational.data && [OPERATIONAL_STATE.IDLE, OPERATIONAL_STATE.LOADING].includes(operational.state)
  const districtUnavailable = !national && !districtPending && !districtResolved
  const loadStatus = districtPending ? 'loading' : districtUnavailable ? 'unavailable' : nationalCases.status === NATIONAL_CASES_STATE.READY && nationalCases.data
    ? 'ready'
    : nationalCases.status === NATIONAL_CASES_STATE.IDLE || nationalCases.status === NATIONAL_CASES_STATE.LOADING ? 'loading' : 'unavailable'
  const unavailableNote = districtUnavailable
    ? 'No single authorised district is resolved for this account. Select Sri Lanka for national analysis.'
    : UNAVAILABLE_LABEL_BY_STATE[nationalCases.status] ?? UNAVAILABLE_LABEL_BY_STATE[NATIONAL_CASES_STATE.ERROR]
  const clusterStatus = !national && !districtFeature
    ? (districtGeometryStatus === 'idle' || districtGeometryStatus === 'loading' ? 'loading' : 'unavailable')
    : stClusters.status === 'ready' && stClusters.data ? 'ready' : stClusters.status === 'error' ? 'unavailable' : 'loading'
  const timelineStatus = timeline.data ? 'ready' : timeline.status === 'error' ? 'unavailable' : 'loading'
  const ready = loadStatus === 'ready'
  const hasActivity = activity.some((d) => d.verified + d.pending > 0)
  const windowText = `${formatDisplayDate(summary.startKey)} – ${formatDisplayDate(summary.endKey)}`

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pb-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-[30px] font-extrabold leading-tight tracking-tight text-white">{PAGE_TITLE}</h2>
          <p className="mt-1 text-[14px] text-on-surface-variant/80">{PAGE_TAGLINE}</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-outline-variant/40 bg-surface-container/70 px-4 py-2 text-[13px] text-on-surface" data-scope-pill>
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-emerald-400" />
          <span>{scopeLabel} · Current surveillance</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-outline-variant/30 bg-surface-container/70 px-4 py-3 shadow-card-subtle">
        <SegmentedControl label="Disease" options={listDiseaseCodes().map((code) => [code, getDiseaseConfig(code).shortLabel])} value={ctx.selectedDisease} onChange={ctx.selectDisease} />
        <span aria-hidden="true" className="hidden h-7 w-px bg-outline-variant/30 sm:block" />
        <SegmentedControl label="Analysis geography" options={[['district', districtName ? `My district · ${districtName}` : 'My district'], ['national', 'Sri Lanka']]} value={analysisScope} onChange={setAnalysisScope} />
        <span className="ml-auto text-[11.5px] text-on-surface-variant/60">ADRS case reports · vet-verified + pending · report date (Asia/Colombo)</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard name="records" label="Current records" loading={loadStatus === 'loading'}
          value={ready ? summary.current : 'N/A'}
          sub={ready ? `${summary.verified} verified · ${summary.pending} pending · last ${windowDays} days` : unavailableNote} />
        <KpiCard name="areas" label="Affected areas" loading={loadStatus === 'loading'}
          value={ready ? summary.affectedAreas : 'N/A'}
          sub={ready ? (national ? `Unique districts with a current record${summary.withoutDistrict ? ` · ${summary.withoutDistrict} without district` : ''}` : `Farm locations in ${districtName} with a current record${summary.withoutGps ? ` · ${summary.withoutGps} without GPS` : ''}`) : unavailableNote} />
        <KpiCard name="clusters" label="Current clusters" loading={clusterStatus === 'loading'}
          value={clusterStatus === 'ready' ? (clusterRows.length || 'N/A') : 'N/A'}
          sub={clusterStatus === 'ready'
            ? (clusterRows.length ? `ST-DBSCAN space–time clusters${national ? '' : ` with a member in ${districtName}`}` : 'No cluster meets ε / minPts (12.4 km · 3 days · 2 farms)')
            : 'Cluster analysis unavailable'} />
        <KpiCard name="horizon" label="Forecast horizon" loading={timelineStatus === 'loading'}
          value={horizon ? `${shortDay(horizon.from)} – ${shortDay(horizon.to)}` : 'N/A'}
          sub={horizon ? `Day 0–${horizon.lastDay} · ${horizon.sources} eligible source${horizon.sources === 1 ? '' : 's'}` : 'No eligible source cases or model frames'} />
      </div>

      <Card
        title={ACTIVITY_TITLE}
        subtitle={`Reported clinical cases per day · verified and pending · ${scopeLabel} · ${windowText}`}
        right={<SegmentedControl size="sm" label="Activity window" options={CURRENT_ACTIVITY_WINDOW_OPTIONS.map((o) => [o.days, o.label])} value={windowDays} onChange={setWindowDays} />}
      >
        {loadStatus === 'unavailable' ? (
          <div className="flex h-40 items-center justify-center px-4 text-center text-[12px] text-on-surface-variant/60">{unavailableNote}</div>
        ) : loadStatus === 'loading' ? (
          <div className="flex h-40 items-center justify-center px-4 text-center text-[12px] text-on-surface-variant/60">Loading {scopeLabel} case records…</div>
        ) : hasActivity ? (
          <ActivityChart days={activity} />
        ) : (
          <div className="flex h-40 flex-col items-center justify-center gap-1 px-4 text-center text-[12px] text-on-surface-variant/60" data-state="no-activity">
            <span>No current outbreak activity in this period.</span>
            <span>{summary.allDates === 0
              ? `No ${diseaseShortLabel} case reports are recorded for ${scopeLabel}.`
              : `${summary.allDates} older report${summary.allDates === 1 ? '' : 's'} on record${summary.latestReportKey ? `; the latest was reported ${formatDisplayDate(summary.latestReportKey)}` : ''}. Try a longer window.`}</span>
          </div>
        )}
      </Card>

      <Card
        title={MOST_AFFECTED_AREAS_TITLE}
        subtitle={national
          ? `Districts by ${diseaseShortLabel} reports in the last ${windowDays} days · change vs the ${windowDays} days before`
          : `${districtName ?? 'Your district'} and nearby districts with a current record within ${horizon?.relevanceKm ? `${Math.round(horizon.relevanceKm)} km` : 'the model influence range'} · last ${windowDays} days`}
      >
        {loadStatus === 'ready'
          ? <AffectedAreasTable rows={areas} windowDays={windowDays} emptyText={`No ${diseaseShortLabel} records in this window.`} />
          : <div className="px-4 pb-4 text-[12px] text-on-surface-variant/60">{loadStatus === 'loading' ? 'Loading…' : unavailableNote}</div>}
      </Card>

      <Card title="Space–time clusters" subtitle={`ST-DBSCAN over eligible verified sources (exploratory, last 14 days${stClusters.data?.as_of ? ` to ${formatDisplayDate(stClusters.data.as_of)}` : ''})${national ? '' : ` · clusters with a member in ${districtName ?? 'your district'}`} · drift = shift of the cluster centre over its period, not a spread route`} label="Space-time clusters">
        {clusterStatus === 'ready'
          ? <ClusterTable rows={clusterRows} emptyText={`No ST-DBSCAN cluster for ${diseaseShortLabel}${national ? '' : ` touching ${districtName}`}.`} />
          : <div className="px-4 pb-4 text-[12px] text-on-surface-variant/60">{clusterStatus === 'loading' ? 'Loading clusters…' : 'Cluster analysis unavailable right now.'}</div>}
      </Card>
    </div>
  )
}
