import React from 'react'

import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { CAPABILITY, hasCapability } from '../disease/diseaseRegistry'

/**
 * LSD-UI-03/04: `Cases | Clusters | Risk Zones | Trajectory | Env`
 * (plan Section 21). Functionality follows actual backend capability,
 * not the visual prototype -- Cases and Risk Zones are real and
 * clickable; Clusters/Trajectory/Env are honestly disabled because the
 * runtime API has no cluster/trajectory/environmental-layer output yet
 * (`services/stdbscan`, `services/hazard`, `services/geospatial/*` are
 * real but unwired -- see plan Section B/O), not because of a frontend
 * limitation. Mode switching never touches outbreak/day/camera state
 * (dispatched via `setMode`, which the reducer guarantees).
 */
const MODES = [
  { id: ANALYSIS_MODE.CASES, label: 'Cases', available: true },
  { id: ANALYSIS_MODE.CLUSTERS, label: 'Clusters', available: false, reason: 'No ST-DBSCAN cluster output is exposed by the runtime API yet.' },
  { id: ANALYSIS_MODE.RISK_ZONES, label: 'Risk Zones', available: true },
  { id: ANALYSIS_MODE.TRAJECTORY, label: 'Trajectory', available: false, reason: 'No trajectory/corridor geometry is produced by the runtime API yet.' },
  { id: ANALYSIS_MODE.ENV, label: 'Env', available: false, reason: 'No environmental driver layers are exposed by the runtime API yet.' },
]

/**
 * FMD-10C: `disease` is OPTIONAL and additive -- omitted (as every
 * pre-existing caller/test still does), Risk Zones stays exactly as
 * `MODES` above declares it (real/clickable, unchanged LSD behavior).
 * Passed explicitly (`OutbreakMapPage.jsx` now does, with
 * `ctx.selectedDisease`), Risk Zones is ADDITIONALLY disabled for a
 * disease lacking the `riskZones` capability (FMD today -- no
 * nominal-reach/spatial-cell data to draw a reach ring from). The
 * static `MODES` export itself is never mutated -- existing tests that
 * inspect it directly keep seeing the LSD baseline.
 */
export default function ModeToolbar({ analysisMode, onSetMode, disease }) {
  const riskZonesAvailable = disease === undefined ? true : hasCapability(disease, CAPABILITY.RISK_ZONES)
  const modes = MODES.map((mode) =>
    mode.id === ANALYSIS_MODE.RISK_ZONES && !riskZonesAvailable
      ? { ...mode, available: false, reason: 'Risk Zones needs a nominal-reach/spatial-cell model not yet frozen for this disease.' }
      : mode,
  )

  return (
    <div
      className="pointer-events-auto flex items-center gap-1 rounded-full border border-emerald-500/20 bg-slate-900/80 px-2 py-1.5 shadow-lg backdrop-blur"
      role="tablist"
      aria-label="Map analysis mode"
    >
      {modes.map((mode) => {
        const active = analysisMode === mode.id
        if (!mode.available) {
          // A real <button> (not <span>) so the explanation is reachable
          // by keyboard focus, not only mouse hover -- `aria-disabled`
          // rather than the native `disabled` attribute keeps it
          // focusable/tabbable while still refusing the click.
          return (
            <button
              key={mode.id}
              type="button"
              role="tab"
              aria-disabled="true"
              aria-selected="false"
              aria-label={`${mode.label}: ${mode.reason}`}
              title={mode.reason}
              onClick={(e) => e.preventDefault()}
              className="cursor-not-allowed rounded-full px-3 py-1.5 text-sm text-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
            >
              {mode.label}
            </button>
          )
        }
        return (
          <button
            key={mode.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onSetMode(mode.id)}
            className={
              active
                ? 'rounded-full border border-emerald-400/40 bg-emerald-400/20 px-3 py-1.5 text-sm font-medium text-emerald-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
                : 'rounded-full px-3 py-1.5 text-sm text-slate-300 transition-colors hover:bg-slate-800 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
            }
          >
            {mode.label}
          </button>
        )
      })}
    </div>
  )
}

export { MODES }
