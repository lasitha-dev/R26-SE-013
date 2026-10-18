import { useEffect, useState } from 'react'

import { findDistrictFeature } from '../adapters/districtGeometry'
import { GEO_TIMING, markTiming } from '../adapters/loadTiming'
// `?url` keeps this real ~240KB dataset as a fetched static asset
// (copied to the build output as-is) rather than inlined into the JS
// bundle -- loaded once, on demand, not parsed on every page load.
import districtGeoJsonUrl from '../data/sri-lanka-districts-adm2.geojson?url'

export const DISTRICT_GEOMETRY_STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
}

/**
 * GEO30B Section 16: resolves the authenticated vet's REAL district
 * polygon from the real geoBoundaries dataset (`data/ATTRIBUTION.md`).
 * Fetched once per mount (not re-fetched per render/disease/window
 * change) -- `vetDistrict` changing only re-runs the (cheap, in-memory)
 * name match against the already-fetched FeatureCollection, never a new
 * network request.
 *
 * Never fabricates a polygon: a fetch failure, an unmatched district
 * name, or no `vetDistrict` at all all resolve to `feature: null` --
 * callers must treat that as "no real geometry available" (Section 17's
 * REAL_DISTRICT_GEOMETRY fallback), never draw a placeholder shape.
 */
export function useDistrictGeometry(vetDistrict) {
  const [status, setStatus] = useState(DISTRICT_GEOMETRY_STATUS.IDLE)
  const [featureCollection, setFeatureCollection] = useState(null)

  useEffect(() => {
    let cancelled = false
    setStatus(DISTRICT_GEOMETRY_STATUS.LOADING)
    // GEO33B Section 1/6: mount-time, parallel with the map's own style
    // load -- the district polygon never waits on MapLibre, and MapLibre
    // never waits on it (`MapLibreCanvas.jsx` seeds the district source
    // empty and `setData`s it whenever this resolves, in either order).
    markTiming(GEO_TIMING.DISTRICT_FETCH_START)
    fetch(districtGeoJsonUrl)
      .then((response) => {
        if (!response.ok) throw new Error(`district geometry request failed with status ${response.status}`)
        return response.json()
      })
      .then((data) => {
        if (cancelled) return
        markTiming(GEO_TIMING.DISTRICT_FETCH_END)
        setFeatureCollection(data)
        setStatus(DISTRICT_GEOMETRY_STATUS.READY)
      })
      .catch(() => {
        if (cancelled) return
        setStatus(DISTRICT_GEOMETRY_STATUS.ERROR)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const feature = status === DISTRICT_GEOMETRY_STATUS.READY ? findDistrictFeature(featureCollection, vetDistrict) : null

  // Page 1 also reuses the already-fetched national ADM2 collection to
  // clip its presentation-only spread geometry to the island. Exposing
  // this in-memory value is additive: existing callers keep reading only
  // `status`/`feature`, and no second fetch is introduced.
  return { status, feature, featureCollection }
}
