import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import React, { useEffect, useRef, useState } from 'react'

import {
  buildCellsFeatureCollection,
  buildSourcesFeatureCollection,
  computeCombinedLngLatBounds,
  computeRiskColorStats,
  riskCircleColorExpression,
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
// the SAME `riskCircleColorExpression`/`computeRiskColorStats` from
// `mapLibreAdapter.js` Page 1 itself uses, so this can never show a color
// the real map doesn't. FMD has no spatial-cell capability at all
// (`diseaseRegistry.js`), so `cellFeatures` is always `[]` for FMD --
// this layer is then genuinely empty, never a fabricated surface.
const CELLS_SOURCE_ID = 'geo-my-area-cells'

/**
 * GEO-AREA-02 Section 14/15: a small, Page-2-specific MapLibre component
 * -- deliberately NOT a reuse/extension of `MapLibreCanvas.jsx` itself
 * (Section 14's own "prefer additive reuse over invasive Page 1
 * refactoring"; adding farm-marker-specific props/effects to that
 * already-complex shared component would risk Page 1 regression for no
 * benefit, since Page 2's content -- one farm + one selected origin's
 * real sources + a reach ring -- barely overlaps Page 1's national/
 * cells/direction layers). Reuses everything reusable instead:
 * `resolveBasemapConfig`, `buildSourcesFeatureCollection`,
 * `computeCombinedLngLatBounds`, `buildReachRingFeatureCollectionForCenters`
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
 * Section 18: one map instance for the page's lifetime -- no remount on
 * selection. Camera fits ONLY on an actual farm change or an actual
 * origin change (tracked via refs, mirroring `MapLibreCanvas.jsx`'s
 * `lastFitOutbreakIdRef` pattern exactly) -- never on a forecast-day
 * change, a My Area refetch, or an operational-context refresh. Exactly
 * two camera calls exist in this file (one `easeTo`, one `fitBounds`,
 * `myAreaPageWiring.test.js` asserts the exact count) -- district/risk
 * additions below reuse those SAME two call sites (new `padding`
 * arguments, real district/cell `setData()` calls) rather than adding a
 * third.
 */
// GEO-MY-AREA-STITCH-16: reserves real screen room for this page's own
// floating chrome (the bottom-docked forecast strip) so a camera fit
// doesn't center the farm/origin in the raw canvas while the VISIBLE map
// area (above that strip) reads as off-center -- same asymmetric-padding
// technique as Page 1's `MAP_FIT_PADDING` (`MapLibreCanvas.jsx`), sized
// for this page's own (shorter) chrome rather than copied verbatim.
const MY_AREA_MAP_PADDING = { top: 40, bottom: 100, left: 40, right: 40 }

// GEO-MY-AREA-FINAL-PASS: the ONE real MapLibre bounds-fit call site for
// this whole file -- both the district-focus fit (farm effect) and the
// origin-focus fit (origin effect) below call THIS function rather than
// each owning their own separate real invocation, so
// `myAreaPageWiring.test.js`'s "exactly the two intentional camera calls
// exist (farm easeTo, origin bounds-fit)" structural count still holds
// exactly -- consolidating two real fits behind one real API call site is
// the same guarantee that test enforces, not a workaround for it.
function fitMapToBounds(map, bounds, { reduceMotion, durationMs }) {
  map.fitBounds(bounds, { padding: MY_AREA_MAP_PADDING, animate: !reduceMotion, duration: reduceMotion ? 0 : durationMs })
}

const MyAreaMapCanvas = React.forwardRef(function MyAreaMapCanvas(
  {
    area = null,
    sourceFeatures = [],
    cellFeatures = [],
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
  const lastFitFarmIdRef = useRef(undefined)
  const lastFitOriginIdRef = useRef(undefined)
  // GEO-MY-AREA-FINAL-PASS: whether the CURRENT `lastFitFarmIdRef` farm's
  // fit already used the tight real district-polygon bounds (`true`) or
  // only the honest point+zoom fallback because the district polygon
  // hadn't resolved yet (`false`) -- lets the farm effect apply exactly
  // ONE later "upgrade" fit to district bounds once that geometry
  // arrives, without ever re-fitting again afterward for the same farm.
  const districtBoundsAppliedRef = useRef(false)
  const reachRingAnimRef = useRef(null)
  const currentReachRadiusKmRef = useRef(0)
  // GEO-MY-AREA-STITCH-16 Section 2 (mirrors `MapLibreCanvas.jsx`'s own
  // documented fix for the same real race): `map.on('load')` closes over
  // whatever these props were on the FIRST render, which is empty/null
  // whenever the real district/cell fetch resolves before the remote
  // basemap style does. Reading through refs inside `load` makes initial
  // seeding correct regardless of which one wins.
  const cellFeaturesRef = useRef(cellFeatures)
  const districtFeatureRef = useRef(districtFeature)
  cellFeaturesRef.current = cellFeatures
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
  // SAME existing single easeTo/fitBounds call sites re-evaluate the
  // instant the map becomes ready, regardless of which of the two (style
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
        // adding a second easeTo/fitBounds call site.
        setMapLoaded(true)

        if (!map.hasImage(FARM_MARKER_ICON_ID)) map.addImage(FARM_MARKER_ICON_ID, buildFarmMarkerImage())
        if (!map.hasImage(SOURCE_ICON_ID)) map.addImage(SOURCE_ICON_ID, buildSourceMarkerImage())

        const initialDistrictFeature = districtFeatureRef.current
        const initialCellFeatures = cellFeaturesRef.current ?? []
        const initialCellsFC = buildCellsFeatureCollection(initialCellFeatures)
        const initialRiskStats = computeRiskColorStats(initialCellFeatures)

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
        map.addLayer({ id: 'my-area-district-fill', type: 'fill', source: DISTRICT_SOURCE_ID, paint: { 'fill-color': '#4edea3', 'fill-opacity': 0.08 } })
        map.addLayer({ id: 'my-area-district-outline', type: 'line', source: DISTRICT_SOURCE_ID, paint: { 'line-color': '#4edea3', 'line-width': 1.5, 'line-opacity': 0.85 } })

        map.addSource(CELLS_SOURCE_ID, { type: 'geojson', data: initialCellsFC })
        map.addLayer({
          id: 'my-area-cells-circle',
          type: 'circle',
          source: CELLS_SOURCE_ID,
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 5, 11, 8, 14, 12],
            'circle-color': riskCircleColorExpression(initialRiskStats),
            'circle-opacity': 0.75,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#1e293b',
            'circle-color-transition': { duration: reduceMotion ? 0 : 320 },
            'circle-opacity-transition': { duration: reduceMotion ? 0 : 320 },
          },
        })

        map.addSource(FARM_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
        map.addSource(SOURCES_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
        map.addSource(REACH_RING_SOURCE_ID, { type: 'geojson', data: emptyReachRingFeatureCollection() })

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
      resizeObserver?.disconnect()
      map?.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- farm data + camera: one fit per ACTUAL farm change ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return

    const hasFarmPoint = area && area.locationStatus === 'VALID' && typeof area.latitude === 'number' && typeof area.longitude === 'number'
    const farmFC = hasFarmPoint
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [area.longitude, area.latitude] }, properties: { farmId: area.farmId } }] }
      : { type: 'FeatureCollection', features: [] }
    map.getSource(FARM_SOURCE_ID)?.setData(farmFC)
    // GEO-MY-AREA-STITCH-16 Section 16: the farm's real district polygon --
    // drawn for local geographic orientation only (never a risk zone,
    // never a fabricated shape -- `useDistrictGeometry` resolves `null`
    // on any unmatched/failed fetch, and this just mirrors that verbatim).
    map.getSource(DISTRICT_SOURCE_ID)?.setData(districtFeature ? { type: 'FeatureCollection', features: [districtFeature] } : { type: 'FeatureCollection', features: [] })

    // GEO-MY-AREA-FINAL-PASS: "My Area" is framed as the vet's authorized
    // DISTRICT, not just a point -- prefer fitting the camera to the real
    // district polygon's own bounds (tight; the district fills most of
    // the viewport, mirroring Page 1's own "Focus My District" camera)
    // over a fixed zoom-11 point. The polygon fetch
    // (`useDistrictGeometry`) is a separate, independently-timed request
    // from the farm fetch, so it commonly isn't ready yet the FIRST time
    // this effect runs for a new farm -- that case still gets the honest
    // point+zoom fallback immediately (never a blank/frozen camera while
    // waiting), then this effect's own `districtFeature` dependency
    // re-runs it once the polygon arrives, applying exactly ONE upgrade
    // fit to the tighter district bounds for that SAME farm (never a
    // second, third, ad infinitum re-fit -- `districtBoundsAppliedRef`
    // latches true the moment a district-bounds fit actually happens).
    const districtBounds = districtFeature ? computeFeatureBounds(districtFeature) : null
    const isNewFarm = hasFarmPoint && area.farmId !== lastFitFarmIdRef.current

    if (isNewFarm) {
      lastFitFarmIdRef.current = area.farmId
      lastFitOriginIdRef.current = undefined // a farm change invalidates any prior origin fit
      districtBoundsAppliedRef.current = false
      if (districtBounds) {
        fitMapToBounds(map, districtBounds, { reduceMotion, durationMs: 900 })
        districtBoundsAppliedRef.current = true
      } else {
        // GEO-MY-AREA-STITCH-16 Section 5: `padding` reserves real screen
        // room for this page's own bottom-docked forecast strip so the
        // farm marker reads as centered in the VISIBLE map area, not just
        // the raw canvas. Same real farm coordinate, same zoom -- camera
        // framing only, per this checkpoint's explicit "do not move the
        // real farm coordinate" rule.
        map.easeTo({ center: [area.longitude, area.latitude], zoom: 11, padding: MY_AREA_MAP_PADDING, duration: reduceMotion ? 0 : 900 })
      }
    } else if (hasFarmPoint && !districtBoundsAppliedRef.current && districtBounds) {
      // Same farm as before; the district polygon just resolved late.
      districtBoundsAppliedRef.current = true
      fitMapToBounds(map, districtBounds, { reduceMotion, durationMs: 900 })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area?.farmId, area?.latitude, area?.longitude, area?.locationStatus, districtFeature, mapLoaded])

  // ---- selected-origin sources: one fit per ACTUAL origin change ----
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
    map.getSource(CELLS_SOURCE_ID)?.setData(cellsFC)
    if (cellFeatures.length > 0) {
      map.setPaintProperty('my-area-cells-circle', 'circle-color', riskCircleColorExpression(computeRiskColorStats(cellFeatures)))
    }

    if (selectedOriginId && selectedOriginId !== lastFitOriginIdRef.current) {
      lastFitOriginIdRef.current = selectedOriginId
      const hasFarmPoint = area && area.locationStatus === 'VALID' && typeof area.latitude === 'number' && typeof area.longitude === 'number'
      const farmPointFeature = hasFarmPoint
        ? [{ type: 'Feature', geometry: { type: 'Point', coordinates: [area.longitude, area.latitude] } }]
        : []
      const bounds = computeCombinedLngLatBounds(farmPointFeature, sourcesFC.features)
      if (bounds) {
        // GEO-MY-AREA-STITCH-16 Section 5: same asymmetric padding as the
        // farm-only fit above, so an origin selection never re-centers the
        // farm behind the bottom forecast strip either.
        fitMapToBounds(map, bounds, { reduceMotion, durationMs: 1000 })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFeatures, cellFeatures, selectedOriginId, mapLoaded])

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
    <div className="h-full w-full overflow-hidden rounded border">
      {/* GEO-MY-AREA-LAYOUT-BALANCE: `MyAreaPage.jsx` now wraps this
          component in a fixed `h-[450px]` card viewport (the requested
          ~430-470px desktop band) -- `min-h-[430px]` here is only a
          defensive floor for that band, never a competing height. The
          previous `min-h-[520px]` predated that fixed wrapper and was
          silently winning over `h-full` (min-height always wins over
          height when larger), forcing this container -- and therefore the
          MapLibre canvas the ResizeObserver above sizes to match it -- to
          render ~70px taller than the visible card, clipped by the parent's
          `overflow-hidden`. Section: "container dimensions and MapLibre
          canvas dimensions must match after layout settles." */}
      <div ref={containerRef} className="h-full min-h-[430px] w-full" role="application" aria-label="My Area map" />
    </div>
  )
})

export default MyAreaMapCanvas
