import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import EnvironmentalContextPanel from './EnvironmentalContextPanel'

const PLAIN_LIMITATIONS = {
  RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY: 'The relative score ranks places by closeness to known sources. It is not a probability of infection.',
  RISK_TIERS_ARE_SNAPSHOT_RELATIVE_QUARTILES_NOT_COMPARABLE_ACROSS_SNAPSHOTS: 'Tiers are quartiles of this snapshot only, so a "highest" zone today is not comparable with another day or disease.',
  C0_SURFACE_AND_TIER_ZONES_IDENTICAL_ON_EVERY_DAY_STATIC_T0_MODEL: 'Risk zones are fixed at the as-of date and do not change across Day 0–14.',
  DAY_TO_DAY_CHANGE_IS_THE_NOMINAL_REACH_ENVELOPE_ONLY: 'The only thing that changes with the selected day is the nominal-reach outline.',
  NOMINAL_REACH_IS_VISUALIZATION_ONLY_NOT_A_HARD_DISEASE_BOUNDARY_NEVER_RECONCILED_WITH_25KM_ENVELOPE: 'Nominal reach is a distance-only visual guide, not a boundary of where disease will be.',
  DAYS_8_14_EXTRAPOLATE_THE_D1_D7_REACH_FORMULA_EXPLORATORY: 'Days 8–14 extend the Day 1–7 distance formula and are exploratory.',
  C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_NOT_DISEASE_SPREAD_DIRECTION: 'Direction arrows show where the relative score falls off most steeply, not the direction disease is spreading.',
  NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE_NEVER_CAUSAL_TRANSMISSION_SOURCE: 'The nearest source is a geometric reference, never a proven cause.',
  SOURCE_SET_FIXED_AT_AS_OF_DATE_NO_FUTURE_CASES_ARE_GENERATED: 'Sources are fixed at the as-of date; no future cases are generated.',
  SCORED_AREA_LIMITED_TO_25KM_SOURCE_BUFFER_DOMAIN_REACH_BEYOND_IT_SHOWS_NO_ZONES: 'Only places within 25 km of a source are scored.',
  OPERATIONAL_SOURCE_POSITION_IS_THE_FARM_GPS_NOT_THE_ANIMAL_LOCATION: 'A verified case is placed at its farm GPS, not the animal’s exact location.',
  ENVIRONMENTAL_VARIABLES_NOT_USED_IN_ANY_SCORE: 'Weather and environment are not used in any score.',
  DEVELOPMENT_HISTORICAL_APPARENT_RATE_ESTIMATION_NOT_BIOLOGICAL_TRANSMISSION_SPEED: 'The reach rate is an apparent historical rate, not a biological transmission speed.',
}

function countByDomain(sources) {
  let operational = 0
  let historical = 0
  for (const s of sources ?? []) {
    if (s?.record_domain === 'OPERATIONAL') operational += 1
    else historical += 1
  }
  return { operational, historical }
}

function Row({ label, children }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 border-t border-outline-variant/15 py-2 text-[11px] first:border-t-0">
      <div className="font-semibold text-on-surface-variant/70">{label}</div>
      <div className="leading-relaxed text-on-surface">{children}</div>
    </div>
  )
}

/**
 * "How to read this map": provenance and method of the active Spatial
 * Timeline snapshot, in plain language, every value read from the
 * backend response. The exact backend limitation codes stay available
 * (collapsed) for scientific traceability.
 */
export default function SpatialEvidencePanel({ timeline, diseaseShortLabel = '', activeFrame = null, defaultOpen = false }) {
  if (!timeline) return null
  const counts = countByDomain(timeline.sources)
  const window = timeline.time_window ?? {}
  const reachFrame = (timeline.frames ?? []).find((f) => f?.day === 7)
  const rate = reachFrame?.reach?.rate_km_day ?? activeFrame?.reach?.rate_km_day
  const modelNotReady = timeline.status === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY'
  const limitations = Array.isArray(timeline.limitations) ? timeline.limitations : []
  const plain = limitations.map((code) => PLAIN_LIMITATIONS[code]).filter(Boolean)
  return (
    <details className="group rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-semibold text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <span>Evidence &amp; method — how to read this map</span>
        <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-on-surface-variant transition-transform group-open:rotate-180">expand_more</span>
      </summary>
      <div className="px-4 pb-4">
        <Row label="Data as of">
          {timeline.as_of ? formatDisplayDate(timeline.as_of) : 'Unknown'}
          {window.source_window_start && window.source_window_end && (
            <span className="text-on-surface-variant"> · sources from {formatDisplayDate(window.source_window_start)} to {formatDisplayDate(window.source_window_end)}</span>
          )}
        </Row>
        <Row label="Sources used">
          {counts.operational} vet-verified {diseaseShortLabel} case{counts.operational === 1 ? '' : 's'} (at farm GPS) · {counts.historical} historical research record{counts.historical === 1 ? '' : 's'}
          {timeline.source_statuses && (
            <span className="text-on-surface-variant"> · feeds: verified cases {String(timeline.source_statuses.operational ?? 'n/a').toLowerCase()}, historical {String(timeline.source_statuses.historical ?? 'n/a').toLowerCase()}</span>
          )}
        </Row>
        <Row label="Model readiness">
          {modelNotReady ? `No validated spatial model for ${diseaseShortLabel}. Verified cases are shown; no zones, direction or reach are computed.` : 'Frozen research relative-score model (C0) available for this disease. Parameters are fixed; nothing is re-fitted at run time.'}
        </Row>
        {!modelNotReady && (
          <>
            <Row label="Relative risk zones">
              Each scored grid cell adds up exp(−distance ÷ 25 km) over every eligible source; zones are this snapshot’s quartiles
              {timeline.tier_thresholds ? ` (cut-offs ${timeline.tier_thresholds.q1.toFixed(2)} / ${timeline.tier_thresholds.median.toFixed(2)} / ${timeline.tier_thresholds.q3.toFixed(2)})` : ''}.
            </Row>
            <Row label="Direction">Arrows at sources show where the relative score falls off most steeply (a geometric tendency), not a transmission route.</Row>
            <Row label="Day 0–14 reach">
              {Number.isFinite(rate) ? `Outline radius = ${rate.toFixed(2)} km/day × day (Day 7 ≈ ${(rate * 7).toFixed(1)} km). ` : ''}
              Day 0 is the as-of context; Days 1–7 use the supported reach horizon; Days 8–14 are exploratory.
            </Row>
          </>
        )}
        <Row label="Environment">
          <EnvironmentalContextPanel environment={timeline.environment} compact />
        </Row>
        {plain.length > 0 && (
          <Row label="Limitations">
            <ul className="list-disc space-y-1 pl-4">
              {plain.map((text) => <li key={text}>{text}</li>)}
            </ul>
            <details className="mt-2">
              <summary className="cursor-pointer text-[10px] text-on-surface-variant/60">Technical limitation codes</summary>
              <div className="mt-1 break-words font-mono text-[9.5px] leading-relaxed text-on-surface-variant/55">{limitations.join(' · ')}</div>
            </details>
          </Row>
        )}
        {timeline.model?.risk && <div className="mt-2 break-words font-mono text-[9.5px] text-on-surface-variant/45">{timeline.model.risk}</div>}
      </div>
    </details>
  )
}
