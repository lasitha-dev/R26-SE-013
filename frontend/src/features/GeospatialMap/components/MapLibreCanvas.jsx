import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import React, { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { resolveBasemapConfig } from './basemapConfig'
import {
  buildCellsFeatureCollection,
  buildDirectionFeatureCollection,
  buildNationalSourcesFeatureCollection,
  buildSourcesFeatureCollection,
  computeCombinedLngLatBounds,
  computeRiskColorStats,
  directionIconLayout,
  riskCircleColorExpression,
  sourceIconLayout,
} from './mapLibreAdapter'
import { buildReachRingFeatureCollectionForCenters, emptyReachRingFeatureCollection } from './nominalReachRing'
import { CLINICAL_CIRCLE_ICON_ID, CLINICAL_DIAMOND_ICON_ID, buildClinicalCircleIcon, buildClinicalDiamondIcon } from './operationalIcons'
import { OPERATIONAL_MARKERS_LAYER_ID, OPERATIONAL_MARKERS_SOURCE_ID, operationalMarkerIconLayout } from './operationalMarkerLayer'
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
const REACH_RING_SOURCE_ID = 'geo-reach-ring'

const RIPPLE_TRANSITION_MS = 1800
const REACH_RING_TWEEN_MS = 800

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
 *  - `reduceMotion`: skips the camera-fit animation, the reach-ring
 *    tween (snaps instead), and the selection ripple.
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
    reachRingCenters = null,
    reachRingRadiusKm = 0,
    reduceMotion = false,
    operationalFeatures = null,
    showOperationalLayer = false,
    onSelectCell,
    onSelectSource,
    onSelectOperationalCase,
    onMapUnavailable,
  },
  ref,
) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const failedRef = useRef(false)
  const loadedRef = useRef(false)
  const lastFitOutbreakIdRef = useRef(undefined)
  const reachRingAnimRef = useRef(null)
  const currentReachRadiusKmRef = useRef(0)

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
    resetView() {
      const map = mapRef.current
      if (!map || !loadedRef.current || !nationalSources) return
      const bounds = computeCombinedLngLatBounds([], nationalSources.features)
      if (bounds) {
        map.fitBounds(bounds, { padding: 40, animate: !reduceMotion })
      }
    },
  }))

  // ---- mount: create the map once, wire every source/layer/handler ----
  useEffect(() => {
    let map
    let resizeObserver
    try {
      const basemap = resolveBasemapConfig(import.meta.env.VITE_GEOSPATIAL_BASEMAP_STYLE_URL)
      map = new maplibregl.Map({
        container: containerRef.current,
        style: basemap.style,
        pitch: 0,
        maxPitch: 0,
        bearing: 0,
        attributionControl: true,
      })
      mapRef.current = map

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
        const cellsFC = buildCellsFeatureCollection(cellFeatures)
        const sourcesFC = buildSourcesFeatureCollection({ type: 'FeatureCollection', features: sourceFeatures })
        const directionsFC = buildDirectionFeatureCollection(cellFeatures)
        const stats = computeRiskColorStats(cellFeatures)
        const nationalFC = nationalSources ?? { type: 'FeatureCollection', features: [] }

        if (!map.hasImage(SOURCE_ICON_ID)) map.addImage(SOURCE_ICON_ID, buildSourceMarkerImage())
        // FMD-10C1: registered unconditionally at mount (cheap,
        // presentation-only pixels) so a later disease switch to FMD
        // never has to add an image mid-session -- only the layer's
        // `icon-image` layout property switches, via the effect below.
        if (!map.hasImage(FMD_SOURCE_ICON_ID)) map.addImage(FMD_SOURCE_ICON_ID, buildFmdSourceMarkerImage())
        if (!map.hasImage(DIRECTION_ICON_ID)) map.addImage(DIRECTION_ICON_ID, buildDirectionArrowImage())
        if (!map.hasImage(CLINICAL_DIAMOND_ICON_ID)) map.addImage(CLINICAL_DIAMOND_ICON_ID, buildClinicalDiamondIcon())
        if (!map.hasImage(CLINICAL_CIRCLE_ICON_ID)) map.addImage(CLINICAL_CIRCLE_ICON_ID, buildClinicalCircleIcon())

        map.addSource(CELLS_SOURCE_ID, { type: 'geojson', data: cellsFC })
        map.addSource(SOURCES_SOURCE_ID, { type: 'geojson', data: sourcesFC })
        map.addSource(DIRECTIONS_SOURCE_ID, { type: 'geojson', data: directionsFC })
        map.addSource(NATIONAL_SOURCES_SOURCE_ID, { type: 'geojson', data: nationalFC, promoteId: 'source_id' })
        map.addSource(REACH_RING_SOURCE_ID, { type: 'geojson', data: emptyReachRingFeatureCollection() })
        map.addSource(OPERATIONAL_MARKERS_SOURCE_ID, { type: 'geojson', data: operationalFeatures ?? { type: 'FeatureCollection', features: [] } })

        map.addLayer({
          id: 'cells-circle',
          type: 'circle',
          source: CELLS_SOURCE_ID,
          paint: {
            'circle-radius': 5,
            'circle-color': riskCircleColorExpression(stats),
            'circle-stroke-width': 1,
            'circle-stroke-color': '#1e293b',
          },
        })

        // Nominal-reach ring (Section 22/26): dashed outline, near-zero
        // fill, a colour deliberately outside the risk red/orange/blue
        // family so it can never read as a risk zone. `-transition`
        // entries only smooth paint-PROPERTY changes (there are none
        // here); the actual grow/shrink is a source-data tween driven by
        // the `reachRingFeatureCollection` effect below.
        map.addLayer({
          id: 'reach-ring-fill',
          type: 'fill',
          source: REACH_RING_SOURCE_ID,
          paint: { 'fill-color': '#14b8a6', 'fill-opacity': 0.04 },
        })
        map.addLayer({
          id: 'reach-ring-line',
          type: 'line',
          source: REACH_RING_SOURCE_ID,
          paint: { 'line-color': '#14b8a6', 'line-width': 1.5, 'line-dasharray': [2, 2], 'line-opacity': 0.85 },
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
        map.addLayer({ id: 'direction-arrows', type: 'symbol', source: DIRECTIONS_SOURCE_ID, layout: directionIconLayout() })

        // GEO-INT-03 Section 9/10: Verified Clinical Context overlay --
        // hollow neutral-mint icon only, no paint-based risk/pulse
        // treatment of any kind. Starts hidden; the showOperationalLayer
        // effect below sets initial + subsequent visibility (Cases mode only).
        // Initial visibility is taken directly from this mount-only
        // effect's closure (the value `showOperationalLayer` had on the
        // FIRST render) -- the dedicated toggle effect below only re-runs
        // on a LATER prop change, so without this the layer could stay
        // hidden forever if Cases mode (the default) never actually
        // "changes" after the map finishes its async load.
        map.addLayer({
          id: OPERATIONAL_MARKERS_LAYER_ID,
          type: 'symbol',
          source: OPERATIONAL_MARKERS_SOURCE_ID,
          layout: { ...operationalMarkerIconLayout(), visibility: showOperationalLayer ? 'visible' : 'none' },
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

        // Initial camera: national bounds when browsing (Page 1's
        // "Sri Lanka Overview"), falling back to the original
        // cells+sources bounds for the single-snapshot debug view.
        const bounds = nationalSources
          ? computeCombinedLngLatBounds([], nationalFC.features)
          : computeCombinedLngLatBounds(cellFeatures, sourceFeatures)
        if (bounds) {
          map.fitBounds(bounds, { padding: 40, animate: false })
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
      const stats = computeRiskColorStats(cellFeatures)
      map.setPaintProperty('cells-circle', 'circle-color', riskCircleColorExpression(stats))
    }

    // One smooth fit, only on an ACTUAL new outbreak selection (never
    // re-fit for the same origin just because the parent re-rendered
    // with a fresh array reference, and never on a timeline day change
    // -- day changes don't touch cellFeatures/sourceFeatures at all in
    // this checkpoint, see plan Section 25).
    if (nationalSources && selectedOutbreakId && selectedOutbreakId !== lastFitOutbreakIdRef.current) {
      lastFitOutbreakIdRef.current = selectedOutbreakId
      const focusedSources = nationalSources.features.filter((f) => f.properties.outbreakId === selectedOutbreakId)
      const bounds = computeCombinedLngLatBounds(cellFeatures, focusedSources)
      if (bounds) {
        map.fitBounds(bounds, { padding: 60, animate: !reduceMotion, duration: reduceMotion ? 0 : 1200 })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cellFeatures, sourceFeatures])

  // ---- national-sources data itself changes (e.g. once fetched) ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !nationalSources) return
    map.getSource(NATIONAL_SOURCES_SOURCE_ID)?.setData(nationalSources)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nationalSources])

  // ---- selection changes: halo/dim/ripple on the national layer ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !nationalSources) return

    for (const feature of nationalSources.features) {
      const id = feature.properties.source_id
      const isSelected = selectedOutbreakId != null && feature.properties.outbreakId === selectedOutbreakId
      const isOtherOrigin = selectedOutbreakId != null && feature.properties.outbreakId !== selectedOutbreakId
      map.setFeatureState({ source: NATIONAL_SOURCES_SOURCE_ID, id }, { selected: isSelected, dimmed: isOtherOrigin, rippleExpanded: false })
    }

    if (selectedOutbreakId != null) {
      // Kick the ripple: start collapsed/opaque (already the default
      // above), then flip to expanded on the next frame so MapLibre's
      // paint-transition animates 8px/45%-opacity -> 22px/0%-opacity
      // once, per plan Section 27 ("one restrained selection animation").
      const selectedIds = nationalSources.features.filter((f) => f.properties.outbreakId === selectedOutbreakId).map((f) => f.properties.source_id)
      requestAnimationFrame(() => {
        for (const id of selectedIds) {
          map.setFeatureState({ source: NATIONAL_SOURCES_SOURCE_ID, id }, { rippleExpanded: true })
        }
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOutbreakId, nationalSources])

  // ---- nominal-reach ring: smooth grow/shrink between real day values ----
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

    // Tween by re-evaluating buildReachRingFeatureCollectionForCenters at
    // the SAME real centers with an interpolated radius each frame. The
    // in-progress radius is tracked in a ref (not read back from the
    // MapLibre source's internal state, which is a private/undocumented
    // property) so the next tween always starts from wherever the
    // previous one actually ended, including a value the user
    // interrupted mid-tween.
    const targetRadiusKm = reachRingRadiusKm

    if (reduceMotion) {
      source.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, targetRadiusKm))
      currentReachRadiusKmRef.current = targetRadiusKm
      return
    }

    const startRadiusKm = currentReachRadiusKmRef.current
    const startTime = performance.now()

    const tick = (now) => {
      const t = Math.min(1, (now - startTime) / REACH_RING_TWEEN_MS)
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2 // ease-in-out
      const currentRadiusKm = startRadiusKm + (targetRadiusKm - startRadiusKm) * eased
      currentReachRadiusKmRef.current = currentRadiusKm
      source.setData(buildReachRingFeatureCollectionForCenters(reachRingCenters, currentRadiusKm))
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
  }, [operationalFeatures])

  // ---- GEO-INT-03 Section 10: Cases-mode-only visibility toggle ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    if (!map.getLayer(OPERATIONAL_MARKERS_LAYER_ID)) return
    map.setLayoutProperty(OPERATIONAL_MARKERS_LAYER_ID, 'visibility', showOperationalLayer ? 'visible' : 'none')
  }, [showOperationalLayer])

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
    <div className="h-full w-full overflow-hidden rounded border">
      <div ref={containerRef} className="h-full min-h-[650px] w-full" role="application" aria-label="Geospatial scientific map" />
    </div>
  )
})

export default MapLibreCanvas
