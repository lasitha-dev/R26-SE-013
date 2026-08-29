import React from 'react'

import { CAPABILITY, getDiseaseConfig, hasCapability, listDiseaseCodes } from '../disease/diseaseRegistry'

/**
 * LSD-PAGE1-HARDENING Section 9/11, updated FMD-10C: compact header
 * disease control (plan layout "[LSD ▼] [Sri Lanka Overview ▼]"). Reads
 * the SAME `diseaseRegistry` the rest of this feature already uses.
 *
 * FMD-10C: gated on the `historicalOrigins` capability, not the coarse
 * `ready` flag -- FMD now has real, live historical origins + a real
 * scalar risk score (confirmed live against the backend, 2026-08-28),
 * so it is a genuine, real selection here even though its full
 * LSD-shaped spatial model (`ready`) is still not API-ready (Page 1's
 * own `!diseaseReady` banner communicates THAT limitation honestly,
 * separately). A disease with NO real capability at all would still
 * render exactly like `ModeToolbar`'s unavailable-mode buttons: a real,
 * keyboard-focusable `<button>` with `aria-disabled`, never a normal
 * clickable option -- so there is still no way to produce a fake
 * "successful switch" to a disease the backend can't serve at all.
 */
export default function DiseaseSelector({ selected, onSelect }) {
  return (
    <div
      className="flex items-center gap-1 rounded-full border border-white/10 bg-slate-900/70 p-1"
      role="group"
      aria-label="Disease"
    >
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
              className="cursor-not-allowed rounded-full px-3 py-1 text-xs text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500"
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
                ? 'rounded-full bg-emerald-400/20 px-3 py-1 text-xs font-medium text-emerald-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
                : 'rounded-full px-3 py-1 text-xs text-slate-300 hover:bg-slate-800 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
            }
          >
            {config.shortLabel}
          </button>
        )
      })}
    </div>
  )
}
