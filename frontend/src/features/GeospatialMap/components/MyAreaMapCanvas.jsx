import maplibregl from 'maplibre-gl'
import { createRiskFieldRenderer } from './riskFieldRenderer'
import { riskHoverHtml } from './riskHoverCard'
import { addTrajectoryLabelLayer, startTrajectoryFlow } from './stageLayers'
import { basemapPlaceSourceId, buildTrajectoryLabels, nearestMappedPlace } from './trajectoryLabels'
import { isPointInsideDistrictFeature } from '../adapters/districtGeometry'
import { IMPACT_LAYER, caseDetailRows, caseFocusStyle, impactLayerVisibility, outsideDistrictMask } from '../adapters/myAreaMapPresentation'
import { CASE_AGE_COLOR } from '../adapters/caseAge'
import { isFatalMapError, MAP_RENDER_ERROR_TEXT, MAP_RESOURCE_ERROR_TEXT } from './mapPresentationError'
import 'maplibre-gl/dist/maplibre-gl.css'
import React, { useEffect, useRef, useState } from 'react'

import {
  buildCellsFeatureCollection,
  buildSourcesFeatureCollection,
  computeRiskTierStats,
  NATIONAL_SOURCES_PULSE_CYCLE_MS,
  nationalSourceAmbientPulsePaint,
  riskTierColorExpression,
  sourceIconLayout,
} from './mapLibreAdapter'
import { buildReachRingFeatureCollectionForCenters, emptyReachRingFeatureCollection } from './nominalReachRing'
// GEO-MY-AREA-FINAL-PASS: the SAME real, tested district-bounds utility
// Page 1's own "Focus My District" button already uses
// (`OutbreakMapPage.jsx::handleFocusMyDistrict`) -- never a second,
// reimplemented bounds calculation. Pure function over the district
// polygon's own real coordinates; returns `null` for missing/unmatched
// geometry, never a fabricated box (see its own docstring).
import { computeFeatureBounds } from '../adapters/districtGeometry'
import { AREA_RISK_COLORS } from '../adapters/timelinePresentation'
import { FARM_MARKER_ICON_ID, buildFarmMarkerImage, farmMarkerIconLayout } from './myAreaIcons'
import { resolveBasemapConfig } from './basemapConfig'
import { SOURCE_ICON_ID, buildSourceMarkerImage } from './presentationIcons'
import {
  DIRECTION_ARROW_ICON_ID,
  EMPTY_FEATURE_COLLECTION,
  buildDirectionArrowIcon,
  createRiskZoneCrossFader,
  directionArrowLayout,
  ensureDirectionArrowImage,
  runCorridorReveal,
} from './mapFrameTransitions'
import { compassPoint, horizonLabel } from '../adapters/spatialTimelineView'
import { monitoringZoneDetails } from '../adapters/myAreaIntelligence'
// GEO-MY-AREA-VISUAL-QA-FIX: the same real, fixed Sri Lanka presentation
// constants Page 1's map already opens on (`MapLibreCanvas.jsx`) -- reused
// verbatim, never redeclared, so this map's FIRST frame (before the real
// farm coordinate has loaded) is already Sri Lanka, never MapLibre's own
// default world view ([0,0], zoom 0).
import { SRI_LANKA_CENTER, SRI_LANKA_INITIAL_ZOOM } from './MapLibreCanvas'
import './myAreaChrome.css'

const FARM_SOURCE_ID = 'geo-my-area-farm'
const SOURCES_SOURCE_ID = 'geo-my-area-sources'
const REACH_RING_SOURCE_ID = 'geo-my-area-reach-ring'
const OBSERVED_CASES_SOURCE_ID = 'geo-my-area-observed-cases'
const AREA_FORECAST_RISK_SOURCE_ID = 'geo-my-area-forecast-risk'
const AREA_FORECAST_PATH_SOURCE_ID = 'geo-my-area-forecast-paths'
const AREA_FORECAST_FRONT_SOURCE_ID = 'geo-my-area-forecast-fronts'
// Phase 4: the day-dependent reach-limited zones are double-buffered (A =
// the original ids, B = `-b` suffix) and cross-faded by opacity; the static
// full-surface context has its own source and never animates.
const AREA_FORECAST_RISK_B_SOURCE_ID = 'geo-my-area-forecast-risk-b'
const AREA_FORECAST_CONTEXT_SOURCE_ID = 'geo-my-area-forecast-context'
const AREA_TIMELINE_ORIGIN_SOURCE_ID = 'geo-my-area-timeline-origins'
const REGISTERED_FARMS_SOURCE_ID = 'geo-my-area-registered-farms'
const PENDING_CASES_SOURCE_ID = 'geo-my-area-pending-cases'
const AREA_FLOW_SOURCE_ID = 'geo-my-area-flow'
// Flow dots along the new outbreaks' own paths (pink).
const AREA_FLOW_NEW_SOURCE_ID = 'geo-my-area-flow-new'
// Future Impact colours: an existing outbreak (the cause) is a small red
// hollow ring; a modelled new outbreak in the district is pink.
const EXISTING_OUTBREAK_RED = '#ef4444'
const NEW_OUTBREAK_PINK = '#ec4899'
const NEW_OUTBREAK_ARROW_ICON_ID = 'my-area-arrow-new-outbreak'
const AREA_RISK_LEVELS = ['green', 'yellow', 'orange', 'red']
const AREA_RISK_BUFFER_SUFFIXES = ['', '-b']
const AREA_RISK_LAYER_IDS = [
  'my-area-forecast-context-fill',
  'my-area-forecast-context-line',
  'my-area-forecast-reach-label',
  ...AREA_RISK_BUFFER_SUFFIXES.flatMap((suffix) => AREA_RISK_LEVELS.flatMap((riskLevel) => [
    `my-area-forecast-risk-${riskLevel}${suffix}`,
    `my-area-forecast-risk-${riskLevel}-outline${suffix}`,
  ])),
]
// Direction indicators only: no glow, travelling dash or moving "front"
// (those made a geometric tendency read as a transmission path; the
// decorative layers are created hidden and never shown).
const AREA_PROJECTION_LAYER_IDS = [
  'my-area-forecast-path',
  'my-area-forecast-path-label',
  'my-area-flow-glow',
  'my-area-flow',
  'my-area-flow-new-glow',
  'my-area-flow-new',
  'my-area-forecast-arrow',
  'my-area-timeline-origin',
  'my-area-forecast-selected-risk-outline',
  'my-area-forecast-selected-path',
]
export { IMPACT_LAYER }
const AREA_TRAJECTORY_LABEL_SOURCE_ID = 'geo-my-area-trajectory-labels'
const AREA_TRAJECTORY_LABEL_LAYER_ID = 'my-area-trajectory-label'
// The along-line "Day N · X km" label is never shown: the front's "Day N · near <place>" label replaces it.
const AREA_TRAJECTORY_LAYER_IDS = AREA_PROJECTION_LAYER_IDS.filter((id) => id !== 'my-area-timeline-origin' && id !== 'my-area-forecast-path-label').concat(AREA_TRAJECTORY_LABEL_LAYER_ID)
const DISTRICT_OUTSIDE_SOURCE_ID = 'geo-my-area-district-outside'
// Modeled possible new cases at registered farms (backend `possible_new_cases`).
const POSSIBLE_CASES_SOURCE_ID = 'geo-my-area-possible-cases'
const POSSIBLE_CASE_LAYER_IDS = ['my-area-possible-case-ring', 'my-area-possible-case-dot', 'my-area-possible-case-label']
const DISTRICT_OUTSIDE_LAYER_ID = 'my-area-district-outside-fade'

const AREA_CORRIDOR_INTERACTIVE_LAYER_IDS = ['my-area-forecast-path', 'my-area-forecast-arrow', 'my-area-timeline-origin']

function finiteOrNull(value) {
  const number = value == null || value === '' ? Number.NaN : Number(value)
  return Number.isFinite(number) ? number : null
}

/** Plain-text tooltip rows for one backend corridor / origin (textContent only). */
function corridorTooltipDom(properties, pinned) {
  const bearing = finiteOrNull(properties.bearingDeg)
  const length = finiteOrNull(properties.lengthKm)
  const day = finiteOrNull(properties.day)
  const root = document.createElement('div')
  root.className = 'space-y-0.5 text-xs'
  const newOutbreak = properties.possibleNewCase === true || properties.possibleNewCase === 'true'
  const handoverDay = finiteOrNull(properties.handoverDay)
  const rows = [
    [newOutbreak ? 'New outbreak (modelled) spread' : bearing == null ? 'Source origin' : 'Estimated spread direction', newOutbreak ? null : properties.sourceId],
    ['Became a new outbreak', handoverDay == null ? null : `on Day ${handoverDay} (its spread continues as the pink outbreak)`],
    ['Type', properties.recordDomain === 'OPERATIONAL' ? 'Vet-verified case' : properties.recordDomain === 'HISTORICAL' ? 'Historical record' : null],
    ['Disease', properties.disease],
    ['Status', properties.horizonStatus ? horizonLabel(properties.horizonStatus) : null],
    ['Heading today', bearing == null ? 'No supported direction' : `${Math.round(bearing)}° ${compassPoint(bearing)}`],
    ['Distance along path', day === 0 || length == null ? 'Starts on Day 1' : `${length.toFixed(1)} km`],
    ['Straight-line from farm', finiteOrNull(properties.displacementKm) == null ? null : `${finiteOrNull(properties.displacementKm).toFixed(1)} km`],
    ['Net wind (this day)', finiteOrNull(properties.windTowardDeg) == null ? null : `toward ${compassPoint(finiteOrNull(properties.windTowardDeg))}`],
    ['Stopped', properties.stopReason === 'REACHED_25KM_LOCAL_DOMAIN' ? 'at the 25 km model limit' : null],
    ['Today', properties.heldAtCoast === true || properties.heldAtCoast === 'true' ? 'waited at the coast' : null],
  ]
  for (const [label, value] of rows) {
    if (!value) continue
    const row = document.createElement('div')
    row.textContent = `${label}: ${value}`
    root.appendChild(row)
  }
  const note = document.createElement('div')
  note.className = 'pt-1 opacity-70'
  note.textContent = pinned
    ? 'From land, cattle, the net wind of the day and nearby cases; not a transmission route.'
    : 'Click to pin. Estimated spread direction, not a transmission route.'
  root.appendChild(note)
  return root
}
// GEO-MY-AREA-STITCH-16: this farm's own real district polygon (same
// geoBoundaries ADM2 dataset/attribution Page 1 already draws,
// `useDistrictGeometry`), for local geographic context only -- never a
// risk zone. Same visual treatment as Page 1's `MY_DISTRICT_*` layers
// (`MapLibreCanvas.jsx`) so a vet reading either page recognizes the same
// "restrained mint outline" language for "administrative boundary".
const DISTRICT_SOURCE_ID = 'geo-my-area-district'
// GEO-MY-AREA-STITCH-16 Section 10: the SAME real per-cell C0 spatial-rank
// output Page 1's Risk Zones mode already fetches for this exact origin
// (`useSelectedOutbreakFrames`, LSD only -- `focus.cells`), painted with
// the existing tested snapshot-relative tier expression from
// `mapLibreAdapter.js`, so this page introduces no new threshold. FMD has
// no spatial-cell capability at all
// (`diseaseRegistry.js`), so `cellFeatures` is always `[]` for FMD --
// this layer is then genuinely empty, never a fabricated surface.
const CELLS_SOURCE_ID = 'geo-my-area-cells'
const ACTIVE_CELLS_SOURCE_ID = 'geo-my-area-active-cells'

/**
 * GEO-AREA-02 Section 14/15: a small, Page-2-specific MapLibre component
 * -- deliberately NOT a reuse/extension of `MapLibreCanvas.jsx` itself
 * (Section 14's own "prefer additive reuse over invasive Page 1
 * refactoring"; adding farm-marker-specific props/effects to that
 * already-complex shared component would risk Page 1 regression for no
 * benefit, since Page 2's content -- one farm + one selected origin's
 * real sources + a reach ring -- barely overlaps Page 1's national/
 * cells/direction layers). Reuses everything reusable instead:
 * `resolveBasemapConfig`, `buildSourcesFeatureCollection`, and
 * `buildReachRingFeatureCollectionForCenters`
 * (Section 15C: "preserve its existing honest source-centered visual
 * strategy" -- unchanged, same function, same rings-around-every-source
 * approach), and the EXISTING amber source icon (`presentationIcons.js`)
 * for historical sources, so a source marker looks identical to Page 1's.
 * Only the farm marker itself is new (`myAreaIcons.js`).
 *
 * Section 15D: static model cells are deliberately NOT rendered here --
 * see `MyAreaPage.jsx`'s module docstring for the reasoning (the backend
 * itself never assigns a cell to the farm; showing colored cells near an
 * unscored farm risked visually implying a relevance the response
 * explicitly does not establish).
 *
 * One map instance exists for the page's lifetime. The camera fits once
 * per real farm+district scope after ADM2 geometry is ready. Origin,
 * timeline, risk, reach, and clinical updates only call source.setData;
 * they never move the district-scoped camera.
 */
// GEO-MY-AREA-STITCH-16: reserves real screen room for this page's own
// floating chrome (the bottom-docked forecast strip) so a camera fit
// doesn't center the farm/origin in the raw canvas while the VISIBLE map
// area (above that strip) reads as off-center -- same asymmetric-padding
// technique as Page 1's `MAP_FIT_PADDING` (`MapLibreCanvas.jsx`), sized
// for this page's own (shorter) chrome rather than copied verbatim.
export function getMyAreaMapPadding(containerWidth) {
  if (containerWidth < 480) return { top: 22, bottom: 116, left: 18, right: 18 }
  if (containerWidth < 900) return { top: 28, bottom: 120, left: 24, right: 24 }
  return { top: 30, bottom: 124, left: 32, right: 32 }
}

/** Hover card of a modelled new outbreak (pink): where and when it starts,
 * which existing outbreak it comes from, never a confirmed case. */
function newOutbreakDom(properties, placeFor = null) {
  const triggered = (() => { try { return Array.isArray(properties.triggeredBy) ? properties.triggeredBy : JSON.parse(properties.triggeredBy ?? '[]') } catch { return [] } })()
  const local = properties.arrival === 'FIRST_MOVE_INSIDE_DISTRICT'
  const root = document.createElement('div')
  root.className = 'space-y-1 text-xs'
  const title = document.createElement('div')
  title.className = 'font-semibold'
  title.style.color = NEW_OUTBREAK_PINK
  title.textContent = `New outbreak (modelled) · Day ${properties.seedDay}`
  root.appendChild(title)
  const cause = triggered[0] ? (placeFor?.(triggered[0]) ?? 'an existing outbreak') : 'an existing outbreak'
  const rows = [
    ['Starts', `${properties.seedDate ? `${properties.seedDate} · ` : ''}Day ${properties.seedDay}`],
    ['Caused by', local ? `the outbreak near ${cause} (first move inside the district)` : `the outbreak near ${cause} (arriving from outside the district)`],
    ['Risk score here that day', Number.isFinite(Number(properties.seedScore)) ? Number(properties.seedScore).toFixed(2) : null],
    ['Spread', 'moves on from the next day with the same model (pink path)'],
  ]
  for (const [label, value] of rows) {
    if (!value) continue
    const row = document.createElement('div')
    const key = document.createElement('span')
    key.className = 'text-slate-400'
    key.textContent = `${label}: `
    row.appendChild(key)
    row.appendChild(document.createTextNode(String(value)))
    root.appendChild(row)
  }
  const note = document.createElement('div')
  note.className = 'pt-1 text-slate-400'
  note.textContent = 'A modelled scenario of where spread could establish a new outbreak; not a confirmed case and not a prediction that infection will occur.'
  root.appendChild(note)
  return root
}

// The one camera-emphasis call site (case focus and farm-list focus): a
// gentle pan/zoom to a real coordinate, never a refit of the district.
function emphasizeCoordinate(map, coordinate, reduceMotion) {
  map.easeTo({ center: coordinate, zoom: Math.max(map.getZoom(), 11.25), duration: reduceMotion ? 0 : 650, essential: true })
}

// The one real MapLibre bounds-fit call site for this file.
function fitMapToBounds(map, bounds, { reduceMotion, durationMs, padding }) {
  map.fitBounds(bounds, { padding, animate: !reduceMotion, duration: reduceMotion ? 0 : durationMs })
}

const MyAreaMapCanvas = React.forwardRef(function MyAreaMapCanvas(
  {
    area = null,
    sourceFeatures = [],
    cellFeatures = [],
    activeCellFeatures = [],
    riskColorReferenceFeatures = cellFeatures,
    observedCaseFeatures = [],
    areaForecastVisualization = null,
    // Animated surface (adapters/riskFieldModel.js) + selected frame index.
    riskFieldModel = null,
    riskFieldIndex = 0,
    showAreaImpact = true,
    // Which Future Impact view is shown: IMPACT_LAYER.CASES | RISK | TRAJECTORY.
    impactLayer = IMPACT_LAYER.RISK,
    // (anchorId | null) when a verified case marker is clicked.
    onSelectCase = null,
    // Modelled new outbreaks that have appeared by the selected day (FeatureCollection).
    possibleCaseFeatures = EMPTY_FEATURE_COLLECTION,
    // ({ [sourceId]: placeName }) nearest mapped OpenStreetMap place of each
    // source, reported when the map is idle (influencing-outbreak cards).
    onSourcePlaces = null,
    focusedCaseId = null,
    districtFeature = null,
    reachRingCenters = null,
    reachRingRadiusKm = 0,
    selectedOriginId = null,
    reduceMotion = false,
    onMapUnavailable,
    onFocusSource = null,
    // Registered district farms (real GPS only) and pending reports (hollow
    // amber, Verified Cases mode only). `focusPoint` = { key, coordinates }.
    registeredFarmFeatures = EMPTY_FEATURE_COLLECTION,
    pendingCaseFeatures = EMPTY_FEATURE_COLLECTION,
    showPendingCases = false,
    focusPoint = null,
    onFocusFarm = null,
  },
  ref,
) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const failedRef = useRef(false)
  const [mapIssue, setMapIssue] = useState(null)
  const loadedRef = useRef(false)
  const lastFitAreaScopeRef = useRef(undefined)
  // The district fit is kept when the map box changes size (layout settling,
  // window resize) until the vet moves the camera themselves.
  const districtFitRef = useRef(null)
  const userMovedCameraRef = useRef(false)
  const reachRingAnimRef = useRef(null)
  const observedPulseAnimRef = useRef(null)
  const currentReachRadiusKmRef = useRef(0)
  // GEO-MY-AREA-STITCH-16 Section 2 (mirrors `MapLibreCanvas.jsx`'s own
  // documented fix for the same real race): `map.on('load')` closes over
  // whatever these props were on the FIRST render, which is empty/null
  // whenever the real district/cell fetch resolves before the remote
  // basemap style does. Reading through refs inside `load` makes initial
  // seeding correct regardless of which one wins.
  const cellFeaturesRef = useRef(cellFeatures)
  const riskColorReferenceFeaturesRef = useRef(riskColorReferenceFeatures)
  const activeCellFeaturesRef = useRef(activeCellFeatures)
  const observedCaseFeaturesRef = useRef(observedCaseFeatures)
  const areaForecastVisualizationRef = useRef(areaForecastVisualization)
  const showAreaImpactRef = useRef(showAreaImpact)
  const districtFeatureRef = useRef(districtFeature)
  cellFeaturesRef.current = cellFeatures
  riskColorReferenceFeaturesRef.current = riskColorReferenceFeatures
  activeCellFeaturesRef.current = activeCellFeatures
  observedCaseFeaturesRef.current = observedCaseFeatures
  areaForecastVisualizationRef.current = areaForecastVisualization
  showAreaImpactRef.current = showAreaImpact
  districtFeatureRef.current = districtFeature
  // GEO-MY-AREA-VISUAL-QA-FIX: real state (not a ref) so the farm-camera
  // and origin-camera effects below -- which key off `loadedRef.current`
  // but only actually RE-RUN when one of their own dependencies changes --
  // get a genuine re-run once the style finishes loading. Traced root
  // cause of the reported permanent world-view/no-farm-marker bug: this
  // page's `myArea` fetch is local (fast) while the remote basemap style
  // is a CDN round trip (slow, same ordering `MapLibreCanvas.jsx` already
  // documents) -- so real farm data commonly arrives BEFORE `loadedRef.
  // current` flips true. Previously, when that happened, the farm effect
  // bailed out on its `!loadedRef.current` guard and nothing ever
  // re-triggered it once `load` actually fired (that handler never reads
  // the farm prop at all), leaving the farm source empty and the camera on
  // its initial view forever. Adding this as a dependency below makes the
  // same district-fit effect re-evaluates the instant the map becomes
  // ready, regardless of which of the two (style
  // vs. data) won the race.
  const [mapLoaded, setMapLoaded] = useState(false)
  const reduceMotionRef = useRef(reduceMotion)
  reduceMotionRef.current = reduceMotion
  const onFocusSourceRef = useRef(onFocusSource)
  onFocusSourceRef.current = onFocusSource
  const impactLayerRef = useRef(impactLayer)
  impactLayerRef.current = impactLayer
  const onSelectCaseRef = useRef(onSelectCase)
  onSelectCaseRef.current = onSelectCase
  const relabelTrajectoryRef = useRef(null)
  const possibleCaseFeaturesRef = useRef(possibleCaseFeatures)
  possibleCaseFeaturesRef.current = possibleCaseFeatures
  const onSourcePlacesRef = useRef(onSourcePlaces)
  onSourcePlacesRef.current = onSourcePlaces
  const sourcePlaceRef = useRef(null)
  const refreshRiskHoverRef = useRef(null)
  const onFocusFarmRef = useRef(onFocusFarm)
  onFocusFarmRef.current = onFocusFarm
  const registeredFarmFeaturesRef = useRef(registeredFarmFeatures)
  registeredFarmFeaturesRef.current = registeredFarmFeatures
  const riskFaderRef = useRef(null)
  const riskFieldRef = useRef(null)
  const riskFieldInputRef = useRef({ model: riskFieldModel, index: riskFieldIndex })
  riskFieldInputRef.current = { model: riskFieldModel, index: riskFieldIndex }
  const revealCancelRef = useRef(null)
  const currentCorridorsRef = useRef(null)
  const zonePopupRef = useRef(null)

  React.useImperativeHandle(ref, () => ({
    resize() {
      mapRef.current?.resize()
    },
  }))

  // ---- mount: create the map once ----
  useEffect(() => {
    let map
    let resizeObserver
    try {
      const basemap = resolveBasemapConfig(import.meta.env.VITE_GEOSPATIAL_BASEMAP_STYLE_URL)
      map = new maplibregl.Map({
        container: containerRef.current,
        style: basemap.style,
        // GEO-MY-AREA-VISUAL-QA-FIX: real, fixed Sri Lanka default -- the
        // same one Page 1 opens on -- so the very first painted frame
        // (before the real farm coordinate has loaded) is never MapLibre's
        // own [0,0]/zoom-0 world default. The farm-camera effect below
        // still refines this to the exact real farm point once real data
        // is ready; this is only the honest pre-data fallback.
        center: SRI_LANKA_CENTER,
        zoom: SRI_LANKA_INITIAL_ZOOM,
        pitch: 0,
        maxPitch: 0,
        bearing: 0,
        // Phase 4: compact attribution at top-right (under zoom) so it never
        // covers the bottom timeline strip on narrow screens.
        attributionControl: false,
      })
      mapRef.current = map
      map.dragRotate.disable()
      map.touchZoomRotate.disableRotation()
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
      map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
      // Start collapsed to the small "i" button so the full credit text
      // never covers the timeline; it stays one click away (OSM/ODbL).
      map.once('load', () => {
        containerRef.current?.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact-show')?.classList.remove('maplibregl-compact-show')
      })

      // GEO-MY-AREA-VISUAL-QA-FIX (kept current by GEO-MY-AREA-LAYOUT-
      // BALANCE): MapLibre has no ResizeObserver of its own -- traced root
      // cause of the reported blank region below the basemap tiles. Even
      // with `MyAreaPage.jsx`'s now-fixed `h-[450px]` desktop card
      // viewport, this container's actual rendered size still genuinely
      // changes across breakpoints (tablet/mobile stack to full width, a
      // banner above the map mounting/unmounting, a later window resize)
      // -- without this, MapLibre's internal canvas buffer stays stuck at
      // whatever size it had at construction while the CSS box around it
      // changes, leaving extra area unpainted or the canvas mismatched
      // with its container. Mirrors `MapLibreCanvas.jsx`'s own proven fix
      // verbatim: observe the real container, resize on any genuine
      // change, disconnect on cleanup.
      if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
        let refitQueued = false
        resizeObserver = new ResizeObserver(() => {
          mapRef.current?.resize()
          if (!districtFitRef.current || userMovedCameraRef.current || refitQueued) return
          // One re-fit per frame of resizing (no timers in the visual layer).
          refitQueued = true
          requestAnimationFrame(() => {
            refitQueued = false
            const current = mapRef.current
            if (!current || !districtFitRef.current || userMovedCameraRef.current) return
            fitMapToBounds(current, districtFitRef.current, { reduceMotion: true, durationMs: 0, padding: getMyAreaMapPadding(containerRef.current?.clientWidth ?? 0) })
          })
        })
        resizeObserver.observe(containerRef.current)
      }

      // A drag, wheel or pinch (an event with an originalEvent) is the vet's own move.
      map.on('movestart', (e) => { if (e?.originalEvent) userMovedCameraRef.current = true })

      map.on('error', (e) => {
        // eslint-disable-next-line no-console
        console.warn('MapLibre map resource error on My Area:', e?.error?.message || e)
        if (isFatalMapError(e?.error) && !failedRef.current) {
          failedRef.current = true
          setMapIssue('fatal')
          onMapUnavailable?.()
        } else if (!failedRef.current) setMapIssue('resource')
      })

      map.on('load', () => {
        loadedRef.current = true
        // GEO-MY-AREA-VISUAL-QA-FIX: real state flip (see the `mapLoaded`
        // declaration above) so the farm/origin camera effects, which read
        // `loadedRef.current` but are otherwise only re-triggered by their
        // own dependency changes, get one guaranteed re-run the instant the
        // map becomes ready -- closing the load/data ordering race without
        // adding another camera call site.
        setMapLoaded(true)

        if (!map.hasImage(FARM_MARKER_ICON_ID)) map.addImage(FARM_MARKER_ICON_ID, buildFarmMarkerImage())
        if (!map.hasImage(SOURCE_ICON_ID)) map.addImage(SOURCE_ICON_ID, buildSourceMarkerImage())

        const initialDistrictFeature = districtFeatureRef.current
        const initialCellFeatures = cellFeaturesRef.current ?? []
        const initialActiveCellFeatures = activeCellFeaturesRef.current ?? []
        const initialObservedCaseFeatures = observedCaseFeaturesRef.current ?? []
        const initialAreaForecast = areaForecastVisualizationRef.current
        const initialAreaImpactVisibility = showAreaImpactRef.current ? 'visible' : 'none'
        const initialCellsFC = buildCellsFeatureCollection(initialCellFeatures)
        const initialActiveCellsFC = buildCellsFeatureCollection(initialActiveCellFeatures)
        const initialRiskStats = computeRiskTierStats(riskColorReferenceFeaturesRef.current ?? [])

        // GEO-MY-AREA-STITCH-16 Section 16/26 stacking order: basemap ->
        // district boundary -> real risk surface -> reach ring -> sources
        // -> farm marker last, so the farm's own anchor marker always
        // paints on top of every other real layer (checkpoint: "the farm
        // marker remains visible above the risk surface").
        map.addSource(DISTRICT_SOURCE_ID, {
          type: 'geojson',
          data: initialDistrictFeature ? { type: 'FeatureCollection', features: [initialDistrictFeature] } : { type: 'FeatureCollection', features: [] },
          attribution: '© OpenStreetMap contributors',
        })
        map.addSource(AREA_FORECAST_CONTEXT_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.contextZones ?? EMPTY_FEATURE_COLLECTION })
        map.addSource(AREA_FORECAST_RISK_SOURCE_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
        map.addSource(AREA_FORECAST_RISK_B_SOURCE_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
        map.addSource(AREA_TIMELINE_ORIGIN_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.origins ?? EMPTY_FEATURE_COLLECTION })
        map.addSource(AREA_FORECAST_PATH_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.paths ?? { type: 'FeatureCollection', features: [] } })
        map.addSource(AREA_FORECAST_FRONT_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.fronts ?? { type: 'FeatureCollection', features: [] } })
        map.addLayer({ id: 'my-area-district-fill', type: 'fill', source: DISTRICT_SOURCE_ID, paint: { 'fill-color': '#4edea3', 'fill-opacity': 0.08 } })
        const tierColorExpression = ['match', ['get', 'riskLevel'], ...AREA_RISK_LEVELS.flatMap((level) => [level, AREA_RISK_COLORS[level]]), 'rgba(0,0,0,0)']
        map.addLayer({
          id: 'my-area-forecast-context-fill',
          type: 'fill',
          source: AREA_FORECAST_CONTEXT_SOURCE_ID,
          layout: { visibility: initialAreaImpactVisibility },
          paint: { 'fill-color': ['match', ['get', 'riskLevel'], 'reach', '#ef4444', tierColorExpression], 'fill-opacity': ['coalesce', ['get', 'fillOpacity'], 0] },
        })
        map.addLayer({
          id: 'my-area-forecast-context-line',
          type: 'line',
          source: AREA_FORECAST_CONTEXT_SOURCE_ID,
          layout: { visibility: initialAreaImpactVisibility },
          // Nominal-reach outline: red, how far the selected day's reach goes.
          paint: { 'line-color': ['match', ['get', 'riskLevel'], 'reach', '#ef4444', tierColorExpression], 'line-width': ['match', ['get', 'riskLevel'], 'reach', 2.4, 1], 'line-opacity': ['coalesce', ['get', 'lineOpacity'], 0], 'line-dasharray': [3, 2] },
        })
        if (map.getStyle?.()?.glyphs) {
          map.addLayer({
            id: 'my-area-forecast-reach-label',
            type: 'symbol',
            source: AREA_FORECAST_CONTEXT_SOURCE_ID,
            filter: ['all', ['==', ['get', 'riskLevel'], 'reach'], ['has', 'label']],
            layout: {
              visibility: initialAreaImpactVisibility,
              'symbol-placement': 'line',
              'symbol-spacing': 280,
              'text-field': ['get', 'label'],
              'text-font': ['Noto Sans Bold'],
              'text-size': 11,
              'text-keep-upright': true,
            },
            paint: { 'text-color': '#fee2e2', 'text-halo-color': '#7f1d1d', 'text-halo-width': 1.8 },
          })
        }
        const areaRiskBuffers = [
          { sourceId: AREA_FORECAST_RISK_SOURCE_ID, suffix: '' },
          { sourceId: AREA_FORECAST_RISK_B_SOURCE_ID, suffix: '-b' },
        ]
        for (const buffer of areaRiskBuffers) {
          for (const riskLevel of AREA_RISK_LEVELS) {
            const color = AREA_RISK_COLORS[riskLevel]
            map.addLayer({
              id: `my-area-forecast-risk-${riskLevel}${buffer.suffix}`,
              type: 'fill',
              source: buffer.sourceId,
              filter: ['==', ['get', 'riskLevel'], riskLevel],
              layout: { visibility: initialAreaImpactVisibility },
              paint: {
                'fill-color': color,
                'fill-opacity': ['coalesce', ['get', 'fillOpacity'], 0],
                'fill-opacity-transition': { duration: 0 },
              },
            })
            map.addLayer({
              id: `my-area-forecast-risk-${riskLevel}-outline${buffer.suffix}`,
              type: 'line',
              source: buffer.sourceId,
              filter: ['==', ['get', 'riskLevel'], riskLevel],
              layout: { visibility: initialAreaImpactVisibility },
              paint: {
                'line-color': color,
                'line-width': 0.8,
                'line-opacity': ['coalesce', ['get', 'lineOpacity'], 0],
                'line-opacity-transition': { duration: 0 },
              },
            })
            const fillLayer = `my-area-forecast-risk-${riskLevel}${buffer.suffix}`
            map.on('mouseenter', fillLayer, () => { map.getCanvas().style.cursor = 'pointer' })
            map.on('mouseleave', fillLayer, () => { map.getCanvas().style.cursor = '' })
            map.on('click', fillLayer, (event) => {
              const properties = event.features?.[0]?.properties
              if (!showAreaImpactRef.current || !properties || properties.date !== areaForecastVisualizationRef.current?.date) return
              const root = document.createElement('div')
              root.className = 'max-w-64 space-y-1 text-xs'
              for (const text of monitoringZoneDetails(properties, districtFeatureRef.current?.properties?.shapeName)) {
                const row = document.createElement('div')
                row.textContent = text
                root.appendChild(row)
              }
              zonePopupRef.current?.remove()
              zonePopupRef.current = new maplibregl.Popup({ closeButton: true, closeOnClick: true })
                .setLngLat(event.lngLat).setDOMContent(root).addTo(map)
            })
          }
        }
        try {
          riskFieldRef.current = createRiskFieldRenderer(map, { sourceId: 'geo-my-area-risk-field', layerId: 'my-area-risk-field', beforeId: 'my-area-district-outline', reduceMotion: () => reduceMotionRef.current })
          riskFieldRef.current.setModel(riskFieldInputRef.current.model, riskFieldInputRef.current.index)
          riskFieldRef.current.setVisible(showAreaImpactRef.current && impactLayerRef.current === IMPACT_LAYER.RISK)
        } catch (error) {
          console.warn('Risk field surface unavailable', error)
          riskFieldRef.current = null
        }
        // Trajectory flow: particles travelling along the selected date's
        // backend direction lines (shared with the Outbreak Map).
        map.addSource(AREA_FLOW_SOURCE_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
        map.addLayer({ id: 'my-area-flow-glow', type: 'circle', source: AREA_FLOW_SOURCE_ID, layout: { visibility: initialAreaImpactVisibility }, paint: { 'circle-radius': 9, 'circle-color': '#a78bfa', 'circle-blur': 1, 'circle-opacity': ['*', 0.55, ['get', 'fade']] } })
        map.addLayer({ id: 'my-area-flow', type: 'circle', source: AREA_FLOW_SOURCE_ID, layout: { visibility: initialAreaImpactVisibility }, paint: { 'circle-radius': 3.4, 'circle-color': '#6d28d9', 'circle-stroke-color': '#ede9fe', 'circle-stroke-width': 1, 'circle-opacity': ['get', 'fade'], 'circle-stroke-opacity': ['get', 'fade'] } })
        map.addSource(AREA_FLOW_NEW_SOURCE_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
        map.addLayer({ id: 'my-area-flow-new-glow', type: 'circle', source: AREA_FLOW_NEW_SOURCE_ID, layout: { visibility: initialAreaImpactVisibility }, paint: { 'circle-radius': 9, 'circle-color': '#f9a8d4', 'circle-blur': 1, 'circle-opacity': ['*', 0.55, ['get', 'fade']] } })
        map.addLayer({ id: 'my-area-flow-new', type: 'circle', source: AREA_FLOW_NEW_SOURCE_ID, layout: { visibility: initialAreaImpactVisibility }, paint: { 'circle-radius': 3.4, 'circle-color': '#be185d', 'circle-stroke-color': '#fce7f3', 'circle-stroke-width': 1, 'circle-opacity': ['get', 'fade'], 'circle-stroke-opacity': ['get', 'fade'] } })
        riskFaderRef.current = createRiskZoneCrossFader({
          map,
          reduceMotion: () => reduceMotionRef.current,
          buffers: areaRiskBuffers.map((buffer) => ({
            sourceId: buffer.sourceId,
            layers: AREA_RISK_LEVELS.flatMap((riskLevel) => [
              { id: `my-area-forecast-risk-${riskLevel}${buffer.suffix}`, property: 'fill-opacity', role: 'fill', base: ['coalesce', ['get', 'fillOpacity'], 0] },
              { id: `my-area-forecast-risk-${riskLevel}-outline${buffer.suffix}`, property: 'line-opacity', role: 'line', base: ['coalesce', ['get', 'lineOpacity'], 0] },
            ]),
          })),
        })
        riskFaderRef.current.show(initialAreaForecast?.riskZones ?? EMPTY_FEATURE_COLLECTION)
        currentCorridorsRef.current = initialAreaForecast
        map.addLayer({ id: 'my-area-district-glow', type: 'line', source: DISTRICT_SOURCE_ID, paint: { 'line-color': '#4edea3', 'line-width': 8, 'line-blur': 5, 'line-opacity': 0.4 } })
        map.addLayer({ id: 'my-area-district-outline', type: 'line', source: DISTRICT_SOURCE_ID, paint: { 'line-color': '#4edea3', 'line-width': 2.4, 'line-opacity': 0.95 } })
        // Subtle wash outside the vet's district (above the risk surface,
        // under every marker): the district reads first, neighbours stay visible.
        map.addSource(DISTRICT_OUTSIDE_SOURCE_ID, { type: 'geojson', data: outsideDistrictMask(initialDistrictFeature) })
        map.addLayer({ id: DISTRICT_OUTSIDE_LAYER_ID, type: 'fill', source: DISTRICT_OUTSIDE_SOURCE_ID, paint: { 'fill-color': '#f1f5f9', 'fill-opacity': 0.35 } })
        map.addLayer({
          id: 'my-area-forecast-path-glow',
          type: 'line',
          source: AREA_FORECAST_PATH_SOURCE_ID,
          layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'none' },
          paint: { 'line-color': ['case', ['boolean', ['get', 'possibleNewCase'], false], NEW_OUTBREAK_PINK, AREA_RISK_COLORS.purple], 'line-width': 12, 'line-blur': 5, 'line-opacity': 0.3 },
        })
        map.addLayer({
          id: 'my-area-forecast-path',
          type: 'line',
          source: AREA_FORECAST_PATH_SOURCE_ID,
          layout: { 'line-cap': 'round', 'line-join': 'round', visibility: initialAreaImpactVisibility },
          paint: { 'line-color': ['case', ['boolean', ['get', 'possibleNewCase'], false], NEW_OUTBREAK_PINK, '#8B5CF6'], 'line-width': 3.6, 'line-opacity': 0.95 },
        })
        // Where and how far: "Day N · X km" along each backend direction line.
        if (map.getStyle?.()?.glyphs) {
          map.addLayer({
            id: 'my-area-forecast-path-label',
            type: 'symbol',
            source: AREA_FORECAST_PATH_SOURCE_ID,
            layout: {
              visibility: initialAreaImpactVisibility,
              'symbol-placement': 'line-center',
              'text-field': ['coalesce', ['get', 'pathLabel'], ''],
              'text-font': ['Noto Sans Bold'],
              'text-size': 11,
              'text-offset': [0, -0.9],
              'text-keep-upright': true,
            },
            paint: { 'text-color': '#f5f3ff', 'text-halo-color': '#4c1d95', 'text-halo-width': 1.8 },
          })
        }
        map.addLayer({
          id: 'my-area-forecast-path-flow',
          type: 'line',
          source: AREA_FORECAST_PATH_SOURCE_ID,
          layout: { 'line-cap': 'butt', 'line-join': 'round', visibility: 'none' },
          paint: { 'line-color': '#F3E8FF', 'line-width': 1.5, 'line-opacity': 0.72, 'line-dasharray': [0, 4, 3] },
        })
        map.addLayer({
          id: 'my-area-forecast-front-glow',
          type: 'circle',
          source: AREA_FORECAST_FRONT_SOURCE_ID,
          layout: { visibility: 'none' },
          paint: { 'circle-radius': 10, 'circle-color': ['case', ['boolean', ['get', 'possibleNewCase'], false], NEW_OUTBREAK_PINK, AREA_RISK_COLORS.purple], 'circle-blur': 0.8, 'circle-opacity': 0.3 },
        })
        map.addLayer({
          id: 'my-area-forecast-front',
          type: 'circle',
          source: AREA_FORECAST_FRONT_SOURCE_ID,
          layout: { visibility: 'none' },
          paint: { 'circle-radius': 5.5, 'circle-color': AREA_RISK_COLORS.purpleAccent, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.2, 'circle-opacity': 0.98 },
        })
        ensureDirectionArrowImage(map)
        if (!map.hasImage?.(NEW_OUTBREAK_ARROW_ICON_ID)) map.addImage(NEW_OUTBREAK_ARROW_ICON_ID, buildDirectionArrowIcon(22, [252, 231, 243], [190, 24, 93]), { pixelRatio: 1 })
        map.addLayer({
          id: 'my-area-forecast-arrow',
          type: 'symbol',
          source: AREA_FORECAST_FRONT_SOURCE_ID,
          layout: { ...directionArrowLayout(initialAreaImpactVisibility), 'icon-image': ['case', ['boolean', ['get', 'possibleNewCase'], false], NEW_OUTBREAK_ARROW_ICON_ID, DIRECTION_ARROW_ICON_ID] },
          paint: { 'icon-opacity': 0.95 },
        })
        map.addLayer({
          id: 'my-area-timeline-origin',
          type: 'circle',
          source: AREA_TIMELINE_ORIGIN_SOURCE_ID,
          layout: { visibility: initialAreaImpactVisibility },
          paint: {
            'circle-radius': 6.5,
            'circle-color': 'rgba(0,0,0,0)',
            'circle-stroke-color': EXISTING_OUTBREAK_RED,
            'circle-stroke-width': 2.4,
            'circle-stroke-opacity': 0.95,
          },
        })
        // "Day N · near <place>" at each path front (basemap OpenStreetMap
        // places, re-resolved after a camera move or new tiles).
        const initialTrajectoryVisibility = showAreaImpactRef.current && impactLayerRef.current === IMPACT_LAYER.TRAJECTORY ? 'visible' : 'none'
        map.addSource(AREA_TRAJECTORY_LABEL_SOURCE_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
        addTrajectoryLabelLayer(map, { id: AREA_TRAJECTORY_LABEL_LAYER_ID, sourceId: AREA_TRAJECTORY_LABEL_SOURCE_ID, visibility: initialTrajectoryVisibility })
        let relabelQueued = false
        const queueRelabel = () => {
          if (relabelQueued) return
          relabelQueued = true
          requestAnimationFrame(() => {
            relabelQueued = false
            const viz = areaForecastVisualizationRef.current
            map.getSource(AREA_TRAJECTORY_LABEL_SOURCE_ID)?.setData(viz
              ? buildTrajectoryLabels({ fronts: viz.fronts, origins: viz.origins, findPlace: (point) => nearestMappedPlace(map, point) })
              : EMPTY_FEATURE_COLLECTION)
          })
        }
        relabelTrajectoryRef.current = queueRelabel
        map.on('moveend', queueRelabel)
        map.on('sourcedata', (e) => { if (e.isSourceLoaded && e.sourceId === basemapPlaceSourceId(map)) queueRelabel() })
        queueRelabel()

        let hoverPopup = null
        let pinnedPopup = null
        for (const layerId of AREA_CORRIDOR_INTERACTIVE_LAYER_IDS) {
          map.on('mousemove', layerId, (event) => {
            const feature = event.features?.[0]
            map.getCanvas().style.cursor = 'pointer'
            if (!feature || pinnedPopup) return
            if (!hoverPopup) hoverPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 })
            hoverPopup.setLngLat(event.lngLat).setDOMContent(corridorTooltipDom(feature.properties, false)).addTo(map)
          })
          map.on('mouseleave', layerId, () => {
            map.getCanvas().style.cursor = ''
            hoverPopup?.remove()
          })
          map.on('click', layerId, (event) => {
            const feature = event.features?.[0]
            if (!feature) return
            hoverPopup?.remove()
            pinnedPopup?.remove()
            pinnedPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, offset: 12 })
              .setLngLat(event.lngLat)
              .setDOMContent(corridorTooltipDom(feature.properties, true))
              .addTo(map)
            pinnedPopup.on('close', () => { pinnedPopup = null })
            if (feature.properties?.anchorId) onFocusSourceRef.current?.(feature.properties.anchorId)
          })
        }
        map.addLayer({
          id: 'my-area-forecast-selected-risk-outline',
          type: 'line',
          source: AREA_FORECAST_RISK_SOURCE_ID,
          filter: ['==', ['get', 'anchorId'], '__none__'],
          layout: { visibility: initialAreaImpactVisibility },
          paint: { 'line-color': '#f5d0fe', 'line-width': 2.8, 'line-opacity': 0.8, 'line-blur': 0.3 },
        })
        map.addLayer({
          id: 'my-area-forecast-selected-path',
          type: 'line',
          source: AREA_FORECAST_PATH_SOURCE_ID,
          filter: ['==', ['get', 'anchorId'], '__none__'],
          layout: { 'line-cap': 'round', 'line-join': 'round', visibility: initialAreaImpactVisibility },
          paint: { 'line-color': '#f5d0fe', 'line-width': 5.5, 'line-opacity': 1 },
        })

        map.addSource(CELLS_SOURCE_ID, { type: 'geojson', data: initialCellsFC })
        map.addLayer({
          id: 'my-area-cells-circle',
          type: 'circle',
          source: CELLS_SOURCE_ID,
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 5, 11, 8, 14, 12],
            'circle-color': riskTierColorExpression(initialRiskStats),
            'circle-opacity': 0.32,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#0e1511',
            'circle-color-transition': { duration: reduceMotion ? 0 : 320 },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : 320 },
          },
        })

        // The static risk score/color never changes with day. This second
        // source only emphasizes cells falling inside the current genuine
        // nominal-reach visualization; it never recolors or rescales them.
        map.addSource(ACTIVE_CELLS_SOURCE_ID, { type: 'geojson', data: initialActiveCellsFC })
        map.addLayer({
          id: 'my-area-active-cells-circle',
          type: 'circle',
          source: ACTIVE_CELLS_SOURCE_ID,
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 6, 11, 9, 14, 13],
            'circle-color': riskTierColorExpression(initialRiskStats),
            'circle-opacity': 0.88,
            'circle-stroke-width': 1.5,
            'circle-stroke-color': '#f8fafc',
            'circle-stroke-opacity': 0.45,
            'circle-color-transition': { duration: reduceMotion ? 0 : 320 },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : 320 },
          },
        })

        map.addSource(FARM_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
        map.addSource(SOURCES_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
        map.addSource(REACH_RING_SOURCE_ID, { type: 'geojson', data: emptyReachRingFeatureCollection() })
        map.addSource(OBSERVED_CASES_SOURCE_ID, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: initialObservedCaseFeatures },
        })

        // Nominal-reach ring first (under the markers), same teal
        // treatment as Page 1's ring -- never a risk color.
        map.addLayer({
          id: 'my-area-reach-ring-fill', type: 'fill', source: REACH_RING_SOURCE_ID,
          paint: { 'fill-color': '#14b8a6', 'fill-opacity': 0.04 },
        })
        map.addLayer({
          id: 'my-area-reach-ring-line', type: 'line', source: REACH_RING_SOURCE_ID,
          paint: { 'line-color': '#14b8a6', 'line-width': 1.5, 'line-dasharray': [2, 2], 'line-opacity': 0.85 },
        })

        // Registered district farms: white = no verified report, red ring =
        // a real verified report. Being inside a scored area never colours a
        // farm as infected.
        map.addSource(REGISTERED_FARMS_SOURCE_ID, { type: 'geojson', data: registeredFarmFeaturesRef.current ?? EMPTY_FEATURE_COLLECTION })
        map.addSource(PENDING_CASES_SOURCE_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
        map.addLayer({
          id: 'my-area-registered-farms', type: 'circle', source: REGISTERED_FARMS_SOURCE_ID,
          paint: {
            'circle-radius': 4.5,
            'circle-color': '#f8fafc',
            'circle-stroke-color': ['case', ['get', 'reporting'], '#ef4444', '#334155'],
            'circle-stroke-width': ['case', ['get', 'reporting'], 2.5, 1.5],
            'circle-opacity': 0.95,
          },
        })
        map.addLayer({
          id: 'my-area-pending-cases', type: 'circle', source: PENDING_CASES_SOURCE_ID,
          layout: { visibility: 'none' },
          paint: { 'circle-radius': 7, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#d97706', 'circle-stroke-width': 2 },
        })
        map.on('click', 'my-area-registered-farms', (event) => {
          const properties = event.features?.[0]?.properties ?? {}
          onFocusFarmRef.current?.(properties.farmId)
          const root = document.createElement('div')
          root.className = 'space-y-1 text-xs'
          for (const value of [properties.label, properties.statusLabel, properties.caseCount > 0 ? `${properties.caseCount} verified report(s)` : 'No verified report for this disease']) {
            const row = document.createElement('div')
            row.textContent = value
            root.appendChild(row)
          }
          new maplibregl.Popup({ closeButton: true, closeOnClick: true }).setLngLat(event.features[0].geometry.coordinates).setDOMContent(root).addTo(map)
        })
        map.on('mouseenter', 'my-area-registered-farms', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'my-area-registered-farms', () => { map.getCanvas().style.cursor = '' })

        map.addSource(POSSIBLE_CASES_SOURCE_ID, { type: 'geojson', data: possibleCaseFeaturesRef.current ?? EMPTY_FEATURE_COLLECTION })
        const possibleVisibility = showAreaImpactRef.current ? 'visible' : 'none'
        map.addLayer({
          id: 'my-area-possible-case-dot', type: 'circle', source: POSSIBLE_CASES_SOURCE_ID, layout: { visibility: possibleVisibility },
          paint: {
            'circle-radius': ['case', ['boolean', ['get', 'newToday'], false], 17, 12],
            'circle-color': NEW_OUTBREAK_PINK,
            'circle-blur': 0.9,
            'circle-opacity': ['case', ['boolean', ['get', 'newToday'], false], 0.5, 0.28],
          },
        })
        map.addLayer({
          id: 'my-area-possible-case-ring', type: 'circle', source: POSSIBLE_CASES_SOURCE_ID, layout: { visibility: possibleVisibility },
          paint: {
            'circle-radius': ['case', ['boolean', ['get', 'newToday'], false], 8.5, 7],
            'circle-color': NEW_OUTBREAK_PINK,
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2,
            'circle-radius-transition': { duration: reduceMotionRef.current ? 0 : 400 },
          },
        })
        if (map.getStyle?.()?.glyphs) {
          map.addLayer({
            id: 'my-area-possible-case-label', type: 'symbol', source: POSSIBLE_CASES_SOURCE_ID,
            layout: {
              visibility: possibleVisibility,
              'text-field': ['get', 'label'],
              'text-font': ['Noto Sans Bold'],
              'text-size': 10.5,
              'text-variable-anchor': ['top', 'bottom', 'left', 'right'],
              'text-radial-offset': 1.2,
              'text-allow-overlap': false,
            },
            paint: { 'text-color': '#9d174d', 'text-halo-color': '#fdf2f8', 'text-halo-width': 1.8 },
          })
        }
        let outbreakHover = null
        const outbreakCard = (feature, pinned) => new maplibregl.Popup({ closeButton: pinned, closeOnClick: pinned, offset: 14, className: 'geo-case-hover geo-cluster-popup' })
          .setLngLat(feature.geometry.coordinates).setDOMContent(newOutbreakDom(feature.properties ?? {}, sourcePlaceRef.current))
        map.on('mousemove', 'my-area-possible-case-ring', (event) => {
          const feature = event.features?.[0]
          map.getCanvas().style.cursor = 'pointer'
          if (!feature) return
          outbreakHover?.remove()
          outbreakHover = outbreakCard(feature, false).addTo(map)
        })
        map.on('mouseleave', 'my-area-possible-case-ring', () => {
          map.getCanvas().style.cursor = ''
          outbreakHover?.remove()
          outbreakHover = null
        })
        map.on('click', 'my-area-possible-case-ring', (event) => {
          const feature = event.features?.[0]
          if (!feature) return
          outbreakHover?.remove()
          outbreakCard(feature, true).addTo(map)
        })
        // Place names for the source cards: only places the basemap has
        // loaded near the source (within 15 km), never a guessed name.
        const knownPlaces = {}
        sourcePlaceRef.current = (sourceId) => knownPlaces[sourceId] ?? null
        map.on('idle', () => {
          const report = onSourcePlacesRef.current
          const origins = areaForecastVisualizationRef.current?.origins?.features ?? []
          const farms = registeredFarmFeaturesRef.current?.features ?? []
          if (!report || (origins.length === 0 && farms.length === 0)) return
          const found = {}
          for (const feature of origins) {
            const sourceId = feature?.properties?.sourceId
            const place = sourceId ? nearestMappedPlace(map, feature.geometry?.coordinates, { maxKm: 15 }) : null
            if (place?.name) found[sourceId] = place.name
          }
          for (const feature of possibleCaseFeaturesRef.current?.features ?? []) {
            const outbreakId = feature?.properties?.id
            const place = outbreakId ? nearestMappedPlace(map, feature.geometry?.coordinates, { maxKm: 15 }) : null
            if (place?.name) found[outbreakId] = place.name
          }
          // Registered farms too ("farm:<id>"), for the farm list location.
          for (const feature of farms) {
            const farmId = feature?.properties?.farmId
            const place = farmId ? nearestMappedPlace(map, feature.geometry?.coordinates, { maxKm: 15 }) : null
            if (place?.name) found[`farm:${farmId}`] = place.name
          }
          Object.assign(knownPlaces, found)
          if (Object.keys(found).length) report(found)
        })

        map.addLayer({ id: 'my-area-sources-symbol', type: 'symbol', source: SOURCES_SOURCE_ID, layout: sourceIconLayout() })
        map.addLayer({ id: 'my-area-farm-symbol', type: 'symbol', source: FARM_SOURCE_ID, layout: farmMarkerIconLayout() })
        map.addLayer({
          id: 'my-area-observed-cases-pulse',
          type: 'circle',
          source: OBSERVED_CASES_SOURCE_ID,
          // Only recent (<=14 d) reports pulse; older ones stay static grey.
          filter: ['==', ['get', 'ageClass'], 'RECENT'],
          paint: {
            ...nationalSourceAmbientPulsePaint(false),
            'circle-radius-transition': { duration: reduceMotion ? 0 : NATIONAL_SOURCES_PULSE_CYCLE_MS / 2 },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : NATIONAL_SOURCES_PULSE_CYCLE_MS / 2 },
          },
        })
        map.addLayer({
          id: 'my-area-observed-cases-core',
          type: 'circle',
          source: OBSERVED_CASES_SOURCE_ID,
          paint: {
            'circle-radius': 6,
            // Report-date age (adapters/caseAge.js): <=30 d red, older grey,
            // unknown white -- set by the page per reference date.
            'circle-color': ['match', ['get', 'ageClass'], 'RECENT', CASE_AGE_COLOR.RECENT, 'OLDER', CASE_AGE_COLOR.OLDER, CASE_AGE_COLOR.DATE_UNKNOWN],
            'circle-stroke-color': ['match', ['get', 'ageClass'], 'RECENT', '#fff1f2', 'OLDER', '#f8fafc', '#334155'],
            'circle-stroke-width': 1.5,
            'circle-opacity': 0.98,
          },
        })
        map.addLayer({
          id: 'my-area-observed-cases-selected',
          type: 'circle',
          source: OBSERVED_CASES_SOURCE_ID,
          filter: ['==', ['get', 'anchorId'], '__none__'],
          paint: {
            'circle-radius': 11,
            'circle-color': 'rgba(0,0,0,0)',
            'circle-stroke-color': '#4edea3',
            'circle-stroke-width': 2.5,
            'circle-stroke-opacity': 0.95,
          },
        })

        map.on('click', 'my-area-observed-cases-core', (event) => {
          const feature = event.features?.[0]
          const properties = feature?.properties ?? {}
          const root = document.createElement('div')
          root.className = 'space-y-1 text-xs'
          for (const [label, value] of caseDetailRows(properties, districtFeatureRef.current?.properties?.shapeName)) {
            const row = document.createElement('div')
            const key = document.createElement('span')
            key.className = 'text-slate-400'
            key.textContent = `${label}: `
            row.appendChild(key)
            row.appendChild(document.createTextNode(value))
            root.appendChild(row)
          }
          const [lon, lat] = feature?.geometry?.coordinates ?? []
          if (Number.isFinite(lon) && Number.isFinite(lat)) {
            const row = document.createElement('div')
            row.className = 'text-slate-400'
            row.textContent = `Farm GPS: ${lat.toFixed(4)}, ${lon.toFixed(4)}`
            root.appendChild(row)
          }
          onSelectCaseRef.current?.(properties.anchorId ?? null)
          new maplibregl.Popup({ closeButton: true, closeOnClick: true, className: 'geo-case-hover geo-cluster-popup' })
            .setLngLat(feature.geometry.coordinates)
            .setDOMContent(root)
            .addTo(map)
        })
        map.on('mouseenter', 'my-area-observed-cases-core', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'my-area-observed-cases-core', () => { map.getCanvas().style.cursor = '' })

        // Risk Zones hover card: the selected day's backend score at the
        // cursor, the cases behind it, the trend and the nearest place
        // (same card as the Outbreak Map). Case markers keep their own popup.
        const riskHoverPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 14, maxWidth: '300px', className: 'geo-case-hover geo-risk-hover' })
        let riskHoverAt = null
        const casePlaces = new Map()
        const casePlace = (coordinates) => {
          const key = coordinates.join(',')
          if (!casePlaces.has(key)) {
            const place = nearestMappedPlace(map, coordinates)
            if (!place) return null
            casePlaces.set(key, place)
          }
          return casePlaces.get(key)
        }
        const refreshRiskHover = () => {
          const active = riskHoverAt && showAreaImpactRef.current && impactLayerRef.current === IMPACT_LAYER.RISK
          const probe = active ? riskFieldRef.current?.probe(riskHoverAt.lng, riskHoverAt.lat) : null
          if (!probe) {
            riskHoverPopup.remove()
            return
          }
          const point = [riskHoverAt.lng, riskHoverAt.lat]
          const district = districtFeatureRef.current
          riskHoverPopup.setLngLat(riskHoverAt).setHTML(riskHoverHtml(probe, {
            pointPlace: nearestMappedPlace(map, point),
            district: district && isPointInsideDistrictFeature(point, district) ? district.properties?.shapeName ?? null : null,
            casePlace,
          })).addTo(map)
        }
        refreshRiskHoverRef.current = refreshRiskHover
        map.on('mousemove', (e) => {
          const markerLayers = ['my-area-observed-cases-core', 'my-area-registered-farms', 'my-area-timeline-origin', 'my-area-possible-case-ring'].filter((id) => map.getLayer(id))
          const onMarker = markerLayers.length > 0 && map.queryRenderedFeatures(e.point, { layers: markerLayers }).length > 0
          riskHoverAt = onMarker ? null : e.lngLat
          refreshRiskHover()
        })
        map.getCanvas().addEventListener('mouseleave', () => {
          riskHoverAt = null
          riskHoverPopup.remove()
        })

        if (!reduceMotion) {
          let expanded = false
          let lastToggle = performance.now()
          const pulse = (now) => {
            if (now - lastToggle >= NATIONAL_SOURCES_PULSE_CYCLE_MS / 2) {
              expanded = !expanded
              lastToggle = now
              const paint = nationalSourceAmbientPulsePaint(expanded)
              map.setPaintProperty('my-area-observed-cases-pulse', 'circle-radius', paint['circle-radius'])
              map.setPaintProperty('my-area-observed-cases-pulse', 'circle-opacity', paint['circle-opacity'])
            }
            observedPulseAnimRef.current = requestAnimationFrame(pulse)
          }
          observedPulseAnimRef.current = requestAnimationFrame(pulse)
        }
      })
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn('MapLibre could not initialize on My Area (falling back):', err)
      if (!failedRef.current) {
        failedRef.current = true
        setMapIssue('fatal')
        onMapUnavailable?.()
      }
    }

    return () => {
      if (reachRingAnimRef.current) cancelAnimationFrame(reachRingAnimRef.current)
      if (observedPulseAnimRef.current) cancelAnimationFrame(observedPulseAnimRef.current)
      riskFaderRef.current?.destroy()
      riskFieldRef.current?.destroy()
      riskFieldRef.current = null
      riskFaderRef.current = null
      revealCancelRef.current?.()
      revealCancelRef.current = null
      resizeObserver?.disconnect()
      map?.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- farm + district: one camera fit per real area scope ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return

    const hasFarmPoint = area && area.locationStatus === 'VALID' && typeof area.latitude === 'number' && typeof area.longitude === 'number'
    const farmFC = hasFarmPoint
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [area.longitude, area.latitude] }, properties: { farmId: area.farmId } }] }
      : { type: 'FeatureCollection', features: [] }
    map.getSource(FARM_SOURCE_ID)?.setData(farmFC)
    map.getSource(DISTRICT_SOURCE_ID)?.setData(districtFeature ? { type: 'FeatureCollection', features: [districtFeature] } : { type: 'FeatureCollection', features: [] })
    map.getSource(DISTRICT_OUTSIDE_SOURCE_ID)?.setData(outsideDistrictMask(districtFeature))

    // Wait for the real ADM2 polygon and fit it exactly once. Origin,
    // timeline, clinical refresh, risk, and reach updates never enter the
    // area-scope key and therefore can never move this camera.
    const districtBounds = districtFeature ? computeFeatureBounds(districtFeature) : null
    const districtIdentity = districtFeature?.properties?.shapeName ?? districtFeature?.properties?.shapeID ?? null
    const areaScopeKey = districtBounds && districtIdentity ? `${area?.farmId ?? 'district'}::${districtIdentity}` : null
    if (areaScopeKey && areaScopeKey !== lastFitAreaScopeRef.current) {
      lastFitAreaScopeRef.current = areaScopeKey
      districtFitRef.current = districtBounds
      userMovedCameraRef.current = false
      fitMapToBounds(map, districtBounds, {
        reduceMotion,
        durationMs: 900,
        padding: getMyAreaMapPadding(containerRef.current?.clientWidth ?? 0),
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area?.farmId, area?.latitude, area?.longitude, area?.locationStatus, districtFeature, mapLoaded])

  // ---- selected-origin sources/risk: data-only, camera stays fixed ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return

    const sourcesFC = buildSourcesFeatureCollection({ type: 'FeatureCollection', features: sourceFeatures })
    map.getSource(SOURCES_SOURCE_ID)?.setData(sourcesFC)

    // GEO-MY-AREA-STITCH-16 Section 10: the real per-cell risk surface for
    // the SAME selected origin (LSD only -- `cellFeatures` is always `[]`
    // for FMD, `MyAreaPage.jsx`'s `focus.status` gate). Updated alongside
    // sources since both come from the exact same `useSelectedOutbreakFrames`
    // fetch for this origin; never a separate/second scientific request.
    const cellsFC = buildCellsFeatureCollection(cellFeatures)
    const activeCellsFC = buildCellsFeatureCollection(activeCellFeatures)
    map.getSource(CELLS_SOURCE_ID)?.setData(cellsFC)
    map.getSource(ACTIVE_CELLS_SOURCE_ID)?.setData(activeCellsFC)
    if (riskColorReferenceFeatures.length > 0) {
      const color = riskTierColorExpression(computeRiskTierStats(riskColorReferenceFeatures))
      map.setPaintProperty('my-area-cells-circle', 'circle-color', color)
      map.setPaintProperty('my-area-active-cells-circle', 'circle-color', color)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFeatures, cellFeatures, activeCellFeatures, riskColorReferenceFeatures, selectedOriginId, mapLoaded])

  // Verified observations never depend on forecast day, reach, risk, or
  // origin. Their source updates only when genuine case data changes.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    map.getSource(OBSERVED_CASES_SOURCE_ID)?.setData({ type: 'FeatureCollection', features: observedCaseFeatures })
  }, [observedCaseFeatures, mapLoaded])

  // The one Page-2 forecast snapshot updates three persistent GeoJSON
  // sources. Timeline ticks never recreate MapLibre and never fetch data.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    // Phase 4: static context set in place; reach-limited zones cross-fade
    // between exact backend frames (an identical plateau frame is left
    // untouched); corridors reveal along their own backend geometry. A newer
    // frame supersedes a running transition. Never moves the camera.
    map.getSource(AREA_FORECAST_CONTEXT_SOURCE_ID)?.setData(areaForecastVisualization?.contextZones ?? EMPTY_FEATURE_COLLECTION)
    map.getSource(AREA_TIMELINE_ORIGIN_SOURCE_ID)?.setData(areaForecastVisualization?.origins ?? EMPTY_FEATURE_COLLECTION)
    riskFaderRef.current?.show(areaForecastVisualization?.riskZones ?? EMPTY_FEATURE_COLLECTION)
    const pathSource = map.getSource(AREA_FORECAST_PATH_SOURCE_ID)
    const frontSource = map.getSource(AREA_FORECAST_FRONT_SOURCE_ID)
    revealCancelRef.current?.()
    const previous = currentCorridorsRef.current
    currentCorridorsRef.current = areaForecastVisualization
    revealCancelRef.current = runCorridorReveal({
      previous: previous && previous !== areaForecastVisualization ? previous : null,
      next: { paths: areaForecastVisualization?.paths, fronts: areaForecastVisualization?.fronts },
      reduceMotion,
      apply: ({ paths, fronts }) => {
        pathSource?.setData(paths)
        frontSource?.setData(fronts)
      },
    })

    relabelTrajectoryRef.current?.()
  }, [areaForecastVisualization, showAreaImpact, mapLoaded])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    map.getSource(POSSIBLE_CASES_SOURCE_ID)?.setData(possibleCaseFeatures ?? EMPTY_FEATURE_COLLECTION)
    for (const layerId of POSSIBLE_CASE_LAYER_IDS) if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', showAreaImpact ? 'visible' : 'none')
  }, [possibleCaseFeatures, showAreaImpact, mapLoaded])

  // One visibility decision per Future Impact view (Cases / Risk Zones /
  // Trajectory), like the Outbreak Map's modes. The old reach outline and the
  // quartile zone polygons are never drawn: the risk surface is the one layer.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const set = (ids, on) => {
      for (const layerId of ids) if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', on ? 'visible' : 'none')
    }
    const visible = impactLayerVisibility(showAreaImpact, impactLayer)
    set([...AREA_RISK_LAYER_IDS, 'my-area-forecast-path-label'], false)
    set(AREA_TRAJECTORY_LAYER_IDS, visible.trajectory)
    set(['my-area-timeline-origin'], visible.modelSources)
    riskFieldRef.current?.setVisible(visible.riskSurface)
    refreshRiskHoverRef.current?.()
  }, [showAreaImpact, impactLayer, areaForecastVisualization, mapLoaded])

  useEffect(() => {
    if (!loadedRef.current) return
    riskFieldRef.current?.setModel(riskFieldModel, riskFieldIndex)
    refreshRiskHoverRef.current?.() // a new day: the open hover card shows that day
  }, [riskFieldModel, riskFieldIndex, mapLoaded])
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !showAreaImpact || impactLayer !== IMPACT_LAYER.TRAJECTORY || reduceMotion) return undefined
    const pathsWhere = (pink) => () => {
      const paths = areaForecastVisualizationRef.current?.paths
      return paths ? { ...paths, features: paths.features.filter((f) => Boolean(f.properties?.possibleNewCase) === pink) } : null
    }
    const stopExisting = startTrajectoryFlow(map, pathsWhere(false), { sourceId: AREA_FLOW_SOURCE_ID })
    const stopNew = startTrajectoryFlow(map, pathsWhere(true), { sourceId: AREA_FLOW_NEW_SOURCE_ID })
    return () => { stopExisting?.(); stopNew?.() }
  }, [showAreaImpact, impactLayer, reduceMotion, mapLoaded])

  // A selected case stays clear; the other case markers fade (never hidden).
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const style = caseFocusStyle(focusedCaseId)
    if (map.getLayer('my-area-observed-cases-core')) {
      map.setPaintProperty('my-area-observed-cases-core', 'circle-opacity', style.coreOpacity)
      map.setPaintProperty('my-area-observed-cases-core', 'circle-stroke-opacity', style.strokeOpacity)
    }
    if (map.getLayer('my-area-observed-cases-pulse')) map.setFilter('my-area-observed-cases-pulse', style.pulseFilter)
  }, [focusedCaseId, observedCaseFeatures, mapLoaded])

  // No travelling dash: a geometric tendency is not movement.

  useEffect(() => {
    zonePopupRef.current?.remove()
    zonePopupRef.current = null
  }, [areaForecastVisualization?.date, showAreaImpact, districtFeature])

  // View on Map changes only camera emphasis/filter state. The parent
  // master activeIndex is intentionally absent from this effect.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const selectedIdentity = focusedCaseId ?? '__none__'
    for (const layerId of ['my-area-forecast-selected-path', 'my-area-forecast-selected-risk-outline', 'my-area-observed-cases-selected']) {
      if (map.getLayer(layerId)) map.setFilter(layerId, ['==', ['get', 'anchorId'], selectedIdentity])
    }
    if (!focusedCaseId) return
    const selectedFeature = observedCaseFeatures.find((feature) => feature?.properties?.anchorId === focusedCaseId)
    const coordinate = selectedFeature?.geometry?.coordinates
    if (!Array.isArray(coordinate) || !coordinate.every(Number.isFinite)) return
    emphasizeCoordinate(map, coordinate, reduceMotion)
  }, [focusedCaseId, observedCaseFeatures, reduceMotion, mapLoaded])

  // Registered farms and pending reports: data-only updates.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    map.getSource(REGISTERED_FARMS_SOURCE_ID)?.setData(registeredFarmFeatures ?? EMPTY_FEATURE_COLLECTION)
    map.getSource(PENDING_CASES_SOURCE_ID)?.setData(pendingCaseFeatures ?? EMPTY_FEATURE_COLLECTION)
    if (map.getLayer('my-area-pending-cases')) map.setLayoutProperty('my-area-pending-cases', 'visibility', showPendingCases ? 'visible' : 'none')
  }, [registeredFarmFeatures, pendingCaseFeatures, showPendingCases, mapLoaded])

  // Farm focus from a list click: camera emphasis only.
  useEffect(() => {
    const map = mapRef.current
    const coordinate = focusPoint?.coordinates
    if (!map || !loadedRef.current || !Array.isArray(coordinate) || !coordinate.every(Number.isFinite)) return
    emphasizeCoordinate(map, coordinate, reduceMotion)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusPoint?.key, mapLoaded])

  // ---- nominal-reach ring: same tween as Page 1, source-centered ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const source = map.getSource(REACH_RING_SOURCE_ID)
    if (!source) return

    if (reachRingAnimRef.current) {
      cancelAnimationFrame(reachRingAnimRef.current)
      reachRingAnimRef.current = null
    }

    if (!reachRingCenters || reachRingCenters.length === 0 || !(reachRingRadiusKm > 0)) {
      source.setData(emptyReachRingFeatureCollection())
      currentReachRadiusKmRef.current = 0
      return
    }

    const targetRadiusKm = reachRingRadiusKm
    if (reduceMotion) {
      source.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, targetRadiusKm))
      currentReachRadiusKmRef.current = targetRadiusKm
      return
    }

    const startRadiusKm = currentReachRadiusKmRef.current
    const startTime = performance.now()
    const TWEEN_MS = 800
    const tick = (now) => {
      const t = Math.min(1, (now - startTime) / TWEEN_MS)
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
      const currentRadiusKm = startRadiusKm + (targetRadiusKm - startRadiusKm) * eased
      currentReachRadiusKmRef.current = currentRadiusKm
      source.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, currentRadiusKm))
      if (t < 1) reachRingAnimRef.current = requestAnimationFrame(tick)
      else reachRingAnimRef.current = null
    }
    reachRingAnimRef.current = requestAnimationFrame(tick)

    return () => {
      if (reachRingAnimRef.current) cancelAnimationFrame(reachRingAnimRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reachRingCenters, reachRingRadiusKm, reduceMotion])

  return (
    <div className="my-area-map-shell relative h-full w-full overflow-hidden">
      {/* Parent owns the responsive viewport height; no competing minimum
          height is allowed, so the MapLibre canvas and card stay exact. */}
      <div ref={containerRef} className="h-full min-h-0 w-full" role="application" aria-label="My Area map" />
      {mapIssue && <div role="status" className={mapIssue === 'fatal' ? 'absolute inset-0 flex items-center justify-center bg-slate-950 p-8 text-center text-xs text-amber-200' : 'pointer-events-none absolute bottom-1 left-2 right-2 rounded bg-slate-950/90 p-2 text-[10px] text-amber-200'}>{mapIssue === 'fatal' ? MAP_RENDER_ERROR_TEXT : MAP_RESOURCE_ERROR_TEXT}</div>}
    </div>
  )
})

export default MyAreaMapCanvas
