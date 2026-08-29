import React from 'react'

import {
  APPARENT_RATE_HELP_TEXT,
  APPARENT_RATE_UNIT,
  LABEL_ANALYSIS_APPARENT_RATE,
  LABEL_CROSS_SNAPSHOT_UNSUPPORTED,
  LABEL_DIRECTION_NOT_DEFINED,
  LABEL_MODEL_NOT_READY_FOR_DISEASE,
  LABEL_NOMINAL_REACH_D1_D7,
  LABEL_ORIGIN_LEVEL_DIRECTION,
  LABEL_RSS_DISTRIBUTION,
  LABEL_RSS_MAX,
  LABEL_RSS_MEDIAN,
  LABEL_RSS_MIN,
  LABEL_RSS_TEMPORAL_BASIS,
  LABEL_SCIENTIFIC_MODEL,
  LABEL_SELECT_ORIGIN_FOR_CONTEXT,
} from '../semanticLabels'

/**
 * GEO-ANALYSIS-02 Section 21-29: selected-origin analytics -- renders
 * ONLY when `selectedOriginAnalytics` is present (Section 21), and
 * respects its own `status` honestly. Every field/label mirrors the
 * real backend DTO names/semantics exactly (Section 22-29):
 *  - apparent rate: "Apparent rate", km/day -- the backend's own frozen
 *    historical-rate wording, never a biological transmission claim.
 *  - direction: always UNAVAILABLE_RUNTIME_METRIC this contract --
 *    rendered as an honest unavailable state, never a fabricated 0°.
 *  - nominal reach: D+1..D+7 real values only, D0 never fabricated as
 *    0 km, exact required disclaimer always visible.
 *  - Relative Spatial Score distribution: raw unitless min/median/max,
 *    never a percentage, never mapped to a risk color, cross-snapshot
 *    comparison explicitly unsupported.
 */
export default function AnalysisTrendsOriginAnalyticsPanel({ selectedOriginAnalytics }) {
  if (!selectedOriginAnalytics) {
    return (
      <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs text-slate-400">{LABEL_SELECT_ORIGIN_FOR_CONTEXT}</div>
    )
  }

  if (selectedOriginAnalytics.status === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY') {
    return (
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-200">
        <div className="font-mono uppercase tracking-wide">{LABEL_SCIENTIFIC_MODEL}</div>
        <div className="mt-1">{LABEL_MODEL_NOT_READY_FOR_DISEASE}</div>
      </div>
    )
  }

  if (selectedOriginAnalytics.status !== 'AVAILABLE') {
    return (
      <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs text-slate-400">
        {LABEL_SCIENTIFIC_MODEL}: {selectedOriginAnalytics.status ?? 'unavailable'}
      </div>
    )
  }

  const { apparentRate, directionContext, nominalReach, relativeSpatialScoreDistribution } = selectedOriginAnalytics

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
        <dl className="space-y-1">
          <Row label="Origin" value={selectedOriginAnalytics.originId} mono />
          {selectedOriginAnalytics.t0 && <Row label="t0" value={selectedOriginAnalytics.t0} />}
          {selectedOriginAnalytics.scientificMode && <Row label="Scientific mode" value={selectedOriginAnalytics.scientificMode} />}
          {typeof selectedOriginAnalytics.eligibleSourceCount === 'number' && (
            <Row label="Eligible source count" value={selectedOriginAnalytics.eligibleSourceCount} />
          )}
        </dl>
      </div>

      {apparentRate && (
        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_ANALYSIS_APPARENT_RATE}</span>
            <span className="text-slate-500" title={APPARENT_RATE_HELP_TEXT}>
              ⓘ
            </span>
          </div>
          {apparentRate.status === 'AVAILABLE' && apparentRate.apparentRateKmDay !== null ? (
            <div className="mt-1 text-slate-200">
              {apparentRate.apparentRateKmDay.toFixed(2)} {APPARENT_RATE_UNIT}
            </div>
          ) : (
            <div className="mt-1 text-slate-500">Not available</div>
          )}
          <div className="mt-1 text-slate-600">{APPARENT_RATE_HELP_TEXT}</div>
        </div>
      )}

      <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
        <div className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_ORIGIN_LEVEL_DIRECTION}</div>
        <div className="mt-1 text-slate-500">{LABEL_DIRECTION_NOT_DEFINED}</div>
        {directionContext?.reason && <div className="mt-1 text-slate-600">{directionContext.reason}</div>}
      </div>

      {nominalReach && (
        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
          <div className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_NOMINAL_REACH_D1_D7}</div>
          {nominalReach.status === 'AVAILABLE' && nominalReach.days.length > 0 ? (
            <div className="mt-2 flex items-end gap-1.5" role="img" aria-label={`Nominal reach for days ${nominalReach.days.map((d) => `D+${d.day}: ${d.nominalReachKm ?? 'unavailable'} km`).join(', ')}`}>
              {(() => {
                const maxKm = Math.max(...nominalReach.days.map((d) => d.nominalReachKm ?? 0), 1)
                return nominalReach.days.map((d) => (
                  <div key={d.day} className="flex flex-col items-center gap-1" title={d.nominalReachKm !== null ? `D+${d.day}: ${d.nominalReachKm.toFixed(1)} km` : `D+${d.day}: unavailable`}>
                    <div
                      className="w-4 rounded-t bg-emerald-400/70"
                      style={{ height: `${d.nominalReachKm !== null ? Math.max((d.nominalReachKm / maxKm) * 64, 2) : 2}px` }}
                    />
                    <span className="text-[10px] text-slate-500">D+{d.day}</span>
                  </div>
                ))
              })()}
            </div>
          ) : (
            <div className="mt-1 text-slate-500">Not available</div>
          )}
          <div className="mt-2 text-slate-500">{nominalReach.disclaimer ?? 'Nominal reach — visualization only, not a disease boundary.'}</div>
        </div>
      )}

      {relativeSpatialScoreDistribution && (
        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
          <div className="font-mono uppercase tracking-wide text-emerald-300">{relativeSpatialScoreDistribution.label ?? LABEL_RSS_DISTRIBUTION}</div>
          <div className="text-[10px] text-slate-600">{relativeSpatialScoreDistribution.temporalBasis ? LABEL_RSS_TEMPORAL_BASIS : null}</div>
          {relativeSpatialScoreDistribution.status === 'AVAILABLE' ? (
            <div className="mt-2 grid grid-cols-3 gap-2 text-center">
              <RssStat label={LABEL_RSS_MIN} value={relativeSpatialScoreDistribution.minScore} />
              <RssStat label={LABEL_RSS_MEDIAN} value={relativeSpatialScoreDistribution.medianScore} />
              <RssStat label={LABEL_RSS_MAX} value={relativeSpatialScoreDistribution.maxScore} />
            </div>
          ) : (
            <div className="mt-1 text-slate-500">Not available</div>
          )}
          <div className="mt-2 text-slate-600">{LABEL_CROSS_SNAPSHOT_UNSUPPORTED}</div>
        </div>
      )}
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className={mono ? 'truncate font-mono text-slate-300' : 'text-slate-300'} title={mono ? String(value) : undefined}>
        {value}
      </dd>
    </div>
  )
}

function RssStat({ label, value }) {
  return (
    <div className="rounded-md border border-white/10 bg-slate-950/60 p-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-slate-200">{typeof value === 'number' ? value.toFixed(3) : '—'}</div>
    </div>
  )
}
