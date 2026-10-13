import React, { useEffect, useMemo, useRef, useState } from 'react'

import { getOutbreakAdapter } from '../adapters'
import { computeFeatureBounds } from '../adapters/districtGeometry'
import { formatDisplayDate } from '../adapters/forecastDate'
import { GEO_TIMING, markTiming } from '../adapters/loadTiming'
import { selectMostRecentOrigin } from '../adapters/mostRecentOrigin'
import { aggregateNationalSourcesByLocation } from '../adapters/nationalSourcePresentation'
import { isWithinObservationWindow, DEFAULT_OBSERVATION_WINDOW_DAYS, OBSERVATION_WINDOW_OPTIONS } from '../adapters/observationWindow'
import { buildObservedReplayDates, filterContextsByReplayDate } from '../adapters/observedReplay'
import { classifyOperationalCaseChanges, verificationByCaseId } from '../adapters/operationalCaseReconciliation'
import { aggregateClinicalContextsByFarm, operationalFarmGroupsSignature } from '../adapters/operationalFarmAggregation'
import CellPopup from '../components/CellPopup'
import DiseaseSelector from '../components/DiseaseSelector'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import LocationScopeSelect, { LOCATION_SCOPE } from '../components/LocationScopeSelect'
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
import { useOperationalContext } from '../context/useOperationalContext'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { FOCUS_STATUS, deriveAvailableForecastDays, useSelectedOutbreakFrames } from '../context/useSelectedOutbreakFrames'
import { CAPABILITY, getDiseaseConfig, hasCapability, isDiseaseReady } from '../disease/diseaseRegistry'
import { LABEL_FORECAST_RISK_TIMELINE, LABEL_NO_VERIFIED_CASES_IN_WINDOW, LABEL_OBSERVED_CASES_TIMELINE, PAGE_TAGLINE, PAGE_TITLE } from '../semanticLabels'

const COUNTRY = 'Sri Lanka'

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
  const [observationWindowDays, setObservationWindowDays] = useState(DEFAULT_OBSERVATION_WINDOW_DAYS)

  // GEO26B Section 15: "Sri Lanka" vs "My assigned farms" camera scope.
  // REAL_DISTRICT_GEOMETRY_BLOCKED -- no Sri Lanka ADM2 boundary dataset
  // exists in this repo, so "My assigned farms" fits the vet's own real,
  // authorized farm bounds rather than drawing a fabricated polygon.
  const [locationScope, setLocationScope] = useState(LOCATION_SCOPE.SRI_LANKA)
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
  const operationalContextsForDisease = useMemo(
    () =>
      (operational.data?.surveillanceContexts ?? [])
        .filter((c) => c.disease === ctx.selectedDisease)
        .filter((c) => isWithinObservationWindow(c.verificationTime, observationWindowDays)),
    [operational.data, ctx.selectedDisease, observationWindowDays],
  )

  // GEO31A Section 5/6: Cases-mode Observed Replay -- real dates only,
  // derived from `operationalContextsForDisease`'s own real verification
  // timestamps (never fabricated). `observedReplayDateKey === null` means
  // "at latest" (every real event currently in the window is shown,
  // identical to this page's pre-GEO31A behavior); scrubbing/playing back
  // to an earlier real date temporarily hides events verified after it.
  const observedReplayDates = useMemo(() => buildObservedReplayDates(operationalContextsForDisease), [operationalContextsForDisease])
  const [observedReplayDateKey, setObservedReplayDateKey] = useState(null)
  const [isObservedPlaybackActive, setIsObservedPlaybackActive] = useState(false)
  // A disease/window change can invalidate the current scrub position
  // (Section 7/13: this must NEVER be derived from location/district
  // scope, only disease+window) -- reset to "at latest" rather than
  // silently keep pointing at a date that may no longer be in range.
  useEffect(() => {
    setObservedReplayDateKey(null)
    setIsObservedPlaybackActive(false)
  }, [ctx.selectedDisease, observationWindowDays])

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
    const signature = operationalFarmGroupsSignature(operationalFarmGroups)
    if (stableOperationalFeaturesRef.current && operationalFeaturesSignatureRef.current === signature) {
      return stableOperationalFeaturesRef.current
    }
    const next = buildOperationalMarkerFeatureCollection(operationalFarmGroups)
    operationalFeaturesSignatureRef.current = signature
    stableOperationalFeaturesRef.current = next
    return next
  }, [operationalFarmGroups])
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
  const { feature: districtFeature } = useDistrictGeometry(operational.data?.vetDistrict)

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
  useEffect(() => {
    if (districtAutoFocusDoneRef.current) return undefined
    if (!myDistrictAvailable) return undefined
    let frame
    const tryFocus = () => {
      if (districtAutoFocusDoneRef.current) return
      if (mapCanvasRef.current?.isReady?.()) {
        handleFocusMyDistrict()
      } else {
        frame = requestAnimationFrame(tryFocus)
      }
    }
    tryFocus()
    return () => {
      if (frame) cancelAnimationFrame(frame)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myDistrictAvailable])

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
  const nationalSourcesFC = useMemo(
    () => aggregateNationalSourcesByLocation(mergedNationalSourcesFC),
    [mergedNationalSourcesFC],
  )

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
  const riskTierStats = useMemo(() => computeRiskTierStats(focusCellFeatures), [focusCellFeatures])

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

  const reachRingCenters = useMemo(() => {
    if (ctx.analysisMode !== ANALYSIS_MODE.RISK_ZONES) return null
    return focus.sources?.features?.map((f) => f.geometry.coordinates) ?? null
  }, [ctx.analysisMode, focus.sources])

  // GEO-VISUAL-POLISH-01 Section 9: a single shared playback-speed
  // multiplier for BOTH timelines below (0.5x/1x/2x) -- speed changes
  // TIMING only, never which real day/date advances to, so one shared
  // value is honest for both the scientific and the observed-replay
  // clock rather than needing two independent controls that could drift.
  const [playbackSpeed, setPlaybackSpeed] = useState(1)

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
        {districtKnown && (
          <div>
            {vetDistrict ? (
              <span className="inline-flex items-center rounded-md border border-primary/20 bg-primary/10 px-2 py-1 text-xs font-bold uppercase tracking-wide text-primary">
                MY DISTRICT · {vetDistrict.toUpperCase()}
              </span>
            ) : (
              <span className="inline-flex items-center rounded-md border border-outline-variant/30 bg-surface-container-high/40 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-on-surface-variant/60">
                DISTRICT NOT AVAILABLE
              </span>
            )}
          </div>
        )}
        <div className="flex items-start justify-between gap-3">
          {/* GEO-STITCH-OUTBREAK-MAP-UI-10B: brings this page's header in
              line with `MyAreaPage.jsx`/`AnalysisTrendsPage.jsx`'s own
              title+tagline pattern -- `PAGE_TAGLINE` already existed
              (wording-firewall tested, `semanticLabels.test.js`) but was
              never rendered here, so Outbreak Map was the one Geospatial
              page missing the secondary descriptive line every sibling
              page already has. */}
          <div>
            <h2 className="text-[28px] font-bold leading-[1.15] text-on-surface">{PAGE_TITLE}</h2>
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
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-outline-variant/30 bg-surface-container/60 px-4 py-2">
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

      {national.status === NATIONAL_STATUS.ERROR && (
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

      {national.status === NATIONAL_STATUS.EMPTY && (
        <div className="shrink-0 rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
          No {diseaseConfig.shortLabel} historical sources are available for this selection.
        </div>
      )}

      {ctx.selectedOutbreakId && focus.status === FOCUS_STATUS.ERROR && (
        <div className="shrink-0 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
          Spatial analysis is unavailable for this origin.
        </div>
      )}

      <div
        ref={mapWrapperRef}
        className="relative min-h-[480px] flex-1 overflow-hidden rounded-xl border border-white/10 bg-slate-950"
        style={{ height: availableMapHeight }}
      >
        {mapUnavailable ? (
          <div className="flex h-full flex-col gap-2 overflow-auto p-3">
            <div className="rounded border border-amber-300/40 bg-amber-400/10 p-2 text-xs text-amber-200">
              The interactive map could not be rendered in this browser. Real source/cell data is still shown below.
            </div>
            <MapCanvas cellFeatures={focusCellFeatures} sourceFeatures={nationalSourcesFC.features} />
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
            arrivalHighlightKey={arrivalHighlightKey}
            newlyRevealedKeys={newlyRevealedKeys}
            selectedOperationalKey={operationalPopupCase ? `${operationalPopupCase.farmId}::${operationalPopupCase.disease}` : null}
            districtFeature={districtFeature}
            onSelectSource={handleSelectSource}
            onSelectCell={handleSelectCell}
            onSelectOperationalCase={handleSelectOperationalCase}
            onMapUnavailable={() => setMapUnavailable(true)}
          />
        )}

        {!ctx.selectedOutbreakId && national.status === NATIONAL_STATUS.READY && (
          <div className="pointer-events-none absolute inset-x-0 top-16 flex justify-center px-4">
            <div className="rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-400 backdrop-blur">
              Select a historical outbreak origin to inspect its spatial context.
            </div>
          </div>
        )}

        {/* GEO-VIVA-TOP-UI-AND-INTERACTION-LATENCY-04: a real disease
            switch (or a manual "check for newer snapshot") clears the
            national historical layer while its real re-fetch is in
            flight (`useNationalOutbreaks.js` -- deliberately locked by
            FMD-10C1's own test so a stale LSD marker is never briefly
            shown under FMD's shape/label, or vice versa). Without this,
            that honest blank read as "did my click even register?" --
            this is presentation-only, subtle, non-blocking feedback that
            an update is genuinely in progress; it never changes what
            data eventually renders or how long the real fetch takes. */}
        {national.status === NATIONAL_STATUS.LOADING && (
          <div className="pointer-events-none absolute inset-x-0 top-16 flex justify-center px-4">
            <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-400 backdrop-blur">
              <span aria-hidden="true" className={reduceMotion ? 'h-1.5 w-1.5 rounded-full bg-primary' : 'h-1.5 w-1.5 animate-pulse rounded-full bg-primary'} />
              Updating…
            </div>
          </div>
        )}

        {showNoVerifiedCasesEmptyState && (
          // GEO30A Section 13: zero local cases is a valid surveillance
          // result, not an error -- a small compact chip, never a
          // map-covering message, and never implying anything about the
          // rest of Sri Lanka (which stays visible on the scientific
          // layer regardless).
          <div className="pointer-events-none absolute inset-x-0 top-16 flex justify-center px-4">
            <div
              className="pointer-events-auto rounded-full border border-white/10 bg-slate-900/85 px-3 py-1.5 text-xs text-slate-300 shadow-lg backdrop-blur"
              title={LABEL_NO_VERIFIED_CASES_IN_WINDOW}
            >
              <span aria-hidden="true" className="mr-1 text-emerald-400">
                ✓
              </span>
              No verified {diseaseConfig.shortLabel} cases in{' '}
              {vetDistrict ? `My District${vetDistrict ? ` · ${vetDistrict}` : ''}` : 'the selected scope'} ·{' '}
              {(OBSERVATION_WINDOW_OPTIONS.find((o) => o.days === observationWindowDays)?.label ?? 'selected window').toLowerCase()}
            </div>
          </div>
        )}

        {clinicalEvents.notifications.length > 0 && (
          <div className="pointer-events-none absolute bottom-24 left-4">
            <GeospatialAlertBanner
              notifications={clinicalEvents.notifications}
              onViewUpdate={handleViewClinicalUpdate}
              onDismiss={clinicalEvents.dismiss}
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
          />
        )}

        <div className="pointer-events-none absolute inset-x-0 top-4 flex justify-center px-4">
          <ModeToolbar analysisMode={ctx.analysisMode} onSetMode={ctx.setMode} disease={ctx.selectedDisease} />
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
          {showOperationalLayer ? (
            <ObservedTimelineControl
              dates={observedReplayDates}
              selectedDateKey={observedReplayDateKey}
              isPlaybackActive={isObservedPlaybackActive}
              onSelectDate={handleSelectObservedDate}
              onPlay={handlePlayObservedReplay}
              onPause={handlePauseObservedReplay}
              onPrev={handleObservedPrev}
              onNext={handleObservedNext}
              windowLabel={(OBSERVATION_WINDOW_OPTIONS.find((o) => o.days === observationWindowDays)?.label ?? 'selected window')}
              emptyStateText={`No verified ${diseaseConfig.shortLabel} cases in ${vetDistrict ? `My District · ${vetDistrict}` : 'the selected scope'}`}
              reduceMotion={reduceMotion}
              playbackSpeed={playbackSpeed}
              onChangeSpeed={setPlaybackSpeed}
              // GEO33B Section 10: stated EXPLICITLY at the call site
              // rather than left to the component default, so it is
              // obvious from this page which real dataset the Cases-mode
              // timeline replays. These dates come from
              // `observedReplayDates`, built only from real verified
              // clinical `verificationTime` values -- never from the
              // national historical/scientific layer, which has no date
              // field in its API response at all and therefore has no
              // replay here. The two are never mixed in one timeline.
              datasetLabel={LABEL_OBSERVED_CASES_TIMELINE}
            />
          ) : (
            <TimelineControl
              availableDays={ctx.availableForecastFrames}
              selectedDay={ctx.selectedForecastDay}
              t0={focus.summary?.analysis_metadata?.t0}
              isPlaybackActive={ctx.isPlaybackActive}
              onSelectDay={handleSelectDay}
              onPlay={ctx.play}
              onPause={ctx.pause}
              onPrev={() => handleSelectDay(ctx.availableForecastFrames[Math.max(0, ctx.availableForecastFrames.indexOf(ctx.selectedForecastDay) - 1)])}
              onNext={() => handleSelectDay(ctx.availableForecastFrames[Math.min(ctx.availableForecastFrames.length - 1, ctx.availableForecastFrames.indexOf(ctx.selectedForecastDay) + 1)])}
              reduceMotion={reduceMotion}
              playbackSpeed={playbackSpeed}
              onChangeSpeed={setPlaybackSpeed}
              isLoadingFocus={focus.status === FOCUS_STATUS.LOADING}
              // GEO-UI-TIMELINE-01: stated explicitly at the call site, same
              // reasoning as `ObservedTimelineControl`'s `datasetLabel`
              // just below -- this is the ONLY mode that currently ever
              // mounts `TimelineControl` (Clusters/Trajectory/Env stay
              // honestly disabled in `ModeToolbar.jsx`), so "Forecast risk"
              // is never a guess about which real dataset is being shown.
              datasetLabel={LABEL_FORECAST_RISK_TIMELINE}
            />
          )}
        </div>
      </div>
    </div>
  )
}
