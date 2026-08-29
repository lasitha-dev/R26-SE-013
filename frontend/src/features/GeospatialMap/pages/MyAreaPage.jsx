import React, { useEffect, useMemo, useRef, useState } from 'react'

import { addDaysToIsoDate, formatDisplayDate } from '../adapters/forecastDate'
import { isEventRelevantToMyArea } from '../adapters/operationalEventRelevance'
import DiseaseSelector from '../components/DiseaseSelector'
import GeospatialAlertBanner from '../components/GeospatialAlertBanner'
import MyAreaClinicalPanel from '../components/MyAreaClinicalPanel'
import MyAreaForecastStrip from '../components/MyAreaForecastStrip'
import MyAreaMapCanvas from '../components/MyAreaMapCanvas'
import MyAreaScientificPanel from '../components/MyAreaScientificPanel'
import MyAreaSummaryPanel from '../components/MyAreaSummaryPanel'
import OperationalStatusChip from '../components/OperationalStatusChip'
import { useGeospatialContext } from '../context/GeospatialContext'
import { useMyAreaContext, MY_AREA_REQUEST_STATE } from '../context/useMyAreaContext'
import { useOperationalContext } from '../context/useOperationalContext'
import { useVerifiedClinicalEvents } from '../context/useVerifiedClinicalEvents'
import { usePrefersReducedMotion } from '../context/usePrefersReducedMotion'
import { FOCUS_STATUS, useSelectedOutbreakFrames } from '../context/useSelectedOutbreakFrames'
import { isDiseaseReady } from '../disease/diseaseRegistry'
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

/**
 * GEO-AREA-02: Page 2 -- My Area. Combines the authorized operational
 * farm (`useOperationalContext`, GEO-INT-03, unchanged) with real
 * historical/model context (`useMyAreaContext`, this checkpoint's own
 * hook over GEO-AREA-01/01H's hardened contract) without mixing their
 * meanings -- two separate fetches, two separate response shapes, never
 * merged into one ad-hoc object.
 *
 * Section 5: `selectedAreaId` is the EXISTING shared reducer field
 * (`outbreakSelectionReducer.js`'s `SELECT_AREA`, verified read-only --
 * an unguarded setter, safe to reuse). `selectedForecastDay` is
 * DELIBERATELY NOT reused for this page's D0-D7 strip: that shared
 * field's `SELECT_DAY` action is guarded by Page 1's own
 * `availableForecastFrames` (derived from a Page-1-selected outbreak's
 * real nominal-reach horizon, `[0]` until one is chosen) -- dispatching
 * a My-Area day outside that specific range would be silently rejected
 * by the reducer. My Area's own valid range (0..7, always) is a
 * different, wider domain, so this page keeps its own local `selectedDay`
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

  // Section 34: disease change clears an origin that may not belong to
  // the new disease's relevant-origin set. Day is preserved (always
  // valid 0..7 regardless of disease).
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
  const reachRingCenters = sourceFeatures.length > 0 ? sourceFeatures.map((f) => f.geometry.coordinates) : null
  const reachRingRadiusKm = myArea.data?.selectedOriginContext?.nominalReachContext?.nominalReachKm ?? 0

  const bodyStatus = myArea.data?.status ?? null
  const t0 = myArea.data?.selectedOriginContext?.t0 ?? null

  function handleSelectDay(day) {
    setSelectedDay(day)
  }

  const showFarmChooser = authorizedFarms.length > 1 && !authorizedFarms.some((f) => f.farmId === ctx.selectedAreaId)

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex shrink-0 flex-col gap-2">
        <div>
          <h2 className="text-lg font-semibold text-white">{MY_AREA_PAGE_TITLE}</h2>
          <p className="text-xs text-slate-400">{MY_AREA_PAGE_TAGLINE}</p>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <DiseaseSelector selected={ctx.selectedDisease} onSelect={ctx.selectDisease} />
            {authorizedFarms.length > 0 && (
              <label className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs text-slate-300">
                <span className="text-slate-500">Farm</span>
                <select
                  value={ctx.selectedAreaId ?? ''}
                  onChange={(e) => ctx.selectArea(e.target.value || null)}
                  className="bg-transparent text-slate-200 focus:outline-none"
                  aria-label="Assigned farm"
                >
                  <option value="" disabled>
                    {LABEL_MY_AREA_CHOOSE_FARM}
                  </option>
                  {authorizedFarms.map((farm) => (
                    <option key={farm.farmId} value={farm.farmId} className="bg-slate-900">
                      {farm.farmId}
                      {farm.locationDistrict ? ` · ${farm.locationDistrict}` : ''}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <OperationalStatusChip state={operational.state} lastRefreshedAt={operational.lastRefreshedAt} onRefresh={operational.refresh} />
        </div>
      </div>

      {operational.data === null && authorizedFarms.length === 0 && (
        <div className="shrink-0 rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
          Operational context not connected. The map below stays available; authorized farm data will populate once connected.
        </div>
      )}

      {operational.data !== null && authorizedFarms.length === 0 && (
        <div className="shrink-0 rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">{LABEL_MY_AREA_NO_ASSIGNED_FARMS}</div>
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
        <div className="shrink-0 rounded border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">{BODY_STATUS_LABEL[bodyStatus]}</div>
      )}

      {bodyStatus === 'LOCATION_REQUIRED' && (
        <div className="shrink-0 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">{LABEL_MY_AREA_LOCATION_REQUIRED}</div>
      )}

      <div className="flex flex-1 flex-col gap-3 overflow-hidden lg:flex-row">
        <div className="relative min-h-[520px] flex-[2.2] overflow-hidden rounded-xl border border-white/10 bg-slate-950">
          <MyAreaMapCanvas
            area={myArea.data?.area ?? null}
            sourceFeatures={sourceFeatures}
            reachRingCenters={reachRingCenters}
            reachRingRadiusKm={reachRingRadiusKm}
            selectedOriginId={selectedOriginId}
            reduceMotion={reduceMotion}
          />
          <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center px-3">
            <div className="pointer-events-auto">
              <MyAreaForecastStrip selectedDay={selectedDay} onSelectDay={handleSelectDay} t0={t0} disabled={!selectedOriginId} />
            </div>
          </div>

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

        <div className="flex-1 overflow-y-auto pr-1">
          <div className="flex flex-col gap-3">
            <MyAreaSummaryPanel
              area={myArea.data?.area ?? null}
              relevantOrigins={myArea.data?.relevantOrigins ?? []}
              selectedOriginId={selectedOriginId}
              onSelectOrigin={setSelectedOriginId}
            />
            <MyAreaScientificPanel
              selectedOriginContext={myArea.data?.selectedOriginContext ?? null}
              forecastFrameUnavailable={bodyStatus === 'FORECAST_FRAME_UNAVAILABLE'}
            />
            <MyAreaClinicalPanel verifiedClinicalContexts={myArea.data?.verifiedClinicalContexts ?? []} />

            <div className="rounded-lg border border-white/10 bg-slate-900/50 p-3 text-[11px] text-slate-500">
              <div>{MY_AREA_NOMINAL_REACH_DISCLAIMER}</div>
              <div className="mt-1">Historical retrospective replay context -- not live operational surveillance.</div>
              {myArea.data?.generatedAt && <div className="mt-1">Generated {myArea.data.generatedAt}</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
