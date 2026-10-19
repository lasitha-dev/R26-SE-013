/**
 * EXPLORATORY runtime ST-DBSCAN (`GET /api/geospatial/st-clusters`).
 * Fetched only while the Clusters mode is active; no timer. The backend runs
 * the existing `services/stdbscan` clustering on real eligible case records
 * with the documented UNFROZEN development parameters.
 */
import { useEffect, useRef, useState } from 'react'

import { GEOSPATIAL_API_PREFIX } from '../api/apiConfig'
import { readAuthToken } from '../api/operationalApi'

const EMPTY = { type: 'FeatureCollection', features: [] }

/** Pure: backend cluster response -> one FeatureCollection (hull/member/noise). */
export function buildClusterFeatureCollection(result) {
  if (!result || !Array.isArray(result.clusters)) return EMPTY
  const features = []
  for (const cluster of result.clusters) {
    const properties = {
      clusterId: cluster.cluster_id,
      memberCount: cluster.member_count ?? null,
      supportCount: cluster.distinct_farm_or_support_count ?? null,
      startDate: cluster.start_date ?? null,
      endDate: cluster.end_date ?? null,
      asOf: result.as_of ?? null,
    }
    if (cluster.hull_geometry?.type) {
      features.push({ type: 'Feature', geometry: cluster.hull_geometry, properties: { ...properties, kind: 'hull' } })
    }
    for (const point of cluster.member_locations ?? []) {
      if (!Number.isFinite(point?.longitude) || Math.abs(point.longitude) > 180 || !Number.isFinite(point?.latitude) || Math.abs(point.latitude) > 90) continue
      features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [point.longitude, point.latitude] }, properties: { ...properties, kind: 'member' } })
    }
  }
  for (const [lat, lon] of result.noise_locations ?? []) {
    if (!Number.isFinite(lat) || Math.abs(lat) > 90 || !Number.isFinite(lon) || Math.abs(lon) > 180) continue
    features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: { kind: 'noise' } })
  }
  return { type: 'FeatureCollection', features }
}

export function useStClusters({ disease, asOf = null, enabled = false, refreshToken = 0 }) {
  const [state, setState] = useState({ status: 'idle', data: null, errorStatus: null })
  // A refresh of the SAME disease/district/date (realtime data change) keeps
  // the current layer visible until the new response lands; any scope change
  // clears it so another selection's results are never shown.
  const scopeKeyRef = useRef(null)
  useEffect(() => {
    if (!enabled || !disease) {
      scopeKeyRef.current = null
      setState({ status: 'idle', data: null })
      return undefined
    }
    const controller = new AbortController()
    const params = new URLSearchParams({ disease: String(disease).toLowerCase() })
    if (asOf) params.set('as_of', asOf)
    const token = readAuthToken()
    const scopeKey = JSON.stringify([disease, asOf])
    const sameScope = scopeKeyRef.current === scopeKey
    scopeKeyRef.current = scopeKey
    setState((prev) => ({ status: 'loading', data: sameScope ? prev.data : null })) // never show another disease's/date's clusters while loading
    fetch(`${GEOSPATIAL_API_PREFIX}/st-clusters?${params}`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          const error = new Error(`st-clusters ${response.status}`)
          error.status = response.status === 401 ? 'SESSION_REQUIRED' : response.status === 403 ? 'FORBIDDEN' : 'SERVICE_UNAVAILABLE'
          throw error
        }
        const data = await response.json()
        if (!Array.isArray(data?.clusters)) {
          const error = new Error('Invalid cluster response')
          error.status = 'INVALID_RESPONSE'
          throw error
        }
        return data
      })
      .then((data) => { if (!controller.signal.aborted) setState({ status: 'ready', data, errorStatus: null }) })
      .catch((error) => { if (!controller.signal.aborted && error?.name !== 'AbortError') setState({ status: 'error', data: null, errorStatus: error.status ?? 'NETWORK_ERROR' }) })
    return () => controller.abort()
  }, [disease, asOf, enabled, refreshToken])
  if (!enabled || !disease) return { status: 'idle', data: null, errorStatus: null }
  if (scopeKeyRef.current !== JSON.stringify([disease, asOf])) return { status: 'loading', data: null, errorStatus: null }
  return state
}

const kmApart = ([lon1, lat1], [lon2, lat2]) => Math.hypot((lon2 - lon1) * 111.32 * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180), (lat2 - lat1) * 110.574)

/** Pure: the ST-DBSCAN result for one case at `coordinates` ([lon, lat]):
 * `member` (with the cluster's counts and dates), `noise` (evaluated, in no
 * cluster), `loading`, or `unavailable` (request failed or the case was not
 * among the clustered records). Matched by farm GPS within `toleranceKm`. */
export function clusterForCase(state, coordinates, toleranceKm = 0.5) {
  if (!Array.isArray(coordinates)) return null
  if (state?.status === 'loading') return { status: 'loading' }
  const result = state?.data
  if (!result || !Array.isArray(result.clusters)) return { status: 'unavailable' }
  const near = (lon, lat) => Number.isFinite(lon) && Number.isFinite(lat) && kmApart(coordinates, [lon, lat]) <= toleranceKm
  for (const cluster of result.clusters) {
    if ((cluster.member_locations ?? []).some((p) => near(p?.longitude, p?.latitude))) {
      return { status: 'member', clusterId: cluster.cluster_id, memberCount: cluster.member_count ?? null, supportCount: cluster.distinct_farm_or_support_count ?? null, startDate: cluster.start_date ?? null, endDate: cluster.end_date ?? null }
    }
  }
  if ((result.noise_locations ?? []).some(([lat, lon]) => near(lon, lat))) return { status: 'noise' }
  return { status: 'unavailable' }
}
