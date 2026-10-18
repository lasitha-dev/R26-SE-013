/**
 * Daily forecast for the vet's district (see adapters/weatherForecast.js):
 * several points inside the district polygon (`points`), or one point.
 * Fetched once per district while enabled -- no polling. `fetchedAt` is when
 * this forecast was retrieved (the provider does not report its model run).
 */
import { useEffect, useState } from 'react'

import { forecastUrl, parseForecast } from '../adapters/weatherForecast'

export function useDistrictWeatherForecast({ latitude, longitude, points = null, enabled = true }) {
  const [state, setState] = useState({ status: 'idle', days: new Map(), fetchedAt: null, pointCount: 0 })
  const list = Array.isArray(points) && points.length ? points : Number.isFinite(latitude) && Number.isFinite(longitude) ? [[longitude, latitude]] : []
  const key = list.length ? list.map(([lon, lat]) => `${lon.toFixed(3)},${lat.toFixed(3)}`).join(';') : null
  useEffect(() => {
    if (!enabled || !key) return undefined
    const controller = new AbortController()
    setState((prev) => ({ ...prev, status: 'loading' }))
    fetch(forecastUrl({ points: list }), { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`forecast ${r.status}`))))
      .then((json) => {
        if (!controller.signal.aborted) setState({ status: 'ready', days: parseForecast(json), fetchedAt: new Date().toISOString(), pointCount: list.length })
      })
      .catch((error) => { if (!controller.signal.aborted && error?.name !== 'AbortError') setState({ status: 'error', days: new Map(), fetchedAt: null, pointCount: 0 }) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])
  return state
}
