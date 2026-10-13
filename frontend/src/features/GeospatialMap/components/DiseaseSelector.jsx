import React from 'react'

import { CAPABILITY, getDiseaseConfig, hasCapability, listDiseaseCodes } from '../disease/diseaseRegistry'

/**
 * LSD-PAGE1-HARDENING Section 9/11, updated FMD-10C, GEO31A: compact
 * header disease control. Reads the SAME `diseaseRegistry` the rest of
 * this feature already uses.
 *
 * GEO31A: now a "bare" segmented control (no self-contained pill/border
 * of its own) -- it is composed inside the single unified toolbar
 * container in `OutbreakMapPage.jsx` alongside Location/Window, matching
 * the approved reference's "ONE toolbar, not several floating chips"
 * layout. Uses the host dashboard's real design tokens
 * (`primary`/`on-surface-variant`/`surface-container-high`, from
 * `tailwind.config.js`) instead of ad-hoc slate/emerald utility colors,
 * so it reads as native to the existing theme. A selected disease shows
 * a real `check` Material Symbol (the same icon font already loaded
 * globally via `index.html` and used throughout `VetLayout.jsx`) --
 * never a decorative emoji.
 *
 * FMD-10C: gated on the `historicalOrigins` capability, not the coarse
 * `ready` flag -- FMD now has real, live historical origins + a real
 * scalar risk score, so it is a genuine, real selection here even though
 * its full LSD-shaped spatial model (`ready`) is still not API-ready
 * (Page 1's own `!diseaseReady` banner communicates THAT limitation
 * honestly, separately). A disease with NO real capability at all still
 * renders as a real, keyboard-focusable `<button>` with `aria-disabled`,
 * never a normal clickable option -- so there is still no way to produce
 * a fake "successful switch" to a disease the backend can't serve at all.
 */
export default function DiseaseSelector({ selected, onSelect }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant/70">Disease</span>
      <div className="flex items-center gap-0.5 rounded-md bg-surface-container-high/60 p-0.5" role="group" aria-label="Disease">
        {listDiseaseCodes().map((code) => {
          const config = getDiseaseConfig(code)
          const selectable = hasCapability(code, CAPABILITY.HISTORICAL_ORIGINS)
          const active = selected === code

          if (!selectable) {
            return (
              <button
                key={code}
                type="button"
                aria-disabled="true"
                aria-label={`${config.label}: no real data available`}
                title={`${config.label} has no real data available from the backend yet.`}
                onClick={(e) => e.preventDefault()}
                className="cursor-not-allowed rounded px-3 py-2 text-sm text-on-surface-variant/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-variant"
              >
                {config.shortLabel}
              </button>
            )
          }

          return (
            <button
              key={code}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(code)}
              className={
                active
                  ? 'flex items-center gap-1 rounded bg-primary px-3 py-2 text-sm font-semibold text-on-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                  : 'rounded px-3 py-2 text-sm font-medium text-on-surface-variant hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
              }
            >
              {active && (
                <span aria-hidden="true" className="material-symbols-outlined text-[15px]">
                  check
                </span>
              )}
              {config.shortLabel}
            </button>
          )
        })}
      </div>
    </div>
  )
}
