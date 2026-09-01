import React from 'react'

import { TREND_WINDOW_OPTIONS } from '../adapters/historicalTrendWindow'

/**
 * PAGE-3-NATIONAL-KPI: 30D / 12W / YTD -- a display-range control over
 * the already-real, already-fetched `historical_trend.points`
 * (`adapters/historicalTrendWindow.js::filterTrendPointsByWindow`).
 * Never triggers a new network request; selecting a window only changes
 * which already-real points are shown.
 */
export default function AnalysisTrendsWindowToggle({ selected, onSelect }) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-white/10 bg-slate-900/70 p-1" role="group" aria-label="Chart window">
      {TREND_WINDOW_OPTIONS.map((window) => {
        const active = selected === window
        return (
          <button
            key={window}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(window)}
            className={
              active
                ? 'rounded-full bg-emerald-400/20 px-2.5 py-1 text-xs font-medium text-emerald-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
                : 'rounded-full px-2.5 py-1 text-xs text-slate-300 transition-colors hover:bg-slate-800 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
            }
          >
            {window}
          </button>
        )
      })}
    </div>
  )
}
