import React from 'react'

import { DISCLAIMER_RELATIVE_SPATIAL_SCORE_UNAVAILABLE } from '../semanticLabels'

/**
 * GEO-MY-AREA-VISUAL-QA-REBUILD: the 5-card summary intelligence row for
 * the rebuilt My Area / Area Risk Intelligence composition. Every value
 * below is read straight from data this page already fetches (`myArea`,
 * `focus`, `national`) -- this component computes no science of its own
 * (no distance, no risk tier, no aggregate) and never substitutes a
 * plausible-looking placeholder for a genuinely unavailable real value.
 *
 * Deliberately does NOT color-code the spatial-risk card by severity: the
 * backend's Relative Spatial Score is an explicitly dimensionless,
 * un-tiered value (see `MyAreaScientificPanel.jsx`'s own "never 0%/Low/
 * Green/Safe" rule) -- inventing a HIGH/MODERATE/LOW banding here would
 * fabricate a classification the real contract never makes.
 *
 * GEO-MY-AREA-LAYOUT-BALANCE: every card is a fixed `h-[92px]` (the
 * requested ~86-100px desktop band) with a `truncate`d label/value/
 * sublabel each -- so a genuinely long real string (a long district name,
 * an "unavailable" explanation) can never expand one card taller than its
 * neighbors. The full untruncated text is always still reachable via each
 * element's own `title` tooltip -- shortening what's ON the card never
 * drops information, it only moves the long form off the primary glance.
 */
function KpiCard({ icon, label, value, valueClassName = 'text-on-surface', valueTitle, sublabel, sublabelTitle, accent }) {
  return (
    <div className="flex h-[92px] min-w-0 flex-1 basis-[180px] flex-col gap-1 overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 p-2.5 shadow-card-subtle">
      <div className="flex items-start justify-between gap-2">
        <div className="truncate text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant/70" title={label}>
          {label}
        </div>
        {icon && (
          <span aria-hidden="true" className={`material-symbols-outlined shrink-0 text-[16px] ${accent ?? 'text-on-surface-variant/50'}`}>
            {icon}
          </span>
        )}
      </div>
      <div className={`truncate text-base font-bold leading-tight ${valueClassName}`} title={valueTitle ?? (typeof value === 'string' ? value : undefined)}>
        {value}
      </div>
      {sublabel && (
        <div className="mt-auto truncate text-[10px] leading-tight text-on-surface-variant/60" title={sublabelTitle ?? sublabel}>
          {sublabel}
        </div>
      )}
    </div>
  )
}

export default function MyAreaKpiCards({
  areaDistrictLabel,
  hasSpatialCells,
  relativeSpatialScore,
  availableForecastDays,
  relevantOriginsCount,
  verifiedClinicalCount,
  nationalCount,
  nationalStatus,
  diseaseShortLabel,
}) {
  // Card 1 -- My Area Risk.
  let riskValue = 'SELECT ORIGIN'
  let riskSub = 'No origin chosen'
  let riskSubTitle = 'Choose a relevant origin to see local spatial risk.'
  let riskClass = 'text-on-surface-variant'
  if (!hasSpatialCells) {
    riskValue = 'NOT AVAILABLE'
    riskSub = 'No spatial model'
    riskSubTitle = `No spatial-cell risk model for ${diseaseShortLabel ?? 'this disease'} yet.`
  } else if (relativeSpatialScore) {
    if (relativeSpatialScore.value === null) {
      riskValue = 'UNAVAILABLE'
      riskSub = 'Not exposed for this location'
      riskSubTitle = DISCLAIMER_RELATIVE_SPATIAL_SCORE_UNAVAILABLE
      riskClass = 'text-on-surface-variant'
    } else {
      riskValue = Number.isInteger(relativeSpatialScore.value) ? String(relativeSpatialScore.value) : relativeSpatialScore.value.toFixed(2)
      riskSub = relativeSpatialScore.label
      riskSubTitle = relativeSpatialScore.label
      riskClass = 'text-primary'
    }
  }

  // Card 2 -- GEO-MY-AREA-FINAL-PASS: the only field that genuinely
  // varies per real forecast day is nominal reach (`nominal_reach_by_day`
  // -- see `MyAreaTemporalOutlook.jsx`'s own docstring); there is no
  // time-varying RISK value in the current runtime. This card previously
  // read "Upcoming risk window", silently implying a risk-over-time
  // semantic the backend doesn't produce -- inconsistent with
  // `MyAreaIntelligencePanel.jsx`'s own "Available forecast window" Row
  // label for the exact same `availableForecastDays` data. Renamed to
  // match that truthful, already-used wording exactly.
  const futureDays = (availableForecastDays ?? []).filter((d) => d > 0)
  const windowValue = futureDays.length === 0 ? 'NOT AVAILABLE' : `D+${Math.min(...futureDays)}–D+${Math.max(...futureDays)}`
  const windowSub = futureDays.length === 0 ? 'No temporal frames' : `${futureDays.length} real frame${futureDays.length === 1 ? '' : 's'}`
  const windowSubTitle = futureDays.length === 0 ? 'No time-varying forecast is available for this selection.' : `${futureDays.length} real forecast frame(s) available`

  // Card 5 -- National situation, real national origin count for the selected disease.
  const nationalValue = nationalStatus === 'loading' ? '…' : nationalStatus === 'error' ? 'UNAVAILABLE' : String(nationalCount ?? 0)
  const nationalSub = nationalStatus === 'error' ? 'Layer unreachable' : `${diseaseShortLabel ?? ''} origins nationally`.trim()

  return (
    <div className="flex flex-wrap gap-2.5">
      <KpiCard
        icon="radar"
        label={`My area risk${areaDistrictLabel ? ` (${areaDistrictLabel})` : ''}`}
        value={riskValue}
        valueClassName={riskClass}
        sublabel={riskSub}
        sublabelTitle={riskSubTitle}
        accent="text-primary"
      />
      <KpiCard icon="calendar_month" label="Available forecast window" value={windowValue} sublabel={windowSub} sublabelTitle={windowSubTitle} accent="text-amber-300" />
      <KpiCard icon="hub" label="Relevant outbreaks" value={relevantOriginsCount} sublabel="Historical / model origins" accent="text-sky-300" />
      <KpiCard icon="medical_information" label="Recent verified cases" value={verifiedClinicalCount} sublabel="This farm" accent="text-rose-300" />
      <KpiCard icon="public" label="National situation" value={nationalValue} sublabel={nationalSub} accent="text-on-surface-variant" />
    </div>
  )
}
