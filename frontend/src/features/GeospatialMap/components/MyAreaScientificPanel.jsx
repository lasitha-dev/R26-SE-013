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
        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
          <div className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_HISTORICAL_SOURCE_CONTEXT}</div>
          <dl className="mt-2 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-slate-500">Source ID</dt>
              <dd className="truncate font-mono text-slate-300" title={nearestHistoricalSource.sourceId}>
                {nearestHistoricalSource.sourceId}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-slate-500">Distance from selected farm</dt>
              <dd className="text-slate-300">{nearestHistoricalSource.distanceFromAreaKm.toFixed(1)} km</dd>
            </div>
            {nearestHistoricalSource.availabilityQuality && (
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">Availability</dt>
                <dd className="text-slate-300">{nearestHistoricalSource.availabilityQuality}</dd>
              </div>
            )}
            {nearestHistoricalSource.gpsQuality && (
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">GPS quality</dt>
                <dd className="text-slate-300">{nearestHistoricalSource.gpsQuality}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {relativeSpatialScore && (
        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
          <div className="font-mono uppercase tracking-wide text-emerald-300">{relativeSpatialScore.label}</div>
          {relativeSpatialScore.value === null ? (
            <>
              <div className="mt-1 text-slate-300">{LABEL_RELATIVE_SPATIAL_SCORE_UNAVAILABLE}</div>
              <div className="mt-1 text-slate-500">{DISCLAIMER_RELATIVE_SPATIAL_SCORE_UNAVAILABLE}</div>
            </>
          ) : (
            <div className="mt-1 text-slate-300">{relativeSpatialScore.value}</div>
          )}
        </div>
      )}

      {forecastFrameUnavailable ? (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-200">
          {LABEL_MY_AREA_FORECAST_FRAME_UNAVAILABLE}
        </div>
      ) : (
        nominalReachContext && (
          <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
            <div className="font-mono uppercase tracking-wide text-emerald-300">Nominal reach</div>
            {nominalReachContext.nominalReachKm === null ? (
              <div className="mt-1 text-slate-300">Observed / origin context — no forward reach to show.</div>
            ) : (
              <div className="mt-1 text-slate-300">{nominalReachContext.nominalReachKm.toFixed(1)} km</div>
            )}
            <div className="mt-1 text-slate-500">{nominalReachContext.disclaimer ?? MY_AREA_NOMINAL_REACH_DISCLAIMER}</div>
          </div>
        )
      )}
    </div>
  )
}
