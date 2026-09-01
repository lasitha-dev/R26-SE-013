import React, { useEffect, useMemo, useRef, useState } from 'react'

import { buildObservedCaseFeatures, scopePointFeaturesToDistrict } from '../adapters/myAreaMapLayers'
import {
  advanceAreaForecastIndex,
  AREA_FORECAST_DATES,
  AREA_FORECAST_OUTLOOK,
  AREA_PLAYBACK_INTERVAL_MS,
  buildMyAreaPresentationForecast,
  clampAreaForecastIndex,
} from '../adapters/myAreaPresentationForecast'
import { isEventRelevantToMyArea } from '../adapters/operationalEventRelevance'
import { formatDisplayDate } from '../adapters/forecastDate'
import DiseaseSelector from '../components/DiseaseSelector'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import MyAreaForecastStrip from '../components/MyAreaForecastStrip'
import MyAreaIntelligencePanel from '../components/MyAreaIntelligencePanel'
import MyAreaKpiCards from '../components/MyAreaKpiCards'
import MyAreaMapCanvas from '../components/MyAreaMapCanvas'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'
import OperationalStatusChip from '../components/OperationalStatusChip'
import { MY_AREA_FETCH_STATUS } from '../api/myAreaApi'
import { useDistrictGeometry } from '../context/useDistrictGeometry'
import { useGeospatialContext } from '../context/GeospatialContext'
import { useMyAreaContext, MY_AREA_REQUEST_STATE } from '../context/useMyAreaContext'
import { NATIONAL_STATUS, useNationalOutbreaks } from '../context/useNationalOutbreaks'
import { useOperationalContext } from '../context/useOperationalContext'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { getDiseaseConfig } from '../disease/diseaseRegistry'
import {
  LABEL_MY_AREA_AREA_NOT_FOUND,
  LABEL_MY_AREA_FORBIDDEN,
  LABEL_MY_AREA_HOST_NOT_CONNECTED,
  LABEL_MY_AREA_LOCATION_REQUIRED,
  LABEL_MY_AREA_MODEL_NOT_READY,
  LABEL_MY_AREA_NO_ASSIGNED_FARMS,
  LABEL_MY_AREA_ORIGIN_NOT_FOUND,
  LABEL_MY_AREA_SESSION_REQUIRED,
  LABEL_MY_AREA_UNSUPPORTED_DISEASE,
  MY_AREA_PAGE_TAGLINE,
  MY_AREA_PAGE_TITLE,
} from '../semanticLabels'

// Presentation-only selection permitted by the leader specification.
// Confirmed case IDs and coordinates are never hard-coded here.
export const MY_AREA_DEMO_DISTRICT_OVERRIDE = 'Matara'

const MY_AREA_ERROR_LABEL = {
  [MY_AREA_FETCH_STATUS.SESSION_REQUIRED]: LABEL_MY_AREA_SESSION_REQUIRED,
  [MY_AREA_FETCH_STATUS.FORBIDDEN]: LABEL_MY_AREA_FORBIDDEN,
  [MY_AREA_FETCH_STATUS.HOST_COMPOSITION_REQUIRED]: LABEL_MY_AREA_HOST_NOT_CONNECTED,
  [MY_AREA_FETCH_STATUS.ASSIGNED_AREA_NOT_FOUND]: LABEL_MY_AREA_AREA_NOT_FOUND,
  [MY_AREA_FETCH_STATUS.ORIGIN_NOT_FOUND]: LABEL_MY_AREA_ORIGIN_NOT_FOUND,
  [MY_AREA_FETCH_STATUS.UNSUPPORTED_DISEASE]: LABEL_MY_AREA_UNSUPPORTED_DISEASE,
  [MY_AREA_FETCH_STATUS.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY]: LABEL_MY_AREA_MODEL_NOT_READY,
  [MY_AREA_FETCH_STATUS.OPERATIONAL_DATA_UNAVAILABLE]: 'Operational context unavailable',
  [MY_AREA_FETCH_STATUS.INVALID_REQUEST]: 'Invalid My Area request',
  [MY_AREA_FETCH_STATUS.NETWORK_ERROR]: 'Could not reach the backend',
}

const BODY_STATUS_LABEL = {
  NO_ASSIGNED_FARMS: LABEL_MY_AREA_NO_ASSIGNED_FARMS,
  ASSIGNED_AREA_NOT_FOUND: LABEL_MY_AREA_AREA_NOT_FOUND,
  UNSUPPORTED_DISEASE: LABEL_MY_AREA_UNSUPPORTED_DISEASE,
  ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY: LABEL_MY_AREA_MODEL_NOT_READY,
  ORIGIN_NOT_FOUND: LABEL_MY_AREA_ORIGIN_NOT_FOUND,
}

const MAP_MODE = { FUTURE_IMPACT: 'FUTURE_IMPACT', VERIFIED_CASES: 'VERIFIED_CASES' }

function mapModePillClass(active) {
  return active
    ? 'rounded px-2.5 py-1 text-[11px] font-semibold text-primary bg-primary/15'
    : 'rounded px-2.5 py-1 text-[11px] font-medium text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface'
}

function sameScopeData(data, farmId, disease) {
  return data?.area?.farmId === farmId && data?.disease === disease
}

function dedupeCaseContexts(contexts, disease) {
  const byCaseId = new Map()
  for (const context of contexts) {
    if (!context?.caseId || context.disease !== disease || byCaseId.has(context.caseId)) continue
    byCaseId.set(context.caseId, context)
  }
  return [...byCaseId.values()]
}

const PRESENTATION_DISCLAIMER_TEXT = 'Frontend presentation only. Purple projections and qualitative risk contours are not confirmed future cases, medical probabilities, or backend model outputs.'

function MapLegend({ showImpact, verifiedCaseCount }) {
  return (
    <div className="pointer-events-none absolute left-3 top-3 max-w-[235px] rounded-lg border border-white/10 bg-[#0e1511]/88 px-2.5 py-2 text-[9.5px] text-slate-200 shadow-lg backdrop-blur-md">
      <div className="mb-1.5 flex items-center gap-1.5 font-semibold uppercase tracking-[0.12em] text-primary/80">
        <span>Matara future impact</span>
        <span
          className="pointer-events-auto grid h-3.5 w-3.5 shrink-0 cursor-help place-items-center rounded-full border border-primary/40 text-[8px] font-bold normal-case tracking-normal text-primary/70 hover:border-primary/70 hover:text-primary"
          title={PRESENTATION_DISCLAIMER_TEXT}
          tabIndex={0}
          role="img"
          aria-label={PRESENTATION_DISCLAIMER_TEXT}
        >
          i
        </span>
      </div>
      <div className="grid grid-cols-[12px_1fr] items-center gap-x-2 gap-y-1">
        <span className="h-2.5 w-2.5 rounded-sm border border-primary/80 bg-primary/10" /><span>Selected district boundary</span>
        {verifiedCaseCount > 0 && <><span className="h-2.5 w-2.5 rounded-full bg-[#EF4444] ring-2 ring-white/70" /><span>Verified case - fixed</span></>}
        {showImpact && <><span className="h-0.5 w-3 rounded bg-[#A855F7] shadow-[0_0_5px_#A855F7]" /><span>Projected future spread</span></>}
        {showImpact && <><span className="h-2.5 w-3 rounded-sm bg-gradient-to-r from-[#22C55E] via-[#FACC15] to-[#EF4444]" /><span>Qualitative local risk fields</span></>}
      </div>
    </div>
  )
}

export default function MyAreaPage() {
  const ctx = useGeospatialContext()
  const reduceMotion = usePrefersReducedMotion()
  const operational = useOperationalContext()
  const authorizedFarms = useMemo(() => operational.data?.farms ?? [], [operational.data])

  useEffect(() => {
    if (authorizedFarms.length === 0) return
    const stillValid = ctx.selectedAreaId && authorizedFarms.some((farm) => farm.farmId === ctx.selectedAreaId)
    if (!stillValid && authorizedFarms.length === 1) ctx.selectArea(authorizedFarms[0].farmId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authorizedFarms, ctx.selectedAreaId])

  // The one Page-2 master temporal state. Camera focus, case emphasis,
  // map mode, live-stream state and farm selection never reset it.
  const [activeAreaForecastIndex, setActiveAreaForecastIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [focusedCaseId, setFocusedCaseId] = useState(null)
  const [retryToken, setRetryToken] = useState(0)
  const [mapMode, setMapMode] = useState(MAP_MODE.FUTURE_IMPACT)
  const playbackRafRef = useRef(null)

  // The existing My Area request remains farm/session-owned and fixed at
  // day 0. The 14 presentation frames below never enter its dependencies.
  const myArea = useMyAreaContext({
    farmId: ctx.selectedAreaId,
    disease: ctx.selectedDisease,
    originId: null,
    day: 0,
    retryToken,
  })
  const responseData = sameScopeData(myArea.data, ctx.selectedAreaId, ctx.selectedDisease) ? myArea.data : null
  const area = responseData?.area ?? null
  const bodyStatus = responseData?.status ?? null

  const authorizedDistrict = MY_AREA_DEMO_DISTRICT_OVERRIDE
  const { feature: districtFeature } = useDistrictGeometry(authorizedDistrict)

  const clinicalEvents = useVerifiedClinicalEvents()
  const lastHandledEventIdRef = useRef(null)
  useEffect(() => {
    const event = clinicalEvents.lastEvent
    if (!event || event.event_id === lastHandledEventIdRef.current) return
    lastHandledEventIdRef.current = event.event_id
    if (isEventRelevantToMyArea(event, { selectedAreaId: ctx.selectedAreaId })) setRetryToken((token) => token + 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinicalEvents.lastEvent, ctx.selectedAreaId])

  function handleViewClinicalUpdate(event) {
    if (event.farm_id !== ctx.selectedAreaId) ctx.selectArea(event.farm_id)
    if (event.disease !== ctx.selectedDisease) ctx.selectDisease(event.disease)
    clinicalEvents.dismiss(event.event_id)
  }

  // Real coordinates come from the existing operational adapter, where a
  // case receives its mapped farm coordinate only after the farm location
  // is validated. The real Matara ADM2 polygon performs final containment.
  const candidateCaseContexts = useMemo(
    () => dedupeCaseContexts([
      ...(operational.data?.surveillanceContexts ?? []),
      ...(operational.data?.clinicalContexts ?? []),
      ...(responseData?.verifiedClinicalContexts ?? []),
    ], ctx.selectedDisease),
    [operational.data, responseData, ctx.selectedDisease],
  )
  const areaCaseFeatures = useMemo(
    () => scopePointFeaturesToDistrict(buildObservedCaseFeatures(candidateCaseContexts), districtFeature),
    [candidateCaseContexts, districtFeature],
  )
  const areaForecastVisualization = useMemo(
    () => buildMyAreaPresentationForecast(areaCaseFeatures, activeAreaForecastIndex, districtFeature),
    [areaCaseFeatures, activeAreaForecastIndex, districtFeature],
  )
  const verifiedCaseFeatures = areaForecastVisualization.anchors.features
  const areaForecastReady = verifiedCaseFeatures.length > 0

  useEffect(() => {
    if (focusedCaseId && !verifiedCaseFeatures.some((feature) => feature.properties.anchorId === focusedCaseId)) setFocusedCaseId(null)
  }, [focusedCaseId, verifiedCaseFeatures])

  function handleSelectAreaForecastIndex(index) {
    setIsPlaying(false)
    setActiveAreaForecastIndex(clampAreaForecastIndex(index))
  }

  function handleTogglePlayback() {
    if (isPlaying) {
      setIsPlaying(false)
      return
    }
    if (!areaForecastReady || activeAreaForecastIndex >= AREA_FORECAST_DATES.length - 1) return
    setIsPlaying(true)
  }

  // One RAF clock advances all Page-2 content. Completion leaves index 13
  // selected; there is deliberately no loop or implicit rewind.
  useEffect(() => {
    if (!isPlaying || !areaForecastReady) return undefined
    if (activeAreaForecastIndex >= AREA_FORECAST_DATES.length - 1) {
      setIsPlaying(false)
      return undefined
    }
    const startedAt = performance.now()
    const intervalMs = AREA_PLAYBACK_INTERVAL_MS[playbackSpeed]
    const tick = (now) => {
      if (now - startedAt >= intervalMs) {
        const next = advanceAreaForecastIndex(activeAreaForecastIndex)
        setActiveAreaForecastIndex(next.index)
        if (next.complete) setIsPlaying(false)
        return
      }
      playbackRafRef.current = requestAnimationFrame(tick)
    }
    playbackRafRef.current = requestAnimationFrame(tick)
    return () => {
      if (playbackRafRef.current) cancelAnimationFrame(playbackRafRef.current)
      playbackRafRef.current = null
    }
  }, [isPlaying, areaForecastReady, activeAreaForecastIndex, playbackSpeed])

  const national = useNationalOutbreaks(ctx.selectedDisease, 'Sri Lanka', retryToken)
  const nationalStatus = national.status === NATIONAL_STATUS.LOADING
    ? 'loading'
    : national.status === NATIONAL_STATUS.ERROR || national.status === NATIONAL_STATUS.UNAVAILABLE ? 'error' : 'ready'
  const diseaseShortLabel = getDiseaseConfig(ctx.selectedDisease).shortLabel
  const showImpact = mapMode === MAP_MODE.FUTURE_IMPACT
  const currentDateLabel = formatDisplayDate(areaForecastVisualization.date)
  const mapExplanationText = areaForecastReady
    ? `${currentDateLabel}. ${areaForecastVisualization.anchorCount} real verified case anchor${areaForecastVisualization.anchorCount === 1 ? '' : 's'} remain fixed while ${areaForecastVisualization.paths.features.length} purple projected path${areaForecastVisualization.paths.features.length === 1 ? '' : 's'} and the ${areaForecastVisualization.districtRisk.toUpperCase()} qualitative Matara risk field update together.`
    : 'Waiting for verified Matara case coordinates. No red marker or projected path is fabricated while data is unavailable.'

  return (
    <div className="my-area-page flex min-h-0 flex-col gap-4 pb-6">
      <div className="flex shrink-0 flex-col gap-2">
        <div>
          <h2 className="text-[28px] font-bold leading-[1.15] text-on-surface">{MY_AREA_PAGE_TITLE}</h2>
          <p className="text-xs text-on-surface-variant/70">{MY_AREA_PAGE_TAGLINE}</p>
        </div>
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-outline-variant/30 bg-surface-container/60 px-4 py-2">
          <DiseaseSelector selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
          <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
          <div className="flex items-center gap-2 text-xs"><span className="font-semibold uppercase tracking-wide text-on-surface-variant/70">Presentation district</span><span className="rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1.5 font-bold text-primary">MATARA</span></div>
          <div className="ml-auto"><OperationalStatusChip state={operational.state} lastRefreshedAt={operational.lastRefreshedAt} onRefresh={operational.refresh} /></div>
        </div>
      </div>

      {operational.data === null && authorizedFarms.length === 0 && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">Operational context not connected. Verified Matara cases will populate once the authorized context connects.</div>}
      {operational.data !== null && authorizedFarms.length === 0 && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">{LABEL_MY_AREA_NO_ASSIGNED_FARMS}</div>}
      {myArea.status === MY_AREA_REQUEST_STATE.ERROR && (
        <div className="flex items-center justify-between gap-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200"><span>{MY_AREA_ERROR_LABEL[myArea.errorStatus] ?? 'My Area is temporarily unavailable.'}</span><button type="button" onClick={() => setRetryToken((token) => token + 1)} className="shrink-0 rounded border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20">Retry</button></div>
      )}
      {bodyStatus && BODY_STATUS_LABEL[bodyStatus] && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">{BODY_STATUS_LABEL[bodyStatus]}</div>}
      {bodyStatus === 'LOCATION_REQUIRED' && <div className="rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">{LABEL_MY_AREA_LOCATION_REQUIRED}</div>}

      <MyAreaKpiCards
        areaDistrictLabel={authorizedDistrict}
        districtRisk={areaForecastVisualization.districtRisk}
        activeDate={areaForecastVisualization.date}
        influencingCaseCount={areaForecastVisualization.anchorCount}
        verifiedClinicalCount={verifiedCaseFeatures.length}
        nationalCount={national.originsWithSources.length}
        nationalStatus={nationalStatus}
        diseaseShortLabel={diseaseShortLabel}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2.15fr)_minmax(290px,0.85fr)] lg:gap-5">
        <div className="flex min-w-0 flex-col gap-4">
          <section className="overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container-lowest shadow-card-subtle" aria-label="Future Impact Map">
            <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 px-3 py-2">
              <div className="truncate text-sm font-semibold text-on-surface">Future Impact Map - Matara</div>
              <div className="flex shrink-0 items-center gap-0.5 rounded-md border border-outline-variant/30 bg-surface-container-lowest/40 p-0.5" role="group" aria-label="Map layer mode">
                <button type="button" aria-pressed={showImpact} onClick={() => setMapMode(MAP_MODE.FUTURE_IMPACT)} className={mapModePillClass(showImpact)}>Future impact</button>
                <button type="button" aria-pressed={!showImpact} onClick={() => setMapMode(MAP_MODE.VERIFIED_CASES)} className={mapModePillClass(!showImpact)}>Verified cases</button>
              </div>
            </div>

            <div className="relative h-[440px] md:h-[480px]">
              <MyAreaMapCanvas
                area={area}
                observedCaseFeatures={verifiedCaseFeatures}
                areaForecastVisualization={areaForecastVisualization}
                showAreaImpact={showImpact}
                focusedCaseId={focusedCaseId}
                districtFeature={districtFeature}
                reduceMotion={reduceMotion}
              />
              <MapLegend showImpact={showImpact} verifiedCaseCount={verifiedCaseFeatures.length} />
              {clinicalEvents.notifications.length > 0 && <div className="pointer-events-none absolute left-3 top-24"><GeospatialAlertBanner notifications={clinicalEvents.notifications} onViewUpdate={handleViewClinicalUpdate} onDismiss={clinicalEvents.dismiss} /></div>}
              <div className="absolute bottom-3 left-1/2 w-[calc(100%-16px)] -translate-x-1/2 md:w-[88%]">
                <MyAreaForecastStrip
                  dates={AREA_FORECAST_DATES}
                  activeIndex={activeAreaForecastIndex}
                  onSelectIndex={handleSelectAreaForecastIndex}
                  isPlaying={isPlaying}
                  onTogglePlayback={handleTogglePlayback}
                  playbackSpeed={playbackSpeed}
                  onPlaybackSpeedChange={setPlaybackSpeed}
                  currentRisk={areaForecastVisualization.districtRisk}
                  disabled={!areaForecastReady}
                />
              </div>
            </div>
            <div className="border-t border-outline-variant/20 px-3 py-2 text-[11px] leading-snug text-on-surface-variant/65" aria-live="polite">{mapExplanationText}</div>
          </section>

          <MyAreaTemporalOutlook areaLabel={authorizedDistrict} activeIndex={activeAreaForecastIndex} onSelectIndex={handleSelectAreaForecastIndex} frames={AREA_FORECAST_OUTLOOK} disabled={!areaForecastReady} />
          <MyAreaOutbreaksInfluencing influences={areaForecastVisualization.influences} focusedCaseId={focusedCaseId} onFocusCase={setFocusedCaseId} />
        </div>

        <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
          <MyAreaIntelligencePanel
            area={area}
            authorizedDistrict={authorizedDistrict}
            activeDate={areaForecastVisualization.date}
            activeIndex={activeAreaForecastIndex}
            districtRisk={areaForecastVisualization.districtRisk}
            influencingCount={areaForecastVisualization.anchorCount}
            projectedPathCount={areaForecastVisualization.paths.features.length}
            verifiedClinicalCount={verifiedCaseFeatures.length}
            focusedCaseId={focusedCaseId}
            overlapRiskLevel={areaForecastVisualization.overlapRiskLevel}
          />
        </div>
      </div>
    </div>
  )
}
