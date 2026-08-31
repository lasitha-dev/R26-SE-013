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
  const {
    source_id: sourceId,
    availability_quality: availabilityQuality,
    gps_quality: gpsQuality,
    // GEO33B Section 7: added by the presentation aggregation
    // (`adapters/nationalSourcePresentation.js`). `stackCount` is the
    // number of DISTINCT REAL source records at this exact coordinate --
    // never the number of merged rows, since one record legitimately
    // appears once per origin whose eligibility window contains it.
    // `outbreakIds` is every real origin this location is eligible under.
    // Both are absent for a non-aggregated caller, which is why every use
    // below is guarded rather than assumed.
    stackCount,
    sourceIds,
    outbreakIds,
  } = feature.properties
  const hasStack = Array.isArray(sourceIds) && stackCount > 1

  return (
    <div className="pointer-events-auto w-64 rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-sm shadow-card-subtle">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-mono text-xs uppercase tracking-wide text-primary">LSD</div>
          <div className="text-on-surface">
            {lat.toFixed(4)}, {lon.toFixed(4)}
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-on-surface-variant/70 hover:text-on-surface">
          ×
        </button>
      </div>
      <div className="mt-2 text-xs text-on-surface-variant/70">
        Historical source
        <div className="text-on-surface-variant">GPS quality: {gpsQuality ?? 'unknown'}</div>
        <div className="text-on-surface-variant">Availability: {availabilityQuality ?? 'unknown'}</div>
        {/* GEO33B Section 7: the exact real count lives here rather than as
            an on-map text badge -- this feature's map layers carry no
            glyph/sprite dependency by design (`visualLayerStructural.test.js`
            forbids `text-field`/`text-font`), so the map shows only a ring
            that something is stacked and the popup states what. Rendered
            ONLY when two or more genuinely distinct real records share this
            coordinate; a single record never displays a count of 1. */}
        {hasStack && (
          <div className="mt-1 text-on-surface-variant">
            {stackCount} distinct historical source records at this exact location
          </div>
        )}
        <div className="mt-1 truncate text-on-surface-variant/70" title={hasStack ? sourceIds.join('\n') : sourceId}>
          {hasStack ? sourceIds.join(', ') : sourceId}
        </div>
        {/* One physical record is genuinely eligible under every origin
            whose 14-day active-source window contains its availability
            date, so a location can legitimately belong to several real
            origins. Stating that is honest; hiding it made the same record
            look like several separate observations. */}
        {Array.isArray(outbreakIds) && outbreakIds.length > 1 && (
          <div className="mt-1 text-on-surface-variant/70">Eligible under {outbreakIds.length} historical origins</div>
        )}
      </div>
      <button type="button" onClick={onViewSpatialContext} className="mt-2 text-xs font-medium text-primary hover:underline">
        View spatial context →
      </button>
    </div>
  )
}
