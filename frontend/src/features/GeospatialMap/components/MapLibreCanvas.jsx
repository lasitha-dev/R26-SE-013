import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { GEO_TIMING, logTimingSummary, markTiming } from '../adapters/loadTiming'
import { featureBelongsToOutbreak, nationalStackIndicatorPaint } from '../adapters/nationalSourcePresentation'
import { interpolatePage1ForecastVisualization } from '../adapters/page1ForecastVisualization'
import { resolveBasemapConfig } from './basemapConfig'
// GEO33B Section 15/16: this feature's OWN MapLibre control chrome (dark
// zoom buttons/attribution), scoped entirely under `.geo-map-shell` below.
// Never a shared/global stylesheet -- `src/index.css`/`src/styles/index.css`
// are another member's read-only surface.
import './geospatialMapChrome.css'
import {
  buildCellsFeatureCollection,
  buildDirectionFeatureCollection,
  buildNationalSourcesFeatureCollection,
  buildSourcesFeatureCollection,
  computeCombinedLngLatBounds,
  computeRiskTierStats,
  directionIconLayout,
  nationalSourceAmbientPulsePaint,
  page1RiskFillColorExpression,
  page1RiskFillOpacityExpression,
  page1RiskLineColorExpression,
  page1RiskLineOpacityExpression,
  riskTierColorExpression,
  sourceIconLayout,
  NATIONAL_SOURCES_PULSE_CYCLE_MS,
} from './mapLibreAdapter'
import {
  REACH_GRADIENT_BAND_OPACITY,
  buildReachGradientFeatureCollectionForCenters,
  buildReachRingFeatureCollectionForCenters,
  emptyReachRingFeatureCollection,
} from './nominalReachRing'
import { CLINICAL_CIRCLE_ICON_ID, CLINICAL_DIAMOND_ICON_ID, buildClinicalCircleIcon, buildClinicalDiamondIcon } from './operationalIcons'
import {
  OPERATIONAL_MARKERS_HALO_LAYER_ID,
  OPERATIONAL_MARKERS_LAYER_ID,
  OPERATIONAL_MARKERS_PROMOTE_ID,
  OPERATIONAL_MARKERS_SOURCE_ID,
  operationalMarkerHaloPaint,
  operationalMarkerIconLayout,
  operationalMarkerPaint,
} from './operationalMarkerLayer'
import {
  DIRECTION_ICON_ID,
  FMD_SOURCE_ICON_ID,
  SOURCE_ICON_ID,
  buildDirectionArrowImage,
  buildFmdSourceMarkerImage,
  buildSourceMarkerImage,
} from './presentationIcons'

const CELLS_SOURCE_ID = 'geo-cells'
const SOURCES_SOURCE_ID = 'geo-sources'
const DIRECTIONS_SOURCE_ID = 'geo-directions'
const NATIONAL_SOURCES_SOURCE_ID = 'geo-national-sources'
const PAGE1_FORECAST_RISK_SOURCE_ID = 'geo-page1-forecast-risk'
const PAGE1_FORECAST_PATH_SOURCE_ID = 'geo-page1-forecast-path'
const PAGE1_FORECAST_FRONT_SOURCE_ID = 'geo-page1-forecast-front'
const PAGE1_FORECAST_TRANSITION_MS = 520
// ONE fill layer + ONE line layer for every Page-1 risk contour feature,
// regardless of how many real outbreaks are currently loaded -- color is
// entirely data-driven off each feature's own `riskLevel` property via a
// `match` expression (`mapLibreAdapter.js`), so a 5th/6th/etc. real
// outbreak never needs a new MapLibre layer, and an unrecognized
// `riskLevel` falls through to a transparent, never black, fill.
const PAGE1_FORECAST_RISK_FILL_LAYER_ID = 'page1-forecast-risk-fill'
const PAGE1_FORECAST_RISK_LINE_LAYER_ID = 'page1-forecast-risk-line'
const PAGE1_RISK_PULSE_CYCLE_MS = 2800
const REACH_RING_SOURCE_ID = 'geo-reach-ring'
// GEO-REACH-GRADIENT-01: a SEPARATE source for the concentric-disk
// gradient bands (`buildReachGradientFeatureCollectionForCenters`) --
// kept apart from `REACH_RING_SOURCE_ID`'s single outline+flat-fill
// feature per center so the crisp boundary line always stays the
// topmost, sharpest element regardless of how many gradient bands exist.
const REACH_GRADIENT_SOURCE_ID = 'geo-reach-gradient'
// One-shot growth pulse: a brief glow drawn at the NEW boundary exactly
// when the real target radius genuinely increases (a real day-forward
// advance), never a continuous/decorative loop -- MapLibre GL has no
// dash-offset/marching-ants primitive to animate a literal "flowing"
// boundary, so this reuses the SAME one-shot expand-then-fade technique
// already proven in this file for `national-sources-ripple` (feature
// re-added + a long paint-transition does the actual fade).
const REACH_GROWTH_PULSE_SOURCE_ID = 'geo-reach-growth-pulse'
const REACH_GROWTH_PULSE_MS = 550
// GEO30B Section 16: the vet's real district polygon (see
// `data/ATTRIBUTION.md`) -- fill + outline, never a symbol/text layer
// (this basemap declares no `glyphs` URL; the "MY DISTRICT · X" label
// already exists as a real React-rendered chip in the page header).
export const MY_DISTRICT_SOURCE_ID = 'geo-my-district'
export const MY_DISTRICT_FILL_LAYER_ID = 'my-district-fill'
export const MY_DISTRICT_OUTLINE_LAYER_ID = 'my-district-outline'
// GEO33B Section 7: the "more than one distinct real observed record at
// this exact coordinate" ring (`nationalSourcePresentation.js`). Painted
// UNDER the national source icon, never over it.
export const NATIONAL_SOURCES_STACK_LAYER_ID = 'national-sources-stack'
// GEO-VISUAL-POLISH-01: the continuous ambient "live outbreak" breathing
// ring -- always on for every national source marker, distinct from the
// one-shot selection ripple/steady halo above.
export const NATIONAL_SOURCES_PULSE_LAYER_ID = 'national-sources-ambient-pulse'

const RIPPLE_TRANSITION_MS = 1800
// GEO-REACH-GRADIENT-01: bumped from 800ms so the real day-to-day growth
// is comfortably visible rather than reading as a near-instant pop, while
// still finishing well inside the 1400ms real per-day playback tick at 1x
// speed (`OutbreakMapPage.jsx`'s `intervalMs = 1400 / playbackSpeed`) --
// timing/UX only, never a change to which real radius is drawn.
const REACH_RING_TWEEN_MS = 1000

// GEO33A Section 8: a flat, small padding left real geography readable
// right up to the map's own edges, where the floating `ModeToolbar`
// (top-4) and bottom timeline/status bar (bottom-4) actually sit -- both
// overlays are taller than a flat 40px pad, so a fit could genuinely
// place Sri Lanka's own coastline or a real marker underneath either one.
// Asymmetric padding reserves real room for both without shrinking the
// fit unnecessarily on the sides.
const MAP_FIT_PADDING = { top: 90, bottom: 110, left: 40, right: 40 }

// GEO33B Section 5: an upper bound for every camera fit on this page.
// Without it, `fitBounds` over a small real geometry (a single origin's
// two sources ~5km apart, or a compact district polygon) zooms to street
// level, which is meaningless for a national disease-surveillance view and
// loses all surrounding context. 11 is roughly "a few districts across" --
// a presentation limit, never derived from any scientific value.
const MAP_FIT_MAX_ZOOM = 11

// GEO29A Part 11: fixed, real Sri Lanka geographic constants -- presentation
// camera defaults only, never derived from or mistaken for scientific/model
// output. [lng, lat] order (MapLibre convention).
// GEO33B Section 5: recentred/retightened to the island's own real extent.
// The previous box ([[79.4,5.7],[82.0,9.9]]) was ~0.25 degrees too wide to
// the west and ~0.15 too far south of any Sri Lankan land, which at this
// aspect ratio pulled a band of southern India into frame and left the
// island reading small and off-centre. Real mainland Sri Lanka spans
// approximately lon 79.65--81.88, lat 5.92--9.84 (Point Pedro in the north
// to Dondra Head in the south, Kalpitiya west to Sangamankanda east); the
// values below add only a small, uniform, documented presentation margin
// so the coastline is never clipped by the fit itself.
export const SRI_LANKA_CENTER = [80.77, 7.87]
export const SRI_LANKA_INITIAL_ZOOM = 7.1
export const SRI_LANKA_BOUNDS = [
  [79.55, 5.85],
  [81.95, 9.92],
]

// GEO-PAGE1-FINAL Section 5.2/6: a real, fixed geographic pan/zoom-out
// constraint -- deliberately much LOOSER than `SRI_LANKA_BOUNDS` above
// (which is only ever used for the "Fit Sri Lanka" camera target), so a
// vet can still freely explore the whole island, its coastline, and a
// reasonable amount of surrounding ocean/southern-India context, while
// never being able to pan/zoom this Sri Lanka surveillance map into an
// unrelated part of the world or into a wrapped duplicate copy of it.
export const SRI_LANKA_MAX_PAN_BOUNDS = [
  [72.0, 2.0],
  [90.0, 15.0],
]

/**
 * Checkpoint 11B Part 2/6/10/19, extended LSD-UI-03/04: a professional
 * MapLibre GL view over an ALREADY-COMMITTED snapshot, still a PURE VIEW
 * -- it never fetches, never opens a second WebSocket/HTTP request.
 *
 * Backward-compatible extension: `cellFeatures`/`sourceFeatures`/
 * `onSelectCell`/`onMapUnavailable` behave EXACTLY as before (still used
 * unchanged by `MapView.jsx`/`GeospatialMapFeature.jsx`, the original
 * Checkpoint 11A/11B single-snapshot debug view). Everything below is
 * ADDITIVE, only active when the new props are actually passed (Page 1's
 * national outbreak map, LSD-UI-03/04):
 *  - `nationalSources`: a FeatureCollection merging every real origin's
 *    sources (`buildNationalSourcesFeatureCollection`), always visible,
 *    used for national browsing + click-to-select + selection halo/dim.
 *  - `selectedOutbreakId`: drives which national-source features get the
 *    halo/ripple (selected) vs dimmed (not selected) treatment.
 *  - `reachRingCenters`/`reachRingRadiusKm`: the real, backend-derived
 *    nominal-reach value (plan Section 22/26) for the selected day,
 *    drawn as a ring around every real source in the selected origin
 *    (see `nominalReachRing.js`'s header for why not just one point);
 *    tweened smoothly between day values, never risk-colored.
 *    GEO-REACH-GRADIENT-01: the SAME real radius also drives a soft
 *    concentric-disk gradient fill (`reach-ring-gradient`) and a one-shot
 *    boundary flash (`reach-ring-growth-pulse`) whenever the real target
 *    radius genuinely increases -- both purely presentational over the
 *    one real value, never a second/independent radius.
 *  - `reduceMotion`: skips the camera-fit animation, the reach-ring
 *    tween (snaps instead), and the selection ripple.
 *  - `showTrajectoryLayer` (GEO-TRAJECTORY-01): shows the real per-cell
 *    `direction-arrows` layer (`bearing_deg`) for Trajectory mode, without
 *    the risk-tier `cells-circle` dots that stay exclusive to Risk Zones
 *    (`showRiskLayer`). The reach ring is shared by both modes via
 *    `reachRingCenters` already being non-null in either (`OutbreakMapPage.jsx`).
 *
 * GEO-INT-03 additions (Section 6/9/10/13): a fourth, independent overlay
 * for the Verified Clinical Context operational layer --
 *  - `operationalFeatures`: a FeatureCollection built by
 *    `operationalMarkerLayer.js` from already-validated data
 *    (`operationalContextAdapter.js` -- Section 25/26). Rendered with a
 *    single restrained hollow neutral-mint icon (`operationalIcons.js`),
 *    diamond for LSD / circle for FMD, NEVER the risk color family and
 *    NEVER any reach-ring/glow/pulse treatment (Section 9).
 *  - `showOperationalLayer`: Section 10 -- the caller passes `true` only
 *    while Cases mode is active; toggled via `setLayoutProperty`
 *    visibility, never by adding/removing the layer.
 *  - `onSelectOperationalCase`: Section 11/12 -- fires with the clicked
 *    feature's properties only. This click handler NEVER calls
 *    `onSelectCell`/`onSelectSource`, never touches `selectedOutbreakId`,
 *    and this file's data-update effect for `operationalFeatures` below
 *    NEVER calls `fitBounds`/`flyTo`/`easeTo` (Section 13 -- an
 *    operational refresh must never move the user's camera).
 *
 * One map instance for the whole national<->focused lifecycle -- no
 * remount on selection (plan Section 18/20). Still excluded from this
 * repo's Node-only Vitest suite (needs real WebGL/DOM); the pure
 * geometry/expression builders it calls (`mapLibreAdapter.js`,
 * `nominalReachRing.js`) are unit-tested instead.
 */
const MapLibreCanvas = forwardRef(function MapLibreCanvas(
  {
    cellFeatures = [],
    sourceFeatures = [],
    nationalSources = null,
    nationalMarkerShape = 'diamond',
    selectedOutbreakId = null,
    // GEO-PAGE1-FINAL Section 24: true while `selectedOutbreakId` is a
    // PAGE-CHOSEN default focus (the most recent real eligible origin,
    // picked so Risk Zones has real data to show without the vet
    // clicking a marker first -- `OutbreakMapPage.jsx`'s own auto-focus
    // effect), never a real click. Suppresses the camera fly-to-origin
    // and the selection halo/ripple/dim treatment ONLY -- `focus.cells`/
    // `focus.sources`/the reach ring still render normally, since those
    // are genuinely real data for a genuinely real origin. The instant a
    // vet actually clicks any marker, the page flips this back to
    // `false` and every one of those behaviors resumes exactly as
    // before. This keeps the default Sri Lanka Overview visually calm
    // (no unexplained glowing marker, no surprise camera jump) while
    // still letting Risk Zones/Play work immediately.
    autoFocusOutbreak = false,
    reachRingCenters = null,
    reachRingRadiusKm = 0,
    reduceMotion = false,
    operationalFeatures = null,
    showOperationalLayer = false,
    // GEO31A Section 8/10: defaults to `true` so the ORIGINAL
    // Checkpoint-11B single-snapshot debug view (`MapView.jsx`/
    // `GeospatialMapFeature.jsx`, which pass `cellFeatures` directly and
    // have no mode concept at all) keeps rendering cells exactly as
    // before -- `OutbreakMapPage.jsx` is the only caller that passes this
    // explicitly, tying it to `ANALYSIS_MODE.RISK_ZONES`.
    showRiskLayer = true,
    // GEO-TRAJECTORY-01: Trajectory mode's own visibility gate for the
    // direction-arrows layer (real per-cell `bearing_deg`) -- deliberately
    // separate from `showRiskLayer` so `cells-circle` (the risk-TIER
    // dots) stays exclusive to Risk Zones mode while the direction arrows
    // are shared real data, honestly relevant to both "how risky is this
    // cell" (Risk Zones) and "which way might this spread" (Trajectory).
    showTrajectoryLayer = false,
    // Deterministic presentation geometry derived by the parent from the
    // CURRENT real national outbreak/source array. These props never
    // trigger a fetch or create another map instance.
    page1ForecastVisualization = null,
    showPage1ForecastLayer = false,
    showPage1ForecastRiskZones = false,
    arrivalHighlightKey = null,
    // GEO33B Section 8/11: real farm+disease keys that became visible on
    // THIS observed-replay step (`OutbreakMapPage.jsx` derives them by
    // diffing the previously-revealed set against the newly-revealed one).
    // Given the same short pulse treatment as a live SSE arrival, then
    // settled back to steady -- never a permanent animation on every
    // historical marker.
    newlyRevealedKeys = null,
    selectedOperationalKey = null,
    districtFeature = null,
    onSelectCell,
    onSelectSource,
    onSelectOperationalCase,
    onMapUnavailable,
  },
  ref,
) {
  // GEO-PAGE1-FINAL Section 24: the id used for every VISUAL selection
  // effect (camera fly, halo, ripple, dim-others) below -- `null` while
  // the current focus is only the page's own auto-picked default, so
  // none of those fire for it. `selectedOutbreakId` itself is untouched
  // everywhere else (it's also implicitly what `cellFeatures`/
  // `sourceFeatures` already reflect via the page's own `focus` hook).
  const visuallySelectedOutbreakId = autoFocusOutbreak ? null : selectedOutbreakId
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const failedRef = useRef(false)
  const loadedRef = useRef(false)
  const lastFitOutbreakIdRef = useRef(undefined)
  // GEO33B Section 4: drives the restrained "Preparing map…" overlay below.
  // Flipped once the style has actually loaded, so the vet never stares at
  // an unexplained black rectangle while the remote basemap style/tiles are
  // still in flight. Deliberately a boolean about PRESENTATION readiness --
  // it never gates, delays, or reports anything about real data.
  const [styleReady, setStyleReady] = useState(false)

  // GEO33B Section 2: latest-value mirrors of every async-arriving prop.
  //
  // THE BUG THESE FIX (a real load-order race, not a hypothetical): the
  // mount effect below is intentionally `[]`-deps, so the `map.on('load')`
  // callback it registers closes over the props as they were on the FIRST
  // render -- when every one of these is still empty/null. Each prop also
  // has its own `setData` effect further down, but those all bail out
  // early while `loadedRef.current` is false. So whenever a fetch resolved
  // BEFORE the remote basemap style finished loading -- which is the
  // common case in practice, since the API is local and the OpenFreeMap
  // style + sprite + glyphs are a remote CDN round trip -- the sequence was:
  //   1. data arrives, its effect runs, sees `!loadedRef.current`, returns;
  //   2. style loads, `map.on('load')` seeds the source from its STALE
  //      first-render closure (empty);
  //   3. no further prop change occurs, so no effect ever re-runs.
  // Net result: the source stayed permanently empty and the markers /
  // district polygon never appeared at all, with no error anywhere. Reading
  // through these refs inside `map.on('load')` makes the wiring genuinely
  // order-independent: data-first and style-first both end up correct.
  const nationalSourcesRef = useRef(nationalSources)
  const page1ForecastVisualizationRef = useRef(page1ForecastVisualization)
  const showPage1ForecastLayerRef = useRef(showPage1ForecastLayer)
  const showPage1ForecastRiskZonesRef = useRef(showPage1ForecastRiskZones)
  const showTrajectoryLayerRef = useRef(showTrajectoryLayer)
  const operationalFeaturesRef = useRef(operationalFeatures)
  const districtFeatureRef = useRef(districtFeature)
  const cellFeaturesRef = useRef(cellFeatures)
  const sourceFeaturesRef = useRef(sourceFeatures)
  nationalSourcesRef.current = nationalSources
  page1ForecastVisualizationRef.current = page1ForecastVisualization
  showPage1ForecastLayerRef.current = showPage1ForecastLayer
  showPage1ForecastRiskZonesRef.current = showPage1ForecastRiskZones
  showTrajectoryLayerRef.current = showTrajectoryLayer
  operationalFeaturesRef.current = operationalFeatures
  districtFeatureRef.current = districtFeature
  cellFeaturesRef.current = cellFeatures
  sourceFeaturesRef.current = sourceFeatures
  const reachRingAnimRef = useRef(null)
  const page1ForecastAnimRef = useRef(null)
  const currentPage1ForecastRef = useRef(null)
  const currentReachRadiusKmRef = useRef(0)
  // GEO31A Section 2: tracks the previously-selected operational farm key
  // so its steady halo can be cleared when a DIFFERENT farm becomes
  // selected (or none), mirroring how the national-sources selection
  // effect iterates every feature -- this ref avoids needing the full
  // operational feature list just to clear one stale feature-state.
  const selectedOperationalKeyRef = useRef(null)

  // LSD-PAGE1-HARDENING Section 24/25: `resize()` is what MapLibre needs
  // called after its container's dimensions change from OUTSIDE React's
  // normal render flow (a `fullscreenchange` event) -- MapLibre has no
  // ResizeObserver of its own. `resetView()` re-fits the SAME real
  // national bounds the initial mount already computes, never a
  // fabricated/favorable viewport. Both are no-ops before the map has
  // loaded, matching every other effect in this file.
  useImperativeHandle(ref, () => ({
    resize() {
      mapRef.current?.resize()
    },
    // GEO-VIVA-VISUAL-RECOVERY-03: lets a caller-driven one-time camera
    // action (`OutbreakMapPage.jsx`'s initial auto-focus-to-district
    // effect) wait for the real map/style load instead of calling
    // `resetView` too early and having it silently no-op (see the
    // `!loadedRef.current` guard on `resetView` below) -- never a
    // guessed timeout, the real internal readiness flag this component
    // already tracks for every other effect in this file.
    isReady() {
      return loadedRef.current
    },
    // GEO26B Section 15: `explicitBounds` (a [[minLon,minLat],[maxLon,maxLat]]
    // pair, e.g. from `computeCombinedLngLatBounds` over the vet's own
    // assigned-farm points) lets the Location control's "My assigned
    // farms" option reuse this SAME single fitBounds call site -- never a
    // second camera-fit primitive, so this remains the only user-
    // triggered (never automatic) map movement this component performs
    // beyond the two other pre-existing sites.
    resetView(explicitBounds) {
      const map = mapRef.current
      if (!map || !loadedRef.current) return
      // GEO29A Part 11: "Fit Sri Lanka" must always fit Sri Lanka, even
      // when there is genuinely no real national source geometry yet
      // (e.g. FMD with zero origins, or before the first fetch resolves)
      // -- uses the real, fixed `SRI_LANKA_BOUNDS` constant rather than
      // silently doing nothing.
      //
      // GEO33B Section 5: this no longer prefers the national MARKER
      // bounds over `SRI_LANKA_BOUNDS`. Every real Sri Lanka LSD record
      // sits in the far north (lat 8.89--9.75, lon 80.03--80.66), so
      // fitting the marker extent moved the camera onto the Jaffna
      // peninsula and dropped the rest of the island out of frame -- from
      // a control the vet had just clicked because it says "Fit Sri
      // Lanka". A named geographic scope must show that geography; the
      // data-driven fit still happens, but only on an explicit outbreak
      // SELECTION (the focused-origin effect below), which is where the
      // vet actually asked to zoom in on real records.
      const bounds = explicitBounds ?? SRI_LANKA_BOUNDS
      // GEO-VIVA-USER-VISIBLE-RECOVERY-05: dev-only marks bracketing the
      // REAL camera animation this control performs -- `moveend` is
      // MapLibre's own native "the camera has actually finished moving"
      // event, never a guessed duration, so a QA session can measure the
      // true click-to-settled-camera time for Location changes.
      markTiming(GEO_TIMING.CAMERA_FIT_START, { repeat: true })
      map.once('moveend', () => markTiming(GEO_TIMING.CAMERA_FIT_END, { repeat: true }))
      map.fitBounds(bounds, { padding: MAP_FIT_PADDING, maxZoom: MAP_FIT_MAX_ZOOM, animate: !reduceMotion })
    },
  }))

  // ---- mount: create the map once, wire every source/layer/handler ----
  useEffect(() => {
    let map
    let resizeObserver
    try {
      const basemap = resolveBasemapConfig(import.meta.env.VITE_GEOSPATIAL_BASEMAP_STYLE_URL)
      // GEO33B Section 1: dev-only marks. `STYLE_LOAD_START` is recorded
      // immediately before construction because MapLibre begins fetching
      // the style URL synchronously inside the constructor.
      markTiming(GEO_TIMING.MAP_CONSTRUCT_START)
      markTiming(GEO_TIMING.STYLE_LOAD_START)
      map = new maplibregl.Map({
        container: containerRef.current,
        style: basemap.style,
        // GEO29A Part 11: a real browser screenshot showed the map
        // starting at MapLibre's own default world view ([0,0], zoom 0,
        // repeating at low zoom) -- this page is Sri Lanka disease
        // surveillance only, so the FIRST frame (before any real
        // national/cell/source bounds have loaded, and for a disease/
        // filter combination that never produces any) must already be
        // Sri Lanka, never the whole world. `SRI_LANKA_CENTER`/
        // `SRI_LANKA_INITIAL_ZOOM` are a real, fixed geographic constant
        // (not derived from any scientific/model data), the same
        // approximate centering the rest of this app's map tooling
        // already uses. The later `fitBounds` calls in this effect (once
        // real bounds exist) still refine/override this immediately.
        center: SRI_LANKA_CENTER,
        zoom: SRI_LANKA_INITIAL_ZOOM,
        pitch: 0,
        maxPitch: 0,
        bearing: 0,
        // GEO-PAGE1-FINAL Section 5.2/6: no wrapped duplicate copies of
        // the map, and panning/zooming out is constrained to a real,
        // fixed region around Sri Lanka -- a vet can never scroll this
        // surveillance map into an unrelated part of the world.
        renderWorldCopies: false,
        maxBounds: SRI_LANKA_MAX_PAN_BOUNDS,
        // GEO33B Section 16: the DEFAULT attribution control renders
        // bottom-right, which is exactly where this page's bottom-docked
        // timeline and its right-hand legend/popup column sit -- at
        // narrower viewports the timeline card overlapped it. Disabled
        // here and re-added explicitly at 'bottom-left' below. Attribution
        // is REPOSITIONED, never removed, never hidden and never made
        // unreadable (the OpenFreeMap/OSM ODbL requirement, plus the
        // district polygon's own `attribution` field, are all still
        // aggregated and displayed by that control).
        attributionControl: false,
      })
      mapRef.current = map
      markTiming(GEO_TIMING.MAP_CONSTRUCT_END)

      // GEO-OWNED-FINAL-08 Section 15 "host-layout safety": MapLibre has
      // no ResizeObserver of its own (only the imperative `resize()` this
      // component already exposes, driven by `OutbreakMapPage.jsx`'s
      // `fullscreenchange` listener). The real host `VetLayout` can also
      // change this container's width from an off-canvas sidebar
      // toggle or a plain window resize -- neither fires
      // `fullscreenchange` -- so without this, the canvas can render at a
      // stale size until some unrelated event happens to trigger a
      // manual resize. Observing the container itself (not `window`)
      // catches every one of those causes uniformly, without needing to
      // know which host layout event caused the change.
      if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
        resizeObserver = new ResizeObserver(() => {
          mapRef.current?.resize()
        })
        resizeObserver.observe(containerRef.current)
      }

      map.dragRotate.disable()
      map.touchZoomRotate.disableRotation()
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
      // GEO33B Section 16: attribution moved off the bottom-right timeline
      // lane. `compact: true` keeps it to a single small "i" affordance
      // that expands on click -- the full required credit text is always
      // one click away and is never suppressed.
      map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')

      // GEO33B Section 1: first actual painted frame, and the point at
      // which the map has finished all pending work. `once`/idempotent
      // marking means a later repaint never overwrites the FIRST timing.
      map.on('render', () => {
        markTiming(GEO_TIMING.FIRST_RENDER)
      })
      map.on('idle', () => {
        markTiming(GEO_TIMING.MAP_IDLE)
        logTimingSummary()
      })

      map.on('error', (e) => {
        // A style/tile-load failure is a PRESENTATION problem, never a
        // scientific-data problem -- surface the fallback, never touch
        // the committed snapshot.
        // eslint-disable-next-line no-console
        console.warn('MapLibre map error (falling back to SVG view):', e?.error?.message || e)
        if (!failedRef.current) {
          failedRef.current = true
          onMapUnavailable?.()
        }
      })

      map.on('load', () => {
        loadedRef.current = true
        markTiming(GEO_TIMING.STYLE_LOAD_END)
        setStyleReady(true)
        // GEO33B Section 2: read the LATEST prop values, never this
        // mount-only effect's first-render closure -- see the
        // `*Ref` block at the top of this component for the full
        // explanation of the load-order race this fixes. Everything below
        // is therefore correct whether the data or the style won.
        const latestCellFeatures = cellFeaturesRef.current ?? []
        const latestSourceFeatures = sourceFeaturesRef.current ?? []
        const latestNationalSources = nationalSourcesRef.current
        const latestPage1Forecast = page1ForecastVisualizationRef.current
        const latestDistrictFeature = districtFeatureRef.current
        const cellsFC = buildCellsFeatureCollection(latestCellFeatures)
        const sourcesFC = buildSourcesFeatureCollection({ type: 'FeatureCollection', features: latestSourceFeatures })
        const directionsFC = buildDirectionFeatureCollection(latestCellFeatures)
        // GEO-VISUAL-POLISH-03: discrete, snapshot-relative risk tiers
        // (red/orange/yellow/green) replace the previous continuous blue
        // -> red gradient as the ACTUAL map paint -- see
        // `mapLibreAdapter.js`'s own module comment for why this is still
        // scientifically honest (real quartiles of the CURRENT snapshot,
        // never a fixed absolute threshold).
        const tierStats = computeRiskTierStats(latestCellFeatures)
        const nationalFC = latestNationalSources ?? { type: 'FeatureCollection', features: [] }

        if (!map.hasImage(SOURCE_ICON_ID)) map.addImage(SOURCE_ICON_ID, buildSourceMarkerImage())
        // FMD-10C1: registered unconditionally at mount (cheap,
        // presentation-only pixels) so a later disease switch to FMD
        // never has to add an image mid-session -- only the layer's
        // `icon-image` layout property switches, via the effect below.
        if (!map.hasImage(FMD_SOURCE_ICON_ID)) map.addImage(FMD_SOURCE_ICON_ID, buildFmdSourceMarkerImage())
        if (!map.hasImage(DIRECTION_ICON_ID)) map.addImage(DIRECTION_ICON_ID, buildDirectionArrowImage())
        if (!map.hasImage(CLINICAL_DIAMOND_ICON_ID)) map.addImage(CLINICAL_DIAMOND_ICON_ID, buildClinicalDiamondIcon())
        if (!map.hasImage(CLINICAL_CIRCLE_ICON_ID)) map.addImage(CLINICAL_CIRCLE_ICON_ID, buildClinicalCircleIcon())

        // GEO30B Section 16/17/26: the vet's real district polygon --
        // added FIRST (before cells/sources/markers) so layer paint
        // order matches Section 26's required stacking (basemap -> district
        // fill -> district outline -> ... -> markers -> labels). Empty by
        // default; `districtFeature` typically resolves asynchronously
        // (a real network fetch, `useDistrictGeometry.js`) shortly after
        // mount -- the data-update effect below calls `setData` once it
        // does, never a second source/layer definition.
        map.addSource(MY_DISTRICT_SOURCE_ID, {
          type: 'geojson',
          data: latestDistrictFeature
            ? { type: 'FeatureCollection', features: [latestDistrictFeature] }
            : { type: 'FeatureCollection', features: [] },
          // ODbL 1.0 attribution requirement, `data/ATTRIBUTION.md` --
          // aggregated by MapLibre's attribution control alongside the
          // OSM raster basemap's own `attribution` field.
          attribution: '© OpenStreetMap contributors',
        })
        map.addLayer({
          id: MY_DISTRICT_FILL_LAYER_ID,
          type: 'fill',
          source: MY_DISTRICT_SOURCE_ID,
          paint: { 'fill-color': '#4edea3', 'fill-opacity': 0.08 },
        })
        map.addLayer({
          id: MY_DISTRICT_OUTLINE_LAYER_ID,
          type: 'line',
          source: MY_DISTRICT_SOURCE_ID,
          paint: { 'line-color': '#4edea3', 'line-width': 1.5, 'line-opacity': 0.85 },
        })

        map.addSource(CELLS_SOURCE_ID, { type: 'geojson', data: cellsFC })
        map.addSource(SOURCES_SOURCE_ID, { type: 'geojson', data: sourcesFC })
        map.addSource(DIRECTIONS_SOURCE_ID, { type: 'geojson', data: directionsFC })
        map.addSource(NATIONAL_SOURCES_SOURCE_ID, { type: 'geojson', data: nationalFC, promoteId: 'source_id' })
        map.addSource(PAGE1_FORECAST_RISK_SOURCE_ID, {
          type: 'geojson',
          data: latestPage1Forecast?.riskZones ?? { type: 'FeatureCollection', features: [] },
        })
        map.addSource(PAGE1_FORECAST_PATH_SOURCE_ID, {
          type: 'geojson',
          data: latestPage1Forecast?.paths ?? { type: 'FeatureCollection', features: [] },
        })
        map.addSource(PAGE1_FORECAST_FRONT_SOURCE_ID, {
          type: 'geojson',
          data: latestPage1Forecast?.fronts ?? { type: 'FeatureCollection', features: [] },
        })
        currentPage1ForecastRef.current = latestPage1Forecast
        // GEO-REACH-GRADIENT-01: the gradient-band source is added FIRST so
        // its `fill` layer paints UNDER the outline/fill of REACH_RING_SOURCE_ID
        // (added next) -- the crisp real-radius boundary line always stays
        // the topmost, sharpest element on top of the soft gradient.
        map.addSource(REACH_GRADIENT_SOURCE_ID, { type: 'geojson', data: emptyReachRingFeatureCollection() })
        map.addSource(REACH_RING_SOURCE_ID, { type: 'geojson', data: emptyReachRingFeatureCollection() })
        map.addSource(REACH_GROWTH_PULSE_SOURCE_ID, { type: 'geojson', data: emptyReachRingFeatureCollection() })
        // GEO26B Section 12: `promoteId` lets `feature-state` (the
        // transient "just arrived" highlight, set by the dedicated effect
        // below) target one specific farm marker by its real
        // `farmDiseaseKey`, surviving the `setData` calls the 60s
        // operational refresh performs.
        map.addSource(OPERATIONAL_MARKERS_SOURCE_ID, {
          type: 'geojson',
          data: operationalFeaturesRef.current ?? { type: 'FeatureCollection', features: [] },
          promoteId: OPERATIONAL_MARKERS_PROMOTE_ID,
        })
        markTiming(GEO_TIMING.SOURCES_CREATED)
        if (nationalFC.features.length > 0) markTiming(GEO_TIMING.FIRST_OUTBREAK_RENDER)

        // GEO31A Section 8/9/10: the real backend model produces one
        // scored POINT per spatial cell (confirmed live, 2026-08-30:
        // `/analysis/{id}/cells` -- 88 real Point features for a real LSD
        // origin, real varying `raw_c0_score`), never a polygon/grid
        // footprint -- so a `circle` layer over that real geometry IS the
        // honest "actual model geometry" rendering (Section 10's "use
        // actual model geometry/grid/cells" -- there is no grid to fill,
        // only real scored points). `circle-radius` grows with zoom so the
        // real cluster of points reads as a visible cloud rather than a
        // handful of near-invisible 5px dots at national zoom (the
        // concrete cause of "Risk Zones not visibly working" -- the real
        // data was always there, Section 9's trace). `-transition` entries
        // give a real D0->D+N frame change (`cellFeatures` changing) a
        // 300ms crossfade (Section 11) instead of an instant hard swap.
        // Visibility is gated to Risk Zones mode only (`showRiskLayer`
        // effect below) -- never shown in Cases mode.
        map.addLayer({
          id: 'cells-circle',
          type: 'circle',
          source: CELLS_SOURCE_ID,
          layout: { visibility: showRiskLayer ? 'visible' : 'none' },
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 4, 8, 7, 12, 11],
            'circle-color': riskTierColorExpression(tierStats),
            'circle-opacity': 0.85,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#1e293b',
            'circle-color-transition': { duration: reduceMotion ? 0 : 320 },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : 320 },
          },
        })

        // Page-1 qualitative risk influence: EVERY real outbreak
        // contributes its own independent set of risk-contour features
        // (`page1ForecastVisualization.js::buildOutbreakRiskFeatures`) into
        // this ONE shared source -- N outbreaks naturally produce N
        // separate local risk fields, never one shared/merged shape. Color
        // is entirely data-driven off each feature's real `riskLevel`
        // property via a `match` expression (never a per-tier filtered
        // layer with a static color), so this stays exactly two layers no
        // matter how many outbreaks or risk bands are currently active,
        // and an unrecognized `riskLevel` falls through to a transparent
        // fill/line -- never the default black that caused the earlier
        // blob. Source features are pre-sorted lowest-to-highest severity
        // (green under yellow under orange under red) by the adapter, so
        // draw order is correct within this single layer.
        map.addLayer({
          id: PAGE1_FORECAST_RISK_FILL_LAYER_ID,
          type: 'fill',
          source: PAGE1_FORECAST_RISK_SOURCE_ID,
          layout: { visibility: showPage1ForecastRiskZonesRef.current ? 'visible' : 'none' },
          paint: {
            'fill-color': page1RiskFillColorExpression(),
            'fill-opacity': page1RiskFillOpacityExpression(false),
            'fill-color-transition': { duration: reduceMotion ? 0 : PAGE1_FORECAST_TRANSITION_MS },
            'fill-opacity-transition': { duration: reduceMotion ? 0 : PAGE1_FORECAST_TRANSITION_MS },
          },
        })
        map.addLayer({
          id: PAGE1_FORECAST_RISK_LINE_LAYER_ID,
          type: 'line',
          source: PAGE1_FORECAST_RISK_SOURCE_ID,
          layout: { visibility: showPage1ForecastRiskZonesRef.current ? 'visible' : 'none' },
          paint: {
            'line-color': page1RiskLineColorExpression(),
            'line-width': 1.1,
            'line-opacity': page1RiskLineOpacityExpression(false),
            'line-color-transition': { duration: reduceMotion ? 0 : PAGE1_FORECAST_TRANSITION_MS },
            'line-opacity-transition': { duration: reduceMotion ? 0 : PAGE1_FORECAST_TRANSITION_MS },
          },
        })

        // GEO-REACH-GRADIENT-01: the soft radial "hot at the origin, fading
        // at the edge" fill -- REACH_GRADIENT_BAND_COUNT concentric filled
        // disks (`buildReachGradientFeatureCollectionForCenters`), all at
        // real fractions of the SAME real radius, each painted at the SAME
        // small flat opacity so ordinary alpha-over compositing (not a data-
        // driven expression) produces the gradient -- see that function's
        // own module comment for the exact math. A colour deliberately
        // outside the risk red/orange/blue family so it can never read as a
        // risk zone (same teal as the boundary line below).
        map.addLayer({
          id: 'reach-ring-gradient',
          type: 'fill',
          source: REACH_GRADIENT_SOURCE_ID,
          paint: { 'fill-color': '#14b8a6', 'fill-opacity': REACH_GRADIENT_BAND_OPACITY },
        })
        // The crisp real-radius boundary -- widened from the previous
        // 1.5px/0.04-opacity-fill combo (too subtle to read as "spread is
        // happening") so the edge itself is the clearest single element of
        // this layer. `-transition` entries only smooth paint-PROPERTY
        // changes (there are none here); the actual grow/shrink is a
        // source-data tween driven by the `reachRingFeatureCollection`
        // effect below.
        map.addLayer({
          id: 'reach-ring-line',
          type: 'line',
          source: REACH_RING_SOURCE_ID,
          paint: { 'line-color': '#14b8a6', 'line-width': 2.5, 'line-dasharray': [2, 2], 'line-opacity': 0.9 },
        })
        // GEO-REACH-GRADIENT-01: the one-shot "just grew" glow -- drawn at
        // the NEW boundary exactly when the real target radius genuinely
        // increases (a real day-forward advance), then fades via the
        // `-transition` below. See `REACH_GROWTH_PULSE_SOURCE_ID`'s own
        // comment for why this (not a continuous dash-flow loop) is the
        // honest, real-event-driven substitute for a "marching ants"
        // boundary MapLibre GL has no primitive for.
        map.addLayer({
          id: 'reach-ring-growth-pulse',
          type: 'line',
          source: REACH_GROWTH_PULSE_SOURCE_ID,
          paint: {
            'line-color': '#5eead4',
            'line-width': 5,
            'line-opacity': 0,
            'line-opacity-transition': { duration: REACH_GROWTH_PULSE_MS },
          },
        })

        // Purple always means projected presentation spread. The path and
        // current front remain visible in Cases, Risk Zones and Trajectory;
        // only the qualitative polygon bands are mode-gated above.
        map.addLayer({
          id: 'page1-forecast-path-glow',
          type: 'line',
          source: PAGE1_FORECAST_PATH_SOURCE_ID,
          layout: { visibility: showPage1ForecastLayerRef.current ? 'visible' : 'none', 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': '#C084FC', 'line-width': 8, 'line-opacity': 0.16 },
        })
        map.addLayer({
          id: 'page1-forecast-path',
          type: 'line',
          source: PAGE1_FORECAST_PATH_SOURCE_ID,
          layout: { visibility: showPage1ForecastLayerRef.current ? 'visible' : 'none', 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': '#A855F7', 'line-width': showTrajectoryLayerRef.current ? 4.5 : 3.25, 'line-opacity': 0.92 },
        })
        map.addLayer({
          id: 'page1-forecast-front-glow',
          type: 'circle',
          source: PAGE1_FORECAST_FRONT_SOURCE_ID,
          layout: { visibility: showPage1ForecastLayerRef.current ? 'visible' : 'none' },
          paint: { 'circle-radius': 12, 'circle-color': '#A855F7', 'circle-opacity': 0.2, 'circle-blur': 0.35 },
        })
        map.addLayer({
          id: 'page1-forecast-front',
          type: 'circle',
          source: PAGE1_FORECAST_FRONT_SOURCE_ID,
          layout: { visibility: showPage1ForecastLayerRef.current ? 'visible' : 'none' },
          paint: {
            'circle-radius': showTrajectoryLayerRef.current ? 6 : 5,
            'circle-color': '#A855F7',
            'circle-stroke-width': 1.5,
            'circle-stroke-color': '#F3E8FF',
            'circle-opacity': 0.98,
          },
        })

        // One-time selection ripple (Section 9/27): radius/opacity are a
        // `case` on feature-state `rippleExpanded`; a long paint
        // -transition on THIS layer makes MapLibre tween automatically
        // whenever that feature-state flips (see the selectedOutbreakId
        // effect below) -- expands once, fades to nothing, never repeats.
        map.addLayer({
          id: 'national-sources-ripple',
          type: 'circle',
          source: NATIONAL_SOURCES_SOURCE_ID,
          paint: {
            'circle-radius': ['case', ['boolean', ['feature-state', 'rippleExpanded'], false], 22, 8],
            'circle-opacity': ['case', ['boolean', ['feature-state', 'rippleExpanded'], false], 0, 0.45],
            'circle-color': '#10b981',
            'circle-radius-transition': { duration: reduceMotion ? 0 : RIPPLE_TRANSITION_MS },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : RIPPLE_TRANSITION_MS },
          },
        })

        // GEO-VISUAL-POLISH-01: the continuous ambient breathing ring --
        // added right after the one-shot ripple and before the steady
        // halo, so paint order reads (bottom to top): one-shot ripple,
        // ambient pulse, steady halo, stack ring, icon. Initial paint is
        // the "collapsed" phase; the dedicated RAF effect below flips it
        // every half-cycle. `-transition` is what makes each flip a smooth
        // grow/fade rather than an instant jump -- reduced motion skips
        // the layer's own toggle effect entirely (see below), leaving it
        // permanently at this same collapsed/steady paint.
        map.addLayer({
          id: NATIONAL_SOURCES_PULSE_LAYER_ID,
          type: 'circle',
          source: NATIONAL_SOURCES_SOURCE_ID,
          paint: {
            ...nationalSourceAmbientPulsePaint(false),
            'circle-radius-transition': { duration: reduceMotion ? 0 : NATIONAL_SOURCES_PULSE_CYCLE_MS / 2 },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : NATIONAL_SOURCES_PULSE_CYCLE_MS / 2 },
          },
        })

        // Stable selection halo -- appears quickly (~250ms) and stays
        // put, distinct from the one-shot ripple above.
        map.addLayer({
          id: 'national-sources-halo',
          type: 'circle',
          source: NATIONAL_SOURCES_SOURCE_ID,
          paint: {
            'circle-radius': 11,
            'circle-color': 'transparent',
            'circle-stroke-width': 2,
            'circle-stroke-color': '#10b981',
            'circle-stroke-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 1, 0],
            'circle-stroke-opacity-transition': { duration: reduceMotion ? 0 : 250 },
          },
        })

        // GEO33B Section 7: the co-location "stack" indicator. Sits
        // between the halo and the icon so it reads as belonging to the
        // marker without ever covering its steady red core. Its paint is
        // a `step` on the real `stackCount` that resolves to radius 0 /
        // stroke-width 0 for the overwhelmingly common `stackCount === 1`
        // case, so this layer is genuinely invisible unless two or more
        // DISTINCT real observed records share one coordinate -- it can
        // never decorate a single record into looking like several.
        map.addLayer({
          id: NATIONAL_SOURCES_STACK_LAYER_ID,
          type: 'circle',
          source: NATIONAL_SOURCES_SOURCE_ID,
          paint: nationalStackIndicatorPaint(),
        })

        map.addLayer({
          id: 'national-sources-symbol',
          type: 'symbol',
          source: NATIONAL_SOURCES_SOURCE_ID,
          // FMD-10C1: initial shape taken from this mount-only effect's
          // closure (the value `nationalMarkerShape` had on the FIRST
          // render) -- the dedicated toggle effect below applies any
          // LATER change, exactly mirroring the existing
          // `showOperationalLayer` mount/toggle pattern in this file.
          layout: sourceIconLayout(nationalMarkerShape === 'circle' ? FMD_SOURCE_ICON_ID : SOURCE_ICON_ID),
          paint: {
            'icon-opacity': ['case', ['boolean', ['feature-state', 'dimmed'], false], 0.35, 1],
            'icon-opacity-transition': { duration: reduceMotion ? 0 : 200 },
          },
        })

        map.addLayer({ id: 'sources-symbol', type: 'symbol', source: SOURCES_SOURCE_ID, layout: sourceIconLayout() })

        // Fixed-size north-facing icon, rotated by the backend's own
        // bearing_deg via a data-driven expression -- never a scaled
        // length (Part 10: no scaling by risk/rate/confidence/clarity).
        map.addLayer({
          id: 'direction-arrows',
          type: 'symbol',
          source: DIRECTIONS_SOURCE_ID,
          // GEO33B Section 2's documented stale-closure caveat applies here
          // too -- this initial value is corrected immediately by the
          // dedicated toggle effect below (`[showRiskLayer, showTrajectoryLayer]`),
          // which also runs once right after mount.
          layout: { ...directionIconLayout(), visibility: showRiskLayer || showTrajectoryLayer ? 'visible' : 'none' },
        })

        // GEO-INT-03 Section 9/10, REDESIGNED by GEO31A Section 2/3:
        // Verified Clinical Context / observed-outbreak overlay -- a red
        // steady-core icon (below) with a soft expanding halo/ring
        // UNDERNEATH it (this circle layer, added first so it paints
        // beneath the icon symbol layer). Starts hidden; the
        // showOperationalLayer effect below sets initial + subsequent
        // visibility for BOTH layers (Cases mode only). Initial visibility
        // is taken directly from this mount-only effect's closure (the
        // value `showOperationalLayer` had on the FIRST render) -- the
        // dedicated toggle effect below only re-runs on a LATER prop
        // change, so without this the layer could stay hidden forever if
        // Cases mode (the default) never actually "changes" after the map
        // finishes its async load.
        map.addLayer({
          id: OPERATIONAL_MARKERS_HALO_LAYER_ID,
          type: 'circle',
          source: OPERATIONAL_MARKERS_SOURCE_ID,
          layout: { visibility: showOperationalLayer ? 'visible' : 'none' },
          paint: operationalMarkerHaloPaint(reduceMotion),
        })
        map.addLayer({
          id: OPERATIONAL_MARKERS_LAYER_ID,
          type: 'symbol',
          source: OPERATIONAL_MARKERS_SOURCE_ID,
          layout: { ...operationalMarkerIconLayout(), visibility: showOperationalLayer ? 'visible' : 'none' },
          paint: operationalMarkerPaint(reduceMotion),
        })

        map.on('click', 'cells-circle', (e) => {
          const feature = e.features?.[0]
          if (feature) onSelectCell?.(feature)
        })
        map.on('click', 'national-sources-symbol', (e) => {
          const feature = e.features?.[0]
          if (feature) onSelectSource?.(feature.properties.outbreakId, feature.properties.source_id)
        })
        // Section 11/12: a compact operational popup only -- deliberately
        // does NOT call onSelectSource/onSelectCell, never touches
        // selectedOutbreakId, never fits/flies the camera.
        map.on('click', OPERATIONAL_MARKERS_LAYER_ID, (e) => {
          const feature = e.features?.[0]
          if (feature) onSelectOperationalCase?.(feature.properties)
        })
        for (const layerId of ['cells-circle', 'national-sources-symbol', OPERATIONAL_MARKERS_LAYER_ID]) {
          map.on('mouseenter', layerId, () => {
            map.getCanvas().style.cursor = 'pointer'
          })
          map.on('mouseleave', layerId, () => {
            map.getCanvas().style.cursor = ''
          })
        }

        // Initial camera.
        //
        // GEO33B Section 5: for Page 1's national browsing view this is
        // now the real, fixed `SRI_LANKA_BOUNDS`, NOT the extent of
        // whatever markers happen to have loaded. Every real Sri Lanka LSD
        // record sits in the far north, so the previous marker-extent fit
        // opened the page zoomed onto the Jaffna peninsula -- the vet's own
        // district (and most of the country) was off-screen before they had
        // touched anything. "Sri Lanka Overview" has to actually open on
        // Sri Lanka; zooming to real records is what an explicit outbreak
        // SELECTION does, in the focused-origin effect below.
        //
        // The original single-snapshot debug view (`MapView.jsx`, which
        // passes no `nationalSources`) is untouched and still fits its own
        // real cells+sources extent exactly as before.
        const bounds = latestNationalSources
          ? SRI_LANKA_BOUNDS
          : computeCombinedLngLatBounds(latestCellFeatures, latestSourceFeatures)
        if (bounds) {
          map.fitBounds(bounds, { padding: MAP_FIT_PADDING, maxZoom: MAP_FIT_MAX_ZOOM, animate: false })
        }
      })
    } catch (err) {
      // WebGL unavailable / construction threw synchronously.
      // eslint-disable-next-line no-console
      console.warn('MapLibre could not initialize (falling back to SVG view):', err)
      if (!failedRef.current) {
        failedRef.current = true
        onMapUnavailable?.()
      }
    }

    return () => {
      if (reachRingAnimRef.current) cancelAnimationFrame(reachRingAnimRef.current)
      if (page1ForecastAnimRef.current) cancelAnimationFrame(page1ForecastAnimRef.current)
      resizeObserver?.disconnect()
      map?.remove()
      mapRef.current = null
    }
    // Intentionally mount-once: every prop that needs to affect an
    // already-created map is applied via the effects below, never by
    // remounting (plan Section 18's "no remount on selection").
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- focused-origin data (cells/sources/directions) arrives/changes ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return

    const cellsFC = buildCellsFeatureCollection(cellFeatures)
    const sourcesFC = buildSourcesFeatureCollection({ type: 'FeatureCollection', features: sourceFeatures })
    const directionsFC = buildDirectionFeatureCollection(cellFeatures)
    map.getSource(CELLS_SOURCE_ID)?.setData(cellsFC)
    map.getSource(SOURCES_SOURCE_ID)?.setData(sourcesFC)
    map.getSource(DIRECTIONS_SOURCE_ID)?.setData(directionsFC)

    if (cellFeatures.length > 0) {
      const tierStats = computeRiskTierStats(cellFeatures)
      map.setPaintProperty('cells-circle', 'circle-color', riskTierColorExpression(tierStats))
    }

    // One smooth fit, only on an ACTUAL new outbreak selection (never
    // re-fit for the same origin just because the parent re-rendered
    // with a fresh array reference, and never on a timeline day change
    // -- day changes don't touch cellFeatures/sourceFeatures at all in
    // this checkpoint, see plan Section 25).
    // GEO-PAGE1-FINAL Section 10/24: `visuallySelectedOutbreakId` is
    // `null` for the page's own auto-picked default focus, so the camera
    // never jumps away from the calm Sri Lanka Overview just because a
    // default origin's real cells/sources happened to resolve -- only a
    // genuine vet click (which flips `autoFocusOutbreak` off) fits here.
    if (nationalSources && visuallySelectedOutbreakId && visuallySelectedOutbreakId !== lastFitOutbreakIdRef.current) {
      lastFitOutbreakIdRef.current = visuallySelectedOutbreakId
      // GEO33B Section 7: membership, not equality. After the presentation
      // aggregation (`nationalSourcePresentation.js`) one marker can carry
      // several real `outbreakIds`, because one physical record is
      // genuinely eligible under several origins' 14-day windows. A plain
      // `properties.outbreakId === selectedOutbreakId` check silently
      // dropped such a record from its own origin's fit whenever the
      // aggregate happened to keep a different origin's id first.
      const focusedSources = nationalSources.features.filter((f) => featureBelongsToOutbreak(f, visuallySelectedOutbreakId))
      const bounds = computeCombinedLngLatBounds(cellFeatures, focusedSources)
      if (bounds) {
        map.fitBounds(bounds, { padding: MAP_FIT_PADDING, maxZoom: MAP_FIT_MAX_ZOOM, animate: !reduceMotion, duration: reduceMotion ? 0 : 1200 })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cellFeatures, sourceFeatures])

  // ---- national-sources data itself changes (e.g. once fetched) ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !nationalSources) return
    map.getSource(NATIONAL_SOURCES_SOURCE_ID)?.setData(nationalSources)
    markTiming(GEO_TIMING.FIRST_SET_DATA)
    if (nationalSources.features.length > 0) markTiming(GEO_TIMING.FIRST_OUTBREAK_RENDER)
    // GEO-VIVA-USER-VISIBLE-RECOVERY-05: repeats on every real update
    // (a disease switch's progressive per-origin reveal calls this many
    // times), unlike the once-ever marks above -- this is the actual
    // moment MapLibre received new real marker geometry to paint.
    markTiming(GEO_TIMING.NATIONAL_SOURCES_SET_DATA, { repeat: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nationalSources])

  // ---- Page-1 presentation frame changes. The three sources are created
  // once with the map and updated in-place; no MapLibre remount and no
  // request occurs on a timeline tick. Geometry interpolates for ~520ms
  // unless the user prefers reduced motion. ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !page1ForecastVisualization) return undefined
    const riskSource = map.getSource(PAGE1_FORECAST_RISK_SOURCE_ID)
    const pathSource = map.getSource(PAGE1_FORECAST_PATH_SOURCE_ID)
    const frontSource = map.getSource(PAGE1_FORECAST_FRONT_SOURCE_ID)
    if (!riskSource || !pathSource || !frontSource) return undefined

    if (page1ForecastAnimRef.current) {
      cancelAnimationFrame(page1ForecastAnimRef.current)
      page1ForecastAnimRef.current = null
    }

    const applySnapshot = (snapshot) => {
      riskSource.setData(snapshot.riskZones)
      pathSource.setData(snapshot.paths)
      frontSource.setData(snapshot.fronts)
      currentPage1ForecastRef.current = snapshot
    }
    const previous = currentPage1ForecastRef.current
    if (reduceMotion || !previous || previous.anchorCount !== page1ForecastVisualization.anchorCount) {
      applySnapshot(page1ForecastVisualization)
      return undefined
    }

    const startTime = performance.now()
    const tick = (now) => {
      const progress = Math.min(1, (now - startTime) / PAGE1_FORECAST_TRANSITION_MS)
      const eased = 1 - (1 - progress) ** 3
      applySnapshot(interpolatePage1ForecastVisualization(previous, page1ForecastVisualization, eased))
      if (progress < 1) page1ForecastAnimRef.current = requestAnimationFrame(tick)
      else page1ForecastAnimRef.current = null
    }
    page1ForecastAnimRef.current = requestAnimationFrame(tick)
    return () => {
      if (page1ForecastAnimRef.current) cancelAnimationFrame(page1ForecastAnimRef.current)
      page1ForecastAnimRef.current = null
    }
  }, [page1ForecastVisualization, reduceMotion])

  // ---- selection changes: halo/dim/ripple on the national layer ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !nationalSources) return

    // GEO33B Section 7: `source_id` is a SAFE promoted feature id again
    // now that the collection is aggregated to one feature per real
    // coordinate. Before aggregation the same `source_id` appeared on
    // several rows (one physical record, several overlapping eligibility
    // windows), so this loop wrote `selected: true` and then
    // `dimmed: true` to the SAME promoted id on different iterations --
    // whichever row happened to come last silently won.
    // GEO-PAGE1-FINAL Section 7/10/24: `visuallySelectedOutbreakId` stays
    // `null` while the current focus is only the page's auto-picked
    // default -- so the default Sri Lanka Overview shows every real
    // marker at full, equal, un-haloed visibility (no unexplained glow
    // on one marker the vet never clicked). A genuine click still dims
    // every other origin and halos/ripples the clicked one exactly as
    // before.
    for (const feature of nationalSources.features) {
      const id = feature.properties.source_id
      const belongs = featureBelongsToOutbreak(feature, visuallySelectedOutbreakId)
      const isSelected = visuallySelectedOutbreakId != null && belongs
      const isOtherOrigin = visuallySelectedOutbreakId != null && !belongs
      map.setFeatureState({ source: NATIONAL_SOURCES_SOURCE_ID, id }, { selected: isSelected, dimmed: isOtherOrigin, rippleExpanded: false })
    }

    if (visuallySelectedOutbreakId != null) {
      // Kick the ripple: start collapsed/opaque (already the default
      // above), then flip to expanded on the next frame so MapLibre's
      // paint-transition animates 8px/45%-opacity -> 22px/0%-opacity
      // once, per plan Section 27 ("one restrained selection animation").
      const selectedIds = nationalSources.features
        .filter((f) => featureBelongsToOutbreak(f, visuallySelectedOutbreakId))
        .map((f) => f.properties.source_id)
      requestAnimationFrame(() => {
        for (const id of selectedIds) {
          map.setFeatureState({ source: NATIONAL_SOURCES_SOURCE_ID, id }, { rippleExpanded: true })
        }
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visuallySelectedOutbreakId, nationalSources])

  // ---- GEO-VISUAL-POLISH-01: continuous ambient pulse clock for every
  // national source marker. A single shared RAF loop toggling ONE
  // layer-level paint property twice per cycle (never a per-feature
  // setFeatureState loop) -- cost is independent of how many real markers
  // exist. RAF-driven, never setInterval/setTimeout (`noAutoPolling.test.js`
  // bans both anywhere in this feature outside the one documented
  // operational scheduler); ticks against `performance.now()` so the
  // actual flip cadence stays correct regardless of frame rate, matching
  // this file's own playback-adjacent reach-ring tween. Skipped entirely
  // under reduced motion -- the layer then simply stays at its initial
  // collapsed/steady paint from the mount effect above. ----
  useEffect(() => {
    if (reduceMotion) return undefined
    const HALF_CYCLE_MS = NATIONAL_SOURCES_PULSE_CYCLE_MS / 2
    let expanded = false
    let lastTick = performance.now()
    let frame
    const tick = (now) => {
      const map = mapRef.current
      if (map && loadedRef.current && map.getLayer(NATIONAL_SOURCES_PULSE_LAYER_ID) && now - lastTick >= HALF_CYCLE_MS) {
        lastTick = now
        expanded = !expanded
        const paint = nationalSourceAmbientPulsePaint(expanded)
        map.setPaintProperty(NATIONAL_SOURCES_PULSE_LAYER_ID, 'circle-radius', paint['circle-radius'])
        map.setPaintProperty(NATIONAL_SOURCES_PULSE_LAYER_ID, 'circle-opacity', paint['circle-opacity'])
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      if (frame) cancelAnimationFrame(frame)
    }
  }, [reduceMotion])

  // ---- Page-1 risk contours: the SAME continuous ambient-pulse pattern
  // as the national-source marker pulse just above -- one shared RAF loop
  // toggling the two risk layers' `fill-opacity`/`line-opacity` paint
  // properties (never geometry) a few percent every half-cycle, purely
  // decorative "breathing". This is entirely separate from the real
  // Sep01-14 timeline geometry update effect below (`page1ForecastVisualization`
  // dependency), which is the ONLY thing that ever changes contour
  // position/size/`riskLevel` -- the two animation concepts never share
  // code or a trigger. Skipped under reduced motion, same as every other
  // ambient effect in this file. ----
  useEffect(() => {
    if (reduceMotion) return undefined
    const HALF_CYCLE_MS = PAGE1_RISK_PULSE_CYCLE_MS / 2
    let expanded = false
    let lastTick = performance.now()
    let frame
    const tick = (now) => {
      const map = mapRef.current
      if (map && loadedRef.current && map.getLayer(PAGE1_FORECAST_RISK_FILL_LAYER_ID) && now - lastTick >= HALF_CYCLE_MS) {
        lastTick = now
        expanded = !expanded
        map.setPaintProperty(PAGE1_FORECAST_RISK_FILL_LAYER_ID, 'fill-opacity', page1RiskFillOpacityExpression(expanded))
        map.setPaintProperty(PAGE1_FORECAST_RISK_LINE_LAYER_ID, 'line-opacity', page1RiskLineOpacityExpression(expanded))
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      if (frame) cancelAnimationFrame(frame)
    }
  }, [reduceMotion])

  // ---- nominal-reach ring: smooth grow/shrink between real day values,
  // plus the same real radius/centers driving the gradient-band source
  // (GEO-REACH-GRADIENT-01) so the fill and the boundary line are always
  // in lockstep -- one real radius value, two rendering layers. ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const source = map.getSource(REACH_RING_SOURCE_ID)
    const gradientSource = map.getSource(REACH_GRADIENT_SOURCE_ID)
    if (!source || !gradientSource) return

    if (reachRingAnimRef.current) {
      cancelAnimationFrame(reachRingAnimRef.current)
      reachRingAnimRef.current = null
    }

    if (!reachRingCenters || reachRingCenters.length === 0 || !(reachRingRadiusKm > 0)) {
      source.setData(emptyReachRingFeatureCollection())
      gradientSource.setData(emptyReachRingFeatureCollection())
      currentReachRadiusKmRef.current = 0
      const pulseSource = map.getSource(REACH_GROWTH_PULSE_SOURCE_ID)
      if (pulseSource && map.getLayer('reach-ring-growth-pulse')) {
        pulseSource.setData(emptyReachRingFeatureCollection())
        map.setPaintProperty('reach-ring-growth-pulse', 'line-opacity-transition', { duration: 0 })
        map.setPaintProperty('reach-ring-growth-pulse', 'line-opacity', 0)
      }
      return
    }

    // Tween by re-evaluating buildReachRingFeatureCollectionForCenters at
    // the SAME real centers with an interpolated radius each frame. The
    // in-progress radius is tracked in a ref (not read back from the
    // MapLibre source's internal state, which is a private/undocumented
    // property) so the next tween always starts from wherever the
    // previous one actually ended, including a value the user
    // interrupted mid-tween.
    const targetRadiusKm = reachRingRadiusKm
    const priorRadiusKm = currentReachRadiusKmRef.current

    // GEO-REACH-GRADIENT-01: a real, event-driven growth pulse -- fires
    // only when the real target radius genuinely INCREASED from wherever
    // the ring currently is (a real forward day advance, never a
    // backward scrub/rewind, and never on the initial reveal from zero
    // radius, which already has its own tween-in). See
    // `REACH_GROWTH_PULSE_SOURCE_ID`'s module comment for why this
    // one-shot flash-then-fade (not a continuous loop) is the honest
    // substitute for a literal marching-ants boundary.
    if (!reduceMotion && priorRadiusKm > 0 && targetRadiusKm > priorRadiusKm && map.getLayer('reach-ring-growth-pulse')) {
      const pulseSource = map.getSource(REACH_GROWTH_PULSE_SOURCE_ID)
      if (pulseSource) {
        pulseSource.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, targetRadiusKm))
        map.setPaintProperty('reach-ring-growth-pulse', 'line-opacity-transition', { duration: 0 })
        map.setPaintProperty('reach-ring-growth-pulse', 'line-opacity', 0.9)
        requestAnimationFrame(() => {
          const stillMounted = mapRef.current === map
          if (!stillMounted || !map.getLayer('reach-ring-growth-pulse')) return
          map.setPaintProperty('reach-ring-growth-pulse', 'line-opacity-transition', { duration: REACH_GROWTH_PULSE_MS })
          map.setPaintProperty('reach-ring-growth-pulse', 'line-opacity', 0)
        })
      }
    }

    if (reduceMotion) {
      source.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, targetRadiusKm))
      gradientSource.setData(buildReachGradientFeatureCollectionForCenters(reachRingCenters, targetRadiusKm))
      currentReachRadiusKmRef.current = targetRadiusKm
      return
    }

    const startRadiusKm = priorRadiusKm
    const startTime = performance.now()

    const tick = (now) => {
      const t = Math.min(1, (now - startTime) / REACH_RING_TWEEN_MS)
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2 // ease-in-out
      const currentRadiusKm = startRadiusKm + (targetRadiusKm - startRadiusKm) * eased
      currentReachRadiusKmRef.current = currentRadiusKm
      source.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, currentRadiusKm))
      gradientSource.setData(buildReachGradientFeatureCollectionForCenters(reachRingCenters, currentRadiusKm))
      if (t < 1) {
        reachRingAnimRef.current = requestAnimationFrame(tick)
      } else {
        reachRingAnimRef.current = null
      }
    }
    reachRingAnimRef.current = requestAnimationFrame(tick)

    return () => {
      if (reachRingAnimRef.current) cancelAnimationFrame(reachRingAnimRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reachRingCenters, reachRingRadiusKm, reduceMotion])

  // ---- GEO-INT-03 Section 13: operational data updates -- NEVER fits/
  // flies/eases the camera. A 60s controlled auto-refresh (or a manual
  // one) must not move the vet's map; only the source data changes. ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    map.getSource(OPERATIONAL_MARKERS_SOURCE_ID)?.setData(operationalFeatures ?? { type: 'FeatureCollection', features: [] })
    // GEO-VIVA-USER-VISIBLE-RECOVERY-05: the real moment a Window
    // (observation-range) change's already-in-memory filter recompute
    // actually reaches the map -- this effect never fits/flies the
    // camera (Section 13 above), so first/final map reaction for a
    // Window change ARE this one instant.
    markTiming(GEO_TIMING.OPERATIONAL_MARKERS_SET_DATA, { repeat: true })
  }, [operationalFeatures])

  // ---- GEO30B Section 16: district geometry resolves asynchronously
  // (a real network fetch) -- this NEVER fits/flies/eases the camera on
  // its own (Section 12/18: resolving the polygon must not silently move
  // the vet's view; only the explicit "Focus My District" action does
  // that, via `resetView(bounds)`). ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    map.getSource(MY_DISTRICT_SOURCE_ID)?.setData(
      districtFeature ? { type: 'FeatureCollection', features: [districtFeature] } : { type: 'FeatureCollection', features: [] },
    )
  }, [districtFeature])

  // ---- GEO26B Section 12: transient "just arrived" farm-marker
  // highlight. `arrivalHighlightKey` is the real `farmDiseaseKey`
  // (`${farmId}::${disease}`) of the farm a genuine new verified-clinical
  // SSE event just landed for (set briefly by `OutbreakMapPage.jsx`,
  // never by this component itself). Uses the SAME `feature-state`
  // mechanism already used for the national-source "dimmed" halo above --
  // never a second, divergent selection-state technique. Clears itself
  // via `requestAnimationFrame`, matching this file's reach-ring tween --
  // never `setTimeout`/`setInterval` (forbidden anywhere in this feature,
  // `noAutoPolling.test.js`). Skips the highlight entirely under reduced
  // motion (the underlying marker/count update from `operationalFeatures`
  // above still happens either way -- only the transient visual emphasis
  // is skipped). ----
  // GEO31A Section 2/3: `justArrived` (6s) still drives ONLY the marker
  // icon's own opacity boost, unchanged. `pulseActive`+`pulseExpanded` are
  // a SHORTER (2.4s), separate pair of feature-states driving the halo
  // ring's "expands and fades... repeat only for a short meaningful
  // arrival sequence, then settle to steady" behavior (Section 2): every
  // `PULSE_CYCLE_MS`, `pulseExpanded` flips, and the halo's own paint-
  // transition (`operationalMarkerHaloPaint`) animates the resulting
  // small<->large/opaque<->faded change smoothly -- one visible pulse per
  // flip. Once `PULSE_REPEAT_COUNT` cycles elapse, `pulseActive` clears
  // and the halo falls back to fully invisible (steady marker, no ring)
  // for the remainder of the (longer) `justArrived` window and beyond --
  // it never stays visible indefinitely. Still RAF-only, never
  // `setInterval`/`setTimeout` (`noAutoPolling.test.js`).
  // GEO33B Section 8/11: the SAME one-shot pulse now also covers markers
  // that a real Observed-Replay step just revealed (`newlyRevealedKeys`),
  // not only live SSE arrivals. This deliberately reuses the existing
  // feature-state machinery and the existing single RAF loop rather than
  // adding a second, divergent animation path -- and it stays strictly
  // per-feature and time-bounded, so historical markers are NEVER given a
  // permanent/global animated layer (the pulse is driven by feature-state
  // that this effect itself clears; the halo layer's fall-through case is
  // `0` opacity, i.e. no ring at all once settled).
  //
  // `pulseKeySignature` is a stable primitive (sorted, joined) so a parent
  // re-render producing an equal-but-new array can never restart a pulse
  // that is already running.
  const pulseKeySignature = Array.from(new Set([arrivalHighlightKey, ...(newlyRevealedKeys ?? [])].filter(Boolean)))
    .sort()
    .join('|')
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !pulseKeySignature || reduceMotion) return undefined
    const ARRIVAL_HIGHLIGHT_MS = 6000
    const PULSE_CYCLE_MS = 800
    const PULSE_REPEAT_COUNT = 3
    const PULSE_SEQUENCE_MS = PULSE_CYCLE_MS * PULSE_REPEAT_COUNT
    const targets = pulseKeySignature.split('|').map((id) => ({ source: OPERATIONAL_MARKERS_SOURCE_ID, id }))
    const applyToAll = (state) => {
      for (const target of targets) map.setFeatureState(target, state)
    }
    applyToAll({ justArrived: true, pulseActive: true, pulseExpanded: false })
    const startTime = performance.now()
    let lastCycleIndex = 0
    let pulseSettled = false
    let frame = requestAnimationFrame(function tick(now) {
      const elapsed = now - startTime
      if (elapsed >= ARRIVAL_HIGHLIGHT_MS) {
        applyToAll({ justArrived: false, pulseActive: false, pulseExpanded: false })
        return
      }
      if (elapsed < PULSE_SEQUENCE_MS) {
        const cycleIndex = Math.floor(elapsed / PULSE_CYCLE_MS)
        if (cycleIndex !== lastCycleIndex) {
          lastCycleIndex = cycleIndex
          applyToAll({ pulseExpanded: cycleIndex % 2 === 1 })
        }
      } else if (!pulseSettled) {
        // The pulse sequence just ended -- settle the ring immediately
        // (Section 2: "repeat only for a short meaningful arrival
        // sequence, then settle to steady"), only once.
        pulseSettled = true
        applyToAll({ pulseActive: false, pulseExpanded: false })
      }
      frame = requestAnimationFrame(tick)
    })
    return () => {
      cancelAnimationFrame(frame)
      applyToAll({ justArrived: false, pulseActive: false, pulseExpanded: false })
    }
  }, [pulseKeySignature, reduceMotion])

  // ---- GEO31A Section 2 "Selected outbreak: additional distinct halo" --
  // a STEADY selection ring, independent of arrival, driven the same way
  // as the national-sources selection halo above: set on the currently
  // popup-open farm, cleared on every previously-selected one. ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return undefined
    const previousKey = selectedOperationalKeyRef.current
    if (previousKey && previousKey !== selectedOperationalKey) {
      map.setFeatureState({ source: OPERATIONAL_MARKERS_SOURCE_ID, id: previousKey }, { selected: false })
    }
    if (selectedOperationalKey) {
      map.setFeatureState({ source: OPERATIONAL_MARKERS_SOURCE_ID, id: selectedOperationalKey }, { selected: true })
    }
    selectedOperationalKeyRef.current = selectedOperationalKey
  }, [selectedOperationalKey])

  // ---- GEO-INT-03 Section 10: Cases-mode-only visibility toggle ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const visibility = showOperationalLayer ? 'visible' : 'none'
    if (map.getLayer(OPERATIONAL_MARKERS_LAYER_ID)) map.setLayoutProperty(OPERATIONAL_MARKERS_LAYER_ID, 'visibility', visibility)
    if (map.getLayer(OPERATIONAL_MARKERS_HALO_LAYER_ID)) map.setLayoutProperty(OPERATIONAL_MARKERS_HALO_LAYER_ID, 'visibility', visibility)
  }, [showOperationalLayer])

  // ---- GEO31A Section 8/10: Risk-Zones-mode-only visibility toggle for
  // the real scored-cell layer -- a mode switch reveals already-fetched
  // real data instantly (no refetch, no camera move), exactly like the
  // operational-layer toggle above. `cells-circle` (risk-TIER dots) stays
  // exclusive to Risk Zones; `direction-arrows` (real per-cell
  // `bearing_deg`) is shared with Trajectory mode (GEO-TRAJECTORY-01) --
  // both real data, never fabricated for either mode. ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    if (map.getLayer('cells-circle')) map.setLayoutProperty('cells-circle', 'visibility', showRiskLayer ? 'visible' : 'none')
    if (map.getLayer('direction-arrows')) {
      map.setLayoutProperty('direction-arrows', 'visibility', showRiskLayer || showTrajectoryLayer ? 'visible' : 'none')
    }
  }, [showRiskLayer, showTrajectoryLayer])

  // The generated purple spread is common to Cases/Risk/Trajectory. Only
  // the four qualitative risk bands switch with Risk Zones mode.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const forecastVisibility = showPage1ForecastLayer ? 'visible' : 'none'
    for (const layerId of ['page1-forecast-path-glow', 'page1-forecast-path', 'page1-forecast-front-glow', 'page1-forecast-front']) {
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', forecastVisibility)
    }
    const riskVisibility = showPage1ForecastLayer && showPage1ForecastRiskZones ? 'visible' : 'none'
    for (const layerId of [PAGE1_FORECAST_RISK_FILL_LAYER_ID, PAGE1_FORECAST_RISK_LINE_LAYER_ID]) {
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', riskVisibility)
    }
    if (map.getLayer('page1-forecast-path')) {
      map.setPaintProperty('page1-forecast-path', 'line-width', showTrajectoryLayer ? 4.5 : 3.25)
      map.setPaintProperty('page1-forecast-path', 'line-opacity', showTrajectoryLayer ? 1 : 0.92)
    }
    if (map.getLayer('page1-forecast-front')) {
      map.setPaintProperty('page1-forecast-front', 'circle-radius', showTrajectoryLayer ? 6 : 5)
    }
  }, [showPage1ForecastLayer, showPage1ForecastRiskZones, showTrajectoryLayer])

  // ---- FMD-10C1: national-source marker shape follows the selected
  // disease's `markerShape` (diamond=LSD, circle=FMD) -- color never
  // changes, only the registered icon image the layer points at. ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    if (!map.getLayer('national-sources-symbol')) return
    map.setLayoutProperty('national-sources-symbol', 'icon-image', nationalMarkerShape === 'circle' ? FMD_SOURCE_ICON_ID : SOURCE_ICON_ID)
  }, [nationalMarkerShape])

  return (
    // `geo-map-shell` is the scope root for this feature's own MapLibre
    // control chrome (`geospatialMapChrome.css`) -- nothing outside this
    // component's subtree is affected.
    <div className="geo-map-shell relative h-full w-full overflow-hidden rounded border">
      <div ref={containerRef} className="h-full min-h-[650px] w-full" role="application" aria-label="Geospatial scientific map" />

      {/* GEO33B Section 4: a restrained, honest "the basemap is still
          loading" state, shown ONLY until the style actually loads.
          Deliberately:
           - `pointer-events-none`, so it never blocks interaction with
             anything beneath or beside it;
           - an overlay on the map card only -- the page header, control
             bar, mode toolbar, legend and timeline all render and stay
             usable underneath it, so the rest of the page is never
             blocked on the map;
           - worded about the BASEMAP specifically, never "loading data".
             Real geography can and does appear before marker data has
             arrived (the two are independent fetches), so this must not
             imply anything about outbreak/case availability;
           - a soft pulse on a single small dot rather than a full-card
             shimmer sweep -- matching this page's existing restrained
             dark chrome instead of introducing a new animation language.
             `aria-hidden` keeps it out of the accessibility tree: the
             map container already carries the real `role="application"`
             label, and this is purely decorative reassurance. */}
      {!styleReady && !failedRef.current && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950"
        >
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-400 backdrop-blur">
            <span className={reduceMotion ? 'h-1.5 w-1.5 rounded-full bg-slate-500' : 'h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500'} />
            Loading map…
          </div>
        </div>
      )}
    </div>
  )
})

export default MapLibreCanvas
