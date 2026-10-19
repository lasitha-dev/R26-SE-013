import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useOptionalLocationState } from '../context/useOptionalRouter'
import '../components/prototypeChrome.css'

import { getOutbreakAdapter } from '../adapters'
import { computeFeatureBounds, isPointInsideDistrictFeature, normalizeDistrictDisplayName } from '../adapters/districtGeometry'
import { addDaysToIsoDate, formatDisplayDate } from '../adapters/forecastDate'
import { GEO_TIMING, markTiming } from '../adapters/loadTiming'
import { selectMostRecentOrigin } from '../adapters/mostRecentOrigin'
import { aggregateNationalSourcesByLocation } from '../adapters/nationalSourcePresentation'
import { PAGE1_PLAYBACK_INTERVAL_MS } from '../adapters/timelinePresentation'
import {
  buildNationalTimelineLayers,
  buildMonitoringZones,
  clampFrameIndex,
  frameDates,
  horizonLabel,
  isTimelineRenderable,
  plateauNote,
  TIMELINE_STATUS,
} from '../adapters/spatialTimelineView'
import { isWithinObservationWindow, ALL_RECORDED_WINDOW, OBSERVATION_WINDOW_OPTIONS, resolveObservationWindow } from '../adapters/observationWindow'
import { buildNationalCaseView, caseDateKey, recentUnmappedRecords, unmappedNoticeText } from '../adapters/nationalCases'
import { CASE_AGE_CLASS, caseAgeReference } from '../adapters/caseAge'
import { buildRiskFieldModel, probeRiskField } from '../adapters/riskFieldModel'
import {
  ANALYSIS_BASIS,
  buildAnalysisBasisOptions,
  buildReachHistory,
  buildRiskCells,
  buildSpatialStory,
  isWithinWindowEndingAt,
  latestHistoricalOriginDate,
  latestVerifiedDate,
  selectedBasisOption,
  unavailableReason,
} from '../adapters/spatialStory'
import { filterContextsByReplayDate } from '../adapters/observedReplay'
import { classifyOperationalCaseChanges, verificationByCaseId } from '../adapters/operationalCaseReconciliation'
import { aggregateClinicalContextsByFarm, operationalFarmGroupsSignature } from '../adapters/operationalFarmAggregation'
import AnalysisBasisSelect from '../components/AnalysisBasisSelect'
import CellPopup from '../components/CellPopup'
import CorridorPopup from '../components/CorridorPopup'
import DiseaseSelector from '../components/DiseaseSelector'
import Era5Observations from '../components/Era5Observations'
import { buildEnvironmentFeatures } from '../adapters/environmentMap'
import { districtSamplePoints, forecastFeature, heatIntensity, kmCircle, weatherCondition } from '../adapters/weatherForecast'
import WeatherForecastStrip from '../components/WeatherForecastStrip'
import { useDistrictWeatherForecast } from '../context/useDistrictWeatherForecast'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import LocationScopeSelect, { LOCATION_SCOPE } from '../components/LocationScopeSelect'
import { MapStatusStack, NationalCaseCard, NewCaseToasts, RiskCellCard, TimelineChooserDock } from '../components/MapOverlayChrome'
import { useNewCaseAlerts } from '../context/useNewCaseAlerts'
import MapCanvas from '../components/MapCanvas'
import MapLibreCanvas from '../components/MapLibreCanvas'
import { buildNationalSourcesFeatureCollection, computeCombinedLngLatBounds, computeRiskTierStats } from '../components/mapLibreAdapter'
import ModeToolbar from '../components/ModeToolbar'
import ObservationWindowSelect from '../components/ObservationWindowSelect'
import ObservedTimelineControl from '../components/ObservedTimelineControl'
import OperationalContextPopup from '../components/OperationalContextPopup'
import { buildOperationalMarkerFeatureCollection } from '../components/operationalMarkerLayer'
import FmdOriginPanel from '../components/FmdOriginPanel'
import PageLegend from '../components/PageLegend'
import { SNAPSHOT_STATUS } from '../components/SnapshotStatusChip'
import SourcePopup from '../components/SourcePopup'
import StatusDiagnosticsMenu from '../components/StatusDiagnosticsMenu'
import TimelineControl from '../components/TimelineControl'
import { useGeospatialContext } from '../context/GeospatialContext'
import { useAvailableMapHeight } from '../context/useAvailableMapHeight'
import { useDistrictGeometry } from '../context/useDistrictGeometry'
import { EVENT_TYPE } from '../context/operationalEventsReducer'
import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { useFmdOriginRisk } from '../context/useFmdOriginRisk'
import { NATIONAL_STATUS, useNationalOutbreaks } from '../context/useNationalOutbreaks'
import { NATIONAL_CASES_STATE, nationalCasesEventKey, useNationalCases } from '../context/useNationalCases'
import { eligibleSourceSignature } from '../adapters/liveSourceSignature'
import { useSourceChangeToken } from '../context/useSourceChangeToken'
import { sriLankaDateKey } from '../adapters/verificationTime'
import { buildClusterFeatureCollection, clusterForCase, useStClusters } from '../context/useStClusters'
import { useOperationalContext } from '../context/useOperationalContext'
import { useAssignedFarmNames } from '../context/useAssignedFarmNames'
import { useEnvironmentObservations } from '../context/useEnvironmentObservations'
import SpatialEvidencePanel from '../components/SpatialEvidencePanel'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { SPATIAL_TIMELINE_STATE, useSpatialTimeline } from '../context/useSpatialTimeline'
import { FOCUS_STATUS, deriveAvailableForecastDays, useSelectedOutbreakFrames } from '../context/useSelectedOutbreakFrames'
import { CAPABILITY, getDiseaseConfig, hasCapability, isDiseaseReady } from '../disease/diseaseRegistry'
import { LABEL_NO_VERIFIED_CASES_IN_WINDOW, LABEL_OBSERVED_CASES_TIMELINE, PAGE_TAGLINE, PAGE_TITLE } from '../semanticLabels'

const COUNTRY = 'Sri Lanka'
const EMPTY_FC = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })

/**
 * LSD-UI-03/04: Page 1 -- Outbreak Map. Map-dominant viewport (plan
 * Section 15), national LSD overview on load, one-time focus fit on
 * selection, bottom-docked timeline that only appears once something
 * is selected. Every visible number/date/geometry is either passed
 * straight through from a real API response or derived by a pure,
 * unit-tested adapter function (`lsdOutbreakAdapter.js`,
 * `nominalReachRing.js`, `forecastDate.js`) -- nothing here invents
 * data (plan Section 8).
 */
// GEO33B Section 1: the earliest point this page's module graph executes
// on a real navigation -- recorded at module scope so it is genuinely
// BEFORE the component body, its hooks, and MapLibre construction, giving
// every other mark a truthful "since page mount" baseline. Dev-only no-op
// (`adapters/loadTiming.js`).
markTiming(GEO_TIMING.PAGE_MOUNT)

export default function OutbreakMapPage() {
  const ctx = useGeospatialContext()
  const reduceMotion = usePrefersReducedMotion()
  const diseaseReady = isDiseaseReady(ctx.selectedDisease)
  const diseaseConfig = getDiseaseConfig(ctx.selectedDisease)

  const [refreshToken, setRefreshToken] = useState(0)
  const national = useNationalOutbreaks(ctx.selectedDisease, COUNTRY, refreshToken)
  const focus = useSelectedOutbreakFrames(ctx.selectedDisease, ctx.selectedOutbreakId, refreshToken)

  // GEO-PAGE1-FINAL: distinguishes the genuine FIRST load (no real
  // national data has ever arrived yet -- the honest "Loading verified
  // outbreaks and forecast snapshots…" message) from a LATER refresh of
  // an already-populated page (a disease/window change, or "Check for
  // newer snapshot" -- the quieter "Updating…" pill). Both are the exact
  // same real `NATIONAL_STATUS.LOADING` state; only the wording differs,
  // never the underlying fetch/behavior.
  const hasEverLoadedNationalRef = useRef(false)
  useEffect(() => {
    if (national.status === NATIONAL_STATUS.READY || national.status === NATIONAL_STATUS.EMPTY) {
      hasEverLoadedNationalRef.current = true
    }
  }, [national.status])

  // FMD-10C: FMD has real historical origins + a real scalar risk score
  // but no coordinate-bearing endpoint yet -- `showFmdOriginPanel` is
  // true for exactly that shape (has an origin ledger, no spatial-cell/
  // source geometry to draw map pins from). `fmdRisk` is a no-op (stays
  // IDLE) for any disease without the `scalarOriginRisk` capability, so
  // this is always safe to call regardless of the selected disease.
  const showFmdOriginPanel = hasCapability(ctx.selectedDisease, CAPABILITY.HISTORICAL_ORIGINS) && !hasCapability(ctx.selectedDisease, CAPABILITY.SPATIAL_CELLS)
  const fmdRisk = useFmdOriginRisk(ctx.selectedDisease, ctx.selectedOutbreakId, refreshToken)
  const [popupFeature, setPopupFeature] = useState(null)
  const [mapUnavailable, setMapUnavailable] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const mapWrapperRef = useRef(null)
  const mapCanvasRef = useRef(null)
  // GEO26B Section 5: real measured available height, replacing the
  // previous `calc(100vh - 220px)` guess (see the hook's own docstring).
  const availableMapHeight = useAvailableMapHeight(mapWrapperRef)

  // GEO-INT-03: the operational Verified Clinical Context overlay --
  // entirely independent of the historical/model data hooks above
  // (Section 7: "Operational context is an ADDITIONAL overlay. It must
  // not replace historical data."). `refreshToken`/`popupFeature`/
  // `selectedOutbreakId` are never reused for it (Section 12) -- its own
  // separate `operationalPopupCase` state is used instead, so opening/
  // closing an operational marker's popup can never disturb the
  // currently-selected historical outbreak/model frame.
  const operational = useOperationalContext()
  const [operationalPopupCase, setOperationalPopupCase] = useState(null)

  // Section 10: Cases mode only -- never implied part of Risk Zones/
  // Clusters/Trajectory/Env. Declared early (GEO28A fix): several memos
  // below (the empty-state check in particular) read this value, so it
  // must exist before them -- referencing a `const` before its
  // declaration is a fatal ReferenceError on every render, which is
  // exactly what crashed the whole app (no error boundary exists above
  // this route, so the error unmounted the entire React tree, taking
  // VetLayout's sidebar/header down with it).
  const showOperationalLayer = ctx.analysisMode === ANALYSIS_MODE.CASES

  // GEO26B Section 6/25: the Observation Date Range -- a clinical-history
  // filter, entirely separate from `ctx.selectedForecastDay` (the
  // scientific forecast timeline). Local page state, not shared context,
  // since it belongs only to this page's Cases view.
  const [observationWindowDays, setObservationWindowDays] = useState(ALL_RECORDED_WINDOW)

  // GEO26B Section 15: "Sri Lanka" vs "My assigned farms" camera scope.
  // REAL_DISTRICT_GEOMETRY_BLOCKED -- no Sri Lanka ADM2 boundary dataset
  // exists in this repo, so "My assigned farms" fits the vet's own real,
  // authorized farm bounds rather than drawing a fabricated polygon.
  const [locationScope, setLocationScope] = useState(LOCATION_SCOPE.SRI_LANKA)
  // One Page-1 presentation clock shared by every current real outbreak.
  // It is deliberately local to this page and independent of selecting a
  // marker, the WebSocket state, or any per-origin backend horizon.
  const [page1ForecastActiveIndex, setPage1ForecastActiveIndex] = useState(0)
  const [isPage1ForecastPlaying, setIsPage1ForecastPlaying] = useState(false)
  // Entering Cases mode stops any running model playback (no forecast in Cases).
  useEffect(() => {
    if (showOperationalLayer) setIsPage1ForecastPlaying(false)
  }, [showOperationalLayer])
  const [isPage1ForecastUpdating, setIsPage1ForecastUpdating] = useState(false)
  // GEO-VIVA-VISUAL-RECOVERY-03: true once the camera scope has been set
  // by EITHER an explicit vet action (Fit Sri Lanka / Focus My District,
  // including via the LocationScopeSelect) OR the one-time auto-focus
  // effect below -- suppresses that effect forever after either, so a
  // manual choice always wins and the auto-focus can never re-fire or
  // fight a later choice.
  const districtAutoFocusDoneRef = useRef(false)

  // GEO26B Section 32: the previously no-op risk-cell click now opens a
  // real popup for the clicked cell.
  const [selectedCellFeature, setSelectedCellFeature] = useState(null)

  // GEO26B Section 12: the real `farmDiseaseKey` of the farm marker a
  // genuine new verified-clinical SSE event just landed for -- passed to
  // `MapLibreCanvas` for a brief "just arrived" highlight, then cleared.
  const [arrivalHighlightKey, setArrivalHighlightKey] = useState(null)

  // GEO-LIVE-05 Section 9: a relevant verified-clinical live event never
  // mutates scientific/marker state directly -- it only invalidates/
  // refetches the authoritative operational-context snapshot (the same
  // path `OperationalStatusChip`'s manual refresh already uses), so the
  // marker layer above stays honest and never fabricates a value.
  const clinicalEvents = useVerifiedClinicalEvents()
  // Realtime invalidation (SSE `geospatial_data_changed` or a changed
  // `ready.data_version` on reconnect), debounced in the hook: refetch the
  // operational context now; the timeline/cases/clusters hooks below take
  // the same token and refetch for the CURRENT disease/date only.
  const dataChangeToken = clinicalEvents.dataChangeToken
  useEffect(() => {
    if (dataChangeToken) operational.refresh?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataChangeToken])
  const lastRefetchedEventIdRef = useRef(null)
  // GEO-LIVE-UPDATE-RECOVERY-06: the real moment a genuine operational
  // update (either a live SSE arrival, or the fallback reconciliation
  // tick discovering a case the push stream failed to deliver) was last
  // processed -- drives `StatusDiagnosticsMenu`'s honest "LIVE UPDATE"
  // wording, never a bare "the transport is open" claim.
  const [lastGenuineUpdateAt, setLastGenuineUpdateAt] = useState(null)
  useEffect(() => {
    const event = clinicalEvents.lastEvent
    const eventId = event?.event_id
    if (!eventId || eventId === lastRefetchedEventIdRef.current) return
    lastRefetchedEventIdRef.current = eventId
    operational.refresh()
    // GEO-HYBRID-LIVE-SYNC-08 Phase 10: LIVE UPDATE for either a new or
    // an updated case -- the event stream genuinely delivered a change.
    setLastGenuineUpdateAt(Date.now())
    // GEO26B Section 12 / GEO-HYBRID-LIVE-SYNC-08 Phase 3 #13/#14: only a
    // genuinely NEW case gets the arrival highlight -- `event.event_id`
    // (`vcc:{case_id}:{verified_at}`) is a per-observation DEDUP key, not
    // the case's own stable entity identity (`event.case_id`); the real
    // signal for "new vs. re-verified" is `event.event_type`
    // (`domain/operational_events.py::OperationalEventType`), never
    // inferred from the event_id shape. MapLibreCanvas clears the
    // highlight itself after the pulse duration; a later different
    // arrival simply overwrites this with its own real farm key.
    if (event.farm_id && event.disease && event.event_type === EVENT_TYPE.CREATED) {
      setArrivalHighlightKey(`${event.farm_id}::${event.disease}`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinicalEvents.lastEvent])

  // GEO-HYBRID-LIVE-SYNC-08 Phase 7/9/10: the fallback reconciliation
  // path. Push is primary (effect above), but a connected transport is
  // not proof a change was actually delivered -- so every real
  // reconciliation snapshot (the ~2s cycle in `useOperationalContext.js`,
  // or a push-triggered refetch above) is diffed by the genuine backend
  // case entity identity (`caseId`, never a transport/event id) against
  // the last known state, classifying each case as NEW (arrival pulse +
  // LIVE UPDATE), CHANGED (LIVE UPDATE only -- Phase 9 "do not pulse
  // merely because an existing case was updated"), or UNCHANGED (no
  // status/map mutation at all). "Changed" mirrors the backend's own
  // change-detection field exactly (`event_stream_service.py`'s
  // `_reconciliation_changes`: same case_id, different `verified_at`).
  // `seenCaseVerificationRef` starts `null` so the FIRST successful load
  // is never treated as a flood of "arrivals" -- Phase 7's own "unchanged
  // snapshot -> no visible mutation" rule. Diffs the full disease-
  // agnostic surveillance set (never the disease/window-filtered view) so
  // switching disease/window can never itself be misread as a change.
  // Membership loss (a case present before, absent now) is NEVER treated
  // as a deletion here (Phase 7 "do not invent deletion semantics") --
  // the FeatureCollection below is simply rebuilt from whatever the
  // current authoritative snapshot contains, exactly as it always was.
  // GEO-LIVE-FINAL-PROOF-09: the classification itself is now a pure,
  // dedicated-tested function (`adapters/operationalCaseReconciliation.js`
  // -- same behavior as before, extracted for direct unit-test coverage
  // of the entity-identity semantics without needing to render this page).
  const seenCaseVerificationRef = useRef(null)
  useEffect(() => {
    const contexts = operational.data?.surveillanceContexts
    if (!contexts) return
    const previous = seenCaseVerificationRef.current
    seenCaseVerificationRef.current = verificationByCaseId(contexts)
    if (!previous) return

    const { newCases, changedCases } = classifyOperationalCaseChanges(previous, contexts)
    if (newCases.length === 0 && changedCases.length === 0) return // Phase 7: unchanged snapshot -- no status/map mutation

    setLastGenuineUpdateAt(Date.now())
    if (newCases.length > 0) {
      const mostRecent = newCases[newCases.length - 1]
      setArrivalHighlightKey(`${mostRecent.farmId}::${mostRecent.disease}`)
    }
  }, [operational.data])

  // Section 12: "View update" opens the Geospatial Cases context and
  // selects the operational clinical case separately -- it NEVER calls
  // ctx.selectOutbreak / sets selectedOutbreakId to a clinical-case id,
  // never touches the timeline/playback/camera (Section 10).
  function handleViewClinicalUpdate(event) {
    if (event.disease !== ctx.selectedDisease) ctx.selectDisease(event.disease)
    ctx.setMode(ANALYSIS_MODE.CASES)
    setOperationalPopupCase({
      caseId: event.case_id,
      farmId: event.farm_id,
      disease: event.disease,
      verificationTime: event.verified_at,
    })
    // GEO26C Section 6: brings the real farm this event belongs to into
    // view -- reuses the SAME `resetView(explicitBounds)` primitive the
    // Location control's "My assigned farms" option already uses (never a
    // second/new camera-fit call site), and only when the farm's real
    // location is actually known (never a guessed/fallback coordinate).
    // Playback/timeline controls are still untouched here, matching
    // Section 10.
    const farm = (operational.data?.farms ?? []).find((f) => f.farmId === event.farm_id)
    if (farm?.locationStatus === 'VALID') {
      const bounds = computeCombinedLngLatBounds([], [{ geometry: { coordinates: [farm.longitude, farm.latitude] } }])
      if (bounds) mapCanvasRef.current?.resetView(bounds)
    }
    clinicalEvents.dismiss(event.event_id)
  }

  // Section 18: disease filtering happens here, not in the hook/adapter
  // (which stay disease-agnostic) -- selecting FMD must never imply the
  // FMD scientific model is ready (the existing `!diseaseReady` banner
  // below is untouched), it only decides which already-verified
  // operational markers, if any, are relevant to show.
  // GEO26B Section 6/7: the Observation Date Range is applied here, right
  // alongside the pre-existing disease filter -- both are plain predicate
  // filters over the same real, already-verified context list; neither
  // fetches anything new or fabricates a value for an excluded case.
  //
  // GEO29A Phase 4/14/16: Cases mode reads the BROADER
  // `surveillanceContexts` (the vet's real registered-district scope),
  // not the narrower `clinicalContexts` (personally-assigned farms
  // only) -- a real, evidenced gap: a vet can have zero personally-
  // assigned farms yet a real registered district with real verified
  // cases in it (see `adapters/operationalFarmAggregation.js`'s
  // `personallyAssigned` flag for how the popup still respects the
  // narrower scope's privacy rules for a farm that is district-only).
  // Analysis date ("as of") for the spatial timeline: today (live), the real
  // latest vet-verified case date, or the real latest historical origin
  // (retrospective replay). Only options backed by a real date are offered.
  // `null` = automatic (`automaticBasisId`): today when a case was verified
  // in the last 14 days, else the latest real verified-case date -- labelled.
  // Once the vet picks a date, that choice is kept.
  const [analysisBasis, setAnalysisBasis] = useState(null)
  const [customAnalysisDate, setCustomAnalysisDate] = useState(null)
  const todayKey = sriLankaDateKey(new Date())
  const latestVerifiedForDisease = useMemo(
    () => latestVerifiedDate(operational.data?.surveillanceContexts, ctx.selectedDisease),
    [operational.data, ctx.selectedDisease],
  )
  const retrospectiveDate = useMemo(() => latestHistoricalOriginDate(national.originsWithSources), [national.originsWithSources])
  const basisOptions = useMemo(
    () => buildAnalysisBasisOptions({ latestVerified: latestVerifiedForDisease, retrospective: retrospectiveDate, allowCustom: true, customDate: customAnalysisDate, today: todayKey }),
    [latestVerifiedForDisease, retrospectiveDate, customAnalysisDate, todayKey],
  )
  // Day 0 = today (Asia/Colombo) unless the vet explicitly picks another date.
  const basisOption = selectedBasisOption(basisOptions, analysisBasis ?? ANALYSIS_BASIS.LIVE)
  // Observed cases (markers, window, colour age) follow today unless the vet
  // explicitly chose another analysis date; the automatic shift only moves
  // the model timeline to the latest real cases.
  // Cases mode: ages against today (unless a date was chosen). Model modes:
  // against the analysis date, so the source cases of the zones stay drawn.
  const casesAsOf = showOperationalLayer && analysisBasis === null ? null : basisOption.asOf
  // Observed-case age reference: today's Asia/Colombo date unless a past
  // analysis date was explicitly chosen (labelled retrospective).
  const caseAgeRef = caseAgeReference({ basisAsOf: casesAsOf, todayKey })
  const operationalContextsForDisease = useMemo(
    () =>
      (operational.data?.surveillanceContexts ?? [])
        .filter((c) => c.disease === ctx.selectedDisease)
        // Live: "last N days" up to now. Latest verified / retrospective: the
        // N days ENDING at that analysis date, so the cases shown are the
        // ones that existed at that date -- never later ones.
        .filter((c) => {
          const window = resolveObservationWindow(observationWindowDays, {
            basisAsOf: casesAsOf,
            latestRecordDate: latestVerifiedDate(operational.data?.surveillanceContexts, ctx.selectedDisease),
          })
          return window.endIsoDate
            ? isWithinWindowEndingAt(c.verificationTime, window.days, window.endIsoDate)
            : isWithinObservationWindow(c.verificationTime, window.days)
        }),
    [operational.data, ctx.selectedDisease, observationWindowDays, casesAsOf],
  )

  // GEO31A Section 5/6: Cases-mode Observed Replay -- real dates only,
  // derived from `operationalContextsForDisease`'s own real verification
  // timestamps (never fabricated). `observedReplayDateKey === null` means
  // "at latest" (every real event currently in the window is shown,
  // identical to this page's pre-GEO31A behavior); scrubbing/playing back
  // to an earlier real date temporarily hides events verified after it.
  const [observedReplayDateKey, setObservedReplayDateKey] = useState(null)
  const [isObservedPlaybackActive, setIsObservedPlaybackActive] = useState(false)
  // A disease/window change can invalidate the current scrub position
  // (Section 7/13: this must NEVER be derived from location/district
  // scope, only disease+window) -- reset to "at latest" rather than
  // silently keep pointing at a date that may no longer be in range.
  useEffect(() => {
    setObservedReplayDateKey(null)
    setIsObservedPlaybackActive(false)
  }, [ctx.selectedDisease, observationWindowDays, basisOption.asOf])

  useEffect(() => {
    if (!showOperationalLayer) {
      setObservedReplayDateKey(null)
      setIsObservedPlaybackActive(false)
    }
  }, [showOperationalLayer])

  const revealedOperationalContexts = useMemo(
    () => filterContextsByReplayDate(operationalContextsForDisease, observedReplayDateKey),
    [operationalContextsForDisease, observedReplayDateKey],
  )
  // GEO26B Section 8: one real farm+disease aggregate per marker, never
  // one marker per individual case.
  const operationalFarmGroups = useMemo(
    () => aggregateClinicalContextsByFarm(revealedOperationalContexts),
    [revealedOperationalContexts],
  )
  // GEO-LIVE-FINAL-PROOF-09: `operational.data` gets a brand-new object
  // reference on every successful ~2s reconciliation fetch even when its
  // real content is byte-for-byte identical, which would otherwise flow
  // through to a new `operationalFeatures` reference every cycle and make
  // `MapLibreCanvas.jsx`'s `[operationalFeatures]` effect call
  // `source.setData()` needlessly. Gated here (never inside
  // MapLibreCanvas.jsx) via a cheap stable signature over the real,
  // rendering-meaningful fields only (`operationalFarmGroupsSignature`) --
  // never `JSON.stringify` of the whole structure. An unchanged signature
  // reuses the SAME FeatureCollection object reference, so the prop is
  // referentially stable and the effect's dependency check skips the
  // update entirely; a real change (new/changed case, or a recency-tier
  // flip) always produces a new reference and a normal setData().
  const operationalFeaturesSignatureRef = useRef(null)
  const stableOperationalFeaturesRef = useRef(null)
  const operationalFeatures = useMemo(() => {
    const signature = `${operationalFarmGroupsSignature(operationalFarmGroups)}@${caseAgeRef.dateKey}`
    if (stableOperationalFeaturesRef.current && operationalFeaturesSignatureRef.current === signature) {
      return stableOperationalFeaturesRef.current
    }
    const next = buildOperationalMarkerFeatureCollection(operationalFarmGroups, { ageReferenceDateKey: caseAgeRef.dateKey })
    operationalFeaturesSignatureRef.current = signature
    stableOperationalFeaturesRef.current = next
    return next
  }, [operationalFarmGroups, caseAgeRef.dateKey])
  const operationalFarmGroupsByKey = useMemo(
    () => new Map(operationalFarmGroups.map((g) => [`${g.farmId}::${g.disease}`, g])),
    [operationalFarmGroups],
  )

  // GEO33B Section 8/11: which real farm markers became visible on THIS
  // Observed-Replay step. Scrubbing/playing the timeline previously just
  // swapped the source data, so a marker appearing at its own real
  // verification date was indistinguishable from one that had been sitting
  // there the whole time -- the replay had no visible "this is new"
  // moment at all. These keys get the same short, time-bounded pulse a
  // live SSE arrival gets (`MapLibreCanvas.jsx`), then settle to steady.
  //
  // Deliberately gated on the REPLAY DATE actually changing. A disease
  // switch or a widened observation window also changes which markers are
  // revealed, but pulsing every marker on those is noise, not information
  // -- and the initial load (no previous date recorded) is never treated
  // as a reveal.
  const revealedOperationalKeys = useMemo(
    () => operationalFarmGroups.map((g) => `${g.farmId}::${g.disease}`),
    [operationalFarmGroups],
  )
  const previousReplayRevealRef = useRef({ dateKey: undefined, keys: null })
  const [newlyRevealedKeys, setNewlyRevealedKeys] = useState(null)
  useEffect(() => {
    const previous = previousReplayRevealRef.current
    const replayDateChanged = previous.dateKey !== undefined && previous.dateKey !== observedReplayDateKey
    const previousKeys = previous.keys
    previousReplayRevealRef.current = { dateKey: observedReplayDateKey, keys: new Set(revealedOperationalKeys) }
    if (!replayDateChanged || !previousKeys) {
      setNewlyRevealedKeys(null)
      return
    }
    const added = revealedOperationalKeys.filter((key) => !previousKeys.has(key))
    setNewlyRevealedKeys(added.length > 0 ? added : null)
  }, [revealedOperationalKeys, observedReplayDateKey])

  // GEO26D Section 6/7/8: an honest "nothing here" state -- ONLY once the
  // real operational-context fetch has actually succeeded at least once
  // (CONNECTED/STALE; never LOADING/ERROR/SESSION_REQUIRED, which already
  // have their own dedicated `OperationalStatusChip` presentation) AND
  // the real, already-disease+window-filtered farm list is genuinely
  // empty. Deliberately independent of `national.status` (Section 8) --
  // a failed/unavailable scientific fetch must never suppress this real,
  // separate clinical read.
  // GEO31A Section 5: deliberately checks the FULL (not replay-filtered)
  // `operationalContextsForDisease` -- "genuinely zero real events in the
  // window" and "not yet revealed because the vet scrubbed the Observed
  // Timeline back" are two different, both-honest states; this chip is
  // only for the former (`ObservedTimelineControl`'s own empty-state
  // branch already covers the latter/general case).
  const showNoVerifiedCasesEmptyState =
    showOperationalLayer &&
    (operational.state === OPERATIONAL_STATE.CONNECTED || operational.state === OPERATIONAL_STATE.STALE) &&
    operationalContextsForDisease.length === 0

  // GEO26B Section 15: the vet's own real, authorized farms with a usable
  // location -- used as a fallback camera target when the real district
  // itself has no usable farm to fit on.
  const assignedFarmPoints = useMemo(
    () =>
      (operational.data?.farms ?? [])
        .filter((f) => f.locationStatus === 'VALID')
        .map((f) => ({ geometry: { coordinates: [f.longitude, f.latitude] } })),
    [operational.data],
  )
  // GEO30A Section 8: "Focus My District" fits the vet's real registered
  // DISTRICT (every real farm `district_matches` puts in
  // `surveillance_farms` -- Section 12's broader real scope), falling
  // back to personally-assigned farms only if the district itself has no
  // usable coordinate. Never a fabricated polygon (REAL_DISTRICT_
  // GEOMETRY_BLOCKED -- no Sri Lanka ADM2 dataset exists in this repo).
  const districtFarmPoints = useMemo(
    () =>
      (operational.data?.surveillanceFarms ?? [])
        .filter((f) => f.locationStatus === 'VALID')
        .map((f) => ({ geometry: { coordinates: [f.longitude, f.latitude] } })),
    [operational.data],
  )
  // GEO30B Section 16/19: the vet's real district polygon (geoBoundaries
  // ADM2 dataset, `data/ATTRIBUTION.md`) -- resolved by real name match
  // against `operational.data.vetDistrict`, never a fabricated shape.
  // Independent of `districtFarmPoints`/`assignedFarmPoints` above: those
  // are real farm coordinates used as a camera-fit fallback when no real
  // polygon is available (or hasn't resolved yet); this is the actual
  // boundary drawn on the map itself. Declared BEFORE `myDistrictAvailable`
  // (which reads it) -- a `const` read before its own declaration is a
  // fatal TDZ ReferenceError that unmounts the whole tree (see GEO29A).
  const { feature: districtFeature, featureCollection: sriLankaDistricts } = useDistrictGeometry(operational.data?.vetDistrict)

  // GEO30B Section 19: a real district polygon match alone is enough to
  // make "Focus My District" meaningful, even with zero real farm points
  // (e.g. a district with genuinely no assigned/surveillance farms yet).
  const myDistrictAvailable = districtFarmPoints.length > 0 || assignedFarmPoints.length > 0 || Boolean(districtFeature)

  // GEO30A Section 7/8: "Fit Sri Lanka"/"Focus My District" are CAMERA-
  // ONLY actions -- neither touches selected disease, observation
  // window, or active map mode (Section 7's explicit requirement), and
  // neither ever mutates `operational`/`national` state (Section 12:
  // national context always stays in application state regardless of
  // which camera scope is active).
  function handleFitSriLanka() {
    districtAutoFocusDoneRef.current = true
    setLocationScope(LOCATION_SCOPE.SRI_LANKA)
    mapCanvasRef.current?.resetView()
  }

  function handleFocusMyDistrict() {
    districtAutoFocusDoneRef.current = true
    setLocationScope(LOCATION_SCOPE.MY_DISTRICT)
    // GEO30B Section 19: prefer the real district POLYGON's own bounds
    // (tighter, and correct even when the vet happens to have zero real
    // farms with a usable coordinate yet) -- fall back to real farm
    // points only when the polygon hasn't resolved (still loading,
    // fetch failed, or no name match), never a fabricated box.
    const bounds = districtFeature
      ? computeFeatureBounds(districtFeature)
      : computeCombinedLngLatBounds([], districtFarmPoints.length ? districtFarmPoints : assignedFarmPoints)
    if (bounds) mapCanvasRef.current?.resetView(bounds)
  }

  function handleLocationScopeChange(nextScope) {
    if (nextScope === LOCATION_SCOPE.MY_DISTRICT) handleFocusMyDistrict()
    else handleFitSriLanka()
  }

  // GEO-VIVA-VISUAL-RECOVERY-03 Section 2: the initial camera previously
  // always opened on the national Sri Lanka view (`MapLibreCanvas.jsx`'s
  // mount-time fit), even when the district-identity badge above
  // (`vetDistrict`) is already showing a real, known district -- a real
  // vet-facing mismatch (the badge names the vet's real district while the
  // map itself still shows the whole island/ocean). Once
  // a real district becomes available for the FIRST time (a real farm/
  // district-polygon match resolving asynchronously after the operational
  // fetch), and only if the vet has not already made an explicit camera
  // choice, this fires the SAME real `handleFocusMyDistrict` a manual
  // click would -- camera-only, never touches disease/mode/timeline, and
  // never re-fires (the ref it sets is checked here too). "Fit Sri Lanka"
  // stays the only way to see the national view once this has run.
  // GEO-VIVA-VISUAL-RECOVERY-03: `handleFocusMyDistrict`'s `resetView`
  // silently no-ops before the map has actually finished loading its
  // style (`MapLibreCanvas.jsx`'s own `!loadedRef.current` guard) -- and
  // the real operational/district fetch this effect depends on commonly
  // resolves BEFORE that remote basemap load finishes (it's a local API
  // call vs. a CDN round trip). Polling `isReady()` via `requestAnimationFrame`
  // (never `setInterval`/`setTimeout` -- forbidden anywhere in this
  // feature, `noAutoPolling.test.js`) waits for the real readiness flag
  // instead of guessing a delay; typically resolves within one or two
  // frames once the map has already loaded, and briefly longer on first
  // page load while the style is still in flight.
  // On login the map focuses the vet's registered district once, as soon as
  // its real polygon resolves and the map is ready -- unless the vet has
  // already chosen a view (Fit Sri Lanka / Location / a case link).
  useEffect(() => {
    if (districtAutoFocusDoneRef.current || !districtFeature || pendingOutbreakFocusRef.current) return undefined
    let frameId = null
    const attempt = () => {
      if (districtAutoFocusDoneRef.current) return
      if (!mapCanvasRef.current?.isReady?.()) {
        frameId = requestAnimationFrame(attempt)
        return
      }
      handleFocusMyDistrict()
    }
    attempt()
    return () => { if (frameId != null) cancelAnimationFrame(frameId) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [districtFeature])

  // Section 11/12: shows the compact operational popup ONLY -- never
  // calls ctx.selectOutbreak, never fetches analysis summary/cells/
  // sources, never starts timeline playback, never draws a reach ring.
  function handleSelectOperationalCase(properties) {
    setOperationalPopupCase(properties)
  }

  // GEO-PAGE1-FINAL Section 18/24: "the timeline should work without
  // clicking a case first". The real, previously-reported root cause:
  // Risk Zones' `TimelineControl` (and FMD's scalar risk) both derive
  // entirely from `focus`, which is `null`/idle until `ctx.selectOutbreak`
  // has been called at least once -- so on a fresh page load the vet saw
  // "Select a historical outbreak origin..." and an empty timeline dock
  // until they clicked a marker. There is no real backend endpoint that
  // aggregates every visible origin's forecast into one shared multi-
  // origin timeline (each real origin has its own independently-shaped
  // day horizon and cell set -- `services/forecast_origin.py`), so a
  // genuine "all outbreaks share one playback" is not something the real
  // API can honestly support today (Section 24's own explicit fallback:
  // "choose the most recent real eligible outbreak deterministically as
  // the default... while keeping all national outbreaks visible").
  //
  // This auto-focuses the REAL origin with the latest real `t0`
  // (`selectMostRecentOrigin`, pure/tested) the instant it's known, via
  // the exact same `ctx.selectOutbreak` a real click uses -- so
  // `focus`/`ctx.availableForecastFrames`/`ctx.selectedForecastDay`/Play
  // all populate for real immediately. `isAutoFocusedOutbreak` is passed
  // to `MapLibreCanvas` as `autoFocusOutbreak` so the camera-fly and the
  // selection halo/ripple/dim-others treatment -- both correct ONLY for
  // a genuine click -- are suppressed for this page-chosen default; the
  // default Sri Lanka Overview therefore looks and behaves exactly as it
  // did before this change. `userPickedOutbreakRef` makes this fire at
  // most until the vet's first real interaction with this disease (never
  // fights or overrides a manual choice afterwards -- mirrors
  // `districtAutoFocusDoneRef`'s identical once-only pattern above).
  // Guarded on `!ctx.isPlaybackActive` so a newly-resolving (typically
  // slow, per `useNationalOutbreaks.js`'s own documented real backend
  // latency) origin can never yank the focus out from under a playback
  // already in progress.
  const userPickedOutbreakRef = useRef(false)
  const [isAutoFocusedOutbreak, setIsAutoFocusedOutbreak] = useState(false)
  useEffect(() => {
    userPickedOutbreakRef.current = false
  }, [ctx.selectedDisease])
  useEffect(() => {
    if (userPickedOutbreakRef.current || ctx.isPlaybackActive) return
    const mostRecent = selectMostRecentOrigin(national.originsWithSources)
    if (mostRecent && mostRecent.outbreakId !== ctx.selectedOutbreakId) {
      setIsAutoFocusedOutbreak(true)
      ctx.selectOutbreak(mostRecent.outbreakId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [national.originsWithSources, ctx.selectedDisease, ctx.isPlaybackActive])

  // GEO33B Section 7: PRESENTATION aggregation over the merged national
  // sources -- one marker per real coordinate, never one per returned row.
  //
  // Why: `/analysis/{id}/sources` returns each origin's ELIGIBLE source
  // set, and eligibility is a 14-day WINDOW (backend
  // `services/source_selector.py`), so one physical historical record is
  // legitimately returned again under every origin whose window still
  // contains it. Reproduced against the real Sri Lanka LSD corpus
  // (2026-08-30): 6 real model-candidate records across 5 real origins
  // produce 9 merged rows over only 6 distinct real locations -- 3 records
  // returned twice each. Those 3 duplicate rows painted a second identical
  // icon at the exact same pixel AND collided on the `promoteId:
  // 'source_id'` feature id used for the selection halo/dim state.
  //
  // This is NOT clustering and must never be described as such (the map's
  // own Clusters mode stays honestly disabled -- no ST-DBSCAN output is
  // exposed by the runtime API). No coordinate is moved, averaged or
  // invented; the aggregate keeps the first contributing record's own real
  // geometry and properties verbatim and only ADDS the real
  // `sourceIds`/`outbreakIds`/`stackCount` it derived from real rows.
  // GEO-VISUAL-POLISH-02 Section 1: kept as its own memo (rather than
  // inlined into `nationalSourcesFC` below) so its own `.features.length`
  // -- stage C, "real source geometries actually resolved" -- is a real
  // number this page can report, distinct from stage D (the aggregated
  // count actually handed to MapLibre).
  const mergedNationalSourcesFC = useMemo(
    () => buildNationalSourcesFeatureCollection(national.originsWithSources),
    [national.originsWithSources],
  )
  // Research layers (historical-origin grid, per-cell gradient arrows, full
  // corridors, 2020 origin replay) are no longer offered on this page.
  const showResearchLayers = false
  // Dated historical research records (grey diamonds) appear only in an
  // explicitly historical context -- Retrospective analysis date or Research
  // layers -- never mixed into live national surveillance.
  const showHistoricalRecords = basisOption.id === ANALYSIS_BASIS.RETROSPECTIVE || showResearchLayers
  const nationalSourcesFC = useMemo(
    () => (showHistoricalRecords ? aggregateNationalSourcesByLocation(mergedNationalSourcesFC) : EMPTY_FC),
    [mergedNationalSourcesFC, showHistoricalRecords],
  )

  // Phase 3: the Page-1 timeline layers come from ONE backend snapshot
  // (`GET /api/geospatial/spatial-timeline`, national scope): backend dates,
  // backend reach-limited relative-risk polygons, backend direction corridors.
  // Fetched once per disease / refresh -- never per animation frame.
  // National case surveillance: countrywide LSD/FMD records, refreshed on the
  // existing reconciliation heartbeat (>=15 s) and on every live case event.
  const nationalCases = useNationalCases({ heartbeat: operational.lastRefreshedAt, eventKey: nationalCasesEventKey(clinicalEvents) })
  // The timeline is refetched when the set of possible sources changes (a
  // case verified or withdrawn, a farm GPS added) -- not on every heartbeat.
  const sourceSignature = useMemo(() => eligibleSourceSignature(nationalCases.data?.records, ctx.selectedDisease), [nationalCases.data, ctx.selectedDisease])
  const sourceChangeToken = useSourceChangeToken(sourceSignature)
  const spatialTimeline = useSpatialTimeline({
    disease: ctx.selectedDisease,
    scope: 'national',
    asOf: basisOption.asOf,
    enabled: Boolean(ctx.selectedDisease),
    refreshToken: `${refreshToken}:${dataChangeToken}:${sourceChangeToken}`,
    retryKey: operational.lastRefreshedAt,
  })
  const timelineSnapshot = spatialTimeline.data
  const timelineFrameDates = useMemo(() => frameDates(timelineSnapshot), [timelineSnapshot])
  const farmNames = useAssignedFarmNames(dataChangeToken)
  // Research inspection (off by default): the selected historical origin's
  // per-cell grid/arrows and the backend's full reach-length corridors.
  // Trajectory shows the backend's own per-day corridors (length = that
  // day's nominal reach); every other mode shows no corridor at all, so the
  // modes stay visually distinct (origins remain marked in every mode).
  const showFullCorridors = ctx.analysisMode === ANALYSIS_MODE.TRAJECTORY || showResearchLayers
  const page1ForecastVisualization = useMemo(() => {
    const layers = buildNationalTimelineLayers(timelineSnapshot, page1ForecastActiveIndex, { research: showFullCorridors && page1ForecastActiveIndex > 0, landDomain: sriLankaDistricts ?? null })
    // Static tier fills are drawn by the stage layers instead (scored extent
    // faded + reach-limited bands bright), so the legacy buffers stay empty.
    if (ctx.analysisMode === ANALYSIS_MODE.TRAJECTORY || showResearchLayers) {
      // Sri Lanka Overview: every eligible case nationwide shows its spread.
      // My District: only the cases inside the logged-in vet's district.
      if (!districtFeature || locationScope !== LOCATION_SCOPE.MY_DISTRICT) return { ...layers, riskZones: EMPTY_FC }
      const inDistrict = new Set((timelineSnapshot?.sources ?? [])
        .filter((src) => isPointInsideDistrictFeature([src.longitude, src.latitude], districtFeature))
        .map((src) => src.source_id))
      const keep = (fc) => ({ type: 'FeatureCollection', features: (fc?.features ?? []).filter((f) => [f.properties?.sourceId, ...(f.properties?.memberSourceIds ?? [])].some((id) => inDistrict.has(id))) })
      return { ...layers, riskZones: EMPTY_FC, paths: keep(layers.paths), fronts: keep(layers.fronts), remaining: keep(layers.remaining), plumes: keep(layers.plumes), origins: keep(layers.origins) }
    }
    return { ...layers, riskZones: EMPTY_FC, paths: EMPTY_FC, fronts: EMPTY_FC, remaining: EMPTY_FC, plumes: EMPTY_FC }
  }, [timelineSnapshot, page1ForecastActiveIndex, showFullCorridors, ctx.analysisMode, showResearchLayers, sriLankaDistricts, districtFeature, locationScope])
  // Only a snapshot the backend actually computed (status OK) drives the
  // master timeline and its layers; FMD (no frozen spatial model) and an
  // empty source set fall back to the existing timelines unchanged.
  const page1ForecastAvailable = isTimelineRenderable(timelineSnapshot)
  const page1ForecastReady = page1ForecastAvailable
  const page1ForecastDateLabel = page1ForecastVisualization.date ? formatDisplayDate(page1ForecastVisualization.date) : null
  const page1HorizonLabel = horizonLabel(page1ForecastVisualization.frame?.horizon_status)
  // The relative score is fixed at the as-of date; the day only moves the
  // nominal-reach outline. Said in the timeline header itself.
  const page1TimelineStatusLabel = timelineSnapshot?.as_of
    ? `${page1HorizonLabel} · score fixed as of ${formatDisplayDate(timelineSnapshot.as_of)}`
    : page1HorizonLabel
  const spatialTimelineErrorNotice = spatialTimeline.status === SPATIAL_TIMELINE_STATE.ERROR
    ? 'Spatial risk timeline unavailable right now (retrying with the next sync).'
    : timelineSnapshot?.status === TIMELINE_STATUS.MODEL_NOT_READY
      ? `No validated spatial risk model for ${diseaseConfig.shortLabel} -- confirmed markers only.`
      : timelineSnapshot?.status === TIMELINE_STATUS.NO_ELIGIBLE_SOURCES
        ? `No eligible ${diseaseConfig.shortLabel} sources in the last 14 days -- no risk zones to show.`
        : null
  // Mode semantics (what the tiers / arrows do and do not mean) now sit in
  // the situation brief's legend; an empty or model-unavailable snapshot gets
  // the explained empty-state card. Only a real fetch failure keeps this
  // small top-right notice.
  const spatialTimelineNotice = spatialTimeline.status === SPATIAL_TIMELINE_STATE.ERROR ? spatialTimelineErrorNotice : null
  // Phase 4: a clicked corridor/origin is pinned by SOURCE id, so the pinned
  // tooltip always shows the selected frame's backend values for it; a
  // hover shows a transient preview.
  const [selectedCorridorId, setSelectedCorridorId] = useState(null)
  const [hoveredCorridor, setHoveredCorridor] = useState(null)
  const selectedCorridor = useMemo(() => {
    if (!selectedCorridorId) return null
    const match = (collection) => collection?.features?.find((f) => f.properties?.sourceId === selectedCorridorId)?.properties
    return match(page1ForecastVisualization.paths) ?? match(page1ForecastVisualization.origins) ?? null
  }, [selectedCorridorId, page1ForecastVisualization])
  const corridorTooltip = selectedCorridor ?? hoveredCorridor
  const page1PlateauNote = plateauNote(timelineSnapshot, page1ForecastActiveIndex)

  // ---- Per-mode stage layers + situation brief (all from the ONE backend
  // snapshot above, or real operational/district data). `vetDistrict` is
  // read straight from `operational.data` here: the page-level
  // `vetDistrict` const is declared further down (TDZ, see GEO29A). ----
  const storyVetDistrict = operational.data?.vetDistrict ?? null
  const spatialStory = useMemo(
    () => buildSpatialStory(timelineSnapshot, page1ForecastActiveIndex, { vetDistrict: storyVetDistrict }),
    [timelineSnapshot, page1ForecastActiveIndex, storyVetDistrict],
  )
  const reachHistory = useMemo(() => buildReachHistory(timelineSnapshot, page1ForecastActiveIndex), [timelineSnapshot, page1ForecastActiveIndex])
  // Risk Zones: the backend's own scored 5 km cells for the selected day
  // (bright once that day's nominal reach covers them).
  const riskCells = useMemo(() => buildRiskCells(timelineSnapshot, page1ForecastActiveIndex), [timelineSnapshot, page1ForecastActiveIndex])
  // Animated surface: backend cells revealed by their first reached day.
  const riskFieldModel = useMemo(() => buildRiskFieldModel(timelineSnapshot), [timelineSnapshot])
  const monitoringZones = useMemo(() => buildMonitoringZones(timelineSnapshot, page1ForecastActiveIndex), [timelineSnapshot, page1ForecastActiveIndex])
  const baselineZones = useMemo(() => buildNationalTimelineLayers(timelineSnapshot, 0).riskZones, [timelineSnapshot])
  const latestNationalRecordDate = useMemo(() => {
    let latest = null
    for (const record of nationalCases.data?.records ?? []) {
      if (record.disease !== ctx.selectedDisease) continue
      const d = caseDateKey(record)
      if (d && (!latest || d > latest)) latest = d
    }
    return latest
  }, [nationalCases.data, ctx.selectedDisease])
  const nationalWindow = resolveObservationWindow(observationWindowDays, { basisAsOf: casesAsOf, latestRecordDate: latestNationalRecordDate })
  const nationalCaseView = useMemo(
    () => buildNationalCaseView(nationalCases.data?.records, {
      disease: ctx.selectedDisease,
      windowDays: nationalWindow.days,
      endIsoDate: nationalWindow.endIsoDate,
      districtFeature: locationScope === LOCATION_SCOPE.MY_DISTRICT ? districtFeature : null,
      ageReferenceDateKey: caseAgeRef.dateKey,
      observedThrough: showOperationalLayer ? observedReplayDateKey : null,
    }),
    [nationalCases.data, ctx.selectedDisease, nationalWindow.days, nationalWindow.endIsoDate, locationScope, districtFeature, caseAgeRef.dateKey, showOperationalLayer, observedReplayDateKey],
  )
  const observedReplayDates = nationalCaseView.replayDates
  const nationalCaseCounts = useMemo(
    () => ({
      verifiedOnMap: nationalCaseView.counts.mappedVerified,
      pendingOnMap: nationalCaseView.counts.mappedPending,
      withoutGps: nationalCaseView.counts.withoutGps,
      hiddenOlder: nationalCaseView.counts.hiddenOlder,
      byAge: nationalCaseView.counts.mappedByAge,
      ageReferenceLabel: caseAgeRef.label,
    }),
    [nationalCaseView, caseAgeRef.label],
  )
  const nationalCaseStatusReady = nationalCases.status === NATIONAL_CASES_STATE.READY && Boolean(nationalCases.data)
  // Real reports from the last 14 days that cannot be placed (farm has no
  // GPS): said on the map, since they are otherwise invisible here.
  const recentUnmappedNotice = useMemo(
    () => unmappedNoticeText(recentUnmappedRecords(nationalCases.data?.records, { disease: ctx.selectedDisease, todayKey }), diseaseConfig.shortLabel),
    [nationalCases.data, ctx.selectedDisease, todayKey, diseaseConfig.shortLabel],
  )
  // "New case" toasts: records that appear (or become verified) on a refresh.
  const newCaseAlerts = useNewCaseAlerts(nationalCases.data?.records)
  function handleViewNewCase(alert) {
    const r = alert.record
    newCaseAlerts.dismiss(alert.id)
    if (!Number.isFinite(r?.latitude) || !Number.isFinite(r?.longitude)) return
    ctx.setMode(ANALYSIS_MODE.CASES)
    const pad = 0.25
    mapCanvasRef.current?.resetView([[r.longitude - pad, r.latitude - pad], [r.longitude + pad, r.latitude + pad]])
  }
  // Cases, Risk Zones and Trajectory all draw the observed case markers.
  const showObservedCaseMarkers = ctx.analysisMode === ANALYSIS_MODE.CASES || ctx.analysisMode === ANALYSIS_MODE.RISK_ZONES || ctx.analysisMode === ANALYSIS_MODE.TRAJECTORY
  const [selectedNationalCase, setSelectedNationalCase] = useState(null)
  useEffect(() => {
    setSelectedNationalCase(null)
  }, [ctx.selectedDisease, ctx.analysisMode, observationWindowDays, basisOption.asOf, observedReplayDateKey])

  // Clicking a case: show its details and, in Trajectory, focus that case's
  // model source (the source at the clicked farm, within 1 km) -- the other
  // paths fade back.
  function handleSelectNationalCase(properties) {
    setSelectedNationalCase(properties)
    const [lon, lat] = Array.isArray(properties?.coordinates) ? properties.coordinates : []
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return
    let best = null
    for (const source of timelineSnapshot?.sources ?? []) {
      const km = Math.hypot((source.longitude - lon) * 110.6 * Math.cos((lat * Math.PI) / 180), (source.latitude - lat) * 110.6)
      if (km <= 1 && (!best || km < best.km)) best = { id: source.source_id, km }
    }
    // Neighbouring cases share one outbreak path: focus the path holding this case.
    const group = best ? (timelineSnapshot?.source_paths ?? []).find((p) => (p.member_source_ids ?? [p.source_id]).includes(best.id)) : null
    setSelectedCorridorId(group?.source_id ?? best?.id ?? null)
  }

  // EXPLORATORY runtime ST-DBSCAN, fetched only in Clusters mode.
  // Also fetched while a case is selected: its card shows the case's cluster result.
  const stClusters = useStClusters({ disease: ctx.selectedDisease, asOf: basisOption.asOf, enabled: ctx.analysisMode === ANALYSIS_MODE.CLUSTERS || Boolean(selectedCorridorId), refreshToken: dataChangeToken })
  const selectedCaseCoordinates = useMemo(() => {
    const source = (timelineSnapshot?.sources ?? []).find((s) => s.source_id === selectedCorridorId)
    return source ? [source.longitude, source.latitude] : null
  }, [timelineSnapshot, selectedCorridorId])
  const selectedCaseCluster = useMemo(() => clusterForCase(stClusters, selectedCaseCoordinates), [stClusters, selectedCaseCoordinates])
  // The selected case's own farm on the selected day (backend risk raster).
  const selectedCaseRisk = useMemo(
    () => (selectedCaseCoordinates ? probeRiskField(riskFieldModel, page1ForecastActiveIndex, ...selectedCaseCoordinates) : null),
    [riskFieldModel, page1ForecastActiveIndex, selectedCaseCoordinates],
  )
  // Env follows the timeline: the selected frame's own date (real ERA5 for
  // that past day). A frame after today has no observation -- never filled.
  // Env dates: the model timeline's dates when it is playable, otherwise its
  // own 15 days from the analysis date (so today's forecast always shows).
  const [envDayIndex, setEnvDayIndex] = useState(0)
  const envDates = useMemo(
    () => (page1ForecastAvailable && timelineFrameDates.length ? timelineFrameDates : Array.from({ length: 15 }, (_, i) => addDaysToIsoDate(basisOption.asOf ?? todayKey, i))),
    [page1ForecastAvailable, timelineFrameDates, basisOption.asOf, todayKey],
  )
  useEffect(() => { setEnvDayIndex(0) }, [basisOption.asOf])
  const environmentFrameDate = page1ForecastAvailable ? timelineFrameDates[page1ForecastActiveIndex] ?? null : envDates[envDayIndex] ?? null
  const environmentDate = environmentFrameDate ?? basisOption.asOf ?? todayKey
  const environmentDateInFuture = environmentDate > todayKey
  const environmentObservations = useEnvironmentObservations({ disease: ctx.selectedDisease, district: storyVetDistrict, asOf: environmentDate, enabled: ctx.analysisMode === ANALYSIS_MODE.ENV && Boolean(storyVetDistrict) && !environmentDateInFuture, refreshToken: dataChangeToken })
  // District forecast (today onward) for Env; past dates use backend ERA5.
  // Weather sample points INSIDE the district polygon; the map label sits at
  // their mean (always on the district, unlike a bounding-box centre).
  const districtWeatherPoints = useMemo(() => (districtFeature ? districtSamplePoints(districtFeature) : []), [districtFeature])
  // Env: a point the vet clicked -> the forecast for that point's model grid
  // cell (~10 km) instead of the district average. Only points on Sri Lanka
  // land (inside a district) are accepted; leaving Env clears it.
  const [envPoint, setEnvPoint] = useState(null) // { point: [lon, lat], place, district }
  function handleEnvPointSelect({ point, place }) {
    const district = (sriLankaDistricts?.features ?? []).find((f) => isPointInsideDistrictFeature(point, f))
    if (!district) return
    setEnvPoint({ point, place: place?.name ?? null, district: normalizeDistrictDisplayName(district.properties?.shapeName ?? district.properties?.name) ?? null })
  }
  useEffect(() => { if (ctx.analysisMode !== ANALYSIS_MODE.ENV) setEnvPoint(null) }, [ctx.analysisMode])
  const districtCentre = useMemo(() => {
    const bounds = districtFeature ? computeFeatureBounds(districtFeature) : null
    if (!bounds) return null
    const [[w, south], [e, n]] = bounds
    const inside = districtWeatherPoints.length
      ? { longitude: districtWeatherPoints.reduce((a, p) => a + p[0], 0) / districtWeatherPoints.length, latitude: districtWeatherPoints.reduce((a, p) => a + p[1], 0) / districtWeatherPoints.length }
      : { longitude: (w + e) / 2, latitude: (south + n) / 2 }
    return { ...inside, spanDeg: Math.max(e - w, n - south) }
  }, [districtFeature, districtWeatherPoints])
  const districtForecast = useDistrictWeatherForecast({
    latitude: districtCentre?.latitude, longitude: districtCentre?.longitude,
    points: envPoint ? [envPoint.point] : districtWeatherPoints,
    enabled: ctx.analysisMode === ANALYSIS_MODE.ENV,
  })
  // Where the forecast symbol sits and how far its wind animation spreads:
  // the selected point's ~10 km grid cell, or the whole district.
  const forecastAnchor = envPoint ? { longitude: envPoint.point[0], latitude: envPoint.point[1], spanDeg: 0.09 } : districtCentre
  const envForecastDay = environmentDate >= todayKey ? districtForecast.days.get(environmentDate) ?? null : null
  const envArea = useMemo(() => {
    if (!districtFeature) return null
    // Selected point: tint a ~5 km radius (about one forecast grid cell), not the district.
    const areaGeometry = envPoint && envForecastDay ? kmCircle(envPoint.point, 5) : districtFeature.geometry
    let condition = envForecastDay?.condition ?? null
    let rainMm = envForecastDay?.rainMm ?? null
    if (!condition) {
      // Past date: the backend ERA5 district reference observation.
      const ref = (environmentObservations.data?.observations ?? []).find((o) => o.role === 'DISTRICT_REFERENCE_POINT' && o.status === 'OK')
      const value = (name) => ref?.features?.find((f) => f.feature_name === name && f.status === 'REAL')?.value ?? null
      if (!ref) return null
      rainMm = value('precipitation_accumulation')
      const windKmh = value('mean_wind_speed') !== null ? value('mean_wind_speed') * 3.6 : null
      condition = weatherCondition({ code: null, rainMm, windKmh })
    }
    const tint = condition === 'RAIN' || condition === 'STORM' ? 0.14 + Math.min(0.22, (rainMm ?? 0) / 60) : 0.12
    // A hot, dry day is coloured by the heat layer alone (no grey/cloud tint under it).
    const heat = heatIntensity(envForecastDay)
    return { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: areaGeometry, properties: { condition, tint: heat > 0 ? 0 : tint, heat } }] }
  }, [districtFeature, envForecastDay, environmentObservations.data, envPoint])
  const clusterFeatures = useMemo(() => buildClusterFeatureCollection(stClusters.data), [stClusters.data])
  const stageLayers = useMemo(
    () => ({
      riskCells,
      monitoringZones,
      baselineZones,
      reachHistory,
      nationalCases: nationalCaseView.featureCollection,
      clusters: clusterFeatures,
      riskField: { model: riskFieldModel, index: page1ForecastActiveIndex },
      environment: ctx.analysisMode !== ANALYSIS_MODE.ENV ? undefined
        : envForecastDay && forecastAnchor ? { type: 'FeatureCollection', features: [forecastFeature(envForecastDay, forecastAnchor)] }
          : !environmentDateInFuture ? buildEnvironmentFeatures(environmentObservations.data) : undefined,
      environmentArea: ctx.analysisMode === ANALYSIS_MODE.ENV ? envArea : undefined,
    }),
    [riskCells, monitoringZones, baselineZones, reachHistory, nationalCaseView, clusterFeatures, riskFieldModel, page1ForecastActiveIndex, ctx.analysisMode, environmentDateInFuture, environmentObservations.data, envForecastDay, forecastAnchor, envArea],
  )
  // Risk Zones / Trajectory: frame the snapshot's real sources + scored cells
  // ONCE per (mode, snapshot) -- never on a day change -- so a small model
  // extent is readable. "Fit Sri Lanka" returns to the national view.
  const modelFramedKeyRef = useRef(null)
  // No automatic zoom on entering Risk Zones / Trajectory: the camera stays
  // on the whole of Sri Lanka (cases and zones visible together) unless the
  // vet zooms or uses Focus My District / Fit Sri Lanka.

  // Env mode looks at the vet's own district: the weather shown is for it.
  // Leaving Env returns to the whole-island view.
  const envFocusedRef = useRef(false)
  useEffect(() => {
    if (ctx.analysisMode !== ANALYSIS_MODE.ENV && envFocusedRef.current) {
      envFocusedRef.current = false
      if (locationScope !== LOCATION_SCOPE.MY_DISTRICT) mapCanvasRef.current?.resetView()
    }
    if (ctx.analysisMode !== ANALYSIS_MODE.ENV || !districtFeature) return undefined
    envFocusedRef.current = true
    let frameId = null
    const attempt = () => {
      if (!mapCanvasRef.current?.isReady?.()) {
        frameId = requestAnimationFrame(attempt)
        return
      }
      const bounds = computeFeatureBounds(districtFeature)
      if (bounds) mapCanvasRef.current.resetView(bounds)
    }
    attempt()
    return () => { if (frameId != null) cancelAnimationFrame(frameId) }
  }, [ctx.analysisMode, districtFeature])

  // Arrived from My Area "View on Map": show that outbreak in Trajectory,
  // centred on its real position, with its direction line pinned. Runs once.
  const locationState = useOptionalLocationState()
  const pendingOutbreakFocusRef = useRef(locationState?.focusOutbreak ?? null)
  useEffect(() => {
    const target = pendingOutbreakFocusRef.current
    if (!target) return
    ctx.setMode(target.mode === 'CASES' ? ANALYSIS_MODE.CASES : ANALYSIS_MODE.TRAJECTORY)
    if (target.disease && target.disease !== ctx.selectedDisease) ctx.selectDisease(target.disease)
    if (target.asOf) {
      setCustomAnalysisDate(target.asOf)
      setAnalysisBasis(ANALYSIS_BASIS.CUSTOM)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    const target = pendingOutbreakFocusRef.current
    if (!target || !Number.isFinite(target.latitude) || !Number.isFinite(target.longitude)) return undefined
    if (target.mode !== 'CASES' && (!isTimelineRenderable(timelineSnapshot) || (target.asOf && timelineSnapshot.as_of !== target.asOf) || (target.disease && ctx.selectedDisease !== target.disease))) return undefined
    let frameId = null
    const attempt = () => {
      if (!mapCanvasRef.current?.isReady?.()) {
        frameId = requestAnimationFrame(attempt)
        return
      }
      pendingOutbreakFocusRef.current = null
      // Keep the automatic snapshot framing from overriding this focus.
      modelFramedKeyRef.current = `${ANALYSIS_MODE.TRAJECTORY}:${timelineSnapshot?.snapshot_id ?? ''}`
      if (target.mode !== 'CASES') setPage1ForecastActiveIndex(clampFrameIndex(timelineSnapshot, target.day))
      const pad = 0.35
      mapCanvasRef.current.resetView([[target.longitude - pad, target.latitude - pad], [target.longitude + pad, target.latitude + pad]])
      if (target.sourceId) setSelectedCorridorId(target.sourceId)
    }
    attempt()
    return () => { if (frameId != null) cancelAnimationFrame(frameId) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timelineSnapshot])

  // A clicked cell is pinned by id, so its card follows the selected day.
  const [selectedRiskCellId, setSelectedRiskCellId] = useState(null)
  const selectedRiskCell = useMemo(
    () => (selectedRiskCellId ? monitoringZones.features.find((f) => f.properties.cellId === selectedRiskCellId)?.properties ?? null : null),
    [selectedRiskCellId, monitoringZones],
  )
  useEffect(() => {
    setSelectedRiskCellId(null)
  }, [ctx.analysisMode, ctx.selectedDisease, basisOption.id])
  const timelineEmptyReason = unavailableReason(timelineSnapshot, { diseaseShortLabel: diseaseConfig.shortLabel, basis: basisOption.id, fetchState: spatialTimeline.status, errorStatus: spatialTimeline.errorStatus })

  // GEO-VISUAL-POLISH-02 Section 1/2/10: the full, honest database ->
  // forecast-origin -> per-origin-geometry -> rendered-marker trace,
  // reported to `StatusDiagnosticsMenu` -- every field is a real count
  // already computed above or by `useNationalOutbreaks.js` itself, never
  // a second/divergent computation.
  const originResolutionStats = useMemo(
    () => ({
      expectedOriginCount: national.expectedOriginCount,
      resolvedOriginCount: national.resolvedOriginCount,
      failedOriginCount: national.failedOriginCount,
      expectedSourceRecordCount: national.expectedSourceRecordCount,
      resolvedGeometryFeatureCount: mergedNationalSourcesFC.features.length,
      renderedFeatureCount: nationalSourcesFC.features.length,
    }),
    [
      national.expectedOriginCount,
      national.resolvedOriginCount,
      national.failedOriginCount,
      national.expectedSourceRecordCount,
      mergedNationalSourcesFC,
      nationalSourcesFC,
    ],
  )

  // Section 7: true only when at least one marker genuinely represents
  // more than one DISTINCT real record at one coordinate -- drives whether
  // the legend shows the stack-ring key at all. For the real Sri Lanka LSD
  // corpus today this is `false` (every location holds exactly one real
  // record), which is the honest answer: 6 markers for 6 real observed
  // locations, and the "9" was an eligibility-window artifact, not 9 real
  // outbreak points.
  const hasStackedSources = useMemo(
    () => nationalSourcesFC.features.some((f) => (f.properties?.stackCount ?? 1) > 1),
    [nationalSourcesFC],
  )

  // GEO-PAGE1-FINAL: a REAL, previously-latent crash found while adding
  // this closure pass's own auto-focus end-to-end test (never triggered
  // manually before -- no prior browser session ever got past this
  // page's own real authentication to select a real LSD outbreak). The
  // real `/analysis/{id}/cells` response is a `CellFeatureCollection`
  // wrapper object (`{ type, features, analysis_metadata, snapshot_id,
  // generated_at_utc }`, `api/schemas.py::CellFeatureCollection`) -- so
  // `focus.cells` is that WHOLE wrapper, never a bare array of features.
  // Every consumer that needs the plain feature array (`computeRiskTierStats`,
  // `MapLibreCanvas`'s `cellFeatures`, the SVG-fallback `MapCanvas`) must
  // unwrap `.features` -- exactly like `reachRingCenters` below already,
  // correctly, does for the equivalent `focus.sources` wrapper. Without
  // this, `computeRiskTierStats`'s `for (const c of cells)` throws
  // `TypeError: cells is not iterable` the instant any real outbreak
  // with real cell data reaches FOCUS_STATUS.READY -- an unhandled
  // exception with no error boundary above this route, which unmounts
  // the entire React tree (the same class of bug GEO28A/GEO29A already
  // fixed elsewhere on this page). One shared derivation, reused by
  // every real consumer below, so this can never drift out of sync again.
  const focusCellFeatures = useMemo(
    () => (focus.status === FOCUS_STATUS.READY ? (focus.cells?.features ?? []) : []),
    [focus.status, focus.cells],
  )

  // GEO-VISUAL-POLISH-03: the SAME real per-snapshot quartile stats the
  // map's own `cells-circle` layer paints with (`MapLibreCanvas.jsx`) --
  // never a second, divergent computation the legend could drift from.
  // Legend tier counts come from the SAME backend cells the Risk Zones layer
  // draws (the selected analysis date's snapshot); the legacy focused origin's
  // cells only when no snapshot is renderable.
  const riskTierStats = useMemo(() => {
    const snapshotCells = isTimelineRenderable(timelineSnapshot)
      ? (timelineSnapshot.cells ?? []).filter((c) => c?.score_status === 'SCORED').map((c) => ({ properties: { risk: { raw_c0_score: c.raw_c0_score } } }))
      : null
    return computeRiskTierStats(snapshotCells ?? focusCellFeatures)
  }, [timelineSnapshot, focusCellFeatures])

  // LSD-PAGE1-HARDENING Section 25: fullscreen targets `mapWrapperRef`
  // (the whole map card, including the toolbar/timeline/legend/popup
  // overlays below -- all siblings of MapLibreCanvas, not children of
  // it), so every one of them stays visible in fullscreen. MapLibre gets
  // an explicit `resize()` on the transition since it has no
  // ResizeObserver of its own.
  useEffect(() => {
    function onFullscreenChange() {
      setIsFullscreen(Boolean(document.fullscreenElement))
      mapCanvasRef.current?.resize()
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  const fullscreenSupported = typeof document !== 'undefined' && typeof document.documentElement?.requestFullscreen === 'function'

  function toggleFullscreen() {
    if (!fullscreenSupported) return
    if (!document.fullscreenElement) {
      mapWrapperRef.current?.requestFullscreen?.()
    } else {
      document.exitFullscreen?.()
    }
  }

  // Once the selected outbreak's real summary arrives, report its real
  // frame horizon + snapshot identity back into shared state (plan
  // Section 20 step 8: "derive available nominal-reach days").
  useEffect(() => {
    if (focus.status === FOCUS_STATUS.READY && ctx.selectedOutbreakId) {
      const days = deriveAvailableForecastDays(ctx.selectedDisease, focus.summary)
      ctx.setAvailableFrames(ctx.selectedOutbreakId, days, focus.summary.snapshot_id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus.status, focus.summary])

  const adapter = diseaseReady ? getOutbreakAdapter(ctx.selectedDisease) : null

  const frame = useMemo(() => {
    if (!adapter || focus.status !== FOCUS_STATUS.READY) return null
    return adapter.buildForecastFrame({ summary: focus.summary, sources: focus.sources, cells: focus.cells, dayIndex: ctx.selectedForecastDay })
  }, [adapter, focus.status, focus.summary, focus.sources, focus.cells, ctx.selectedForecastDay])

  // GEO-TRAJECTORY-01: the real nominal-reach ring is honest, real
  // day-varying data (`nominal_reach_by_day`) in BOTH Risk Zones and
  // Trajectory mode -- Trajectory is the dedicated "where might this
  // spread" view (reach ring + per-cell direction arrows, no risk-tier
  // dots), Risk Zones is the dedicated "how risky is this cell right now"
  // view (tier dots + the same reach ring for scale). Never shown outside
  // either mode.
  const reachRingCenters = useMemo(() => {
    if (ctx.analysisMode !== ANALYSIS_MODE.RISK_ZONES && ctx.analysisMode !== ANALYSIS_MODE.TRAJECTORY) return null
    // The auto-focused HISTORICAL origin's own ring belongs to that origin's
    // t0, not to the analysis date shown -- drawing it by default produced
    // "no eligible sources" next to visible reach artifacts. Research only.
    if (!showResearchLayers) return null
    return focus.sources?.features?.map((f) => f.geometry.coordinates) ?? null
  }, [ctx.analysisMode, focus.sources, showResearchLayers])

  // GEO-TRAJECTORY-01: whether the CURRENTLY selected real origin actually
  // has real direction data on at least one cell -- `direction_status` is
  // `DIRECTION_AVAILABLE` only when the frozen C0 combined direction
  // vector didn't cancel/vanish for that cell (`c0_cell_local_tendency_8b3.py`). Confirmed
  // live against the running backend (2026-09-01): every real LSD origin
  // sampled had `DIRECTION_AVAILABLE` on 100% of its cells, but this is
  // computed from the real per-origin response rather than assumed, so an
  // origin where the combined direction vector genuinely cancels/vanishes
  // for every cell still gets the honest "unavailable for this origin"
  // state below instead of a silently empty arrow layer.
  const trajectoryDirectionAvailable = useMemo(
    () => focusCellFeatures.some((f) => f.properties?.direction?.bearing_deg !== null && f.properties?.direction?.bearing_deg !== undefined),
    [focusCellFeatures],
  )
  // Whole-origin reach availability -- NOT the current single day's value
  // (day 0/observed always has no forward reach by design, see
  // `lsdOutbreakAdapter.js`'s `findNominalReach`, and must never itself
  // read as "this origin has no reach model at all").
  const trajectoryReachAvailable = (focus.summary?.nominal_reach_by_day?.length ?? 0) > 0
  // Legend-facing, day-specific signal -- whether the ring is actually
  // drawn on THIS snapshot (day 0/observed has no forward reach by design,
  // so the ring legitimately draws nothing there even for an origin with a
  // real reach table) -- mirrors `hasClinicalMarkers`'s existing "only key
  // what's currently really on the map" pattern (`PageLegend.jsx`).
  const reachRingCurrentlyVisible = (frame?.nominalReachKm ?? 0) > 0
  const showTrajectoryLayer = ctx.analysisMode === ANALYSIS_MODE.TRAJECTORY
  const trajectoryUnavailableForOrigin =
    showTrajectoryLayer && ctx.selectedOutbreakId && focus.status === FOCUS_STATUS.READY && !trajectoryDirectionAvailable && !trajectoryReachAvailable

  // GEO-VISUAL-POLISH-01 Section 9: a single shared playback-speed
  // multiplier for BOTH timelines below (0.5x/1x/2x) -- speed changes
  // TIMING only, never which real day/date advances to, so one shared
  // value is honest for both the scientific and the observed-replay
  // clock rather than needing two independent controls that could drift.
  const [playbackSpeed, setPlaybackSpeed] = useState(1)

  useEffect(() => {
    setPage1ForecastActiveIndex(0)
    setIsPage1ForecastPlaying(false)
    setSelectedCorridorId(null)
    setHoveredCorridor(null)
  }, [ctx.selectedDisease])
  // A focused path belongs to Trajectory: switching mode clears the focus.
  useEffect(() => {
    setSelectedCorridorId(null)
    setHoveredCorridor(null)
  }, [ctx.analysisMode])

  // Exactly one user-triggered clock advances the 14 presentation frames.
  // Speeds are 2200/1100/550ms for 0.5x/1x/2x, and the final frame stops
  // in place. RAF keeps this compatible with the feature's timer policy.
  const page1PlaybackFrameRef = useRef(null)
  const page1PlaybackLastTickRef = useRef(0)
  useEffect(() => {
    if (!isPage1ForecastPlaying || !page1ForecastAvailable) return undefined
    page1PlaybackLastTickRef.current = performance.now()
    const intervalMs = PAGE1_PLAYBACK_INTERVAL_MS[playbackSpeed] ?? PAGE1_PLAYBACK_INTERVAL_MS[1]
    const tick = (now) => {
      if (now - page1PlaybackLastTickRef.current >= intervalMs) {
        page1PlaybackLastTickRef.current = now
        setPage1ForecastActiveIndex((current) => {
          const finalIndex = timelineFrameDates.length - 1
          const next = Math.min(finalIndex, current + 1)
          if (next >= finalIndex) setIsPage1ForecastPlaying(false)
          return next
        })
      }
      page1PlaybackFrameRef.current = requestAnimationFrame(tick)
    }
    page1PlaybackFrameRef.current = requestAnimationFrame(tick)
    return () => {
      if (page1PlaybackFrameRef.current) cancelAnimationFrame(page1PlaybackFrameRef.current)
      page1PlaybackFrameRef.current = null
    }
  }, [isPage1ForecastPlaying, page1ForecastAvailable, playbackSpeed, timelineFrameDates.length])

  // The small "Updating…" acknowledgement is tied to a real timeline
  // change and removes itself after 340ms. It never reflects connection
  // health and therefore cannot become stuck on RECONNECTING.
  const page1UpdateFeedbackFrameRef = useRef(null)
  const page1UpdateFeedbackMountedRef = useRef(false)
  useEffect(() => {
    if (!page1UpdateFeedbackMountedRef.current) {
      page1UpdateFeedbackMountedRef.current = true
      return undefined
    }
    setIsPage1ForecastUpdating(true)
    const startedAt = performance.now()
    const tick = (now) => {
      if (now - startedAt >= 340) {
        setIsPage1ForecastUpdating(false)
        page1UpdateFeedbackFrameRef.current = null
        return
      }
      page1UpdateFeedbackFrameRef.current = requestAnimationFrame(tick)
    }
    page1UpdateFeedbackFrameRef.current = requestAnimationFrame(tick)
    return () => {
      if (page1UpdateFeedbackFrameRef.current) cancelAnimationFrame(page1UpdateFeedbackFrameRef.current)
      page1UpdateFeedbackFrameRef.current = null
    }
  }, [page1ForecastActiveIndex])

  function handleSelectPage1ForecastIndex(index) {
    setIsPage1ForecastPlaying(false)
    setPage1ForecastActiveIndex(clampFrameIndex(timelineSnapshot, index))
  }

  function handlePlayPage1Forecast() {
    if (!page1ForecastAvailable) return
    // At the last day, Play replays from Day 0.
    if (page1ForecastActiveIndex >= timelineFrameDates.length - 1) setPage1ForecastActiveIndex(0)
    setIsPage1ForecastPlaying(true)
  }

  useEffect(() => {
    setPage1ForecastActiveIndex(0)
    setIsPage1ForecastPlaying(false)
  }, [basisOption.id, basisOption.asOf])

  // Playback: advances one real day roughly every 1.4s (divided by the
  // real user-selected speed multiplier) while the vet has explicitly
  // pressed Play. Driven by `requestAnimationFrame`, never
  // `setInterval`/`setTimeout` -- this feature's structural tests
  // (`noAutoPolling.test.js`, `visualLayerStructural.test.js`) forbid
  // those tokens anywhere in the source tree (no automatic background
  // timer of ANY kind, scientific or not), so a user-triggered playback
  // clock still has to be RAF-driven, exactly like the reach-ring tween
  // in `MapLibreCanvas.jsx`. Stops itself at the end (`ADVANCE_DAY`
  // already flips `isPlaybackActive` off in the reducer).
  const playbackFrameRef = useRef(null)
  const playbackLastTickRef = useRef(0)
  useEffect(() => {
    if (!ctx.isPlaybackActive) return undefined
    playbackLastTickRef.current = performance.now()
    const intervalMs = 1400 / playbackSpeed
    const tick = (now) => {
      if (now - playbackLastTickRef.current >= intervalMs) {
        playbackLastTickRef.current = now
        ctx.advanceDay()
      }
      playbackFrameRef.current = requestAnimationFrame(tick)
    }
    playbackFrameRef.current = requestAnimationFrame(tick)
    return () => {
      if (playbackFrameRef.current) cancelAnimationFrame(playbackFrameRef.current)
      playbackFrameRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.isPlaybackActive, playbackSpeed])

  // GEO31A Section 6: Observed Replay playback -- advances one real
  // observed date roughly every 1.4s (same base cadence as the scientific
  // playback above, divided by the same shared speed multiplier),
  // RAF-driven only (`noAutoPolling.test.js`). Stops itself at the last
  // real date; a manual scrub always pauses it first (mirrors
  // `handleSelectDay`'s existing interrupt behavior).
  const observedPlaybackFrameRef = useRef(null)
  const observedPlaybackLastTickRef = useRef(0)
  useEffect(() => {
    if (!isObservedPlaybackActive) return undefined
    observedPlaybackLastTickRef.current = performance.now()
    const intervalMs = 1400 / playbackSpeed
    const tick = (now) => {
      if (now - observedPlaybackLastTickRef.current >= intervalMs) {
        observedPlaybackLastTickRef.current = now
        setObservedReplayDateKey((current) => {
          const currentIndex = current ? observedReplayDates.indexOf(current) : observedReplayDates.length - 1
          const nextIndex = currentIndex + 1
          if (nextIndex >= observedReplayDates.length - 1) {
            setIsObservedPlaybackActive(false)
            return null // reaching the last real date is the same as "at latest"
          }
          return observedReplayDates[nextIndex]
        })
      }
      observedPlaybackFrameRef.current = requestAnimationFrame(tick)
    }
    observedPlaybackFrameRef.current = requestAnimationFrame(tick)
    return () => {
      if (observedPlaybackFrameRef.current) cancelAnimationFrame(observedPlaybackFrameRef.current)
      observedPlaybackFrameRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isObservedPlaybackActive, observedReplayDates, playbackSpeed])

  function handleSelectObservedDate(dateKey) {
    setIsObservedPlaybackActive(false)
    // Selecting the real LAST date is equivalent to "at latest".
    setObservedReplayDateKey(dateKey === observedReplayDates[observedReplayDates.length - 1] ? null : dateKey)
  }
  function handlePlayObservedReplay() {
    // Replaying from "at latest" restarts from the real FIRST date.
    if (observedReplayDateKey === null && observedReplayDates.length > 0) setObservedReplayDateKey(observedReplayDates[0])
    setIsObservedPlaybackActive(true)
  }
  function handlePauseObservedReplay() {
    setIsObservedPlaybackActive(false)
  }
  function handleObservedPrev() {
    setIsObservedPlaybackActive(false)
    const currentIndex = observedReplayDateKey ? observedReplayDates.indexOf(observedReplayDateKey) : observedReplayDates.length - 1
    setObservedReplayDateKey(observedReplayDates[Math.max(0, currentIndex - 1)])
  }
  function handleObservedNext() {
    setIsObservedPlaybackActive(false)
    const currentIndex = observedReplayDateKey ? observedReplayDates.indexOf(observedReplayDateKey) : observedReplayDates.length - 1
    const nextIndex = Math.min(observedReplayDates.length - 1, currentIndex + 1)
    setObservedReplayDateKey(nextIndex === observedReplayDates.length - 1 ? null : observedReplayDates[nextIndex])
  }

  // Marker click triggers full focus mode directly (plan Section 20:
  // pause playback / select / one smooth fit / dim others / fetch real
  // summary+cells+sources / reset D0 / expand timeline -- all driven by
  // `ctx.selectOutbreak` + the effects above/in MapLibreCanvas), and
  // shows the compact popup (plan Section 19) alongside it as the
  // small info card for the exact source that was clicked.
  function handleSelectSource(outbreakId, sourceId) {
    const feature = nationalSourcesFC.features.find((f) => f.properties.source_id === sourceId)
    setPopupFeature(feature ?? null)
    userPickedOutbreakRef.current = true
    setIsAutoFocusedOutbreak(false)
    ctx.selectOutbreak(outbreakId)
  }

  // LSD-PAGE1-HARDENING Section 18: manually picking a day (a timeline
  // pill, or Prev/Next) must interrupt an active playback predictably --
  // the RAF-driven playback loop only stops itself at the end of the
  // horizon (see `ADVANCE_DAY` in the reducer), so a manual jump while
  // playing would otherwise keep auto-advancing on top of it.
  function handleSelectDay(day) {
    if (ctx.isPlaybackActive) ctx.pause()
    ctx.selectDay(day)
  }

  // GEO26B Section 32: previously a no-op stub (`console.debug` only) --
  // now opens a real popup for the clicked cell's real fields
  // (`CellPopup.jsx`/`CellDetailPanel.jsx`). Still not the national
  // source-selection path.
  function handleSelectCell(feature) {
    setPopupFeature(null)
    setSelectedCellFeature(feature)
  }

  // A cell selection only makes sense for the forecast day/disease it was
  // clicked under -- clears itself the moment either changes so a stale
  // cell's real fields are never shown against a different day/disease.
  useEffect(() => {
    setSelectedCellFeature(null)
  }, [ctx.selectedForecastDay, ctx.selectedDisease, ctx.selectedOutbreakId])

  const snapshotStatus =
    national.status === NATIONAL_STATUS.LOADING || focus.status === FOCUS_STATUS.LOADING
      ? SNAPSHOT_STATUS.LOADING
      : national.status === NATIONAL_STATUS.ERROR || focus.status === FOCUS_STATUS.ERROR
        ? SNAPSHOT_STATUS.UNAVAILABLE
        : SNAPSHOT_STATUS.CONNECTED

  // GEO30A Section 2: a personalized context indicator only -- never a
  // data filter (Section 5/12 keep national context in state regardless
  // of this). Only rendered once the real operational fetch has actually
  // resolved (never during the initial loading flash, and never
  // fabricated): a real district shows "MY DISTRICT · X"; a confirmed
  // absence of one shows a subtle, honest "DISTRICT NOT AVAILABLE".
  const districtKnown = operational.state === OPERATIONAL_STATE.CONNECTED || operational.state === OPERATIONAL_STATE.STALE
  const vetDistrict = operational.data?.vetDistrict ?? null

  // GEO30A Section 4: Cases works for BOTH diseases -- the scientific-
  // readiness warning only matters for a scientific mode (Risk Zones/
  // Trajectory/Env/history browsing), never Cases, so it no longer shows
  // by default in the mode this page opens in.
  const showDiseaseReadinessWarning = !diseaseReady && ctx.analysisMode !== ANALYSIS_MODE.CASES

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex shrink-0 flex-col gap-1.5">
        <div className="flex items-start justify-between gap-3">
          {/* GEO-STITCH-OUTBREAK-MAP-UI-10B: brings this page's header in
              line with `MyAreaPage.jsx`/`AnalysisTrendsPage.jsx`'s own
              title+tagline pattern -- `PAGE_TAGLINE` already existed
              (wording-firewall tested, `semanticLabels.test.js`) but was
              never rendered here, so Outbreak Map was the one Geospatial
              page missing the secondary descriptive line every sibling
              page already has. */}
          {/* Compact header: the district chip sits inline with the title so
              the map (sized from the remaining viewport) gets the height. */}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h2 className="text-[22px] font-bold leading-[1.15] text-on-surface">{PAGE_TITLE}</h2>
              {districtKnown && (vetDistrict ? (
                <span className="inline-flex items-center rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-primary">
                  MY DISTRICT · {vetDistrict.toUpperCase()}
                </span>
              ) : (
                <span className="inline-flex items-center rounded-md border border-outline-variant/30 bg-surface-container-high/40 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-on-surface-variant/60">
                  DISTRICT NOT AVAILABLE
                </span>
              ))}
            </div>
            <p className="text-xs text-on-surface-variant/70">{PAGE_TAGLINE}</p>
          </div>
          <StatusDiagnosticsMenu
            snapshotStatus={snapshotStatus}
            snapshotAsOfDate={frame ? formatDisplayDate(frame.actualDate) : undefined}
            onCheckForNewerSnapshot={() => setRefreshToken((t) => t + 1)}
            operationalState={operational.state}
            operationalLastRefreshedAt={operational.lastRefreshedAt}
            onRefreshOperational={operational.refresh}
            pushState={clinicalEvents.state}
            pushTransportMode={clinicalEvents.transportMode}
            pushIsStale={clinicalEvents.isStale}
            pushReconnectAttempt={clinicalEvents.reconnectAttempt}
            lastGenuineUpdateAt={lastGenuineUpdateAt}
            originResolutionStats={originResolutionStats}
          />
        </div>
        {/* GEO30A/GEO31A: ONE unified toolbar -- Disease, Location,
            Observation Window, then Fit/Focus/Fullscreen right-aligned,
            all inside a single bordered container (never several
            separate floating pill chips). Map modes (Cases/Clusters/Risk
            Zones/...) stay floating inside the map (Section 14); the
            scientific D0/D+N timeline stays docked to the map's own
            bottom edge (Section 15) -- neither ever appears in this row. */}
        <div className="geo-filterbar flex flex-wrap items-center gap-2.5 rounded-[14px] border border-outline-variant/30 bg-surface-container/60 px-3 py-2 2xl:flex-nowrap">
          <DiseaseSelector selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
          <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
          <LocationScopeSelect
            value={locationScope}
            onChange={handleLocationScopeChange}
            myDistrictAvailable={myDistrictAvailable}
            districtName={vetDistrict}
          />
          <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
          <ObservationWindowSelect days={observationWindowDays} onChange={setObservationWindowDays} />
          <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
          <AnalysisBasisSelect options={basisOptions} value={basisOption.id} onChange={setAnalysisBasis} customDate={customAnalysisDate} onCustomDateChange={setCustomAnalysisDate} maxDate={todayKey} />
          {/* GEO-UI-TIMELINE-01 Part 1: a single bordered, dividered
              "map utility controls" group -- matches the divider pattern
              already used between Disease/Location/Window above, so this
              reads as one deliberate control cluster rather than three
              unexplained icons trailing off the end of the row. */}
          <div
            className="ml-auto flex items-center gap-0.5 rounded-md border border-outline-variant/30 bg-surface-container-lowest/40 p-0.5"
            role="group"
            aria-label="Map utility controls"
          >
            {/* GEO-UI-TIMELINE-01: this control's wording is deliberately
                UNCHANGED from "Fit Sri Lanka" -- traced: `handleFitSriLanka`
                calls `resetView()` with no bounds, which fits the fixed
                `SRI_LANKA_BOUNDS` constant (`MapLibreCanvas.jsx`), never
                the current marker/data extent. That is a deliberate,
                documented choice (GEO33B Section 5): every real Sri Lanka
                LSD record sits in the far north, so fitting to marker
                extent would zoom onto the Jaffna peninsula alone whenever
                a vet clicks a control that says "Sri Lanka". A generic
                "fit the currently visible data" label would describe
                behavior this button does not have -- see the
                pre-implementation report for the full trace. */}
            <button
              type="button"
              onClick={handleFitSriLanka}
              aria-label="Fit Sri Lanka"
              title="Fit Sri Lanka"
              className="flex h-9 w-9 items-center justify-center rounded text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
                fit_screen
              </span>
            </button>
            <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
            {/* GEO-UI-TIMELINE-01: the tooltip now names the vet's real
                district ("Center on Matara") whenever one is known --
                `aria-label` stays the stable, already-tested "Focus My
                District" (screen-reader identity of the control never
                changes), while the hover/focus `title` is the dynamic
                scope label a sighted user actually reads. */}
            <button
              type="button"
              onClick={handleFocusMyDistrict}
              disabled={!myDistrictAvailable}
              aria-label="Focus My District"
              title={
                !myDistrictAvailable
                  ? 'Focus My District (unavailable -- no real farm location yet)'
                  : vetDistrict
                    ? `Center on ${vetDistrict}`
                    : 'Focus My District'
              }
              className="flex h-9 w-9 items-center justify-center rounded text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
                my_location
              </span>
            </button>
            {fullscreenSupported && (
              <>
                <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
                <button
                  type="button"
                  onClick={toggleFullscreen}
                  aria-pressed={isFullscreen}
                  aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
                  title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
                  className={
                    isFullscreen
                      ? 'flex h-9 w-9 items-center justify-center rounded bg-primary/15 text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                      : 'flex h-9 w-9 items-center justify-center rounded text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                  }
                >
                  <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
                    {isFullscreen ? 'fullscreen_exit' : 'fullscreen'}
                  </span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {showDiseaseReadinessWarning && (
        <div className="shrink-0 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
          {showFmdOriginPanel
            ? `${diseaseConfig.label} has no spatial cell/reach/direction model yet -- select a real historical origin below for its scalar spatial score.`
            : `${diseaseConfig.label} analysis is not yet available from the backend (model not API-ready). Select LSD to see real data.`}
        </div>
      )}

      {national.status === NATIONAL_STATUS.ERROR && showHistoricalRecords && (
        // GEO26D Section 8/18: scoped to the historical/scientific layer
        // ONLY -- never worded as "Geospatial data" broadly, since real
        // verified clinical markers (Cases mode) are a separate fetch
        // that keeps working independently of this one failing.
        <div className="flex shrink-0 items-center justify-between gap-3 rounded-full border border-red-400/30 bg-red-400/10 px-3 py-1.5 text-xs text-red-200">
          <span>Scientific/historical layer unavailable. Verified clinical cases are unaffected.</span>
          <button
            type="button"
            onClick={() => setRefreshToken((t) => t + 1)}
            className="shrink-0 rounded border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20"
          >
            Retry
          </button>
        </div>
      )}

      {national.status === NATIONAL_STATUS.EMPTY && showHistoricalRecords && (
        <div className="shrink-0 rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
          No {diseaseConfig.shortLabel} historical sources are available for this selection.
        </div>
      )}

      {ctx.selectedOutbreakId && focus.status === FOCUS_STATUS.ERROR && (
        <div className="shrink-0 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
          Spatial analysis is unavailable for this origin.
        </div>
      )}

      {/* GEO-TRAJECTORY-01: honest per-origin unavailable state -- shown
          only when Trajectory mode is active AND this specific real
          origin's own data genuinely has neither a real direction vector
          on any cell nor a real nominal-reach table, never a silently
          blank layer (mirrors the disease-level disabled reason already
          shown by `ModeToolbar.jsx` for a disease with no model at all). */}
      {trajectoryUnavailableForOrigin && (
        <div className="shrink-0 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
          This model run does not include spread direction or nominal reach for this origin.
        </div>
      )}

      <div
        ref={mapWrapperRef}
        // `shrink-0`, not `flex-1`: a zero flex-basis inside this
        // indefinite-height column ignored the measured `height` below.
        className="relative min-h-[480px] shrink-0 overflow-hidden rounded-[18px] border border-white/10 bg-slate-950 geo-map-card"
        style={{ height: availableMapHeight }}
      >
        {mapUnavailable ? (
          <div className="flex h-full flex-col gap-2 overflow-auto p-3">
            <div className="rounded border border-amber-300/40 bg-amber-400/10 p-2 text-xs text-amber-200">
              The interactive map could not be rendered in this browser. Geographic playback is unavailable. Observed reports remain accessible below; the timeline and monitoring metrics retain their selected dates.
            </div>
            <div className="rounded-lg border border-white/10 bg-slate-900/60 p-3" aria-label="Observed reports when map is unavailable">
              <div className="mb-2 text-xs font-semibold text-slate-200">Observed reports{nationalCases.status === NATIONAL_CASES_STATE.READY ? ` · ${nationalCaseView.counts.inWindow} records · ${nationalCaseView.counts.withoutGps} without GPS` : ' · counts pending'}</div>
              {nationalCases.status !== NATIONAL_CASES_STATE.READY ? <p className="text-xs text-slate-400">{nationalCases.status === NATIONAL_CASES_STATE.LOADING || nationalCases.status === NATIONAL_CASES_STATE.IDLE ? 'Loading authorised case records…' : 'Authorised case records could not be loaded.'}</p> : (
                <ul className="grid max-h-52 gap-1 overflow-y-auto text-xs sm:grid-cols-2">
                  {nationalCaseView.featureCollection.features.map((feature) => <li key={`${feature.properties.recordKey}:${feature.properties.ageClass}`}><button type="button" onClick={() => setSelectedNationalCase(feature.properties)} className="w-full rounded-md border border-white/10 px-2 py-2 text-left text-slate-300 hover:border-primary/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">{feature.properties.district ?? 'District unknown'} · {feature.properties.count} {feature.properties.verificationStatus === 'VERIFIED' ? 'verified' : 'pending'} report{feature.properties.count === 1 ? '' : 's'} · {feature.properties.reportDateKey ?? 'Report date unknown'}</button></li>)}
                </ul>
              )}
            </div>
            {(focusCellFeatures.length > 0 || nationalSourcesFC.features.length > 0) && <details className="rounded-lg border border-white/10 p-2 text-xs text-slate-400"><summary className="cursor-pointer">Historical source/cell preview · static analysis snapshot</summary><MapCanvas cellFeatures={focusCellFeatures} sourceFeatures={nationalSourcesFC.features} /></details>}
          </div>
        ) : (
          <MapLibreCanvas
            ref={mapCanvasRef}
            nationalSources={nationalSourcesFC}
            nationalMarkerShape={diseaseConfig.markerShape}
            cellFeatures={focusCellFeatures}
            selectedOutbreakId={ctx.selectedOutbreakId}
            autoFocusOutbreak={isAutoFocusedOutbreak}
            reachRingCenters={reachRingCenters}
            reachRingRadiusKm={frame?.nominalReachKm ?? 0}
            reduceMotion={reduceMotion}
            operationalFeatures={operationalFeatures}
            showOperationalLayer={showOperationalLayer}
            showRiskLayer={ctx.analysisMode === ANALYSIS_MODE.RISK_ZONES}
            showTrajectoryLayer={showTrajectoryLayer}
            page1ForecastVisualization={page1ForecastVisualization}
            // Model sources/directions belong to Risk Zones and Trajectory only.
            showPage1ForecastLayer={page1ForecastReady && (ctx.analysisMode === ANALYSIS_MODE.RISK_ZONES || ctx.analysisMode === ANALYSIS_MODE.TRAJECTORY)}
            showPage1ForecastRiskZones={page1ForecastReady && ctx.analysisMode === ANALYSIS_MODE.RISK_ZONES}
            showResearchLayers={showResearchLayers}
            stage={stageLayers}
            stageMode={ctx.analysisMode}
            onSelectNationalCase={handleSelectNationalCase}
            onEnvPointSelect={handleEnvPointSelect}
            onSelectRiskCell={(properties) => setSelectedRiskCellId(properties?.cellId ?? null)}
            arrivalHighlightKey={arrivalHighlightKey}
            newlyRevealedKeys={newlyRevealedKeys}
            selectedOperationalKey={operationalPopupCase ? `${operationalPopupCase.farmId}::${operationalPopupCase.disease}` : null}
            districtFeature={districtFeature}
            districtCollection={sriLankaDistricts}
            onSelectSource={handleSelectSource}
            onSelectCell={handleSelectCell}
            onSelectCorridor={(properties) => setSelectedCorridorId(properties?.sourceId ?? null)}
            onHoverCorridor={setHoveredCorridor}
            selectedCorridorSourceId={selectedCorridorId}
            focusedCaseKey={showObservedCaseMarkers ? selectedNationalCase?.recordKey ?? null : null}
            onSelectOperationalCase={handleSelectOperationalCase}
            onMapUnavailable={() => setMapUnavailable(true)}
          />
        )}




        {/* Sits above the bottom timeline card (bottom-7, ~110px tall) so
            the two never overlap. */}
        {clinicalEvents.notifications.length > 0 && (
          <div className="pointer-events-none absolute bottom-[9.5rem] left-4 right-4 sm:right-auto">
            <GeospatialAlertBanner
              notifications={clinicalEvents.notifications}
              onViewUpdate={handleViewClinicalUpdate}
              onDismiss={clinicalEvents.dismiss}
              farmNames={farmNames}
            />
          </div>
        )}

        {/* GEO30A Section 14: Fit Sri Lanka/Fullscreen now live ONLY in
            the top control bar (`handleFitSriLanka`/`toggleFullscreen`
            above) -- no longer duplicated as floating buttons inside the
            map itself. */}

        {/* GEO33B Section 9: the legend is told what is ACTUALLY on the
            map right now -- whether any real verified-clinical marker is
            drawn, whether any national marker genuinely stacks more than
            one real record, and which real marker shape the current
            disease paints -- so it can never key a symbol that isn't
            there. `operationalFeatures` is the exact FeatureCollection
            handed to MapLibre above, so this can't drift from it. */}
        {!mapUnavailable && (
          <PageLegend
            analysisMode={ctx.analysisMode}
            riskTierStats={riskTierStats}
            hasClinicalMarkers={showOperationalLayer && operationalFeatures.features.length > 0}
            hasStackedSources={hasStackedSources}
            nationalMarkerShape={diseaseConfig.markerShape}
            hasReachRing={reachRingCurrentlyVisible}
            // Per-cell gradient arrows are a research layer: keyed only when shown.
            hasDirectionArrows={trajectoryDirectionAvailable && showResearchLayers}
            hasPage1Forecast={page1ForecastReady}
            page1ForecastDateLabel={page1ForecastDateLabel}
            nationalCaseCounts={nationalCaseStatusReady ? nationalCaseCounts : null}
            unmappedRecords={nationalCaseStatusReady ? nationalCaseView.unmappedRecords : []}
            onSelectUnmappedRecord={setSelectedNationalCase}
            hasHistoricalRecords={showHistoricalRecords}
          />
        )}

        <div className="pointer-events-none absolute inset-x-0 top-4 flex justify-center pl-4 pr-14 sm:px-4">
          <ModeToolbar analysisMode={ctx.analysisMode} onSetMode={ctx.setMode} disease={ctx.selectedDisease} clustersAvailable envAvailable={Boolean(storyVetDistrict)} />
        </div>
        {/* Status notices: compact stack top-right (open sea), below the zoom buttons. */}
        <div className="pointer-events-none absolute right-3 top-24 z-10 flex w-[21rem] max-w-[calc(100%-1.5rem)] justify-end">
          <MapStatusStack
            items={[
              // The national research origins only feed the Retrospective view:
              // their background load is not announced over the live map.
              showHistoricalRecords && national.status === NATIONAL_STATUS.LOADING && {
                key: 'national-loading',
                tone: 'loading',
                text: hasEverLoadedNationalRef.current ? 'Updating…' : 'Loading historical research records…',
              },
              showObservedCaseMarkers && nationalCases.status === NATIONAL_CASES_STATE.ERROR && {
                key: 'national-cases-error',
                tone: 'warn',
                text: nationalCases.data
                  ? `Could not refresh case records -- showing the last update (${new Date(nationalCases.lastSyncedAt).toLocaleTimeString('en-GB', { timeZone: 'Asia/Colombo', hour: '2-digit', minute: '2-digit' })}). Retrying with the next sync.`
                  : 'Countrywide case records unavailable right now (retrying with the next sync).',
              },
              showOperationalLayer && recentUnmappedNotice && { key: 'recent-unmapped', tone: 'warn', text: recentUnmappedNotice },
              spatialTimelineNotice && { key: 'timeline-error', tone: 'warn', text: spatialTimelineNotice },
            ]}
          />
        </div>

        {showFmdOriginPanel && (
          <div className="pointer-events-none absolute left-4 top-20">
            <FmdOriginPanel
              origins={national.originsWithSources}
              selectedOriginId={ctx.selectedOutbreakId}
              onSelect={(outbreakId) => {
                userPickedOutbreakRef.current = true
                setIsAutoFocusedOutbreak(false)
                if (outbreakId) ctx.selectOutbreak(outbreakId)
                else ctx.clearOutbreakSelection()
              }}
              risk={fmdRisk}
            />
          </div>
        )}

        {popupFeature && (
          <div className="pointer-events-none absolute bottom-28 left-4">
            <SourcePopup feature={popupFeature} onClose={() => setPopupFeature(null)} onViewSpatialContext={() => setPopupFeature(null)} />
          </div>
        )}

        {operationalPopupCase && (
          <div className="pointer-events-none absolute left-4 top-20">
            <OperationalContextPopup clinicalContext={operationalFarmGroupsByKey.get(`${operationalPopupCase.farmId}::${operationalPopupCase.disease}`) ?? operationalPopupCase} onClose={() => setOperationalPopupCase(null)} />
          </div>
        )}

        {/* Left, below the mode toolbar: the right side holds the zoom
            controls and the map legend (`PageLegend`, bottom-28 right-4),
            which a pinned corridor popup used to cover. */}
        {corridorTooltip && (
          <div className="pointer-events-none absolute left-4 top-20">
            <CorridorPopup
              corridor={corridorTooltip}
              cluster={selectedCorridor ? selectedCaseCluster : null}
              risk={selectedCorridor ? selectedCaseRisk : null}
              pinned={Boolean(selectedCorridor)}
              onClose={() => {
                setSelectedCorridorId(null)
                setHoveredCorridor(null)
              }}
            />
          </div>
        )}

        <div className="pointer-events-none absolute right-16 top-4 z-20">
          <NewCaseToasts alerts={newCaseAlerts.alerts} onView={handleViewNewCase} onDismiss={newCaseAlerts.dismiss} />
        </div>

        {/* Env with a playable timeline: the observed values for the selected
            day sit beside the map; the dock below drives the date. */}
        {ctx.analysisMode === ANALYSIS_MODE.ENV && (
          <div className="pointer-events-auto absolute left-4 top-20 z-10 max-h-[70%] w-[20rem] max-w-[calc(100%-2rem)] overflow-y-auto rounded-xl border border-white/10 bg-slate-900/95 p-3 shadow-xl">
            <WeatherForecastStrip
              district={storyVetDistrict}
              areaLabel={envPoint ? [envPoint.place ? `near ${envPoint.place}` : `${envPoint.point[1].toFixed(3)}, ${envPoint.point[0].toFixed(3)}`, envPoint.district].filter(Boolean).join(' · ') : null}
              pointMode={Boolean(envPoint)}
              onClearPoint={() => setEnvPoint(null)}
              dates={envDates}
              selectedDate={environmentDate}
              days={districtForecast.days}
              status={districtForecast.status}
              fetchedAt={districtForecast.fetchedAt}
              pointCount={districtForecast.pointCount}
              todayKey={todayKey}
              onSelectIndex={page1ForecastAvailable ? handleSelectPage1ForecastIndex : setEnvDayIndex}
            />
            {!envForecastDay && (
              <div className="mt-2 border-t border-white/10 pt-2">
                <Era5Observations
                  state={environmentObservations}
                  asOf={environmentDate}
                  district={storyVetDistrict}
                  unavailableText={!storyVetDistrict ? 'An authorised district must be resolved before loading its environmental observations.' : environmentDateInFuture ? `No observed weather exists yet for ${formatDisplayDate(environmentDate)}.` : null}
                />
              </div>
            )}
          </div>
        )}

        {selectedNationalCase && showObservedCaseMarkers && (
          <div className="pointer-events-none absolute left-4 top-20">
            <NationalCaseCard record={selectedNationalCase} ageReferenceLabel={caseAgeRef.label} onClose={() => { setSelectedNationalCase(null); setSelectedCorridorId(null) }} />
          </div>
        )}

        {selectedRiskCell && !selectedNationalCase && ctx.analysisMode === ANALYSIS_MODE.RISK_ZONES && (
          <div className="pointer-events-none absolute left-4 top-20">
            <RiskCellCard cell={selectedRiskCell} story={spatialStory} onClose={() => setSelectedRiskCellId(null)} />
          </div>
        )}





        {selectedCellFeature && (
          <div className="pointer-events-none absolute bottom-28 right-4">
            <CellPopup
              cell={selectedCellFeature}
              dayIndex={ctx.selectedForecastDay}
              dayDate={frame ? formatDisplayDate(frame.actualDate) : undefined}
              onClose={() => setSelectedCellFeature(null)}
            />
          </div>
        )}

        {/* GEO31A Section 5/7/13/18: exactly ONE bottom timeline/status
            surface at a time, chosen by ANALYSIS MODE only -- never by
            location/district scope, never by how many real events/frames
            currently exist (both controls handle their own zero/one-frame
            honest states internally, Section 5/12, rather than this page
            deciding to hide either one). */}
        {/* GEO33B Section 16: raised from `bottom-4` to `bottom-7`. MapLibre's
            attribution control is now docked bottom-LEFT
            (`MapLibreCanvas.jsx`) and occupies roughly the lowest 24px of
            the card. At >=768px viewports this centred, `max-w-3xl` card
            never reaches that far left anyway, but below that width it
            spans edge-to-edge and did sit on top of it. A ~12px clearance
            removes the collision at every width without changing the
            control's own size, and stays well inside the 110px bottom
            camera padding that already reserves room for this lane. */}
        <div className="pointer-events-none absolute inset-x-0 bottom-7 flex justify-center px-4">
          {/* Cases mode never offers model (future) playback: only the observed
              replay of real verification dates below. */}
          {ctx.analysisMode === ANALYSIS_MODE.ENV && !page1ForecastAvailable ? null : ctx.analysisMode === ANALYSIS_MODE.CLUSTERS ? (
            <div className="pointer-events-auto w-full max-w-3xl rounded-xl border border-violet-400/30 bg-[#0e1511]/[0.92] px-4 py-2.5 text-[11px] text-slate-200 shadow-lg" role="status" aria-label="ST-DBSCAN clusters">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded border border-amber-300/50 px-1.5 text-[9px] font-bold uppercase tracking-wide text-amber-200">Exploratory</span>
                <span className="font-semibold text-violet-200">ST-DBSCAN space-time clusters</span>
                {stClusters.data && <span>{stClusters.data.cluster_count} cluster{stClusters.data.cluster_count === 1 ? '' : 's'} · {stClusters.data.noise_count} noise · {stClusters.data.input.operational_case_points} case reports ({stClusters.data.input.distinct_operational_farms} farms) · {stClusters.data.as_of}</span>}
                {stClusters.status === 'loading' && <span>Computing...</span>}
                {stClusters.status === 'error' && <span>{stClusters.errorStatus === 'SESSION_REQUIRED' ? 'Sign in to load cluster data.' : stClusters.errorStatus === 'FORBIDDEN' ? 'Veterinarian access is required.' : stClusters.errorStatus === 'INVALID_RESPONSE' ? 'Cluster response could not be parsed.' : 'Cluster calculation unavailable: request failed.'}</span>}
              </div>
              {stClusters.data && (
                <div className="mt-1 leading-snug text-slate-400">
                  {stClusters.data.clusters.map((c) => `${c.member_count} reports from ${c.distinct_farm_or_support_count} farms, ${c.start_date} to ${c.end_date}`).join(' · ') || (stClusters.data.status === 'NO_ELIGIBLE_POINTS' ? 'No eligible observed records for this analysis date.' : 'Eligible records were evaluated; no cluster met the configured space-time and support thresholds.')}
                  {' '}Clusters describe observed records at the analysis date; they do not move or create future cases during reach playback.
                  {' '}Parameters ε<sub>s</sub>={stClusters.data.parameters.eps_space_km} km, ε<sub>t</sub>={stClusters.data.parameters.eps_time_days} d, min farms={stClusters.data.parameters.min_core_supports} (unfrozen development candidate). Descriptive grouping only -- not a validated outbreak chain or transmission evidence.
                </div>
              )}
            </div>
          ) : page1ForecastAvailable && !showOperationalLayer && (ctx.analysisMode === ANALYSIS_MODE.RISK_ZONES || ctx.analysisMode === ANALYSIS_MODE.TRAJECTORY || ctx.analysisMode === ANALYSIS_MODE.ENV) ? (
            <TimelineControl
              presentationDates={timelineFrameDates}
              activeIndex={page1ForecastActiveIndex}
              isPlaybackActive={isPage1ForecastPlaying}
              onSelectDay={handleSelectPage1ForecastIndex}
              onPlay={handlePlayPage1Forecast}
              onPause={() => setIsPage1ForecastPlaying(false)}
              onPrev={() => handleSelectPage1ForecastIndex(page1ForecastActiveIndex - 1)}
              onNext={() => handleSelectPage1ForecastIndex(page1ForecastActiveIndex + 1)}
              reduceMotion={reduceMotion}
              playbackSpeed={playbackSpeed}
              onChangeSpeed={setPlaybackSpeed}
              datasetLabel="Reach horizon"
              statusLabel={[page1HorizonLabel, `${basisOption.shortLabel} · as of ${formatDisplayDate(timelineSnapshot.as_of)}`].filter(Boolean).join(' · ')}
              plateauLabel={page1PlateauNote}
              isUpdating={isPage1ForecastUpdating || spatialTimeline.status === SPATIAL_TIMELINE_STATE.LOADING}
            />
          ) : showOperationalLayer ? null : (
            spatialTimeline.status === SPATIAL_TIMELINE_STATE.READY || spatialTimeline.status === SPATIAL_TIMELINE_STATE.ERROR ? (
              <TimelineChooserDock
                title={timelineEmptyReason.title}
                body={timelineEmptyReason.body}
                options={timelineEmptyReason.canSwitchBasis ? basisOptions : []}
                currentId={basisOption.id}
                onChoose={setAnalysisBasis}
              />
            ) : null
          )}
        </div>
      </div>
      <div className="shrink-0">
        <SpatialEvidencePanel timeline={timelineSnapshot} diseaseShortLabel={diseaseConfig.shortLabel} />
      </div>
    </div>
  )
}
