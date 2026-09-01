import React, { useState } from 'react'

import { AREA_RISK_COLORS } from '../adapters/myAreaPresentationForecast'
import { formatDisplayDate } from '../adapters/forecastDate'

const TAB = { AREA: 'AREA', EXPLAINER: 'EXPLAINER' }

function Row({ label, value, valueClassName = '' }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2">
      <dt className="text-[11px] leading-snug text-on-surface-variant/60">{label}</dt>
      <dd className={`max-w-[62%] text-right text-xs font-semibold leading-snug text-on-surface ${valueClassName}`}>{value}</dd>
    </div>
  )
}

function districtRiskColor(level) {
  if (level === 'low') return AREA_RISK_COLORS.green
  if (level === 'moderate') return AREA_RISK_COLORS.yellow
  if (level === 'elevated') return AREA_RISK_COLORS.orange
  return AREA_RISK_COLORS.red
}

/** Deterministic Page-2 intelligence readout. Every changing row receives
 * the same active forecast snapshot as the map, timeline, chart and cards. */
export default function MyAreaIntelligencePanel({
  area,
  authorizedDistrict = 'Matara',
  activeDate,
  activeIndex,
  districtRisk,
  influencingCount,
  projectedPathCount,
  verifiedClinicalCount,
  focusedCaseId,
  overlapRiskLevel,
}) {
  const [tab, setTab] = useState(TAB.AREA)
  const coordinates = area && typeof area.latitude === 'number' && typeof area.longitude === 'number'
    ? `${area.latitude.toFixed(4)}, ${area.longitude.toFixed(4)}`
    : 'Not available'

  return (
    <section className="flex flex-col rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" aria-label="Area Intelligence">
      <div className="flex shrink-0 gap-1 border-b border-outline-variant/20 p-2" role="tablist" aria-label="Area intelligence tabs">
        <button type="button" role="tab" aria-selected={tab === TAB.AREA} onClick={() => setTab(TAB.AREA)} className={tab === TAB.AREA ? 'rounded-md bg-primary/15 px-3 py-1.5 text-xs font-semibold text-primary' : 'rounded-md px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-high/60'}>Area Intelligence</button>
        <button type="button" role="tab" aria-selected={tab === TAB.EXPLAINER} onClick={() => setTab(TAB.EXPLAINER)} className={tab === TAB.EXPLAINER ? 'rounded-md bg-primary/15 px-3 py-1.5 text-xs font-semibold text-primary' : 'rounded-md px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-high/60'}>How to read this</button>
      </div>

      <div className="p-3">
        {tab === TAB.AREA ? (
          <div className="flex flex-col gap-3 text-xs">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant/60">Authorized district</div>
              <div className="mt-0.5 flex items-center gap-2 text-lg font-bold text-on-surface"><span className="h-2.5 w-2.5 rounded-sm bg-primary/30 ring-1 ring-primary" />{authorizedDistrict}</div>
              <div className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-outline-variant/15 bg-surface-container-lowest/35 p-2">
                <div className="min-w-0"><div className="text-[9px] uppercase tracking-wide text-on-surface-variant/50">Current area</div><div className="truncate font-mono text-[10.5px] text-on-surface" title={area?.farmId}>{area?.farmId ?? 'Matara district scope'}</div></div>
                <div className="min-w-0 text-right"><div className="text-[9px] uppercase tracking-wide text-on-surface-variant/50">Farm coordinates</div><div className="truncate font-mono text-[10.5px] text-on-surface" title={coordinates}>{coordinates}</div></div>
              </div>
            </div>
            <dl className="divide-y divide-outline-variant/10 border-t border-outline-variant/10">
              <Row label="Active date" value={activeDate ? formatDisplayDate(activeDate) : 'Date unavailable'} />
              <Row label="Current frame" value={`${activeIndex + 1} of 14`} />
              <Row label="District risk" value={districtRisk?.toUpperCase() ?? 'Unavailable'} valueClassName="uppercase" />
              <Row label="Active influencing origins" value={influencingCount} />
              <Row label="Projected spread" value={`${projectedPathCount} active path${projectedPathCount === 1 ? '' : 's'}`} />
              <Row label="Verified cases mapped" value={verifiedClinicalCount} />
              <Row label="Local overlap" value={overlapRiskLevel ? `${overlapRiskLevel.toUpperCase()} qualitative overlap` : 'Not active at this frame'} />
              <Row label="Focused verified case" value={focusedCaseId ?? 'All cases'} />
            </dl>
            {districtRisk && <div className="rounded-lg border px-3 py-2 text-[10.5px]" style={{ borderColor: `${districtRiskColor(districtRisk)}55`, backgroundColor: `${districtRiskColor(districtRisk)}12`, color: districtRiskColor(districtRisk) }}>Map contours and the highlighted chart bar use this same qualitative district-risk frame.</div>}
          </div>
        ) : (
          <ul className="flex flex-col gap-2.5 text-xs text-on-surface-variant">
            <li className="rounded-lg border border-outline-variant/15 bg-surface-container-lowest/40 p-2.5 leading-relaxed">Red markers are existing verified cases at their real stored farm coordinates. They do not move.</li>
            <li className="rounded-lg border border-violet-400/20 bg-violet-400/[0.06] p-2.5 leading-relaxed">Purple lines and fronts are deterministic frontend presentation projections for the selected Sep date, not confirmed future cases.</li>
            <li className="rounded-lg border border-outline-variant/15 bg-surface-container-lowest/40 p-2.5 leading-relaxed">Green, yellow, orange and red fields are qualitative presentation contours. Explicit overlap can raise local severity without asserting a medical probability.</li>
          </ul>
        )}
      </div>
    </section>
  )
}
