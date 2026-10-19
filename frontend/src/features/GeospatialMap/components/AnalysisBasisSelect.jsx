import React from 'react'

import { ANALYSIS_BASIS } from '../adapters/spatialStory'

const BASIS_TONE = {
  [ANALYSIS_BASIS.LIVE]: 'bg-primary',
  [ANALYSIS_BASIS.LATEST_VERIFIED]: 'bg-sky-400',
  [ANALYSIS_BASIS.RETROSPECTIVE]: 'bg-amber-400',
  [ANALYSIS_BASIS.CUSTOM]: 'bg-violet-400',
}

/**
 * The analysis date ("as of") the spatial timeline is fixed at. Options are
 * built by `buildAnalysisBasisOptions` from real dates only: today (live),
 * the latest real vet-verified case date, and the latest real historical
 * research origin -- plus, when offered, a past date the vet chooses (never
 * future; `maxDate` is today in Asia/Colombo). Switching never moves the
 * camera or the map mode.
 */
export default function AnalysisBasisSelect({ options, value, onChange, customDate = null, onCustomDateChange = null, maxDate = null }) {
  const selected = options.find((option) => option.id === value) ?? options[0]
  return (
    <label className="flex items-center gap-2" title={selected?.description}>
      <span className="whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-on-surface-variant/70">Analysis date</span>
      <span className="relative flex items-center">
        <span aria-hidden="true" className={`pointer-events-none absolute left-2.5 h-2 w-2 rounded-full ${BASIS_TONE[selected?.id] ?? 'bg-primary'}`} />
        <select
          value={selected?.id}
          onChange={(e) => onChange(e.target.value)}
          aria-label="Analysis date"
          className="max-w-[13rem] cursor-pointer appearance-none truncate rounded-md bg-surface-container-high/60 py-2 pl-7 pr-7 text-sm font-medium text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {options.map((option) => (
            <option key={option.id} value={option.id} className="bg-surface-container-high">
              {option.label}
            </option>
          ))}
        </select>
        <span aria-hidden="true" className="material-symbols-outlined pointer-events-none absolute right-1.5 text-[18px] text-on-surface-variant/70">
          expand_more
        </span>
      </span>
      {selected?.id === ANALYSIS_BASIS.CUSTOM && onCustomDateChange && (
        <input
          type="date"
          aria-label="Choose analysis date"
          value={customDate ?? selected.asOf ?? ''}
          max={maxDate ?? undefined}
          onChange={(e) => {
            const next = e.target.value
            if (next && (!maxDate || next <= maxDate)) onCustomDateChange(next)
          }}
          className="rounded-md bg-surface-container-high/60 px-2 py-1.5 text-sm text-on-surface [color-scheme:dark] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        />
      )}
    </label>
  )
}
