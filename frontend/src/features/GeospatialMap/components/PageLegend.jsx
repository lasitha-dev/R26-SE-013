import React, { useState } from 'react'

import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { DISCLAIMER_OPERATIONAL, DISCLAIMER_RISK, LABEL_OPERATIONAL_CONTEXT_SHORT, LABEL_RISK_SCORE } from '../semanticLabels'
import { NEUTRAL_SINGLE_COLOR, RISK_TIER_COLOR, RISK_TIER_LABEL, RISK_TIER_ORDER, UNAVAILABLE_RISK_COLOR } from './mapLibreAdapter'
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
/**
 * GEO33B Section 9 additions:
 *  - `hasClinicalMarkers`: whether the map is CURRENTLY drawing at least
 *    one real verified-clinical marker. When it is not (a vet with
 *    genuinely zero verified cases in the selected disease/window/scope),
 *    the legend must NOT present a live clinical swatch as if that symbol
 *    were on the map -- that would imply data exists where none does. The
 *    row stays present (so the vet still learns what the symbol means)
 *    but is explicitly marked as not currently shown.
 *  - `hasStackedSources`: whether any national marker genuinely represents
 *    more than one distinct real observed record at one coordinate. The
 *    stack-ring key only appears when that ring is actually drawn.
 *  - `nationalMarkerShape`: mirrors the real `icon-image` the national
 *    layer is painting (diamond = LSD, circle = FMD,
 *    `diseaseRegistry.js`'s `markerShape`), so the legend swatch is the
 *    shape actually on screen rather than a generic dot.
 */
export default function PageLegend({
  analysisMode,
  riskTierStats,
  initialOpen = false,
  hasClinicalMarkers = false,
  hasStackedSources = false,
  nationalMarkerShape = 'diamond',
}) {
  const [open, setOpen] = useState(initialOpen)

  return (
    <div className="pointer-events-auto absolute bottom-28 right-4 flex flex-col items-end gap-2">
      {open && (
        <div className="w-64 rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs text-on-surface-variant shadow-card-subtle backdrop-blur">
          {analysisMode === ANALYSIS_MODE.RISK_ZONES ? (
            <RiskZonesLegendBody stats={riskTierStats} />
          ) : (
            <CasesLegendBody
              hasClinicalMarkers={hasClinicalMarkers}
              hasStackedSources={hasStackedSources}
              nationalMarkerShape={nationalMarkerShape}
            />
          )}
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? 'Hide map legend' : 'Show map legend — what each map symbol means'}
        // GEO33B Section 9: a bare "i" glyph carries no meaning on its
        // own; both the pointer tooltip and the accessible name now say
        // what this control actually opens.
        title={open ? 'Hide map legend' : 'Map legend — what each map symbol means'}
        className="flex h-8 w-8 items-center justify-center rounded-full border border-outline-variant/30 bg-surface-container-high/90 text-sm text-on-surface-variant shadow-sm backdrop-blur hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        i
      </button>
    </div>
  )
}

// GEO30B Section 8/12/33: matches `presentationIcons.js`'s `SOURCE_FILL`
// exactly -- RED is the one color reserved for a real OBSERVED
// outbreak/trigger-source marker on the map, so the legend swatch must
// read the same color a vet actually sees, never an approximation.
const OBSERVED_SOURCE_COLOR = '#ef4444'
// The vet's real district polygon (`MapLibreCanvas.jsx`'s
// `MY_DISTRICT_FILL_LAYER_ID`/`MY_DISTRICT_OUTLINE_LAYER_ID`) -- same hex.
const DISTRICT_BOUNDARY_COLOR = '#4edea3'
// GEO33B Section 9: the two remaining REAL colors this map paints, copied
// from their own layer definitions so this key can never drift from what
// is actually drawn.
// `national-sources-halo`'s `circle-stroke-color` (MapLibreCanvas.jsx) --
// the emerald ring that marks the SELECTED historical origin.
const SELECTION_HALO_COLOR = '#10b981'
// `nationalStackIndicatorPaint`'s `circle-stroke-color`
// (`adapters/nationalSourcePresentation.js`).
const STACK_RING_COLOR = '#fca5a5'

/**
 * GEO33B Section 9. The three things a vet must be able to tell apart in
 * Cases mode each get their own row, named for what they really are:
 *
 *  1. a NATIONAL HISTORICAL/SCIENTIFIC observed outbreak source;
 *  2. an authorized VERIFIED CLINICAL location;
 *  3. the vet's own real DISTRICT OUTLINE.
 *
 * HONESTY NOTE, deliberately reflected in the copy below: (1) and (2) are
 * drawn in the SAME red family and the SAME per-disease shape today
 * (`presentationIcons.js` and `operationalIcons.js` both use red-500 core
 * / red-700 ring, diamond for LSD and circle for FMD) -- GEO30B/GEO31A
 * chose that on purpose so "red means a real observed event" reads
 * consistently across both layers. The genuinely different drawn cues are
 * the SELECTION HALO COLOR (emerald for a selected historical origin, red
 * for a verified clinical marker's own halo) and marker size. This legend
 * therefore states the shared appearance plainly instead of inventing a
 * distinguishing symbol that no layer actually paints.
 */
function CasesLegendBody({ hasClinicalMarkers, hasStackedSources, nationalMarkerShape }) {
  const markerShape = nationalMarkerShape === 'circle' ? 'circle' : 'diamond'
  return (
    <div className="space-y-1.5">
      <div className="font-semibold text-on-surface">Cases</div>

      <LegendRow color={OBSERVED_SOURCE_COLOR} shape={markerShape} label="Observed outbreak source (national)" />
      <LegendRow color={OBSERVED_SOURCE_COLOR} shape={markerShape} label="Not in the selected origin" dim />
      <LegendRow color={SELECTION_HALO_COLOR} label="Selected origin (ring)" hollow />
      {hasStackedSources && <LegendRow color={STACK_RING_COLOR} label="More than one record here" hollow />}
      <div className="pt-1 text-on-surface-variant/70">
        Real historical source positions from the current snapshot only. One marker per real location.
      </div>

      {/* GEO-INT-03 Section 8/21: a visually and textually distinct row --
          never merged into the historical-source rows above -- so the
          legend itself makes the two contexts unmistakably different. */}
      <div className="mt-1 border-t border-outline-variant/30 pt-1.5">
        {/* GEO31A Section 2: solid, not hollow -- the marker itself is now
            a steady red core (never a hollow outline), see
            `operationalIcons.js`. */}
        <LegendRow
          color={CLINICAL_MARKER_COLOR_HEX}
          shape={markerShape}
          label={`${LABEL_OPERATIONAL_CONTEXT_SHORT} location`}
          dim={!hasClinicalMarkers}
        />
        {/* GEO33B Section 9: never present a clinical swatch as a live key
            when nothing clinical is actually on the map right now -- that
            would imply the vet has verified cases they do not have. */}
        {!hasClinicalMarkers && <div className="pl-4 text-on-surface-variant/70">None shown in the current selection</div>}
        <div className="pt-1 text-on-surface-variant/70">{DISCLAIMER_OPERATIONAL}</div>
      </div>

      {/* GEO30B Section 16/26: honest key for the real district polygon --
          an outline only, never implying it carries a scientific value. */}
      <div className="mt-1 border-t border-outline-variant/30 pt-1.5">
        <LegendRow color={DISTRICT_BOUNDARY_COLOR} label="My District boundary" hollow />
        <div className="pt-1 text-on-surface-variant/70">Real administrative boundary, shown for orientation only.</div>
      </div>
    </div>
  )
}

/**
 * GEO-VISUAL-POLISH-03: discrete, SNAPSHOT-RELATIVE risk tiers -- replaces
 * the previous continuous min->max gradient bar. Every color/label used
 * (`RISK_TIER_COLOR`/`RISK_TIER_LABEL`/`RISK_TIER_ORDER`/
 * `NEUTRAL_SINGLE_COLOR`/`UNAVAILABLE_RISK_COLOR`) is imported verbatim
 * from the SAME `mapLibreAdapter.js` module the map's own `cells-circle`
 * paint expression uses, so this legend can never drift from what is
 * actually drawn. Counts are REAL per-tier cell counts from the current
 * snapshot (`computeRiskTierStats`) -- never a percentage, never
 * estimated. Tier boundaries are real quartiles of THIS snapshot's own
 * valid scores, never a fixed absolute threshold -- see
 * `mapLibreAdapter.js`'s own module comment for the full honesty
 * rationale (`raw_c0_score` is a relative spatial ranking, not an
 * infection probability).
 */
function RiskZonesLegendBody({ stats }) {
  return (
    <div className="space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-on-surface">{LABEL_RISK_SCORE}</div>
      {!stats || stats.allUnavailable ? (
        <div>
          All cells <span style={{ color: UNAVAILABLE_RISK_COLOR }}>unavailable</span> in this snapshot.
        </div>
      ) : !stats.hasVariation ? (
        <div>
          All valid scores equal — one neutral color (<span style={{ color: NEUTRAL_SINGLE_COLOR }}>&#9679;</span>), no tiers in this snapshot.
        </div>
      ) : (
        <div className="space-y-1">
          {RISK_TIER_ORDER.slice()
            .reverse()
            .map((tier) => (
              <div key={tier} className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: RISK_TIER_COLOR[tier] }} />
                  {RISK_TIER_LABEL[tier]}
                </span>
                <span className="font-mono text-on-surface">{stats.counts[tier]}</span>
              </div>
            ))}
          <div className="text-on-surface-variant/70">Tiers are real quartiles of THIS snapshot's own scores only -- not comparable across snapshots.</div>
        </div>
      )}
      <div className="border-t border-outline-variant/30 pt-1.5 text-on-surface-variant/70">{DISCLAIMER_RISK}</div>
      <div className="text-on-surface-variant/70">Static T0 spatial ranking context -- not a temporal forecast polygon.</div>
    </div>
  )
}

/**
 * GEO33B Section 9: `shape` mirrors the real `icon-image` the matching map
 * layer paints -- 'diamond' (LSD) is drawn as a rotated square, 'circle'
 * (FMD) stays round -- so the swatch is the actual on-screen symbol, not a
 * generic dot standing in for two different marker shapes. Omitting
 * `shape` keeps the original round swatch, which is correct for the rows
 * that key a RING (selection halo, stack ring, district outline) rather
 * than a marker icon.
 */
function LegendRow({ color, label, dim, hollow, shape }) {
  const isDiamond = shape === 'diamond'
  const style = hollow ? { border: `1.5px solid ${color}`, backgroundColor: 'transparent' } : { backgroundColor: color }
  return (
    <div className={`flex items-center gap-2 ${dim ? 'opacity-60' : ''}`}>
      {/* The diamond swatch is rotated inside a fixed-size box so the
          label text stays on the same baseline as every other row. */}
      <span aria-hidden="true" className="flex h-3 w-3 shrink-0 items-center justify-center">
        <span className={isDiamond ? 'h-2 w-2 rotate-45' : 'h-2 w-2 rounded-full'} style={style} />
      </span>
      <span>{label}</span>
    </div>
  )
}
