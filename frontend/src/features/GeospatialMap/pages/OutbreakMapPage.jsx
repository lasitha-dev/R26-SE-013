import React, { useEffect, useMemo, useRef, useState } from 'react'

import { getOutbreakAdapter } from '../adapters'
import { formatDisplayDate } from '../adapters/forecastDate'
import DiseaseSelector from '../components/DiseaseSelector'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import MapCanvas from '../components/MapCanvas'
import MapLibreCanvas from '../components/MapLibreCanvas'
import { buildNationalSourcesFeatureCollection, computeRiskColorStats } from '../components/mapLibreAdapter'
import ModeToolbar from '../components/ModeToolbar'
import OperationalContextPopup from '../components/OperationalContextPopup'
import { buildOperationalMarkerFeatureCollection } from '../components/operationalMarkerLayer'
import FmdOriginPanel from '../components/FmdOriginPanel'
import OperationalStatusChip from '../components/OperationalStatusChip'
import PageLegend from '../components/PageLegend'
import SnapshotStatusChip, { SNAPSHOT_STATUS } from '../components/SnapshotStatusChip'
import SourcePopup from '../components/SourcePopup'
import TimelineControl from '../components/TimelineControl'
import { useGeospatialContext } from '../context/GeospatialContext'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { useFmdOriginRisk } from '../context/useFmdOriginRisk'
import { NATIONAL_STATUS, useNationalOutbreaks } from '../context/useNationalOutbreaks'
import { useOperationalContext } from '../context/useOperationalContext'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { FOCUS_STATUS, deriveAvailableForecastDays, useSelectedOutbreakFrames } from '../context/useSelectedOutbreakFrames'
import { CAPABILITY, getDiseaseConfig, hasCapability, isDiseaseReady } from '../disease/diseaseRegistry'
import { PAGE_TAGLINE, PAGE_TITLE } from '../semanticLabels'

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

  // GEO-LIVE-05 Section 9: a relevant verified-clinical live event never
  // mutates scientific/marker state directly -- it only invalidates/
  // refetches the authoritative operational-context snapshot (the same
  // path `OperationalStatusChip`'s manual refresh already uses), so the
  // marker layer above stays honest and never fabricates a value.
  const clinicalEvents = useVerifiedClinicalEvents()
  const lastRefetchedEventIdRef = useRef(null)
  useEffect(() => {
    const eventId = clinicalEvents.lastEvent?.event_id
    if (!eventId || eventId === lastRefetchedEventIdRef.current) return
    lastRefetchedEventIdRef.current = eventId
    operational.refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinicalEvents.lastEvent])

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
    clinicalEvents.dismiss(event.event_id)
  }

  // Section 18: disease filtering happens here, not in the hook/adapter
  // (which stay disease-agnostic) -- selecting FMD must never imply the
  // FMD scientific model is ready (the existing `!diseaseReady` banner
  // below is untouched), it only decides which already-verified
  // operational markers, if any, are relevant to show.
  const operationalContextsForDisease = useMemo(
    () => (operational.data?.clinicalContexts ?? []).filter((c) => c.disease === ctx.selectedDisease),
    [operational.data, ctx.selectedDisease],
  )
  const operationalFeatures = useMemo(
    () => buildOperationalMarkerFeatureCollection(operationalContextsForDisease),
    [operationalContextsForDisease],
  )
  // Section 10: Cases mode only -- never implied part of Risk Zones/
  // Clusters/Trajectory/Env.
  const showOperationalLayer = ctx.analysisMode === ANALYSIS_MODE.CASES

  // Section 11/12: shows the compact operational popup ONLY -- never
  // calls ctx.selectOutbreak, never fetches analysis summary/cells/
  // sources, never starts timeline playback, never draws a reach ring.
  function handleSelectOperationalCase(properties) {
    setOperationalPopupCase(properties)
  }

  const nationalSourcesFC = useMemo(
    () => buildNationalSourcesFeatureCollection(national.originsWithSources),
    [national.originsWithSources],
  )

  const riskStats = useMemo(
    () => computeRiskColorStats(focus.status === FOCUS_STATUS.READY ? focus.cells : []),
    [focus.status, focus.cells],
  )

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

  // Playback: advances one real day roughly every 1.4s while the vet has
  // explicitly pressed Play. Driven by `requestAnimationFrame`, never
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
    const tick = (now) => {
      if (now - playbackLastTickRef.current >= 1400) {
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
  }, [ctx.isPlaybackActive])

  // Marker click triggers full focus mode directly (plan Section 20:
  // pause playback / select / one smooth fit / dim others / fetch real
  // summary+cells+sources / reset D0 / expand timeline -- all driven by
  // `ctx.selectOutbreak` + the effects above/in MapLibreCanvas), and
  // shows the compact popup (plan Section 19) alongside it as the
  // small info card for the exact source that was clicked.
  function handleSelectSource(outbreakId, sourceId) {
    const feature = nationalSourcesFC.features.find((f) => f.properties.source_id === sourceId)
    setPopupFeature(feature ?? null)
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

  function handleSelectCell(feature) {
    // Focused-view cell click (existing Checkpoint 11B behaviour,
    // preserved) -- not the national source-selection path.
    setPopupFeature(null)
    // eslint-disable-next-line no-console
    console.debug('cell selected', feature.properties)
  }

  const snapshotStatus =
    national.status === NATIONAL_STATUS.LOADING || focus.status === FOCUS_STATUS.LOADING
      ? SNAPSHOT_STATUS.LOADING
      : national.status === NATIONAL_STATUS.ERROR || focus.status === FOCUS_STATUS.ERROR
        ? SNAPSHOT_STATUS.UNAVAILABLE
        : SNAPSHOT_STATUS.CONNECTED

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex shrink-0 flex-col gap-2">
        <div>
          <h2 className="text-lg font-semibold text-white">{PAGE_TITLE}</h2>
          <p className="text-xs text-slate-400">{PAGE_TAGLINE}</p>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <DiseaseSelector selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
            <span className="rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-300">{COUNTRY} Overview</span>
          </div>
          <div className="flex items-center gap-2">
            <SnapshotStatusChip
              status={snapshotStatus}
              asOfDate={frame ? formatDisplayDate(frame.actualDate) : undefined}
              onCheckForNewer={() => setRefreshToken((t) => t + 1)}
            />
            <OperationalStatusChip state={operational.state} lastRefreshedAt={operational.lastRefreshedAt} onRefresh={operational.refresh} />
          </div>
        </div>
      </div>

      {!diseaseReady && (
        <div className="shrink-0 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
          {showFmdOriginPanel
            ? `${diseaseConfig.label} has no spatial cell/reach/direction model yet -- select a real historical origin below for its scalar spatial score.`
            : `${diseaseConfig.label} analysis is not yet available from the backend (model not API-ready). Select LSD to see real data.`}
        </div>
      )}

      {national.status === NATIONAL_STATUS.ERROR && (
        <div className="flex shrink-0 items-center justify-between gap-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
          <span>Geospatial data is temporarily unavailable.</span>
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
        className="relative min-h-[650px] flex-1 overflow-hidden rounded-xl border border-white/10 bg-slate-950"
        style={{ height: 'calc(100vh - 220px)' }}
      >
        {mapUnavailable ? (
          <div className="flex h-full flex-col gap-2 overflow-auto p-3">
            <div className="rounded border border-amber-300/40 bg-amber-400/10 p-2 text-xs text-amber-200">
              The interactive map could not be rendered in this browser. Real source/cell data is still shown below.
            </div>
            <MapCanvas cellFeatures={focus.cells ?? []} sourceFeatures={nationalSourcesFC.features} />
          </div>
        ) : (
          <MapLibreCanvas
            ref={mapCanvasRef}
            nationalSources={nationalSourcesFC}
            nationalMarkerShape={diseaseConfig.markerShape}
            cellFeatures={focus.status === FOCUS_STATUS.READY ? focus.cells : []}
            selectedOutbreakId={ctx.selectedOutbreakId}
            reachRingCenters={reachRingCenters}
            reachRingRadiusKm={frame?.nominalReachKm ?? 0}
            reduceMotion={reduceMotion}
            operationalFeatures={operationalFeatures}
            showOperationalLayer={showOperationalLayer}
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

        {clinicalEvents.notifications.length > 0 && (
          <div className="pointer-events-none absolute bottom-24 left-4">
            <GeospatialAlertBanner
              notifications={clinicalEvents.notifications}
              onViewUpdate={handleViewClinicalUpdate}
              onDismiss={clinicalEvents.dismiss}
            />
          </div>
        )}

        {!mapUnavailable && (
          <div className="pointer-events-auto absolute right-4 top-20 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => mapCanvasRef.current?.resetView()}
              aria-label={`Reset map view to ${COUNTRY} overview`}
              title="Reset view"
              className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-slate-900/80 text-sm text-slate-300 shadow-lg backdrop-blur hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              &#8634;
            </button>
            {fullscreenSupported && (
              <button
                type="button"
                onClick={toggleFullscreen}
                aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
                title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-slate-900/80 text-sm text-slate-300 shadow-lg backdrop-blur hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              >
                {isFullscreen ? '⤡' : '⤢'}
              </button>
            )}
          </div>
        )}

        {!mapUnavailable && <PageLegend analysisMode={ctx.analysisMode} riskStats={riskStats} />}

        <div className="pointer-events-none absolute inset-x-0 top-4 flex justify-center px-4">
          <ModeToolbar analysisMode={ctx.analysisMode} onSetMode={ctx.setMode} disease={ctx.selectedDisease} />
        </div>

        {showFmdOriginPanel && (
          <div className="pointer-events-none absolute left-4 top-20">
            <FmdOriginPanel
              origins={national.originsWithSources}
              selectedOriginId={ctx.selectedOutbreakId}
              onSelect={(outbreakId) => (outbreakId ? ctx.selectOutbreak(outbreakId) : ctx.clearOutbreakSelection())}
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
            <OperationalContextPopup clinicalContext={operationalPopupCase} onClose={() => setOperationalPopupCase(null)} />
          </div>
        )}

        <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center px-4">
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
          />
        </div>

        {focus.status === FOCUS_STATUS.READY && ctx.selectedOutbreakId && ctx.availableForecastFrames.length <= 1 && (
          <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center px-4">
            <div className="pointer-events-auto rounded-lg border border-white/10 bg-slate-900/85 px-3 py-2 text-xs text-slate-400 shadow-lg backdrop-blur">
              Temporal reach context is unavailable for this origin.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
