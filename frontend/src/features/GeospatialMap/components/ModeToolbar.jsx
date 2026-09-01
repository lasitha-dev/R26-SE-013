import React from 'react'

import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { CAPABILITY, hasCapability } from '../disease/diseaseRegistry'

/**
 * LSD-UI-03/04: `Cases | Clusters | Risk Zones | Trajectory | Env`
 * (plan Section 21). Functionality follows actual backend capability,
 * not the visual prototype -- Cases and Risk Zones are real and
 * clickable; Clusters/Env are honestly disabled because the runtime API
 * has no cluster/environmental-layer output yet (`services/stdbscan`,
 * `services/hazard` are real but unwired -- see plan Section B/O), not
 * because of a frontend limitation. Trajectory's availability instead
 * follows the selected disease's real `trajectory` capability (see
 * below) -- unlike Clusters/Env, the runtime API DOES produce real
 * per-cell direction (`bearing_deg`, Checkpoint 8B.3) and real
 * `nominal_reach_by_day` today, so it is not honest to hold it
 * permanently disabled. Mode switching never touches outbreak/day/
 * camera state (dispatched via `setMode`, which the reducer guarantees).
 */
const MODES = [
  { id: ANALYSIS_MODE.CASES, label: 'Cases', available: true },
  { id: ANALYSIS_MODE.CLUSTERS, label: 'Clusters', available: false, reason: 'No ST-DBSCAN cluster output is exposed by the runtime API yet.' },
  { id: ANALYSIS_MODE.RISK_ZONES, label: 'Risk Zones', available: true },
  {
    id: ANALYSIS_MODE.TRAJECTORY,
    label: 'Trajectory',
    available: false,
    reason: 'Trajectory needs a selected disease with a real per-cell direction/reach model.',
  },
  { id: ANALYSIS_MODE.ENV, label: 'Env', available: false, reason: 'No environmental driver layers are exposed by the runtime API yet.' },
]

/**
 * FMD-10C: `disease` is OPTIONAL and additive -- omitted (as every
 * pre-existing caller/test still does), Risk Zones/Trajectory stay
 * exactly as `MODES` above declares them (Risk Zones real/clickable,
 * Trajectory disabled with its disease-agnostic reason). Passed
 * explicitly (`OutbreakMapPage.jsx` now does, with `ctx.selectedDisease`):
 * Risk Zones is ADDITIONALLY disabled for a disease lacking the
 * `riskZones` capability (FMD today -- no nominal-reach/spatial-cell
 * data to draw a reach ring from); Trajectory is ENABLED for a disease
 * that has the real `trajectory` capability (LSD today -- confirmed live
 * per-cell `bearing_deg` + `nominal_reach_by_day`, see
 * `diseaseRegistry.js`) and stays disabled, with an accurate per-disease
 * reason, otherwise (FMD -- no spatial-cell/direction model at all). The
 * static `MODES` export itself is never mutated -- existing tests that
 * inspect it directly keep seeing the same baseline.
 */
export default function ModeToolbar({ analysisMode, onSetMode, disease }) {
  const riskZonesAvailable = disease === undefined ? true : hasCapability(disease, CAPABILITY.RISK_ZONES)
  const trajectoryAvailable = disease !== undefined && hasCapability(disease, CAPABILITY.TRAJECTORY)
  const modes = MODES.map((mode) => {
    if (mode.id === ANALYSIS_MODE.RISK_ZONES && !riskZonesAvailable) {
      return { ...mode, available: false, reason: 'Risk Zones needs a nominal-reach/spatial-cell model not yet frozen for this disease.' }
    }
    if (mode.id === ANALYSIS_MODE.TRAJECTORY) {
      return trajectoryAvailable
        ? { ...mode, available: true, reason: undefined }
        : { ...mode, available: false, reason: disease === undefined ? mode.reason : 'Trajectory needs a per-cell direction/reach model not yet frozen for this disease.' }
    }
    return mode
  })

  return (
    <div
      // GEO33B Section 14: `shadow-lg` (a 10px-blur, 15%-opacity black
      // drop shadow) read as a heavy dark smear under this pill against
      // the dark map card -- the toolbar floats over geography, so a
      // large soft blur muddies real coastline/labels directly beneath
      // it. Replaced with a small `shadow-sm` plus a slightly more
      // present border, which is what actually separates the pill from
      // the map. Nothing about size, spacing, contrast or hit area
      // changes.
      className="pointer-events-auto flex items-center gap-1 rounded-full border border-outline-variant/40 bg-surface-container/90 p-1.5 shadow-sm backdrop-blur"
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
              className="cursor-not-allowed rounded-full px-3.5 py-2 text-sm text-on-surface-variant/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-variant"
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
              // GEO-STITCH-PAGE1-14: a genuinely STRONG active state (solid
              // fill + the same restrained emerald glow the rest of this
              // theme already uses for primary affordances --
              // `shadow-glow-sm`, `tailwind.config.js`, e.g. the timeline's
              // own play button) rather than a soft 20%-opacity tint, so
              // the active mode reads unmistakably at a glance -- matches
              // the Stitch reference's filled-pill active button.
              active
                ? 'rounded-full bg-primary px-3.5 py-2 text-sm font-semibold text-on-primary shadow-glow-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                : 'rounded-full px-3.5 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container-highest/60 hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
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
