import React from 'react'

import { getDiseaseConfig, listDiseaseCodes } from '../disease/diseaseRegistry'

/**
 * GEO-ANALYSIS-02 Section 9/13/35: Page-3-specific disease control --
 * deliberately NOT a reuse of the shared `DiseaseSelector.jsx`. That
 * component marks any disease whose `isDiseaseReady()` is false (today,
 * FMD) as non-interactive, because on Page 1 there is
 * genuinely nothing to show without a ready scientific model. Page 3 is
 * different: FMD historical source records/forecast origins/trend ARE
 * real and available (GEO-ANALYSIS-01H proved 16 real Sri Lanka FMD
 * records) even though the FMD scientific MODEL is not ready -- Section
 * 13's explicit requirement is that this real historical evidence stay
 * visible and selectable, not blocked behind the same readiness gate
 * Page 1 uses for an unrelated reason (Page 1 needs a full forecast
 * frame; Page 3's historical view does not). Both diseases are always a
 * real, clickable option here; model-not-ready is communicated
 * separately and honestly inside the page body (Section 35), never by
 * disabling disease selection itself.
 */
export default function AnalysisTrendsDiseaseToggle({ selected, onSelect }) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-white/10 bg-slate-900/70 p-1" role="group" aria-label="Disease">
      {listDiseaseCodes().map((code) => {
        const config = getDiseaseConfig(code)
        const active = selected === code
        return (
          <button
            key={code}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(code)}
            className={
              active
                ? 'rounded-full bg-emerald-400/20 px-3.5 py-1.5 text-sm font-medium text-emerald-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
                : 'rounded-full px-3.5 py-1.5 text-sm text-slate-300 transition-colors hover:bg-slate-800 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
            }
          >
            {config.shortLabel}
          </button>
        )
      })}
    </div>
  )
}
