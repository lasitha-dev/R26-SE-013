import maplibregl from 'maplibre-gl'
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
import { AREA_RISK_COLORS } from '../adapters/myAreaPresentationForecast'
import { FARM_MARKER_ICON_ID, buildFarmMarkerImage, farmMarkerIconLayout } from './myAreaIcons'
import { resolveBasemapConfig } from './basemapConfig'
import { SOURCE_ICON_ID, buildSourceMarkerImage } from './presentationIcons'
// GEO-MY-AREA-VISUAL-QA-FIX: the same real, fixed Sri Lanka presentation
// constants Page 1's map already opens on (`MapLibreCanvas.jsx`) -- reused
// verbatim, never redeclared, so this map's FIRST frame (before the real
// farm coordinate has loaded) is already Sri Lanka, never MapLibre's own
// default world view ([0,0], zoom 0).
import { SRI_LANKA_CENTER, SRI_LANKA_INITIAL_ZOOM } from './MapLibreCanvas'

const FARM_SOURCE_ID = 'geo-my-area-farm'
const SOURCES_SOURCE_ID = 'geo-my-area-sources'
const REACH_RING_SOURCE_ID = 'geo-my-area-reach-ring'
const OBSERVED_CASES_SOURCE_ID = 'geo-my-area-observed-cases'
const AREA_FORECAST_RISK_SOURCE_ID = 'geo-my-area-forecast-risk'
const AREA_FORECAST_PATH_SOURCE_ID = 'geo-my-area-forecast-paths'
const AREA_FORECAST_FRONT_SOURCE_ID = 'geo-my-area-forecast-fronts'
const AREA_RISK_LAYER_IDS = ['green', 'yellow', 'orange', 'red'].flatMap((riskLevel) => [
  `my-area-forecast-risk-${riskLevel}`,
  `my-area-forecast-risk-${riskLevel}-outline`,
])
const AREA_PROJECTION_LAYER_IDS = [
  'my-area-forecast-path-glow',
  'my-area-forecast-path',
  'my-area-forecast-front-glow',
  'my-area-forecast-front',
  'my-area-forecast-selected-risk-outline',
  'my-area-forecast-selected-path',
]
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
  if (containerWidth < 900) return { top: 30, bottom: 120, left: 28, right: 28 }
  return { top: 38, bottom: 124, left: 42, right: 42 }
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
    showAreaImpact = true,
    focusedCaseId = null,
    districtFeature = null,
    reachRingCenters = null,
    reachRingRadiusKm = 0,
    selectedOriginId = null,
    reduceMotion = false,
    onMapUnavailable,
  },
  ref,
) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const failedRef = useRef(false)
  const loadedRef = useRef(false)
  const lastFitAreaScopeRef = useRef(undefined)
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
        attributionControl: true,
      })
      mapRef.current = map
      map.dragRotate.disable()
      map.touchZoomRotate.disableRotation()
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

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
        resizeObserver = new ResizeObserver(() => {
          mapRef.current?.resize()
        })
        resizeObserver.observe(containerRef.current)
      }

      map.on('error', (e) => {
        // eslint-disable-next-line no-console
        console.warn('MapLibre map error on My Area (falling back):', e?.error?.message || e)
        if (!failedRef.current) {
          failedRef.current = true
          onMapUnavailable?.()
        }
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
        map.addSource(AREA_FORECAST_RISK_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.riskZones ?? { type: 'FeatureCollection', features: [] } })
        map.addSource(AREA_FORECAST_PATH_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.paths ?? { type: 'FeatureCollection', features: [] } })
        map.addSource(AREA_FORECAST_FRONT_SOURCE_ID, { type: 'geojson', data: initialAreaForecast?.fronts ?? { type: 'FeatureCollection', features: [] } })
        map.addLayer({ id: 'my-area-district-fill', type: 'fill', source: DISTRICT_SOURCE_ID, paint: { 'fill-color': '#4edea3', 'fill-opacity': 0.08 } })
        for (const riskLevel of ['green', 'yellow', 'orange', 'red']) {
          const color = AREA_RISK_COLORS[riskLevel]
          map.addLayer({
            id: `my-area-forecast-risk-${riskLevel}`,
            type: 'fill',
            source: AREA_FORECAST_RISK_SOURCE_ID,
            filter: ['==', ['get', 'riskLevel'], riskLevel],
            layout: { visibility: initialAreaImpactVisibility },
            paint: {
              'fill-color': color,
              'fill-opacity': ['coalesce', ['get', 'fillOpacity'], 0],
              'fill-opacity-transition': { duration: reduceMotion ? 0 : 420 },
            },
          })
          map.addLayer({
            id: `my-area-forecast-risk-${riskLevel}-outline`,
            type: 'line',
            source: AREA_FORECAST_RISK_SOURCE_ID,
            filter: ['==', ['get', 'riskLevel'], riskLevel],
            layout: { visibility: initialAreaImpactVisibility },
            paint: {
              'line-color': color,
              'line-width': riskLevel === 'red' ? 1.6 : 1.15,
              'line-opacity': ['coalesce', ['get', 'lineOpacity'], 0],
              'line-blur': 0.35,
              'line-opacity-transition': { duration: reduceMotion ? 0 : 420 },
            },
          })
        }
        map.addLayer({ id: 'my-area-district-outline', type: 'line', source: DISTRICT_SOURCE_ID, paint: { 'line-color': '#4edea3', 'line-width': 1.5, 'line-opacity': 0.85 } })
        map.addLayer({
          id: 'my-area-forecast-path-glow',
          type: 'line',
          source: AREA_FORECAST_PATH_SOURCE_ID,
          layout: { 'line-cap': 'round', 'line-join': 'round', visibility: initialAreaImpactVisibility },
          paint: { 'line-color': AREA_RISK_COLORS.purple, 'line-width': 8, 'line-blur': 4, 'line-opacity': 0.18 },
        })
        map.addLayer({
          id: 'my-area-forecast-path',
          type: 'line',
          source: AREA_FORECAST_PATH_SOURCE_ID,
          layout: { 'line-cap': 'round', 'line-join': 'round', visibility: initialAreaImpactVisibility },
          paint: { 'line-color': AREA_RISK_COLORS.purpleAccent, 'line-width': 3.1, 'line-opacity': 0.95 },
        })
        map.addLayer({
          id: 'my-area-forecast-front-glow',
          type: 'circle',
          source: AREA_FORECAST_FRONT_SOURCE_ID,
          layout: { visibility: initialAreaImpactVisibility },
          paint: { 'circle-radius': 10, 'circle-color': AREA_RISK_COLORS.purple, 'circle-blur': 0.8, 'circle-opacity': 0.3 },
        })
        map.addLayer({
          id: 'my-area-forecast-front',
          type: 'circle',
          source: AREA_FORECAST_FRONT_SOURCE_ID,
          layout: { visibility: initialAreaImpactVisibility },
          paint: { 'circle-radius': 5.5, 'circle-color': AREA_RISK_COLORS.purpleAccent, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.2, 'circle-opacity': 0.98 },
        })
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

        map.addLayer({ id: 'my-area-sources-symbol', type: 'symbol', source: SOURCES_SOURCE_ID, layout: sourceIconLayout() })
        map.addLayer({ id: 'my-area-farm-symbol', type: 'symbol', source: FARM_SOURCE_ID, layout: farmMarkerIconLayout() })
        map.addLayer({
          id: 'my-area-observed-cases-pulse',
          type: 'circle',
          source: OBSERVED_CASES_SOURCE_ID,
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
            'circle-color': '#EF4444',
            'circle-stroke-color': '#fff1f2',
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
          const properties = event.features?.[0]?.properties ?? {}
          const root = document.createElement('div')
          root.className = 'space-y-1 text-xs'
          for (const [label, value] of [
            ['Verified case', properties.caseId],
            ['Disease', properties.disease],
            ['Verified', properties.verificationTime],
          ]) {
            if (!value) continue
            const row = document.createElement('div')
            row.textContent = `${label}: ${value}`
            root.appendChild(row)
          }
          new maplibregl.Popup({ closeButton: true, closeOnClick: true })
            .setLngLat(event.features[0].geometry.coordinates)
            .setDOMContent(root)
            .addTo(map)
        })
        map.on('mouseenter', 'my-area-observed-cases-core', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'my-area-observed-cases-core', () => { map.getCanvas().style.cursor = '' })

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
        onMapUnavailable?.()
      }
    }

    return () => {
      if (reachRingAnimRef.current) cancelAnimationFrame(reachRingAnimRef.current)
      if (observedPulseAnimRef.current) cancelAnimationFrame(observedPulseAnimRef.current)
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

    // Wait for the real ADM2 polygon and fit it exactly once. Origin,
    // timeline, clinical refresh, risk, and reach updates never enter the
    // area-scope key and therefore can never move this camera.
    const districtBounds = districtFeature ? computeFeatureBounds(districtFeature) : null
    const districtIdentity = districtFeature?.properties?.shapeName ?? districtFeature?.properties?.shapeID ?? null
    const areaScopeKey = districtBounds && districtIdentity ? `${area?.farmId ?? 'district'}::${districtIdentity}` : null
    if (areaScopeKey && areaScopeKey !== lastFitAreaScopeRef.current) {
      lastFitAreaScopeRef.current = areaScopeKey
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
    const empty = { type: 'FeatureCollection', features: [] }
    map.getSource(AREA_FORECAST_RISK_SOURCE_ID)?.setData(areaForecastVisualization?.riskZones ?? empty)
    map.getSource(AREA_FORECAST_PATH_SOURCE_ID)?.setData(areaForecastVisualization?.paths ?? empty)
    map.getSource(AREA_FORECAST_FRONT_SOURCE_ID)?.setData(areaForecastVisualization?.fronts ?? empty)

    const visibility = showAreaImpact ? 'visible' : 'none'
    for (const layerId of [...AREA_RISK_LAYER_IDS, ...AREA_PROJECTION_LAYER_IDS]) {
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', visibility)
    }
  }, [areaForecastVisualization, showAreaImpact, mapLoaded])

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
    map.easeTo({
      center: coordinate,
      zoom: Math.max(map.getZoom(), 11.25),
      duration: reduceMotion ? 0 : 650,
      essential: true,
    })
  }, [focusedCaseId, observedCaseFeatures, reduceMotion, mapLoaded])

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
    <div className="h-full w-full overflow-hidden">
      {/* Parent owns the responsive viewport height; no competing minimum
          height is allowed, so the MapLibre canvas and card stay exact. */}
      <div ref={containerRef} className="h-full min-h-0 w-full" role="application" aria-label="My Area map" />
    </div>
  )
})

export default MyAreaMapCanvas
