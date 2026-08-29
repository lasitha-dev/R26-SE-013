import React from 'react'

/**
 * LSD-UI-04: compact selected-source popup (plan Section 19) -- ONLY
 * real API-backed fields. The real `sources` response has no
 * "confirmed"/farm-name/district/case-count/date field (verified
 * against the live backend, 2026-08-27: `source_id`,
 * `availability_quality`, `gps_quality` only), so this deliberately
 * shows none of those and no date -- "Historical source" + its real
 * availability quality is the honest label, not a fabricated
 * "Confirmed" badge or an invented date.
 */
export default function SourcePopup({ feature, onViewSpatialContext, onClose }) {
  if (!feature) return null
  const [lon, lat] = feature.geometry.coordinates
  const { source_id: sourceId, availability_quality: availabilityQuality, gps_quality: gpsQuality } = feature.properties

  return (
    <div className="pointer-events-auto w-64 rounded-lg border border-white/10 bg-slate-900/95 p-3 text-sm shadow-xl">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-mono text-xs uppercase tracking-wide text-emerald-300">LSD</div>
          <div className="text-slate-200">
            {lat.toFixed(4)}, {lon.toFixed(4)}
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-white">
          ×
        </button>
      </div>
      <div className="mt-2 text-xs text-slate-400">
        Historical source
        <div className="text-slate-300">GPS quality: {gpsQuality ?? 'unknown'}</div>
        <div className="text-slate-300">Availability: {availabilityQuality ?? 'unknown'}</div>
        <div className="mt-1 truncate text-slate-500" title={sourceId}>
          {sourceId}
        </div>
      </div>
      <button type="button" onClick={onViewSpatialContext} className="mt-2 text-xs font-medium text-emerald-300 hover:underline">
        View spatial context →
      </button>
    </div>
  )
}
