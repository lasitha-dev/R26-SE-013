import { BAND_LABEL, BAND_RGBA, DEFAULT_DISPLAY_BANDS } from '../adapters/riskFieldModel'
import React, { useState } from 'react'

import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { DISCLAIMER_OPERATIONAL, DISCLAIMER_RISK, LABEL_OPERATIONAL_CONTEXT_SHORT, LABEL_RISK_SCORE } from '../semanticLabels'
import { NEUTRAL_SINGLE_COLOR, RISK_TIER_COLOR, RISK_TIER_LABEL, RISK_TIER_ORDER, UNAVAILABLE_RISK_COLOR } from './mapLibreAdapter'
import { CLINICAL_MARKER_COLOR_HEX } from './operationalIcons'
import { CASE_AGE_CLASS, CASE_AGE_COLOR, RECENT_CASE_MAX_AGE_DAYS, VISIBLE_CASE_MAX_AGE_DAYS } from '../adapters/caseAge'

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
  // GEO-TRAJECTORY-01: whether the CURRENTLY selected real origin genuinely
  // has a real nominal-reach table / a real per-cell bearing on this
  // snapshot -- each legend row only appears while its own real layer is
  // actually capable of being drawn, never a permanently-shown row backed
  // by nothing (mirrors `hasClinicalMarkers`'s existing honesty pattern).
  hasReachRing = false,
  hasDirectionArrows = false,
  hasPage1Forecast = false,
  page1ForecastDateLabel,
  // National surveillance (Outbreak Map): real countrywide report counts on
  // the map, and whether dated historical research records are shown at all
  // (only in an explicitly retrospective/research context).
  nationalCaseCounts = null,
  unmappedRecords = [],
  onSelectUnmappedRecord = null,
  hasHistoricalRecords = true,
}) {
  const [open, setOpen] = useState(initialOpen)

  return (
    // Spans from below the zoom controls to above the timeline dock so a tall
    // legend scrolls inside the map instead of being clipped by its top edge.
    <div className="pointer-events-none absolute bottom-28 right-4 top-20 flex flex-col items-end justify-end gap-2">
      {open && (
        <div className="geo-map-legend pointer-events-auto min-h-0 w-64 overflow-y-auto rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs text-on-surface-variant shadow-card-subtle backdrop-blur">
          {analysisMode === ANALYSIS_MODE.RISK_ZONES ? (
            <RiskZonesLegendBody
              nationalCaseCounts={nationalCaseCounts}
              stats={riskTierStats}
              hasReachRing={hasReachRing}
              hasPage1Forecast={hasPage1Forecast}
              page1ForecastDateLabel={page1ForecastDateLabel}
            />
          ) : analysisMode === ANALYSIS_MODE.TRAJECTORY ? (
            <TrajectoryLegendBody
              nationalCaseCounts={nationalCaseCounts}
              hasReachRing={hasReachRing}
              hasDirectionArrows={hasDirectionArrows}
              hasPage1Forecast={hasPage1Forecast}
              page1ForecastDateLabel={page1ForecastDateLabel}
            />
          ) : (
            <CasesLegendBody
              hasClinicalMarkers={hasClinicalMarkers}
              hasStackedSources={hasStackedSources}
              nationalMarkerShape={nationalMarkerShape}
              hasPage1Forecast={hasPage1Forecast}
              page1ForecastDateLabel={page1ForecastDateLabel}
              nationalCaseCounts={nationalCaseCounts}
              hasHistoricalRecords={hasHistoricalRecords}
            />
          )}
          {unmappedRecords.length > 0 && <details className="mt-2 border-t border-outline-variant/30 pt-2">
            <summary className="cursor-pointer text-[11px] font-semibold">Reports without usable GPS ({unmappedRecords.length})</summary>
            <ul className="mt-1 space-y-1">
              {unmappedRecords.map((record) => <li key={record.recordKey}><button type="button" onClick={() => onSelectUnmappedRecord?.(record)} className="w-full rounded border border-outline-variant/30 p-2 text-left text-[10px] hover:border-primary/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">{record.disease} · {record.district ?? 'District unknown'} · {record.verified ? 'Vet-verified' : 'Pending'}<span className="block truncate font-mono">{record.recordKey}</span></button></li>)}
            </ul>
          </details>}
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
        className="geo-map-info-button pointer-events-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-outline-variant/30 bg-surface-container-high/90 text-sm text-on-surface-variant shadow-sm backdrop-blur hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
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
// Historical WAHIS/EMPRES records are drawn grey (`presentationIcons.js`
// SOURCE_FILL); red is reserved for vet-verified ADRS cases.
const OBSERVED_SOURCE_COLOR = '#94a3b8'
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
// GEO-TRAJECTORY-01: the two real colors the reach-ring/direction layers
// paint with, copied verbatim from their own layer definitions
// (`MapLibreCanvas.jsx`'s `reach-ring-line` paint, `presentationIcons.js`'s
// `DIRECTION_FILL`) so this key can never drift from what is actually drawn.
const REACH_RING_COLOR = '#14b8a6'
const DIRECTION_ARROW_COLOR = '#1e293b'
const PAGE1_FORECAST_COLOR = '#8B5CF6'
// Nominal-reach outline (`MapLibreCanvas.jsx` context line paint).

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
function CasesLegendBody({ hasClinicalMarkers, hasStackedSources, nationalMarkerShape, hasPage1Forecast, page1ForecastDateLabel, nationalCaseCounts = null, hasHistoricalRecords = true }) {
  const markerShape = nationalMarkerShape === 'circle' ? 'circle' : 'diamond'
  return (
    <div className="space-y-1.5">
      <div className="font-semibold text-on-surface">Cases</div>

      {nationalCaseCounts && <ObservedCaseLegendRows counts={nationalCaseCounts} />}

      {hasHistoricalRecords && (
        <>
          <LegendRow color={OBSERVED_SOURCE_COLOR} shape={markerShape} label="Historical record (WAHIS/EMPRES, dated)" />
          <LegendRow color={OBSERVED_SOURCE_COLOR} shape={markerShape} label="Not in the selected origin" dim />
          <LegendRow color={SELECTION_HALO_COLOR} label="Selected origin (ring)" hollow />
          {hasStackedSources && <LegendRow color={STACK_RING_COLOR} label="More than one record here" hollow />}
          <div className="pt-1 text-on-surface-variant/70">
            Official historical outbreak records at their own report dates (grey) -- not current cases. One marker per real location.
          </div>
        </>
      )}
      {hasPage1Forecast && <LegendRow color={PAGE1_FORECAST_COLOR} label="Geometric tendency at source (not a route)" />}

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
/** Observed ADRS case markers: fill = report-date age, outline = status.
 * Counts are RECORDS placed on the map (a stacked marker carries several),
 * never the number of marker symbols. */
export function ObservedCaseLegendRows({ counts }) {
  const byAge = counts.byAge ?? {}
  const undated = (byAge[CASE_AGE_CLASS.DATE_UNKNOWN] ?? 0) + (byAge[CASE_AGE_CLASS.AFTER_REFERENCE] ?? 0)
  return (
    <div className="space-y-1.5 border-b border-outline-variant/30 pb-1.5">
      <div className="font-semibold text-on-surface">Observed cases</div>
      {counts.ageReferenceLabel && <div className="text-[10.5px] text-on-surface-variant/80">{counts.ageReferenceLabel}</div>}
      <LegendRow color={CASE_AGE_COLOR.RECENT} shape="circle" label={`0–${RECENT_CASE_MAX_AGE_DAYS} days since report, pulsing (${byAge[CASE_AGE_CLASS.RECENT] ?? 0})`} />
      <LegendRow color={CASE_AGE_COLOR.OLDER} shape="circle" label={`${RECENT_CASE_MAX_AGE_DAYS + 1}–${VISIBLE_CASE_MAX_AGE_DAYS} days since report (${byAge[CASE_AGE_CLASS.OLDER] ?? 0})`} />
      {undated > 0 && <LegendRow color="#334155" shape="circle" hollow label={`Report date unknown or after reference (${undated})`} />}
      <LegendRow color="#ffffff" shape="circle" hollow label={`White ring: vet-verified (${counts.verifiedOnMap})`} />
      <LegendRow color="#d97706" shape="circle" hollow label={`Amber ring: pending verification (${counts.pendingOnMap})`} />
      {counts.withoutGps > 0 && <div className="pl-4 text-on-surface-variant/70">{counts.withoutGps} more without farm GPS -- counted, not placed.</div>}
      {counts.hiddenOlder > 0 && <div className="pl-4 text-on-surface-variant/70">{counts.hiddenOlder} reported more than {VISIBLE_CASE_MAX_AGE_DAYS} days ago -- not shown.</div>}
      <div className="text-on-surface-variant/70">Age = days since the ADRS report date. Pending is not a confirmed outbreak.</div>
    </div>
  )
}

/** Low -> High colour bar of the fixed display bands (risk surface colours). */
export function RiskScoreColourBar({ dateLabel = null }) {
  const bands = [...DEFAULT_DISPLAY_BANDS].reverse() // low first
  return (
    <div className="space-y-1.5 border-b border-outline-variant/30 pb-2" data-testid="risk-score-colour-bar">
      <div className="flex gap-1">
        {bands.map(({ band }) => (
          <span key={band} className="h-2.5 flex-1 rounded-sm" style={{ background: `rgb(${BAND_RGBA[band].slice(0, 3).join(',')})` }} />
        ))}
      </div>
      <div className="flex text-[10.5px] text-on-surface-variant">
        {bands.map(({ band, min }) => (
          <span key={band} className="flex-1" title={`Score ≥ ${min.toFixed(2)}`}>{BAND_LABEL[band]}</span>
        ))}
      </div>
      <div className="text-on-surface-variant/70">
        {dateLabel ? `${dateLabel}: ` : ''}each case&apos;s 25 km C0 score, shown only as far as its spread can have travelled along its path (3.9 km/day). Overlapping cases add up. Hover a zone for details. Not an infection probability. Uncoloured land = not reached or unscored.
      </div>
    </div>
  )
}

function RiskZonesLegendBody({ nationalCaseCounts = null, stats, hasReachRing = false, hasPage1Forecast = false, page1ForecastDateLabel }) {
  return (
    <div className="space-y-2">
      {nationalCaseCounts && <ObservedCaseLegendRows counts={nationalCaseCounts} />}
      <div className="text-[11px] font-semibold uppercase tracking-wide text-on-surface">
        {hasPage1Forecast ? 'Risk Zones · relative spatial score' : LABEL_RISK_SCORE}
      </div>
      {hasPage1Forecast && <RiskScoreColourBar dateLabel={page1ForecastDateLabel} />}
      {/* GEO-TRAJECTORY-01: the same real reach ring Trajectory mode shows,
          also drawn here for scale (`OutbreakMapPage.jsx`'s `reachRingCenters`
          is non-null in both modes) -- only shown while the selected real
          origin actually has a real `nominal_reach_by_day` table for the
          active day (never a permanently-listed key backed by nothing). */}
      {hasReachRing && <LegendRow color={REACH_RING_COLOR} label="Model-projected nominal reach" hollow />}
      {!hasPage1Forecast &&
        (!stats || stats.allUnavailable ? (
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
        ))}
      {!hasPage1Forecast && (
        <>
          <div className="border-t border-outline-variant/30 pt-1.5 text-on-surface-variant/70">{DISCLAIMER_RISK}</div>
          <div className="text-on-surface-variant/70">Static T0 spatial ranking context -- not a temporal forecast polygon.</div>
        </>
      )}
    </div>
  )
}

/**
 * GEO-TRAJECTORY-01: Trajectory mode's dedicated legend -- the "where might
 * this spread" view, distinct from Risk Zones' "how risky is this cell"
 * tier dots (which this mode deliberately hides, `MapLibreCanvas.jsx`'s
 * `showRiskLayer`-only `cells-circle` gate). Both rows are real, backend-
 * derived data (`nominal_reach_by_day`, per-cell `direction.bearing_deg`,
 * Checkpoint 8B.3) and each is shown ONLY while the selected real origin's
 * current snapshot actually has that data -- never a permanently-listed
 * key backed by nothing (Section 6 of this pass's own requirements).
 */
function TrajectoryLegendBody({ nationalCaseCounts = null, hasReachRing, hasDirectionArrows, hasPage1Forecast, page1ForecastDateLabel }) {
  return (
    <div className="space-y-2">
      {nationalCaseCounts && <ObservedCaseLegendRows counts={nationalCaseCounts} />}
      <div className="text-[11px] font-semibold uppercase tracking-wide text-on-surface">Trajectory</div>
      <div className="space-y-1.5">
        {hasPage1Forecast && <LegendRow color="#7c3aed" label="Dashed ring: nominal reach on this date (distance only)" hollow />}
        {hasPage1Forecast && <LegendRow color={PAGE1_FORECAST_COLOR} label="Purple line: geometric direction tendency (not a route)" />}
        {hasReachRing && <LegendRow color={REACH_RING_COLOR} label="Nominal reach (geometric distance)" hollow />}
        {hasDirectionArrows && <LegendRow color={DIRECTION_ARROW_COLOR} label="Per-cell C0 gradient (research layer)" hollow />}
        {!hasPage1Forecast && !hasReachRing && !hasDirectionArrows && (
          <div className="text-on-surface-variant/70">No geometric tendency or nominal reach for the current selection.</div>
        )}
      </div>
      <div className="border-t border-outline-variant/30 pt-1.5 text-on-surface-variant/70">
        No validated movement trajectory is available. Direction is the local gradient of the relative score at the
        as-of date -- not a transmission route or forecast. Reach is a visualization distance, not a disease boundary.
      </div>
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
