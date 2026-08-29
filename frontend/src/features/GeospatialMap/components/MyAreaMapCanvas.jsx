import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import React, { useEffect, useRef } from 'react'

import { buildSourcesFeatureCollection, computeCombinedLngLatBounds, sourceIconLayout } from './mapLibreAdapter'
import { buildReachRingFeatureCollectionForCenters, emptyReachRingFeatureCollection } from './nominalReachRing'
import { FARM_MARKER_ICON_ID, buildFarmMarkerImage, farmMarkerIconLayout } from './myAreaIcons'
import { resolveBasemapConfig } from './basemapConfig'
import { SOURCE_ICON_ID, buildSourceMarkerImage } from './presentationIcons'

const FARM_SOURCE_ID = 'geo-my-area-farm'
const SOURCES_SOURCE_ID = 'geo-my-area-sources'
const REACH_RING_SOURCE_ID = 'geo-my-area-reach-ring'

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
 * change, a My Area refetch, or an operational-context refresh.
 */
const MyAreaMapCanvas = React.forwardRef(function MyAreaMapCanvas(
  { area = null, sourceFeatures = [], reachRingCenters = null, reachRingRadiusKm = 0, selectedOriginId = null, reduceMotion = false, onMapUnavailable },
  ref,
) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const failedRef = useRef(false)
  const loadedRef = useRef(false)
  const lastFitFarmIdRef = useRef(undefined)
  const lastFitOriginIdRef = useRef(undefined)
  const reachRingAnimRef = useRef(null)
  const currentReachRadiusKmRef = useRef(0)

  React.useImperativeHandle(ref, () => ({
    resize() {
      mapRef.current?.resize()
    },
  }))

  // ---- mount: create the map once ----
  useEffect(() => {
    let map
    try {
      const basemap = resolveBasemapConfig(import.meta.env.VITE_GEOSPATIAL_BASEMAP_STYLE_URL)
      map = new maplibregl.Map({
        container: containerRef.current, style: basemap.style, pitch: 0, maxPitch: 0, bearing: 0, attributionControl: true,
      })
      mapRef.current = map
      map.dragRotate.disable()
      map.touchZoomRotate.disableRotation()
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

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

        if (!map.hasImage(FARM_MARKER_ICON_ID)) map.addImage(FARM_MARKER_ICON_ID, buildFarmMarkerImage())
        if (!map.hasImage(SOURCE_ICON_ID)) map.addImage(SOURCE_ICON_ID, buildSourceMarkerImage())

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

    if (hasFarmPoint && area.farmId !== lastFitFarmIdRef.current) {
      lastFitFarmIdRef.current = area.farmId
      lastFitOriginIdRef.current = undefined // a farm change invalidates any prior origin fit
      map.easeTo({ center: [area.longitude, area.latitude], zoom: 11, duration: reduceMotion ? 0 : 900 })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area?.farmId, area?.latitude, area?.longitude, area?.locationStatus])

  // ---- selected-origin sources: one fit per ACTUAL origin change ----
  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return

    const sourcesFC = buildSourcesFeatureCollection({ type: 'FeatureCollection', features: sourceFeatures })
    map.getSource(SOURCES_SOURCE_ID)?.setData(sourcesFC)

    if (selectedOriginId && selectedOriginId !== lastFitOriginIdRef.current) {
      lastFitOriginIdRef.current = selectedOriginId
      const hasFarmPoint = area && area.locationStatus === 'VALID' && typeof area.latitude === 'number' && typeof area.longitude === 'number'
      const farmPointFeature = hasFarmPoint
        ? [{ type: 'Feature', geometry: { type: 'Point', coordinates: [area.longitude, area.latitude] } }]
        : []
      const bounds = computeCombinedLngLatBounds(farmPointFeature, sourcesFC.features)
      if (bounds) {
        map.fitBounds(bounds, { padding: 60, animate: !reduceMotion, duration: reduceMotion ? 0 : 1000 })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFeatures, selectedOriginId])

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
      <div ref={containerRef} className="h-full min-h-[520px] w-full" role="application" aria-label="My Area map" />
    </div>
  )
})

export default MyAreaMapCanvas
