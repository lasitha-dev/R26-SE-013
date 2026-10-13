import React from 'react'

import { OBSERVATION_WINDOW_OPTIONS } from '../adapters/observationWindow'
import { LABEL_OBSERVATION_WINDOW } from '../semanticLabels'

/**
 * GEO26B Section 6/25, GEO31A: the Observation Date Range control --
 * filters which already-verified clinical contexts are shown (Cases
 * mode). Deliberately a plain, separate control from the scientific
 * forecast TimelineControl -- selecting a wider date range never changes
 * `selectedForecastDay` or fetches a model frame.
 *
 * GEO31A: "bare" (no self-contained pill) -- composed inside the single
 * unified toolbar in `OutbreakMapPage.jsx`, using the host dashboard's
 * real design tokens and a real `expand_more` Material Symbol (see
 * `LocationScopeSelect.jsx`'s docstring for why, same reasoning here).
 */
export default function ObservationWindowSelect({ days, onChange }) {
  return (
    <label className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant/70">{LABEL_OBSERVATION_WINDOW}</span>
      <span className="relative flex items-center">
        <select
          value={days}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={LABEL_OBSERVATION_WINDOW}
          className="cursor-pointer appearance-none rounded-md bg-surface-container-high/60 py-2 pl-3 pr-7 text-sm font-medium text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {OBSERVATION_WINDOW_OPTIONS.map((option) => (
            <option key={option.id} value={option.days} className="bg-surface-container-high">
              {option.label}
            </option>
          ))}
        </select>
        <span aria-hidden="true" className="material-symbols-outlined pointer-events-none absolute right-1.5 text-[18px] text-on-surface-variant/70">
          expand_more
        </span>
      </span>
    </label>
  )
}
