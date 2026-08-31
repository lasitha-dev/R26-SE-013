import React from 'react'

/**
 * URGENT-MATARA-REAL-FILTER Section 15: deterministic, template-only
 * insight sentences built from real values already on screen -- no
 * causal/predictive language ("will be infected", "critical
 * transmission", "trajectory intersects"), matching this codebase's
 * existing wording-firewall discipline (`semanticLabels.js`'s
 * `FORBIDDEN_WORDING`). Exported as a pure function so the sentence
 * logic is testable without rendering.
 */
export function buildKeySpatialInsights({ mataraOriginCount, mataraPeriod, peakActivity, selectedOriginAnalytics }) {
  const insights = []

  insights.push(
    mataraOriginCount > 0
      ? `${mataraOriginCount} historical/model origin${mataraOriginCount === 1 ? '' : 's'} in the current dataset ${mataraOriginCount === 1 ? 'is' : 'are'} located inside Matara district.`
      : 'No historical/model origins in the current dataset are located inside Matara district.',
  )

  if (mataraPeriod) {
    insights.push(`Matara origin activity spans ${mataraPeriod.firstDate} to ${mataraPeriod.lastDate}.`)
  }

  if (peakActivity) {
    insights.push(`Activity was highest in ${peakActivity.period}, with ${peakActivity.count} origin${peakActivity.count === 1 ? '' : 's'}.`)
  }

  if (selectedOriginAnalytics?.status === 'AVAILABLE') {
    if (typeof selectedOriginAnalytics.eligibleSourceCount === 'number') {
      insights.push(`The selected Matara origin uses ${selectedOriginAnalytics.eligibleSourceCount} eligible historical sources.`)
    }
    const d7 = selectedOriginAnalytics.nominalReach?.days?.find((d) => d.day === 7)
    if (d7 && typeof d7.nominalReachKm === 'number') {
      insights.push(`D7 nominal reach is ${d7.nominalReachKm.toFixed(1)} km in the current historical-rate context.`)
    }
  }

  return insights
}

export default function AnalysisTrendsKeySpatialInsights({ mataraOriginCount, mataraPeriod, peakActivity, selectedOriginAnalytics }) {
  const insights = buildKeySpatialInsights({ mataraOriginCount, mataraPeriod, peakActivity, selectedOriginAnalytics })

  return (
    <div className="flex flex-col gap-2">
      {insights.map((line, index) => (
        <div key={index} className="flex items-start gap-2 rounded-lg border border-white/5 bg-slate-950/40 px-2.5 py-2 text-xs text-slate-300">
          <span aria-hidden="true" className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
          <span>{line}</span>
        </div>
      ))}
    </div>
  )
}
