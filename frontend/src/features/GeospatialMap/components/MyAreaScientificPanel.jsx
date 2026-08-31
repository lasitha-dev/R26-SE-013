import React from 'react'

import {
  DISCLAIMER_RELATIVE_SPATIAL_SCORE_UNAVAILABLE,
  LABEL_HISTORICAL_SOURCE_CONTEXT,
  LABEL_MY_AREA_FORECAST_FRAME_UNAVAILABLE,
  LABEL_RELATIVE_SPATIAL_SCORE_UNAVAILABLE,
  MY_AREA_NOMINAL_REACH_DISCLAIMER,
} from '../semanticLabels'

/**
 * GEO-AREA-02: selected-origin scientific context -- nearest historical
 * source (Section 28, its own separate concept from an active-case
 * claim), Relative Spatial Score (Section 21 -- honestly unavailable,
 * never a percentage or a qualitative safety label), and the
 * nominal-reach scalar (Section 20 -- relation is always
 * `NOT_APPLICABLE`; this component never computes or displays a
 * farm-inside/outside claim).
 * Renders nothing (returns `null`) until an origin is actually selected
 * -- there is nothing scientific to show before that (Section 9/11).
 */
export default function MyAreaScientificPanel({ selectedOriginContext, forecastFrameUnavailable = false }) {
  if (!selectedOriginContext) return null

  const { nearestHistoricalSource, relativeSpatialScore, nominalReachContext } = selectedOriginContext

  return (
    <div className="flex flex-col gap-3">
      {nearestHistoricalSource && (
        <div className="rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs shadow-card-subtle">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">{LABEL_HISTORICAL_SOURCE_CONTEXT}</div>
          <dl className="mt-2 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-on-surface-variant/70">Source ID</dt>
              <dd className="truncate font-mono text-on-surface-variant" title={nearestHistoricalSource.sourceId}>
                {nearestHistoricalSource.sourceId}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-on-surface-variant/70">Distance from selected farm</dt>
              <dd className="text-on-surface-variant">{nearestHistoricalSource.distanceFromAreaKm.toFixed(1)} km</dd>
            </div>
            {nearestHistoricalSource.availabilityQuality && (
              <div className="flex items-center justify-between gap-2">
                <dt className="text-on-surface-variant/70">Availability</dt>
                <dd className="text-on-surface-variant">{nearestHistoricalSource.availabilityQuality}</dd>
              </div>
            )}
            {nearestHistoricalSource.gpsQuality && (
              <div className="flex items-center justify-between gap-2">
                <dt className="text-on-surface-variant/70">GPS quality</dt>
                <dd className="text-on-surface-variant">{nearestHistoricalSource.gpsQuality}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {relativeSpatialScore && (
        <div className="rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs shadow-card-subtle">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">{relativeSpatialScore.label}</div>
          {relativeSpatialScore.value === null ? (
            <>
              <div className="mt-1 text-on-surface-variant">{LABEL_RELATIVE_SPATIAL_SCORE_UNAVAILABLE}</div>
              <div className="mt-1 text-on-surface-variant/70">{DISCLAIMER_RELATIVE_SPATIAL_SCORE_UNAVAILABLE}</div>
            </>
          ) : (
            <div className="mt-1 text-on-surface-variant">{relativeSpatialScore.value}</div>
          )}
        </div>
      )}

      {forecastFrameUnavailable ? (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-200">
          {LABEL_MY_AREA_FORECAST_FRAME_UNAVAILABLE}
        </div>
      ) : (
        nominalReachContext && (
          <div className="rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs shadow-card-subtle">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">Nominal reach</div>
            {nominalReachContext.nominalReachKm === null ? (
              <div className="mt-1 text-on-surface-variant">Observed / origin context — no forward reach to show.</div>
            ) : (
              <div className="mt-1 text-on-surface-variant">{nominalReachContext.nominalReachKm.toFixed(1)} km</div>
            )}
            <div className="mt-1 text-on-surface-variant/70">{nominalReachContext.disclaimer ?? MY_AREA_NOMINAL_REACH_DISCLAIMER}</div>
          </div>
        )
      )}
    </div>
  )
}
