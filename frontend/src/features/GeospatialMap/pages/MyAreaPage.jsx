import React, { useEffect, useMemo, useRef, useState } from 'react'

import { isEventRelevantToMyArea } from '../adapters/operationalEventRelevance'
import DiseaseSelector from '../components/DiseaseSelector'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import MyAreaIntelligencePanel from '../components/MyAreaIntelligencePanel'
import MyAreaKpiCards from '../components/MyAreaKpiCards'
import MyAreaMapCanvas from '../components/MyAreaMapCanvas'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import MyAreaTemporalOutlook from '../components/MyAreaTemporalOutlook'
import OperationalStatusChip from '../components/OperationalStatusChip'
import { useDistrictGeometry } from '../context/useDistrictGeometry'
import { useGeospatialContext } from '../context/GeospatialContext'
import { useMyAreaContext, MY_AREA_REQUEST_STATE } from '../context/useMyAreaContext'
import { NATIONAL_STATUS, useNationalOutbreaks } from '../context/useNationalOutbreaks'
import { useOperationalContext } from '../context/useOperationalContext'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { FOCUS_STATUS, deriveAvailableForecastDays, useSelectedOutbreakFrames } from '../context/useSelectedOutbreakFrames'
import { CAPABILITY, getDiseaseConfig, hasCapability, isDiseaseReady } from '../disease/diseaseRegistry'
import { MY_AREA_FETCH_STATUS } from '../api/myAreaApi'
import {
  LABEL_MY_AREA_AREA_NOT_FOUND,
  LABEL_MY_AREA_CHOOSE_FARM,
  LABEL_MY_AREA_FORBIDDEN,
  LABEL_MY_AREA_HOST_NOT_CONNECTED,
  LABEL_MY_AREA_LOCATION_REQUIRED,
  LABEL_MY_AREA_MODEL_NOT_READY,
  LABEL_MY_AREA_NO_ASSIGNED_FARMS,
  LABEL_MY_AREA_ORIGIN_NOT_FOUND,
  LABEL_MY_AREA_SESSION_REQUIRED,
  LABEL_MY_AREA_UNSUPPORTED_DISEASE,
  MY_AREA_NOMINAL_REACH_DISCLAIMER,
  MY_AREA_PAGE_TAGLINE,
  MY_AREA_PAGE_TITLE,
} from '../semanticLabels'

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

const MAP_MODE = { RISK: 'RISK', OUTBREAKS: 'OUTBREAKS' }

function mapModePillClass(active) {
  return active
    ? 'rounded px-2.5 py-1 text-[11px] font-semibold text-primary bg-primary/15'
    : 'rounded px-2.5 py-1 text-[11px] font-medium text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface'
}

/**
 * GEO-AREA-02: Page 2 -- My Area. Combines the authorized operational
 * farm (`useOperationalContext`, GEO-INT-03, unchanged) with real
 * historical/model context (`useMyAreaContext`, this checkpoint's own
 * hook over GEO-AREA-01/01H's hardened contract) without mixing their
 * meanings -- two separate fetches, two separate response shapes, never
 * merged into one ad-hoc object.
 *
 * GEO-MY-AREA-VISUAL-QA-REBUILD: the page's INFORMATION ARCHITECTURE was
 * rebuilt to follow the reference "Area Risk Intelligence" composition --
 * a heading + 5 real-data KPI cards, a left column (map / nominal-reach
 * outlook / outbreaks-influencing-my-area) and a right "Area Intelligence
 * / AI Explainer" panel -- instead of the previous fixed-viewport
 * giant-map-plus-narrow-stacked-panels layout. Every real fetch/hook
 * below is UNCHANGED from the prior checkpoint; only how their results
 * are composed into new presentation components changed. See the new
 * `MyAreaKpiCards.jsx` / `MyAreaTemporalOutlook.jsx` /
 * `MyAreaOutbreaksInfluencing.jsx` / `MyAreaIntelligencePanel.jsx` for the
 * new presentation, each documenting exactly which real field it reads.
 *
 * Section 5: `selectedAreaId` is the EXISTING shared reducer field
 * (`outbreakSelectionReducer.js`'s `SELECT_AREA`, verified read-only --
 * an unguarded setter, safe to reuse). `selectedForecastDay` is
 * DELIBERATELY NOT reused for this page's D0-D7 strip: that shared
 * field's `SELECT_DAY` action is guarded by Page 1's own
 * `availableForecastFrames` (derived from a Page-1-selected outbreak's
 * real nominal-reach horizon, `[0]` until one is chosen) -- dispatching
 * a My-Area day outside that specific range would be silently rejected
 * by the reducer. My Area's own valid range is a different, per-origin
 * domain (GEO-MY-AREA-STITCH-16: the selected origin's own real
 * `nominal_reach_by_day` horizon, never assumed to be 0..7 for every
 * origin -- see `availableForecastDays` below), so this page keeps its
 * own local `selectedDay`
 * state rather than risk silently-dropped day changes; the shared
 * reducer itself is left completely untouched (Section 35 -- no Page 1
 * regression risk from editing a shared component).
 */
export default function MyAreaPage() {
  const ctx = useGeospatialContext()
  const reduceMotion = usePrefersReducedMotion()
  const operational = useOperationalContext()

  const authorizedFarms = useMemo(() => operational.data?.farms ?? [], [operational.data])

  // Section 5: preserve a still-valid selection; auto-select the ONLY
  // farm; otherwise require an explicit choice -- never nearest/first.
  useEffect(() => {
    if (authorizedFarms.length === 0) return
    const stillValid = ctx.selectedAreaId && authorizedFarms.some((f) => f.farmId === ctx.selectedAreaId)
    if (stillValid) return
    if (authorizedFarms.length === 1) {
      ctx.selectArea(authorizedFarms[0].farmId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authorizedFarms, ctx.selectedAreaId])

  const [selectedOriginId, setSelectedOriginId] = useState(null)
  const [selectedDay, setSelectedDay] = useState(0)
  const [retryToken, setRetryToken] = useState(0)
  const [mapMode, setMapMode] = useState(MAP_MODE.RISK)

  // Section 34: disease change clears an origin that may not belong to
  // the new disease's relevant-origin set. Day is reset to 0 by the
  // selectedOriginId effect below once that clears (a day number is only
  // ever meaningful relative to a specific selected origin's own real
  // horizon, never a fixed range valid across diseases).
  const prevDiseaseRef = useRef(ctx.selectedDisease)
  useEffect(() => {
    if (prevDiseaseRef.current !== ctx.selectedDisease) {
      prevDiseaseRef.current = ctx.selectedDisease
      setSelectedOriginId(null)
    }
  }, [ctx.selectedDisease])

  // Section 34: area change clears the selected origin (relevance is
  // area-specific) but never touches disease.
  const prevAreaRef = useRef(ctx.selectedAreaId)
  useEffect(() => {
    if (prevAreaRef.current !== ctx.selectedAreaId) {
      prevAreaRef.current = ctx.selectedAreaId
      setSelectedOriginId(null)
    }
  }, [ctx.selectedAreaId])

  const myArea = useMyAreaContext({
    farmId: ctx.selectedAreaId, disease: ctx.selectedDisease, originId: selectedOriginId, day: selectedDay, retryToken,
  })

  // GEO-MY-AREA-STITCH-16 Section 16: the farm's own real district
  // polygon (same geoBoundaries ADM2 dataset Page 1 already draws) for
  // local map framing/context -- resolved by the farm's own real
  // `locationDistrict`, never the signed-in vet's district (a My Area
  // farm and the vet's own registered district are two different real
  // fields; this page is about the SELECTED FARM's location).
  const { feature: districtFeature } = useDistrictGeometry(myArea.data?.area?.locationDistrict)

  // GEO-MY-AREA-STITCH-16 Section 6/16 "reset model timeline to genuine
  // D0": a newly selected origin's own real forecast horizon may differ
  // from the previous one's (or have none at all) -- never keep pointing
  // at a day number that was only ever valid for the origin just left.
  useEffect(() => {
    setSelectedDay(0)
  }, [selectedOriginId])

  // GEO-LIVE-05 Section 9: a live verified-clinical event refetches My
  // Area's own authoritative context ONLY when it is relevant to the
  // farm currently on screen -- an event for a different assigned farm
  // must never refresh THIS farm's context (Section 9/15 "irrelevant
  // event does not refresh unrelated farm context"). Never mutates
  // `myArea.data` directly; the same real fetch path a manual retry
  // already uses (`retryToken`) is reused, never a second ad-hoc fetch.
  const clinicalEvents = useVerifiedClinicalEvents()
  const lastHandledEventIdRef = useRef(null)
  useEffect(() => {
    const event = clinicalEvents.lastEvent
    if (!event || event.event_id === lastHandledEventIdRef.current) return
    lastHandledEventIdRef.current = event.event_id
    if (isEventRelevantToMyArea(event, { selectedAreaId: ctx.selectedAreaId })) {
      setRetryToken((t) => t + 1)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinicalEvents.lastEvent, ctx.selectedAreaId])

  // Section 12: preserves disease/farm/origin/day semantics -- never
  // touches selectedOriginId/selectedDay directly (switching farm/disease
  // triggers this page's OWN pre-existing origin-reset effects above,
  // never a new clinical-vs-historical identity mix-up).
  function handleViewClinicalUpdate(event) {
    if (event.farm_id !== ctx.selectedAreaId) ctx.selectArea(event.farm_id)
    if (event.disease !== ctx.selectedDisease) ctx.selectDisease(event.disease)
    clinicalEvents.dismiss(event.event_id)
  }

  // Section 11: a Page-1-selected origin may be offered ONCE as the
  // initial selection here -- only if it is verified present in this
  // disease's real relevant_origins. Never re-applied after that (an
  // explicit later reset/choice always wins), and never chosen by
  // nearest-distance inference.
  const seededFromPage1Ref = useRef(false)
  useEffect(() => {
    if (seededFromPage1Ref.current) return
    if (!myArea.data?.relevantOrigins?.length) return
    seededFromPage1Ref.current = true
    if (ctx.selectedOutbreakId && myArea.data.relevantOrigins.some((o) => o.originId === ctx.selectedOutbreakId)) {
      setSelectedOriginId(ctx.selectedOutbreakId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myArea.data])

  // Section 13: real map geometry (source points) for the SELECTED
  // origin reuses Page 1's own existing fetch path verbatim -- never a
  // second scientific API, never a recomputed model. Naturally honest
  // for FMD (isDiseaseReady('FMD') === false -> FOCUS_STATUS.UNAVAILABLE,
  // matching My Area's own 409 model-not-ready gate for the same reason).
  const focus = useSelectedOutbreakFrames(ctx.selectedDisease, selectedOriginId, 0)
  const sourceFeatures = focus.status === FOCUS_STATUS.READY ? focus.sources?.features ?? [] : []
  // GEO-MY-AREA-STITCH-16 Section 10: the real per-cell risk surface for
  // the selected origin -- LSD only (`useSelectedOutbreakFrames` itself
  // stays `UNAVAILABLE` for FMD, never READY, so this is always `[]` for
  // FMD -- the same honest gate Page 1's own Risk Zones mode relies on,
  // never a second capability check reimplemented here).
  const cellFeatures = focus.status === FOCUS_STATUS.READY ? focus.cells ?? [] : []
  // GEO-MY-AREA-STITCH-16 Section 11/14/19: the real available forecast
  // days for THIS selected origin -- the exact same adapter function
  // Page 1's `TimelineControl` uses (`deriveAvailableForecastDays`, reads
  // the origin's own real `nominal_reach_by_day`), never a hardcoded
  // D0-D+7 assumption. Falls back to `[0]` (observed-only) before an
  // origin's real summary has loaded, or when the disease has no forecast
  // capability at all (FMD) -- both honest "nothing beyond D0" states.
  const availableForecastDays = focus.status === FOCUS_STATUS.READY ? deriveAvailableForecastDays(ctx.selectedDisease, focus.summary) : [0]
  const reachRingCenters = sourceFeatures.length > 0 ? sourceFeatures.map((f) => f.geometry.coordinates) : null
  const reachRingRadiusKm = myArea.data?.selectedOriginContext?.nominalReachContext?.nominalReachKm ?? 0

  const bodyStatus = myArea.data?.status ?? null
  const t0 = myArea.data?.selectedOriginContext?.t0 ?? null

  function handleSelectDay(day) {
    setSelectedDay(day)
  }

  const showFarmChooser = authorizedFarms.length > 1 && !authorizedFarms.some((f) => f.farmId === ctx.selectedAreaId)

  // GEO-MY-AREA-VISUAL-QA-REBUILD: real fine-grained capability read
  // (never the coarse `ready` flag) so the KPI/Intelligence/map-mode
  // presentation can honestly say "not available" for FMD's current
  // spatial-cell gap without a second ad-hoc check.
  const hasSpatialCells = hasCapability(ctx.selectedDisease, CAPABILITY.SPATIAL_CELLS)
  const diseaseShortLabel = getDiseaseConfig(ctx.selectedDisease).shortLabel
  const areaDistrictLabel = myArea.data?.area?.locationDistrict ?? null

  // GEO-MY-AREA-VISUAL-QA-REBUILD Card 5 "National situation": reuses
  // Page 1's own real national-origins fetch (`useNationalOutbreaks`,
  // unchanged) for the selected disease -- a genuine national count, never
  // a fabricated aggregate. Shares this page's own `retryToken` so a
  // My Area retry also refreshes this real national read.
  const national = useNationalOutbreaks(ctx.selectedDisease, 'Sri Lanka', retryToken)
  const nationalStatus = national.status === NATIONAL_STATUS.LOADING ? 'loading' : national.status === NATIONAL_STATUS.ERROR || national.status === NATIONAL_STATUS.UNAVAILABLE ? 'error' : 'ready'

  // GEO-MY-AREA-VISUAL-QA-REBUILD Section 5/13: the "Future Impact Map"
  // mode pills (Risk / Trajectory / Outbreaks). "Risk" is only ever
  // offered while the selected disease genuinely has a spatial-cell
  // model; "Trajectory" has no current Page runtime/API endpoint at all
  // (`diseaseRegistry.js`) and stays permanently disabled rather than
  // faking a corridor. This is a presentation-only toggle over data this
  // page already fetched -- it never triggers a second request and never
  // touches the map's own camera (only which already-fetched layers are
  // handed to `MyAreaMapCanvas` as props changes).
  const effectiveMapMode = mapMode === MAP_MODE.RISK && !hasSpatialCells ? MAP_MODE.OUTBREAKS : mapMode
  const showRiskLayer = effectiveMapMode === MAP_MODE.RISK && hasSpatialCells
  const mapExplanationText = showRiskLayer
    ? 'This view is centered on your authorized area and shows the currently available local spatial risk surface and nominal reach for the selected origin.'
    : 'This view is centered on your authorized area and shows only the currently available observed and historical spatial context.'

  return (
    <div className="flex flex-col gap-4 pb-6">
      <div className="flex shrink-0 flex-col gap-2">
        <div>
          <h2 className="text-[28px] font-bold leading-[1.15] text-on-surface">{MY_AREA_PAGE_TITLE}</h2>
          <p className="text-xs text-on-surface-variant/70">{MY_AREA_PAGE_TAGLINE}</p>
        </div>
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-outline-variant/30 bg-surface-container/60 px-4 py-2">
          <DiseaseSelector selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
          {authorizedFarms.length > 0 && (
            <>
              <span aria-hidden="true" className="h-6 w-px bg-outline-variant/30" />
              <label className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant/70">Farm</span>
                <span className="relative flex items-center">
                  <select
                    value={ctx.selectedAreaId ?? ''}
                    onChange={(e) => ctx.selectArea(e.target.value || null)}
                    aria-label="Assigned farm"
                    className="cursor-pointer appearance-none rounded-md bg-surface-container-high/60 py-2 pl-3 pr-7 text-sm font-medium text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    <option value="" disabled>
                      {LABEL_MY_AREA_CHOOSE_FARM}
                    </option>
                    {authorizedFarms.map((farm) => (
                      <option key={farm.farmId} value={farm.farmId} className="bg-surface-container-high">
                        {farm.locationDistrict ?? farm.farmId}
                        {farm.locationDistrict ? ` (${farm.farmId.slice(0, 8)}…)` : ''}
                      </option>
                    ))}
                  </select>
                  <span aria-hidden="true" className="material-symbols-outlined pointer-events-none absolute right-1.5 text-[18px] text-on-surface-variant/70">
                    expand_more
                  </span>
                </span>
              </label>
            </>
          )}
          <div className="ml-auto">
            <OperationalStatusChip state={operational.state} lastRefreshedAt={operational.lastRefreshedAt} onRefresh={operational.refresh} />
          </div>
        </div>
      </div>

      {operational.data === null && authorizedFarms.length === 0 && (
        <div className="shrink-0 rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">
          Operational context not connected. The map below stays available; authorized farm data will populate once connected.
        </div>
      )}

      {operational.data !== null && authorizedFarms.length === 0 && (
        <div className="shrink-0 rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">{LABEL_MY_AREA_NO_ASSIGNED_FARMS}</div>
      )}

      {showFarmChooser && (
        <div className="shrink-0 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">{LABEL_MY_AREA_CHOOSE_FARM}</div>
      )}

      {myArea.status === MY_AREA_REQUEST_STATE.ERROR && (
        <div className="flex shrink-0 items-center justify-between gap-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
          <span>{MY_AREA_ERROR_LABEL[myArea.errorStatus] ?? 'My Area is temporarily unavailable.'}</span>
          <button
            type="button"
            onClick={() => setRetryToken((t) => t + 1)}
            className="shrink-0 rounded border border-red-300/40 px-2 py-0.5 font-medium text-red-100 hover:bg-red-400/20"
          >
            Retry
          </button>
        </div>
      )}

      {bodyStatus && BODY_STATUS_LABEL[bodyStatus] && (
        <div className="shrink-0 rounded border border-outline-variant/30 bg-surface-container/60 px-3 py-2 text-xs text-on-surface-variant">{BODY_STATUS_LABEL[bodyStatus]}</div>
      )}

      {bodyStatus === 'LOCATION_REQUIRED' && (
        <div className="shrink-0 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">{LABEL_MY_AREA_LOCATION_REQUIRED}</div>
      )}

      <MyAreaKpiCards
        areaDistrictLabel={areaDistrictLabel}
        hasSpatialCells={hasSpatialCells}
        relativeSpatialScore={myArea.data?.selectedOriginContext?.relativeSpatialScore ?? null}
        availableForecastDays={availableForecastDays}
        relevantOriginsCount={myArea.data?.relevantOrigins?.length ?? 0}
        verifiedClinicalCount={myArea.data?.verifiedClinicalContexts?.length ?? 0}
        nationalCount={national.originsWithSources.length}
        nationalStatus={nationalStatus}
        diseaseShortLabel={diseaseShortLabel}
      />

      {/* GEO-MY-AREA-LAYOUT-BALANCE Section 3/4/6: a real CSS grid (not
          flex) so the left column's first card and the right panel start
          in the SAME grid row -- their tops align exactly, by
          construction, rather than relying on flex cross-axis alignment.
          `lg:` (>=1024px) is this codebase's closest existing Tailwind
          breakpoint to the requested "~1180px" 2-column threshold (no
          custom breakpoint was added -- `tailwind.config.js` is outside
          this feature's editable scope); the right column keeps a real
          290px floor via `minmax`, matching Section 3's "do not hardcode
          fragile absolute widths". */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2.1fr)_minmax(290px,0.9fr)] lg:gap-5">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container-lowest">
            <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 px-3 py-2">
              <div className="truncate text-sm font-semibold text-on-surface">Future Impact Map{areaDistrictLabel ? ` — ${areaDistrictLabel}` : ''}</div>
              <div className="flex shrink-0 items-center gap-0.5 rounded-md border border-outline-variant/30 bg-surface-container-lowest/40 p-0.5" role="group" aria-label="Map layer mode">
                <button type="button" disabled={!hasSpatialCells} aria-pressed={effectiveMapMode === MAP_MODE.RISK} onClick={() => setMapMode(MAP_MODE.RISK)} className={`${mapModePillClass(effectiveMapMode === MAP_MODE.RISK)} disabled:cursor-not-allowed disabled:opacity-30`}>
                  Risk
                </button>
                <button type="button" disabled aria-disabled="true" title="Not available -- no current runtime trajectory endpoint" className="cursor-not-allowed rounded px-2.5 py-1 text-[11px] font-medium text-on-surface-variant/30">
                  Trajectory
                </button>
                <button type="button" aria-pressed={effectiveMapMode === MAP_MODE.OUTBREAKS} onClick={() => setMapMode(MAP_MODE.OUTBREAKS)} className={mapModePillClass(effectiveMapMode === MAP_MODE.OUTBREAKS)}>
                  Outbreaks
                </button>
              </div>
            </div>

            {/* GEO-MY-AREA-LAYOUT-BALANCE Section 1/5: 450px sits inside
                the requested ~430-470px desktop map-viewport band -- the
                map card is now shorter/wider-looking rather than
                vertically dominant. `MyAreaMapCanvas.jsx`'s own
                ResizeObserver (unchanged by this edit) keeps the MapLibre
                canvas synchronized to whatever height this container
                actually has; `map.resize()` alone never moves the camera. */}
            <div className="relative h-[450px]">
              <MyAreaMapCanvas
                area={myArea.data?.area ?? null}
                sourceFeatures={sourceFeatures}
                cellFeatures={showRiskLayer ? cellFeatures : []}
                districtFeature={districtFeature}
                reachRingCenters={showRiskLayer ? reachRingCenters : null}
                reachRingRadiusKm={showRiskLayer ? reachRingRadiusKm : 0}
                selectedOriginId={selectedOriginId}
                reduceMotion={reduceMotion}
              />

              {clinicalEvents.notifications.length > 0 && (
                <div className="pointer-events-none absolute left-3 top-3">
                  <GeospatialAlertBanner
                    notifications={clinicalEvents.notifications}
                    onViewUpdate={handleViewClinicalUpdate}
                    onDismiss={clinicalEvents.dismiss}
                  />
                </div>
              )}
            </div>

            <div className="truncate border-t border-outline-variant/20 px-3 py-1.5 text-[11px] text-on-surface-variant/60" title={mapExplanationText}>
              {mapExplanationText}
            </div>
          </div>

          <MyAreaTemporalOutlook
            areaLabel={areaDistrictLabel}
            selectedDay={selectedDay}
            onSelectDay={handleSelectDay}
            t0={t0}
            availableDays={availableForecastDays}
            nominalReachByDay={focus.status === FOCUS_STATUS.READY ? focus.summary?.nominal_reach_by_day ?? [] : []}
            disabled={!selectedOriginId}
          />

          <MyAreaOutbreaksInfluencing
            relevantOrigins={myArea.data?.relevantOrigins ?? []}
            selectedOriginId={selectedOriginId}
            onSelectOrigin={setSelectedOriginId}
          />

          {/* GEO-MY-AREA-LAYOUT-BALANCE Section 10: a thin provenance
              footer (not a large standalone card) -- caveats stay fully
              readable, just compacted. */}
          <div className="rounded-lg border border-outline-variant/20 bg-surface-container/30 px-3 py-2 text-[10.5px] leading-snug text-on-surface-variant/60">
            <div className="truncate" title={`${MY_AREA_NOMINAL_REACH_DISCLAIMER} Historical retrospective replay context -- not live operational surveillance.`}>
              {MY_AREA_NOMINAL_REACH_DISCLAIMER} Historical retrospective replay -- not live operational surveillance.
            </div>
            {myArea.data?.generatedAt && <div className="mt-0.5 text-on-surface-variant/40">Generated {myArea.data.generatedAt}</div>}
          </div>
        </div>

        {/* GEO-MY-AREA-LAYOUT-BALANCE Section 4/13: sticky ONLY at
            `lg:` and up (never tablet/mobile), offset `top-20` (80px)
            to clear VetLayout's own `sticky top-0 h-16` header (64px)
            plus real breathing room -- this never covers or edits
            TopHeader/VetLayout. The panel itself is a normal,
            non-scrolling block (`MyAreaIntelligencePanel.jsx`'s own
            `h-full`/`overflow-y-auto` was removed) -- while the vet
            scrolls through the nominal-reach/outbreak sections below,
            this stays visible as contextual information instead of
            leaving a tall empty right column. */}
        <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
          <MyAreaIntelligencePanel
            area={myArea.data?.area ?? null}
            selectedOriginContext={myArea.data?.selectedOriginContext ?? null}
            hasSpatialCells={hasSpatialCells}
            diseaseShortLabel={diseaseShortLabel}
            availableForecastDays={availableForecastDays}
            relevantOriginsCount={myArea.data?.relevantOrigins?.length ?? 0}
            verifiedClinicalCount={myArea.data?.verifiedClinicalContexts?.length ?? 0}
          />
        </div>
      </div>
    </div>
  )
}
