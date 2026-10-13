import React, { useEffect, useState } from 'react'
import { fetchOrigins } from '../api/geospatialApi'

/**
 * Loading/empty/error states (Part 7). Never reconstructs
 * `forecast_origin_id` -- always uses the backend-provided string
 * verbatim. Never auto-selects a "favorable" origin.
 */
export default function OriginSelector({ selectedOriginId, onSelect, onRequest, transportReady = true }) {
  const [status, setStatus] = useState('loading') // loading | ready | empty | error
  const [origins, setOrigins] = useState([])
  const [country, setCountry] = useState('')
  const [errorMessage, setErrorMessage] = useState(null)

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    fetchOrigins({ country: country || undefined })
      .then((data) => {
        if (cancelled) return
        const sorted = [...data.origins].sort((a, b) => a.forecast_origin_id.localeCompare(b.forecast_origin_id))
        setOrigins(sorted)
        setStatus(sorted.length === 0 ? 'empty' : 'ready')
      })
      .catch((err) => {
        if (cancelled) return
        setErrorMessage(err.message)
        setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [country])

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium">Forecast origin</label>
      <input
        type="text"
        placeholder="Filter by country (optional)"
        value={country}
        onChange={(e) => setCountry(e.target.value)}
        className="w-full rounded border px-2 py-1 text-sm"
      />
      {status === 'loading' && <div className="text-sm text-gray-500">Loading origins…</div>}
      {status === 'error' && <div className="text-sm text-red-600">Could not load origins: {errorMessage}</div>}
      {status === 'empty' && <div className="text-sm text-gray-500">No origins match this filter.</div>}
      {status === 'ready' && (
        <select
          className="w-full rounded border px-2 py-1 text-sm"
          value={selectedOriginId || ''}
          onChange={(e) => onSelect(e.target.value)}
        >
          <option value="" disabled>
            Select a forecast origin…
          </option>
          {origins.map((o) => (
            <option key={o.forecast_origin_id} value={o.forecast_origin_id}>
              {o.forecast_origin_id} ({o.country}, {o.t0})
            </option>
          ))}
        </select>
      )}
      <button
        type="button"
        disabled={!selectedOriginId || !transportReady}
        onClick={onRequest}
        className="rounded bg-blue-600 px-3 py-1 text-sm text-white disabled:opacity-40"
      >
        Load snapshot
      </button>
      {!transportReady && <div className="text-xs text-gray-500">Waiting for the transport connection…</div>}
    </div>
  )
}
