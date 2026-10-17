import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useOptionalNavigate } from '../context/useOptionalRouter'

import { collectMyAreaCaseContexts, MY_AREA_DISTRICT_STATUS, resolveMyAreaDistrict } from '../adapters/myAreaDistrict'
import { buildObservedCaseFeatures, scopePointFeaturesToDistrict } from '../adapters/myAreaMapLayers'
import { AREA_PLAYBACK_INTERVAL_MS, normalizeRealAreaCaseFeatures } from '../adapters/timelinePresentation'
import { buildMyAreaTimelineView, horizonLabel, TIMELINE_STATUS } from '../adapters/spatialTimelineView'
import { BAND_LABEL, BAND_RGBA, DEFAULT_DISPLAY_BANDS, buildRiskFieldModel } from '../adapters/riskFieldModel'
import { buildAreaExplainer } from '../adapters/areaExplainer'
import { buildAreaIntelligenceSummary } from '../adapters/areaIntelligenceSummary'
import { buildFarmListRows, FARM_LIST_STATUS } from '../adapters/myAreaFarmList'
import { computeFeatureBounds, districtNameAtPoint } from '../adapters/districtGeometry'
import WeatherForecastStrip from '../components/WeatherForecastStrip'
import { districtSamplePoints } from '../adapters/weatherForecast'
import { useDistrictWeatherForecast } from '../context/useDistrictWeatherForecast'
import { recentUnmappedRecords, unmappedNoticeText } from '../adapters/nationalCases'
import {
  buildDistrictFarmRoster,
  buildRecommendedActions,
  buildRegisteredFarmFeatures,
  buildSourceBreakdown,
  buildVerifiedCaseIntelligence,
  staticTierAreas,
} from '../adapters/myAreaIntelligence'
import { sriLankaDateKey } from '../adapters/verificationTime'
import { CASE_AGE_COLOR, RECENT_CASE_MAX_AGE_DAYS, VISIBLE_CASE_MAX_AGE_DAYS, caseAgeReference, classifyCaseAge, isCaseMarkerVisible } from '../adapters/caseAge'
import { isEventRelevantToMyArea } from '../adapters/operationalEventRelevance'
import { formatDisplayDate } from '../adapters/forecastDate'
import { ANALYSIS_BASIS, buildAnalysisBasisOptions, latestHistoricalOriginDate, latestVerifiedDate, selectedBasisOption } from '../adapters/spatialStory'
import AnalysisBasisSelect from '../components/AnalysisBasisSelect'
import DiseaseSelector from '../components/DiseaseSelector'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import { NewCaseToasts } from '../components/MapOverlayChrome'
import { useNewCaseAlerts } from '../context/useNewCaseAlerts'
import MyAreaCaseHistory from '../components/MyAreaCaseHistory'
import MyAreaForecastStrip from '../components/MyAreaForecastStrip'
import MyAreaIntelligencePanel from '../components/MyAreaIntelligencePanel'
import MyAreaKpiCards from '../components/MyAreaKpiCards'
import MyAreaAiExplainer from '../components/MyAreaAiExplainer'
import MyAreaFarmList from '../components/MyAreaFarmList'
import MyAreaMapCanvas from '../components/MyAreaMapCanvas'
import { IMPACT_LAYER, IMPACT_LAYER_LABEL, impactLayerVisibility } from '../adapters/myAreaMapPresentation'
import { buildRiskOutlookRows } from '../adapters/riskOutlook'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'
import OperationalStatusChip from '../components/OperationalStatusChip'
import { MY_AREA_FETCH_STATUS } from '../api/myAreaApi'
import { DISTRICT_GEOMETRY_STATUS, useDistrictGeometry } from '../context/useDistrictGeometry'
import { useGeospatialContext } from '../context/GeospatialContext'
import { useMyAreaContext, MY_AREA_REQUEST_STATE } from '../context/useMyAreaContext'
import { NATIONAL_STATUS, useNationalOutbreaks } from '../context/useNationalOutbreaks'
import { useOperationalContext } from '../context/useOperationalContext'
import { AREA_CONTEXT_STATE, OPERATIONAL_FAILURE_TEXT, resolveAreaContextState } from '../adapters/myAreaContextState'
import { useAssignedFarmNames } from '../context/useAssignedFarmNames'
import { nationalCasesEventKey, useNationalCases } from '../context/useNationalCases'
import { eligibleSourceSignature } from '../adapters/liveSourceSignature'
import { useSourceChangeToken } from '../context/useSourceChangeToken'
import { useEnvironmentObservations } from '../context/useEnvironmentObservations'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { SPATIAL_TIMELINE_STATE, useSpatialTimeline } from '../context/useSpatialTimeline'
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
  MY_AREA_PAGE_TITLE,
} from '../semanticLabels'

// The district comes from the logged-in vet's own operational context
// (`resolveMyAreaDistrict`) -- never a fixed district, case ID or coordinate.
const DISTRICT_STATUS_MESSAGE = {
  [MY_AREA_DISTRICT_STATUS.NO_REGISTERED_DISTRICT]: 'No district is registered on your veterinarian profile. Add your district in Settings to see My Area.',
  [MY_AREA_DISTRICT_STATUS.SELECT_FARM_FOR_NATIONAL_SCOPE]: 'Your account covers all districts. Select one of your assigned farms to focus My Area on its district.',
  [MY_AREA_DISTRICT_STATUS.DISTRICT_DATA_UNAVAILABLE]: 'District surveillance data is temporarily unavailable. Try refreshing.',
}

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

const OBSERVED_AGE_DRAW_ORDER = { DATE_UNKNOWN: 0, AFTER_REFERENCE: 0, EXPIRED: 0, OLDER: 1, RECENT: 2 }


function mapModePillClass(active) {
  return active
    ? 'rounded px-2.5 py-1 text-[11px] font-semibold text-primary bg-primary/15'
    : 'rounded px-2.5 py-1 text-[11px] font-medium text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface'
}

function sameScopeData(data, farmId, disease) {
  return data?.area?.farmId === farmId && data?.disease === disease
}

const PRESENTATION_DISCLAIMER_TEXT = 'Same backend snapshot as the Outbreak Map: the C0 score of each eligible case, shown as far as its spread can have travelled by the selected day, and its estimated spread direction. Not infection probabilities, not confirmed future cases, not transmission routes. Days 8-14 are an exploratory extension.'

/** Compact one-line key under the map (the map itself carries no legend box). */
function MapLegend({ showImpact, impactLayer, verifiedCaseCount, possibleCaseCount = 0, ageReferenceLabel = null }) {
  const swatch = 'inline-block h-2.5 w-2.5 shrink-0'
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-outline-variant/20 px-3 py-1.5 text-[10px] text-on-surface-variant/80" aria-label="Map key">
      {showImpact ? (
        <>
          {impactLayer === IMPACT_LAYER.RISK && [...DEFAULT_DISPLAY_BANDS].reverse().map(({ band, min }) => (
            <span key={band} className="flex items-center gap-1"><span className={`${swatch} rounded-sm`} style={{ backgroundColor: `rgb(${BAND_RGBA[band].slice(0, 3).join(',')})` }} />{BAND_LABEL[band]}{min > 0 ? ` ≥${min.toFixed(2)}` : ''}</span>
          ))}
          {impactLayer === IMPACT_LAYER.TRAJECTORY && <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-3.5 rounded bg-[#8B5CF6]" />Spread of an existing outbreak</span>}
          {impactLayer === IMPACT_LAYER.TRAJECTORY && possibleCaseCount > 0 && <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-3.5 rounded bg-[#ec4899]" />Spread of a new outbreak</span>}
          {impactLayer === IMPACT_LAYER.CASES && verifiedCaseCount > 0 && <span className="flex items-center gap-1"><span className={`${swatch} rounded-full`} style={{ backgroundColor: CASE_AGE_COLOR.RECENT }} />Reported ≤{RECENT_CASE_MAX_AGE_DAYS} days ago</span>}
          {impactLayer === IMPACT_LAYER.CASES && verifiedCaseCount > 0 && <span className="flex items-center gap-1"><span className={`${swatch} rounded-full`} style={{ backgroundColor: CASE_AGE_COLOR.OLDER }} />Reported {RECENT_CASE_MAX_AGE_DAYS + 1}–{VISIBLE_CASE_MAX_AGE_DAYS} days ago</span>}
          <span className="flex items-center gap-1" title="A verified outbreak today: the cause of the modelled spread"><span className="inline-block h-2.5 w-2.5 rounded-full border-[2px] border-[#ef4444]" />Existing outbreak (cause)</span>
          {possibleCaseCount > 0 && <span className="flex items-center gap-1" title="Where an existing outbreak's spread first stands in your district: modelled, not confirmed"><span className="inline-block h-2.5 w-2.5 rounded-full border-[1.5px] border-white bg-[#ec4899]" />New outbreak (modelled)</span>}
          <span className="flex items-center gap-1"><span className={`${swatch} rounded-full border-[1.5px] border-[#334155] bg-[#f8fafc]`} />Farm</span>
          <span className="ml-auto cursor-help text-on-surface-variant/55" title={PRESENTATION_DISCLAIMER_TEXT}>{impactLayer === IMPACT_LAYER.RISK ? 'Hover a zone for details · ' : ''}Relative score, not a probability ⓘ</span>
        </>
      ) : (
        <>
          {verifiedCaseCount > 0 && <span className="flex items-center gap-1"><span className={`${swatch} rounded-full`} style={{ backgroundColor: CASE_AGE_COLOR.RECENT }} />Reported ≤{RECENT_CASE_MAX_AGE_DAYS} days ago</span>}
          {verifiedCaseCount > 0 && <span className="flex items-center gap-1"><span className={`${swatch} rounded-full`} style={{ backgroundColor: CASE_AGE_COLOR.OLDER }} />Reported {RECENT_CASE_MAX_AGE_DAYS + 1}–{VISIBLE_CASE_MAX_AGE_DAYS} days ago</span>}
          <span className="flex items-center gap-1"><span className={`${swatch} rounded-full border-2 border-[#d97706]`} />Pending verification</span>
          <span className="flex items-center gap-1"><span className={`${swatch} rounded-full border-[1.5px] border-[#334155] bg-[#f8fafc]`} />Farm</span>
          {ageReferenceLabel && <span className="ml-auto text-on-surface-variant/55">{ageReferenceLabel}</span>}
        </>
      )}
    </div>
  )
}

export default function MyAreaPage() {
  const ctx = useGeospatialContext()
  const navigate = useOptionalNavigate()
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
  // Future Impact view, same three views as the Outbreak Map.
  const [impactLayer, setImpactLayer] = useState(IMPACT_LAYER.RISK)
  const showImpact = mapMode === MAP_MODE.FUTURE_IMPACT
  const [observedIndex, setObservedIndex] = useState(null) // null = latest real report date
  const [focusPoint, setFocusPoint] = useState(null)
  // Nearest mapped place per source id (reported by the map when idle).
  const [sourcePlaces, setSourcePlaces] = useState({})
  const mapSectionRef = useRef(null)
  const [focusedFarmId, setFocusedFarmId] = useState(null)
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

  const districtResolution = useMemo(
    () => resolveMyAreaDistrict({ operationalData: operational.data, selectedFarmId: ctx.selectedAreaId }),
    [operational.data, ctx.selectedAreaId],
  )
  const authorizedDistrict = districtResolution.district
  const districtLabel = authorizedDistrict ?? 'My district'
  const { feature: districtFeature, status: districtGeometryStatus, featureCollection: districtCollection } = useDistrictGeometry(authorizedDistrict)
  const districtBoundaryMissing = Boolean(authorizedDistrict) && districtGeometryStatus === DISTRICT_GEOMETRY_STATUS.READY && !districtFeature
  const districtStatusMessage = DISTRICT_STATUS_MESSAGE[districtResolution.status]
    ?? (districtBoundaryMissing ? `No official boundary was found for "${authorizedDistrict}". Check the district name on your profile.` : null)
  const areaContextState = resolveAreaContextState({
    operationalState: operational.state,
    hasOperationalData: Boolean(operational.data),
    district: authorizedDistrict,
    districtGeometryStatus,
    hasDistrictFeature: Boolean(districtFeature),
  })
  const areaContextReady = areaContextState === AREA_CONTEXT_STATE.READY
  // One sentence for every counter/panel while the district context is not
  // ready -- shown instead of zeros.
  const areaContextPendingText = areaContextState === AREA_CONTEXT_STATE.LOADING
    ? (authorizedDistrict ? `Loading the ${authorizedDistrict} boundary…` : 'Loading your authorised district…')
    : areaContextState === AREA_CONTEXT_STATE.FAILED
      ? OPERATIONAL_FAILURE_TEXT[operational.state]
      : areaContextState === AREA_CONTEXT_STATE.UNRESOLVED
        ? (districtStatusMessage ? 'No authorised district resolved -- see the notice above.' : 'No authorised district could be resolved for this account.')
        : areaContextState === AREA_CONTEXT_STATE.BOUNDARY_FAILED
          ? (districtBoundaryMissing ? `No official boundary was found for "${authorizedDistrict}".` : `The ${authorizedDistrict} boundary could not be loaded, so cases and farms cannot be placed in the district.`)
          : null

  const clinicalEvents = useVerifiedClinicalEvents()
  // Realtime invalidation (SSE `geospatial_data_changed`, or a changed
  // `ready.data_version` after a reconnect), debounced in the hook. Every
  // query below refetches for the CURRENT disease/district/date; responses
  // for an older selection are discarded by each hook.
  const dataChangeToken = clinicalEvents.dataChangeToken
  useEffect(() => {
    if (dataChangeToken) operational.refresh?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataChangeToken])
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
  // is validated. The vet's own district ADM2 polygon performs final containment.
  const candidateCaseContexts = useMemo(
    () => collectMyAreaCaseContexts({
      operationalData: operational.data,
      myAreaContexts: responseData?.verifiedClinicalContexts ?? [],
      disease: ctx.selectedDisease,
    }),
    [operational.data, responseData, ctx.selectedDisease],
  )
  const areaCaseFeatures = useMemo(
    () => scopePointFeaturesToDistrict(buildObservedCaseFeatures(candidateCaseContexts), districtFeature),
    [candidateCaseContexts, districtFeature],
  )
  // Real verified cases inside the district polygon: every one of them,
  // fixed at its validated farm coordinate.
  const verifiedCaseFeatures = useMemo(() => normalizeRealAreaCaseFeatures(areaCaseFeatures), [areaCaseFeatures])

  // Phase 3: ONE backend snapshot for the vet's district drives every
  // timeline element (map layers, strip, chart, cards, panel). Fetched once
  // per disease / district / refresh -- never per animation frame.
  // Analysis date: today (live 14-day window) or the real date of the latest
  // vet-verified case for this disease in the vet's surveillance scope. The
  // vet chooses; the page never switches it automatically.
  // Declared early (the Retrospective option needs its real origins); kept
  // as `national` below, after the playback clock, for the page's readers.
  const nationalOrigins = useNationalOutbreaks(ctx.selectedDisease, 'Sri Lanka', retryToken)
  // null = automatic: today when a case was verified in the last 14 days,
  // otherwise the latest real verified-case date (labelled). A vet's own
  // choice is kept.
  const [analysisBasis, setAnalysisBasis] = useState(null)
  const [customAnalysisDate, setCustomAnalysisDate] = useState(null)
  const todayKey = sriLankaDateKey(new Date())
  const latestVerifiedInScope = useMemo(
    () => latestVerifiedDate(operational.data?.surveillanceContexts, ctx.selectedDisease),
    [operational.data, ctx.selectedDisease],
  )
  // Retrospective replay: the real latest historical research origin for this
  // disease, explicitly chosen and labelled with its real date.
  const retrospectiveDate = useMemo(() => latestHistoricalOriginDate(nationalOrigins.originsWithSources), [nationalOrigins.originsWithSources])
  const basisOptions = useMemo(
    () => buildAnalysisBasisOptions({ latestVerified: latestVerifiedInScope, retrospective: retrospectiveDate, allowCustom: true, customDate: customAnalysisDate, today: todayKey }),
    [latestVerifiedInScope, retrospectiveDate, customAnalysisDate, todayKey],
  )
  // Day 0 = today (Asia/Colombo) unless the vet explicitly picks another date.
  const basisOption = selectedBasisOption(basisOptions, analysisBasis ?? ANALYSIS_BASIS.LIVE)
  // Observed-case colour age follows today unless a past date was chosen.
  const caseAgeRef = caseAgeReference({ basisAsOf: analysisBasis === null ? null : basisOption.asOf, todayKey })
  const nationalCases = useNationalCases({ heartbeat: operational.lastRefreshedAt, eventKey: nationalCasesEventKey(clinicalEvents) })
  // Refetch the timeline when the set of possible sources changes (a case
  // verified or withdrawn, a farm GPS added), not on every heartbeat.
  const sourceSignature = useMemo(() => eligibleSourceSignature(nationalCases.data?.records, ctx.selectedDisease), [nationalCases.data, ctx.selectedDisease])
  const sourceChangeToken = useSourceChangeToken(sourceSignature)
  const spatialTimeline = useSpatialTimeline({
    disease: ctx.selectedDisease,
    scope: 'district',
    district: authorizedDistrict,
    asOf: basisOption.asOf,
    enabled: Boolean(authorizedDistrict),
    refreshToken: `${retryToken}:${dataChangeToken}:${sourceChangeToken}`,
    retryKey: operational.lastRefreshedAt,
  })
  useEffect(() => {
    setActiveAreaForecastIndex(0)
    setIsPlaying(false)
  }, [basisOption.id, basisOption.asOf, authorizedDistrict, ctx.selectedDisease])
  const areaForecastVisualization = useMemo(
    () => buildMyAreaTimelineView(spatialTimeline.data, activeAreaForecastIndex, authorizedDistrict, { landDomain: districtFeature ?? null }),
    [spatialTimeline.data, activeAreaForecastIndex, authorizedDistrict, districtFeature],
  )
  const areaForecastReady = areaForecastVisualization.renderable
  const areaRiskFieldModel = useMemo(() => buildRiskFieldModel(spatialTimeline.data), [spatialTimeline.data])
  const districtCentre = useMemo(() => {
    const bounds = districtFeature ? computeFeatureBounds(districtFeature) : null
    return bounds ? { latitude: (bounds[0][1] + bounds[1][1]) / 2, longitude: (bounds[0][0] + bounds[1][0]) / 2 } : null
  }, [districtFeature])
  const areaWeatherPoints = useMemo(() => (districtFeature ? districtSamplePoints(districtFeature) : []), [districtFeature])
  const areaWeather = useDistrictWeatherForecast({ latitude: districtCentre?.latitude, longitude: districtCentre?.longitude, points: areaWeatherPoints, enabled: Boolean(districtCentre) })
  const finalFrameIndex = Math.max(0, areaForecastVisualization.frameCount - 1)
  const timelineNotice = spatialTimeline.status === SPATIAL_TIMELINE_STATE.ERROR
    ? 'Spatial risk timeline unavailable right now.'
    : spatialTimeline.data?.status === TIMELINE_STATUS.MODEL_NOT_READY
      ? 'No validated spatial risk model for this disease -- verified cases only.'
      : spatialTimeline.data?.status === TIMELINE_STATUS.NO_ELIGIBLE_SOURCES
        ? basisOption.id === ANALYSIS_BASIS.LIVE && basisOptions.length > 1
          ? `No eligible sources in the last 14 days -- no risk zones for this district. Switch Analysis date (e.g. "Choose a date…") to review a past window.`
          : basisOption.asOf
            ? `No eligible sources in the 14 days up to ${formatDisplayDate(basisOption.asOf)} -- no risk zones for this district on that date.`
            : 'No eligible sources in the last 14 days -- no risk zones for this district.'
        : null
  const kpiScoreUnavailable = spatialTimeline.status === SPATIAL_TIMELINE_STATE.ERROR
    ? { value: 'UNAVAILABLE', sublabel: 'Spatial timeline unreachable' }
    : spatialTimeline.data?.status === TIMELINE_STATUS.MODEL_NOT_READY
      ? { value: 'NO MODEL', sublabel: 'No validated spatial model for this disease' }
      : spatialTimeline.data?.status === TIMELINE_STATUS.NO_ELIGIBLE_SOURCES
        ? { value: 'NO SOURCES', sublabel: basisOption.asOf ? `Nothing eligible to score · 14 days to ${formatDisplayDate(basisOption.asOf)}` : 'Nothing eligible to score · last 14 days' }
        : null

  useEffect(() => {
    if (focusedCaseId && !verifiedCaseFeatures.some((feature) => feature.properties.anchorId === focusedCaseId)) setFocusedCaseId(null)
  }, [focusedCaseId, verifiedCaseFeatures])

  function handleSelectAreaForecastIndex(index) {
    setIsPlaying(false)
    setActiveAreaForecastIndex(Math.max(0, Math.min(finalFrameIndex, Number.isInteger(index) ? index : 0)))
  }

  function handleTogglePlayback() {
    if (isPlaying) {
      setIsPlaying(false)
      return
    }
    if (!areaForecastReady || activeAreaForecastIndex >= finalFrameIndex) return
    setIsPlaying(true)
  }

  // One RAF clock advances all Page-2 content. Completion leaves the final
  // backend frame selected; there is deliberately no loop or implicit rewind.
  useEffect(() => {
    if (!isPlaying || !areaForecastReady) return undefined
    if (activeAreaForecastIndex >= finalFrameIndex) {
      setIsPlaying(false)
      return undefined
    }
    const startedAt = performance.now()
    const intervalMs = AREA_PLAYBACK_INTERVAL_MS[playbackSpeed]
    const tick = (now) => {
      if (now - startedAt >= intervalMs) {
        const next = Math.min(finalFrameIndex, activeAreaForecastIndex + 1)
        setActiveAreaForecastIndex(next)
        if (next >= finalFrameIndex) setIsPlaying(false)
        return
      }
      playbackRafRef.current = requestAnimationFrame(tick)
    }
    playbackRafRef.current = requestAnimationFrame(tick)
    return () => {
      if (playbackRafRef.current) cancelAnimationFrame(playbackRafRef.current)
      playbackRafRef.current = null
    }
  }, [isPlaying, areaForecastReady, activeAreaForecastIndex, playbackSpeed, finalFrameIndex])

  const national = nationalOrigins
  const nationalStatus = national.status === NATIONAL_STATUS.LOADING
    ? 'loading'
    : national.status === NATIONAL_STATUS.ERROR || national.status === NATIONAL_STATUS.UNAVAILABLE ? 'error' : 'ready'
  const diseaseShortLabel = getDiseaseConfig(ctx.selectedDisease).shortLabel
  const farmNames = useAssignedFarmNames(dataChangeToken)
  const timelineData = areaForecastReady ? spatialTimeline.data : null
  const modelReady = spatialTimeline.data?.status !== TIMELINE_STATUS.MODEL_NOT_READY
  // Short status for map caption / chart / panel (the full notice is shown once, above).
  const modelShortStatus = !areaContextReady
    ? areaContextPendingText
    : spatialTimeline.status === SPATIAL_TIMELINE_STATE.LOADING
    ? 'Loading the spatial timeline for this district and date...'
    : spatialTimeline.status === SPATIAL_TIMELINE_STATE.ERROR
    ? 'Spatial timeline unreachable.'
    : !modelReady ? `No validated spatial model for ${getDiseaseConfig(ctx.selectedDisease).shortLabel}; verified cases only.`
      : spatialTimeline.data?.status === TIMELINE_STATUS.NO_ELIGIBLE_SOURCES ? 'No eligible sources for this analysis date.' : null

  // ---- One shared district state for map, chart, KPIs and Area Intelligence ----
  const newCaseAlerts = useNewCaseAlerts(nationalCases.data?.records)
  const recentUnmapped = useMemo(
    () => recentUnmappedRecords(nationalCases.data?.records, { disease: ctx.selectedDisease, todayKey }),
    [nationalCases.data, ctx.selectedDisease, todayKey],
  )
  function handleViewNewCase(alert) {
    newCaseAlerts.dismiss(alert.id)
    const r = alert.record
    if (Number.isFinite(r?.latitude) && Number.isFinite(r?.longitude)) navigate?.('..', { relative: 'path', state: { focusOutbreak: { latitude: r.latitude, longitude: r.longitude, mode: 'CASES' } } })
  }
  const roster = useMemo(
    () => buildDistrictFarmRoster({ operationalData: operational.data, farmNames, districtName: authorizedDistrict, districtFeature, timeline: timelineData, frameIndex: activeAreaForecastIndex, disease: ctx.selectedDisease }),
    [operational.data, farmNames, authorizedDistrict, districtFeature, timelineData, activeAreaForecastIndex, ctx.selectedDisease],
  )
  const caseIntel = useMemo(
    () => buildVerifiedCaseIntelligence({ roster, nationalRecords: nationalCases.data?.records ?? [], districtName: authorizedDistrict, districtFeature, disease: ctx.selectedDisease }),
    [roster, nationalCases.data, authorizedDistrict, districtFeature, ctx.selectedDisease],
  )
  const sourceBreakdown = useMemo(() => buildSourceBreakdown(timelineData, districtFeature), [timelineData, districtFeature])
  // Future Risk Outlook = the same backend day rasters the Risk Zones map colours.
  const outlookRows = useMemo(
    // District farms only (the same set as the farm total), with herd size.
    () => (timelineData ? buildRiskOutlookRows(areaRiskFieldModel, districtFeature, { farms: (roster?.rows ?? []).filter((r) => !r.outsideDistrict && r.coordinates).map((r) => ({ coordinates: r.coordinates, totalAnimals: r.totalAnimals })) }) : []),
    [timelineData, areaRiskFieldModel, districtFeature, roster],
  )
  const districtTierAreas = useMemo(() => staticTierAreas(timelineData), [timelineData])
  const actions = useMemo(
    () => buildRecommendedActions({ caseIntel, roster, breakdown: sourceBreakdown, modelReady, timelineOk: areaForecastReady, diseaseShortLabel, districtLabel }),
    [caseIntel, roster, sourceBreakdown, modelReady, areaForecastReady, diseaseShortLabel, districtLabel],
  )
  // Farms in my district: status from the selected day's Risk Zones raster
  // at each farm's GPS (Future Impact), the same lookup as the map colour.
  const farmList = useMemo(() => buildFarmListRows({
    roster,
    model: areaRiskFieldModel,
    dayIndex: areaForecastVisualization.activeIndex ?? 0,
    futureMode: mapMode === MAP_MODE.FUTURE_IMPACT && areaForecastVisualization.renderable,
    possibleNewCases: timelineData?.possible_new_cases ?? [],
    placeFor: (farmId) => sourcePlaces[`farm:${farmId}`] ?? null,
    // Active = verified in the last 30 days of the reference date (map rule).
    disease: ctx.selectedDisease,
    referenceDateKey: caseAgeRef.dateKey,
    // Spread lines (backend paths) for PENDING farms.
    timeline: timelineData,
  }), [roster, areaRiskFieldModel, areaForecastVisualization.activeIndex, areaForecastVisualization.renderable, mapMode, timelineData, sourcePlaces, ctx.selectedDisease, caseAgeRef.dateKey])
  const registeredFarmFeatures = useMemo(() => {
    const features = buildRegisteredFarmFeatures(roster, { ageReferenceDateKey: caseAgeRef.dateKey, disease: ctx.selectedDisease })
    // The map popup shows the same selected-day status as the farm list.
    const listed = new Map(farmList.rows.map((row) => [row.farmId, row]))
    return {
      ...features,
      features: features.features.map((feature) => {
        const row = listed.get(feature.properties.farmId)
        if (!row) return feature
        const statusLabel = row.status === FARM_LIST_STATUS.PENDING ? `Pending · ${row.detail}` : row.status === FARM_LIST_STATUS.AFFECTED ? `Could be affected · ${row.detail}` : row.status === FARM_LIST_STATUS.VERIFIED ? `${row.caseCount} active case${row.caseCount === 1 ? '' : 's'} (last 30 days)` : row.detail ? `Monitoring · ${row.detail}` : 'Monitoring'
        return { ...feature, properties: { ...feature.properties, statusLabel, listStatus: row.status } }
      }),
    }
  }, [roster, caseAgeRef.dateKey, ctx.selectedDisease, farmList])

  // ---- Verified Cases: observed chronology over REAL report dates ----
  const observedDates = caseIntel.history.map((h) => h.date)
  const observedLastIndex = Math.max(0, observedDates.length - 1)
  const observedActiveIndex = observedIndex === null ? observedLastIndex : Math.min(observedIndex, observedLastIndex)
  const observedThrough = observedDates[observedActiveIndex] ?? null
  const environmentDate = showImpact ? areaForecastVisualization.date ?? basisOption.asOf ?? todayKey : observedThrough ?? basisOption.asOf ?? todayKey
  const futureEnvironmentDate = environmentDate > todayKey
  const environmentObservations = useEnvironmentObservations({ disease: ctx.selectedDisease, district: authorizedDistrict, asOf: environmentDate, enabled: Boolean(authorizedDistrict) && !futureEnvironmentDate, refreshToken: dataChangeToken })
  const [observedPlaying, setObservedPlaying] = useState(false)
  useEffect(() => {
    setObservedIndex(null)
    setObservedPlaying(false)
  }, [ctx.selectedDisease, authorizedDistrict])
  useEffect(() => {
    if (!observedPlaying) return undefined
    if (observedActiveIndex >= observedLastIndex) {
      setObservedPlaying(false)
      return undefined
    }
    // Same RAF clock pattern as the model timeline (no timers in this page).
    const startedAt = performance.now()
    let raf = null
    const tick = (now) => {
      if (now - startedAt >= AREA_PLAYBACK_INTERVAL_MS[playbackSpeed]) {
        setObservedIndex(observedActiveIndex + 1)
        return
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { if (raf) cancelAnimationFrame(raf) }
  }, [observedPlaying, observedActiveIndex, observedLastIndex, playbackSpeed])
  function handleSelectObservedIndex(index) {
    setObservedPlaying(false)
    setObservedIndex(Math.max(0, Math.min(observedLastIndex, Number.isInteger(index) ? index : 0)))
  }
  function handleToggleObservedPlayback() {
    if (observedPlaying) { setObservedPlaying(false); return }
    if (observedDates.length === 0) return
    if (observedActiveIndex >= observedLastIndex) setObservedIndex(0)
    setObservedPlaying(true)
  }
  // Cases recorded up to the selected observed date -- they appear, they never move.
  const observedCaseFeatures = useMemo(
    () => verifiedCaseFeatures
      .filter((f) => !observedThrough || (sriLankaDateKey(f.properties?.verificationTime) ?? '') <= observedThrough)
      .map((f) => ({ ...f, properties: { ...f.properties, ageClass: classifyCaseAge(f.properties?.reportedAt, caseAgeRef.dateKey).ageClass } }))
      // Reported more than 30 days before the reference date: not a current-case marker.
      .filter((f) => isCaseMarkerVisible(f.properties.ageClass))
      // Later features draw on top: a recent report is never hidden under an
      // older one at the same farm.
      .sort((a, b) => (OBSERVED_AGE_DRAW_ORDER[a.properties.ageClass] ?? 0) - (OBSERVED_AGE_DRAW_ORDER[b.properties.ageClass] ?? 0)),
    [verifiedCaseFeatures, observedThrough, caseAgeRef.dateKey],
  )
  const pendingCaseFeatures = useMemo(() => ({
    type: 'FeatureCollection',
    features: caseIntel.pending
      .filter((p) => p.coordinates && (!observedThrough || (p.date ?? '') <= observedThrough))
      .filter((p) => isCaseMarkerVisible(classifyCaseAge(p.reportedAt, caseAgeRef.dateKey).ageClass))
      .map((p) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: p.coordinates }, properties: { recordKey: p.recordKey, date: p.date } })),
  }), [caseIntel.pending, observedThrough, caseAgeRef.dateKey])

  // A new district, disease or analysis date clears every selection that
  // belonged to the previous scope (farm focus, source focus, map focus).
  useEffect(() => {
    setFocusedFarmId(null)
    setFocusPoint(null)
    setFocusedCaseId(null)
  }, [authorizedDistrict, ctx.selectedDisease, basisOption.asOf])

  // Switching mode pauses both clocks; neither selected date is reset.
  useEffect(() => {
    setIsPlaying(false)
    setObservedPlaying(false)
  }, [mapMode])

  // "View on Map" opens the Outbreak Map focused on this outbreak (its real
  // position), in Trajectory mode, with its direction line pinned.
  function handleViewOnOutbreakMap(influence) {
    if (!Number.isFinite(influence?.latitude) || !Number.isFinite(influence?.longitude)) {
      setFocusedCaseId(influence?.anchorId ?? null)
      return
    }
    navigate?.('..', {
      relative: 'path',
      state: { focusOutbreak: {
        sourceId: influence.sourceId, latitude: influence.latitude, longitude: influence.longitude,
        disease: ctx.selectedDisease, district: authorizedDistrict,
        asOf: spatialTimeline.data?.as_of ?? basisOption.asOf,
        day: areaForecastVisualization.day ?? 0,
        mode: 'TRAJECTORY',
      } },
    })
  }

  // "View on Map": focus this source on the My Area map (selection +
  // camera) at the selected timeline day; the day is never changed.
  function handleViewSourceOnMap(influence) {
    const feature = areaForecastVisualization.origins.features.find((source) => source.properties.sourceId === influence?.sourceId)
    const coordinates = feature?.geometry?.coordinates
      ?? (Number.isFinite(influence?.longitude) && Number.isFinite(influence?.latitude) ? [influence.longitude, influence.latitude] : null)
    setFocusedFarmId(null)
    setFocusedCaseId(influence?.anchorId ?? null)
    if (coordinates) setFocusPoint({ key: `${influence.sourceId}:${Date.now()}`, coordinates })
    try { mapSectionRef.current?.scrollIntoView?.({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' }) } catch { /* jsdom */ }
  }
  function mergeSourcePlaces(found) {
    setSourcePlaces((previous) => (Object.entries(found).every(([id, name]) => previous[id] === name) ? previous : { ...previous, ...found }))
  }
  function sourceLocation(influence) {
    const coordinates = Number.isFinite(influence?.longitude) && Number.isFinite(influence?.latitude) ? [influence.longitude, influence.latitude] : null
    return { place: sourcePlaces[influence?.sourceId] ?? null, district: coordinates ? districtNameAtPoint(districtCollection, coordinates) : null }
  }

  function handleFocusFarm(row) {
    setFocusedFarmId(row?.farmId ?? null)
    if (row?.coordinates) setFocusPoint({ key: `${row.farmId}:${Date.now()}`, coordinates: row.coordinates })
  }
  function handleFocusFarmId(farmId) {
    setFocusedFarmId(farmId ?? null)
  }
  function handleFocusSource(sourceId) {
    const feature = areaForecastVisualization.origins.features.find((source) => source.properties.sourceId === sourceId)
    if (!feature) return
    setFocusedFarmId(null)
    setFocusedCaseId(feature.properties.anchorId)
    setFocusPoint({ key: `${sourceId}:${Date.now()}`, coordinates: feature.geometry.coordinates })
  }

  const possibleCaseFeatures = useMemo(() => ({
    type: 'FeatureCollection',
    features: (areaForecastVisualization.possibleCases?.features ?? []).map((feature) => ({
      ...feature,
      properties: { ...feature.properties, farmName: farmNames.get?.(feature.properties.farmId) ?? null },
    })),
  }), [areaForecastVisualization.possibleCases, farmNames])
  const possibleCaseCount = possibleCaseFeatures.features.length
  const currentDateLabel = areaForecastVisualization.date ? formatDisplayDate(areaForecastVisualization.date) : null
  const reachText = areaForecastVisualization.reachKm !== null ? `nominal reach ${areaForecastVisualization.reachKm.toFixed(1)} km` : 'no reach yet (as-of day)'
  // The view's clamped frame index: the map, the panel and this row share one frame.
  const selectedRiskRow = outlookRows[areaForecastVisualization.activeIndex] ?? null
  // Panel/narrative read the same row (band areas under their tier keys).
  const selectedOutlook = selectedRiskRow ? {
    ...selectedRiskRow,
    scoredAreaKm2: selectedRiskRow.coloredKm2,
    tierAreas: { highest: selectedRiskRow.bandAreas.high, high: selectedRiskRow.bandAreas.elevated, moderate: selectedRiskRow.bandAreas.moderate, lower: selectedRiskRow.bandAreas.low },
  } : null
  const focusedSourceProperties = areaForecastVisualization.origins.features.find((feature) => feature.properties.anchorId === focusedCaseId)?.properties ?? null
  // Area Intelligence: every metric from the selected frame (same raster row
  // as the outlook bar and the map, same cards as the influencing list).
  const areaSummary = areaForecastReady ? buildAreaIntelligenceSummary({
    view: areaForecastVisualization, frame: areaForecastVisualization.frame, row: selectedRiskRow, roster, caseIntel, breakdown: sourceBreakdown,
    focusedSource: focusedSourceProperties,
    focusedLabel: focusedSourceProperties ? (areaForecastVisualization.influences.find((i) => i.anchorId === focusedCaseId)?.card?.caseRef ?? focusedSourceProperties.sourceId) : null,
  }) : null
  // AI Explainer: rule-based, from the same selected-day inputs as the panel.
  const explainer = buildAreaExplainer({
    districtName: districtLabel, disease: ctx.selectedDisease, diseaseShortLabel, futureMode: showImpact, timelineOk: areaForecastReady,
    summary: areaSummary, influences: areaForecastVisualization.influences, farmList, caseIntel, locationFor: sourceLocation,
    asOf: spatialTimeline.data?.as_of ?? null, statusText: areaContextReady ? modelShortStatus : areaContextPendingText,
    newOutbreaks: (timelineData?.possible_new_cases ?? []).filter((o) => Number.isInteger(o.seed_day)).map((o) => {
      const cause = (timelineData?.sources ?? []).find((src) => src.source_id === o.triggered_by?.[0])
      return {
        seedDay: o.seed_day,
        place: sourcePlaces[o.id] ?? null,
        local: o.arrival === 'FIRST_MOVE_INSIDE_DISTRICT',
        causePlace: cause ? (sourcePlaces[cause.source_id] ?? sourceLocation({ sourceId: cause.source_id, longitude: cause.longitude, latitude: cause.latitude }).district) : null,
      }
    }),
  })
  const readyKpiCards = showImpact
    ? [
      { id: 'zone', icon: 'radar', label: `Highest risk in ${districtLabel}`, value: selectedRiskRow?.maxBand ? `${BAND_LABEL[selectedRiskRow.maxBand].toUpperCase()} ${selectedRiskRow.maxScore.toFixed(2)}` : kpiScoreUnavailable?.value ?? (selectedRiskRow ? 'NONE' : 'WAITING'), sublabel: kpiScoreUnavailable?.sublabel ?? null, accent: 'text-primary' },
      { id: 'sources', icon: 'hub', label: 'Eligible sources', value: areaForecastReady ? `${sourceBreakdown.sources.length} (${sourceBreakdown.outside} outside)` : '0', sublabel: null, accent: 'text-violet-300' },
      { id: 'reach', icon: 'straighten', label: 'Coloured land in district', value: selectedRiskRow ? `${Math.round(selectedRiskRow.coloredKm2).toLocaleString('en-US')} km² (${Math.round(selectedRiskRow.coloredShare * 100)}%)` : '—', sublabel: null, accent: 'text-teal-300' },
      { id: 'farms', icon: 'agriculture', label: 'Farms on coloured land', value: selectedRiskRow ? `${selectedRiskRow.monitoredFarms} / ${roster.summary.mapped}` : `0 / ${roster.summary.mapped}`, sublabel: null, accent: 'text-sky-300' },
      { id: 'horizon', icon: 'calendar_month', label: 'Selected date', value: areaForecastReady ? formatDisplayDate(areaForecastVisualization.date).toUpperCase() : kpiScoreUnavailable ? 'UNAVAILABLE' : 'WAITING', sublabel: areaForecastReady ? null : modelShortStatus ?? 'Waiting for backend frames', accent: 'text-amber-300' },
    ]
    : [
      { id: 'reports', icon: 'medical_information', label: `Verified ${diseaseShortLabel} reports`, value: String(caseIntel.reportCount), sublabel: `${caseIntel.mappedReportCount} mapped at farm GPS · vet-verified, not official outbreaks`, accent: 'text-rose-300' },
      { id: 'farms', icon: 'agriculture', label: 'Reporting farms', value: String(caseIntel.uniqueFarmCount), sublabel: `of ${roster.summary.total} registered farms in ${districtLabel}`, accent: 'text-sky-300' },
      { id: 'pending', icon: 'pending_actions', label: 'Pending verification', value: String(caseIntel.pending.length), sublabel: 'Awaiting a vet; drawn hollow, never as verified', accent: 'text-amber-300' },
      { id: 'nogps', icon: 'location_off', label: 'Without GPS', value: String(caseIntel.verifiedWithoutGps.length + roster.summary.withoutGps), sublabel: `${caseIntel.verifiedWithoutGps.length} reports · ${roster.summary.withoutGps} farms · listed, not mapped`, accent: 'text-on-surface-variant' },
      { id: 'latest', icon: 'event', label: 'Latest verified report', value: caseIntel.latestDate ? formatDisplayDate(caseIntel.latestDate) : 'NONE', sublabel: 'Asia/Colombo verification date', accent: 'text-primary' },
    ]
  // Until the district context is READY no counter shows a number.
  const kpiCards = areaContextReady
    ? readyKpiCards
    : readyKpiCards.map((card) => ({ ...card, value: '—', sublabel: areaContextState === AREA_CONTEXT_STATE.LOADING ? 'Loading…' : 'Unavailable -- see notice above' }))

  return (
    <div className="my-area-page flex min-h-0 flex-col gap-4 pb-6">
      <div className="flex shrink-0 flex-col gap-2">
        <div>
          <h2 className="text-[28px] font-bold leading-[1.15] text-on-surface">{MY_AREA_PAGE_TITLE}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-outline-variant/30 bg-surface-container/60 px-4 py-2">
          <DiseaseSelector selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
          <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
          <AnalysisBasisSelect options={basisOptions} value={basisOption.id} onChange={setAnalysisBasis} customDate={customAnalysisDate} onCustomDateChange={setCustomAnalysisDate} maxDate={todayKey} />
          <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
          <div className="flex items-center gap-2 text-xs"><span className="font-semibold uppercase tracking-wide text-on-surface-variant/70">Authorised district</span><span className="rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1.5 font-bold text-primary">{authorizedDistrict ? authorizedDistrict.toUpperCase() : 'NOT RESOLVED'}</span></div>
          <div className="ml-auto"><OperationalStatusChip state={operational.state} lastRefreshedAt={operational.lastRefreshedAt} onRefresh={operational.refresh} /></div>
        </div>
      </div>

      {areaContextState === AREA_CONTEXT_STATE.LOADING && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant" role="status">{areaContextPendingText}</div>}
      {areaContextState === AREA_CONTEXT_STATE.FAILED && (
        <div className="flex items-center justify-between gap-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200" role="alert"><span>{areaContextPendingText}</span>{operational.refresh && <button type="button" onClick={() => operational.refresh()} className="shrink-0 rounded border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20">Retry</button>}</div>
      )}
      {areaContextState === AREA_CONTEXT_STATE.BOUNDARY_FAILED && !districtBoundaryMissing && <div className="rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200" role="status">{areaContextPendingText}</div>}
      {recentUnmapped.length > 0 && <div className="rounded border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-xs text-amber-100" role="alert">{unmappedNoticeText(recentUnmapped, diseaseShortLabel)}</div>}
      {timelineNotice && areaContextReady && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant" role="status">{timelineNotice}</div>}
      {operational.data !== null && districtStatusMessage && <div className="rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200" role="status">{districtStatusMessage}</div>}
      {operational.data !== null && authorizedFarms.length === 0 && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">{LABEL_MY_AREA_NO_ASSIGNED_FARMS}</div>}
      {myArea.status === MY_AREA_REQUEST_STATE.ERROR && (
        <div className="flex items-center justify-between gap-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200"><span>{MY_AREA_ERROR_LABEL[myArea.errorStatus] ?? 'My Area is temporarily unavailable.'}</span><button type="button" onClick={() => setRetryToken((token) => token + 1)} className="shrink-0 rounded border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20">Retry</button></div>
      )}
      {bodyStatus && BODY_STATUS_LABEL[bodyStatus] && <div className="rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">{BODY_STATUS_LABEL[bodyStatus]}</div>}
      {bodyStatus === 'LOCATION_REQUIRED' && <div className="rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">{LABEL_MY_AREA_LOCATION_REQUIRED}</div>}

      <MyAreaKpiCards cards={kpiCards} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2.15fr)_minmax(290px,0.85fr)] lg:gap-5">
        <div className="flex min-w-0 flex-col gap-4">
          <section className="overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container-lowest shadow-card-subtle" aria-label="Relative Risk Map">
            <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 px-3 py-2">
              <div className="truncate text-sm font-semibold text-on-surface">{showImpact ? 'Future Impact' : 'Verified Cases'} - {districtLabel}</div>
              {showImpact && (
                <div className="ml-auto flex shrink-0 items-center gap-0.5 rounded-md border border-outline-variant/30 bg-surface-container-lowest/40 p-0.5" role="group" aria-label="Future Impact view">
                  {[IMPACT_LAYER.CASES, IMPACT_LAYER.RISK, IMPACT_LAYER.TRAJECTORY].map((layer) => (
                    <button key={layer} type="button" aria-pressed={impactLayer === layer} onClick={() => setImpactLayer(layer)} className={mapModePillClass(impactLayer === layer)}>{IMPACT_LAYER_LABEL[layer]}</button>
                  ))}
                </div>
              )}
              <div className="flex shrink-0 items-center gap-0.5 rounded-md border border-outline-variant/30 bg-surface-container-lowest/40 p-0.5" role="group" aria-label="Map layer mode">
                <button type="button" aria-pressed={showImpact} onClick={() => setMapMode(MAP_MODE.FUTURE_IMPACT)} className={mapModePillClass(showImpact)}>Future impact</button>
                <button type="button" aria-pressed={!showImpact} onClick={() => setMapMode(MAP_MODE.VERIFIED_CASES)} className={mapModePillClass(!showImpact)}>Verified cases</button>
              </div>
            </div>

            <div ref={mapSectionRef} className="relative h-[440px] md:h-[480px]">
              <MyAreaMapCanvas
                area={area}
                observedCaseFeatures={impactLayerVisibility(showImpact, impactLayer).verifiedCases ? observedCaseFeatures : []}
                impactLayer={impactLayer}
                onSelectCase={setFocusedCaseId}
                possibleCaseFeatures={possibleCaseFeatures}
                onSourcePlaces={mergeSourcePlaces}
                areaForecastVisualization={areaForecastVisualization}
                riskFieldModel={areaRiskFieldModel}
                riskFieldIndex={activeAreaForecastIndex}
                showAreaImpact={showImpact}
                focusedCaseId={focusedCaseId}
                districtFeature={districtFeature}
                reduceMotion={reduceMotion}
                onFocusSource={setFocusedCaseId}
                registeredFarmFeatures={registeredFarmFeatures}
                pendingCaseFeatures={pendingCaseFeatures}
                showPendingCases={!showImpact}
                focusPoint={focusPoint}
                onFocusFarm={handleFocusFarmId}
              />
              {focusedCaseId && (
                <button type="button" onClick={() => setFocusedCaseId(null)} className="absolute left-3 top-3 z-20 rounded-md border border-outline-variant/40 bg-surface-container/95 px-2.5 py-1 text-[11px] font-semibold text-on-surface shadow hover:bg-surface-container-high">
                  ✕ Clear case selection
                </button>
              )}
              <div className="pointer-events-none absolute right-14 top-3 z-20"><NewCaseToasts alerts={newCaseAlerts.alerts} onView={handleViewNewCase} onDismiss={newCaseAlerts.dismiss} /></div>
              {clinicalEvents.notifications.length > 0 && <div className="pointer-events-none absolute left-3 top-24"><GeospatialAlertBanner notifications={clinicalEvents.notifications} onViewUpdate={handleViewClinicalUpdate} onDismiss={clinicalEvents.dismiss} farmNames={farmNames} /></div>}
              <div className="absolute bottom-3 left-1/2 w-[calc(100%-16px)] -translate-x-1/2 md:w-[88%]">
                {showImpact ? (
                  <MyAreaForecastStrip
                    dates={areaForecastVisualization.dates}
                    activeIndex={activeAreaForecastIndex}
                    onSelectIndex={handleSelectAreaForecastIndex}
                    isPlaying={isPlaying}
                    onTogglePlayback={handleTogglePlayback}
                    onRestartPlayback={areaForecastVisualization.frameCount > 1 ? () => { setActiveAreaForecastIndex(0); setIsPlaying(true) } : null}
                    playbackSpeed={playbackSpeed}
                    onPlaybackSpeedChange={setPlaybackSpeed}
                    currentRisk={selectedRiskRow?.maxBand ? BAND_LABEL[selectedRiskRow.maxBand] : null}
                    horizonStatus={areaForecastVisualization.horizonStatus}
                    plateauNote={areaForecastVisualization.plateauNote}
                    disabled={!areaForecastReady}
                  />
                ) : (
                  <MyAreaForecastStrip
                    observed
                    heading="Observed case history"
                    dates={observedDates}
                    activeIndex={observedActiveIndex}
                    onSelectIndex={handleSelectObservedIndex}
                    isPlaying={observedPlaying}
                    onTogglePlayback={handleToggleObservedPlayback}
                    onRestartPlayback={observedDates.length > 1 ? () => { setObservedIndex(0); setObservedPlaying(true) } : null}
                    playbackSpeed={playbackSpeed}
                    onPlaybackSpeedChange={setPlaybackSpeed}
                    disabled={observedDates.length === 0}
                  />
                )}
              </div>
            </div>
            <MapLegend showImpact={showImpact} impactLayer={impactLayer} verifiedCaseCount={observedCaseFeatures.length} possibleCaseCount={showImpact ? possibleCaseCount : 0} ageReferenceLabel={caseAgeRef.label} />
          </section>

          {/* Chart directly below the map (original layout), reading the same
              selected model day (Future Impact) or observed date (Verified Cases). */}
          {showImpact ? (
            <MyAreaTemporalOutlook areaLabel={districtLabel} activeIndex={activeAreaForecastIndex} onSelectIndex={handleSelectAreaForecastIndex} rows={outlookRows} disabled={!areaForecastReady} unavailableText={modelShortStatus} />
          ) : (
            <MyAreaCaseHistory areaLabel={districtLabel} history={caseIntel.history} activeIndex={observedActiveIndex} onSelectIndex={handleSelectObservedIndex} diseaseShortLabel={diseaseShortLabel} />
          )}

          {showImpact && (
            <MyAreaOutbreaksInfluencing
              influences={areaForecastVisualization.influences}
              day={areaForecastVisualization.day ?? 0}
              focusedCaseId={focusedCaseId}
              onFocusCase={setFocusedCaseId}
              onViewOnMap={handleViewSourceOnMap}
              onViewOnOutbreakMap={handleViewOnOutbreakMap}
              locationFor={sourceLocation}
              influenceDataAvailable={areaForecastVisualization.influenceDataAvailable !== false}
              horizonDays={Math.max(0, (areaForecastVisualization.frameCount ?? 15) - 1)}
              statusText={areaForecastReady ? null : (modelShortStatus ?? 'Waiting for the backend spatial timeline.')}
              districtLabel={districtLabel}
              farmNames={farmNames}
              diseaseShortLabel={diseaseShortLabel}
            />
          )}
          {/* Farms + AI Explainer side by side under the map column (stacked on
              narrow screens); the right column stays a compact summary. */}
          <section className="grid grid-cols-1 items-start gap-4 xl:grid-cols-2" aria-label="Area explanation and actions">
            <MyAreaFarmList districtLabel={districtLabel} farmList={farmList} futureMode={showImpact && areaForecastReady} day={areaForecastVisualization.day ?? 0} focusedFarmId={focusedFarmId} onFocusFarm={handleFocusFarm} />
            <MyAreaAiExplainer explainer={explainer} />
          </section>
        </div>

        <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
          <MyAreaIntelligencePanel
            includeNarrative={false}
            authorizedDistrict={authorizedDistrict}
            contextPendingText={areaContextReady ? null : areaContextPendingText}
            mode={mapMode}
            diseaseShortLabel={diseaseShortLabel}
            diseaseCode={ctx.selectedDisease}
            timelineOk={areaForecastReady}
            modelStatusText={modelShortStatus}
            asOf={spatialTimeline.data?.as_of ?? null}
            activeDate={areaForecastVisualization.date}
            activeDay={areaForecastVisualization.day}
            horizonStatus={areaForecastVisualization.horizonStatus}
            reachKm={areaForecastVisualization.reachKm}
            reachIntervalKm={areaForecastVisualization.reachIntervalKm}
            outlookRow={selectedOutlook}
            staticTierAreas={districtTierAreas}
            sourceBreakdown={sourceBreakdown}
            roster={roster}
            caseIntel={caseIntel}
            observedThrough={observedThrough}
            environment={spatialTimeline.data?.environment ?? null}
            environmentObservations={environmentObservations}
            environmentDate={environmentDate}
            weatherStrip={showImpact && areaForecastReady ? (
              <WeatherForecastStrip
                showSourceNote={false}
                district={authorizedDistrict}
                dates={areaForecastVisualization.dates}
                selectedDate={areaForecastVisualization.date}
                days={areaWeather.days}
                status={areaWeather.status}
                fetchedAt={areaWeather.fetchedAt}
                pointCount={areaWeather.pointCount}
                todayKey={todayKey}
                onSelectIndex={handleSelectAreaForecastIndex}
              />
            ) : null}
            environmentUnavailableText={futureEnvironmentDate ? 'ERA5 observations are unavailable for this future date. No forecast weather source is integrated.' : null}
            actions={actions}
            focusedFarmId={focusedFarmId}
            onFocusFarm={handleFocusFarm}
            onFocusSource={handleFocusSource}
            farmNames={farmNames}
            focusedSource={focusedSourceProperties}
            farmsElsewhere
            areaSummary={showImpact ? areaSummary : null}
          />
        </div>
      </div>
    </div>
  )
}
