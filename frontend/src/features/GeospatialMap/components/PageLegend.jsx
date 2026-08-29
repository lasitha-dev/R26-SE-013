import React, { useState } from 'react'

import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { DISCLAIMER_OPERATIONAL, DISCLAIMER_RISK, LABEL_OPERATIONAL_CONTEXT_SHORT, LABEL_RISK_SCORE } from '../semanticLabels'
import { NEUTRAL_SINGLE_COLOR, UNAVAILABLE_RISK_COLOR } from './mapLibreAdapter'
import { CLINICAL_MARKER_COLOR_HEX } from './operationalIcons'

/**
 * LSD-PAGE1-HARDENING Section 8/14/15: a compact, collapsible, dark
 * legend docked inside the map (the plan layout's "[Legend]" slot),
 * mode-aware so it never shows Risk Zones semantics while Cases is
 * active or vice versa. Deliberately a NEW component rather than
 * reusing `MapLegend.jsx` (Checkpoint 11B's light-themed debug-view
 * legend, still used unchanged by `MapView.jsx`) -- restyling that one
 * for this page's dark map chrome would risk the older debug view.
 * Every string/color below is either imported from the vetted
 * `semanticLabels.js` wording firewall or copied from the same
 * `mapLibreAdapter.js` color constants the map itself paints with, so
 * this can never drift from what's actually rendered.
 */
export default function PageLegend({ analysisMode, riskStats, initialOpen = false }) {
  const [open, setOpen] = useState(initialOpen)

  return (
    <div className="pointer-events-auto absolute bottom-28 right-4 flex flex-col items-end gap-2">
      {open && (
        <div className="w-64 rounded-lg border border-white/10 bg-slate-900/90 p-3 text-xs text-slate-300 shadow-xl backdrop-blur">
          {analysisMode === ANALYSIS_MODE.RISK_ZONES ? <RiskZonesLegendBody stats={riskStats} /> : <CasesLegendBody />}
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? 'Hide map legend' : 'Show map legend'}
        title="Legend"
        className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-slate-900/80 text-sm text-slate-300 shadow-lg backdrop-blur hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        i
      </button>
    </div>
  )
}

function CasesLegendBody() {
  return (
    <div className="space-y-1.5">
      <div className="font-semibold text-slate-200">Cases</div>
      <LegendRow color="#10b981" label="Selected source" />
      <LegendRow color="#10b981" label="Context source" dim />
      <div className="pt-1 text-slate-500">Real historical source positions from the current snapshot only.</div>
      {/* GEO-INT-03 Section 8/21: a visually and textually distinct row --
          never merged into the historical-source rows above -- so the
          legend itself makes the two contexts unmistakably different. */}
      <div className="mt-1 border-t border-white/10 pt-1.5">
        <LegendRow color={CLINICAL_MARKER_COLOR_HEX} label={LABEL_OPERATIONAL_CONTEXT_SHORT} hollow />
        <div className="pt-1 text-slate-500">{DISCLAIMER_OPERATIONAL}</div>
      </div>
    </div>
  )
}

function RiskZonesLegendBody({ stats }) {
  return (
    <div className="space-y-1.5">
      <div className="font-semibold text-slate-200">{LABEL_RISK_SCORE}</div>
      {!stats || stats.allUnavailable ? (
        <div>
          All cells <span style={{ color: UNAVAILABLE_RISK_COLOR }}>unavailable</span> in this snapshot.
        </div>
      ) : !stats.hasVariation ? (
        <div>
          All valid scores equal — one neutral color (<span style={{ color: NEUTRAL_SINGLE_COLOR }}>&#9679;</span>), no gradient in this snapshot.
        </div>
      ) : (
        <div>
          low <span className="text-blue-400">&#9679;</span> &rarr; high <span className="text-red-500">&#9679;</span> (range{' '}
          {stats.min?.toFixed(2)}–{stats.max?.toFixed(2)} in this snapshot only)
        </div>
      )}
      <div className="text-slate-500">Color is normalized within this snapshot for presentation only -- not comparable across snapshots.</div>
      <div className="text-slate-500">{DISCLAIMER_RISK}</div>
      <div className="text-slate-500">Static T0 spatial ranking context -- not a temporal forecast polygon.</div>
    </div>
  )
}

function LegendRow({ color, label, dim, hollow }) {
  return (
    <div className={`flex items-center gap-2 ${dim ? 'opacity-60' : ''}`}>
      <span
        aria-hidden="true"
        className="h-2 w-2 rounded-full"
        style={hollow ? { border: `1.5px solid ${color}`, backgroundColor: 'transparent' } : { backgroundColor: color }}
      />
      <span>{label}</span>
    </div>
  )
}
