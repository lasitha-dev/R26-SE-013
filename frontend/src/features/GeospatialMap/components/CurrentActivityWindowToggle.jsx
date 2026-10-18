import React from 'react'

import { CURRENT_ACTIVITY_WINDOW_OPTIONS } from '../adapters/currentSurveillance'

/**
 * PAGE-3-CURRENT-DASHBOARD: 7D / 14D / 30D -- real rolling wall-clock
 * windows over the current Verified Clinical Context collection
 * (`adapters/currentSurveillance.js::buildRecentActivityBuckets`). Never
 * triggers a new network request; selecting a window only changes how
 * many already-real daily buckets are shown.
 */
export default function CurrentActivityWindowToggle({ selectedDays, onSelect }) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-white/10 bg-slate-900/70 p-1" role="group" aria-label="Activity window">
      {CURRENT_ACTIVITY_WINDOW_OPTIONS.map((option) => {
        const active = selectedDays === option.days
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(option.days)}
            className={
              active
                ? 'rounded-full bg-emerald-400/20 px-2.5 py-1 text-xs font-medium text-emerald-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
                : 'rounded-full px-2.5 py-1 text-xs text-slate-300 transition-colors hover:bg-slate-800 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
            }
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
