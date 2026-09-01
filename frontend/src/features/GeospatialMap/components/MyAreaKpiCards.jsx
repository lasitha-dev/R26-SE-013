import React from 'react'

import { AREA_RISK_COLORS } from '../adapters/myAreaPresentationForecast'
import { formatDisplayDate } from '../adapters/forecastDate'

function KpiCard({ icon, label, value, valueClassName = 'text-on-surface', valueTitle, sublabel, accent }) {
  return (
    <div className="flex h-[92px] min-w-0 flex-1 basis-[180px] flex-col gap-1 overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 p-2.5 shadow-card-subtle">
      <div className="flex items-start justify-between gap-2">
        <div className="truncate text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant/70" title={label}>{label}</div>
        <span aria-hidden="true" className={`material-symbols-outlined shrink-0 text-[16px] ${accent ?? 'text-on-surface-variant/50'}`}>{icon}</span>
      </div>
      <div className={`truncate text-base font-bold leading-tight ${valueClassName}`} title={valueTitle ?? value}>{value}</div>
      <div className="mt-auto truncate text-[10px] leading-tight text-on-surface-variant/60" title={sublabel}>{sublabel}</div>
    </div>
  )
}

function riskColor(level) {
  if (level === 'low') return AREA_RISK_COLORS.green
  if (level === 'moderate') return AREA_RISK_COLORS.yellow
  if (level === 'elevated') return AREA_RISK_COLORS.orange
  return AREA_RISK_COLORS.red
}

export default function MyAreaKpiCards({
  areaDistrictLabel = 'Matara',
  districtRisk,
  activeDate,
  influencingCaseCount,
  verifiedClinicalCount,
  nationalCount,
  nationalStatus,
  diseaseShortLabel,
}) {
  const nationalValue = nationalStatus === 'loading' ? '...' : nationalStatus === 'error' ? 'UNAVAILABLE' : String(nationalCount ?? 0)
  return (
    <div className="flex flex-wrap gap-2.5">
      <KpiCard icon="radar" label={`My area risk (${areaDistrictLabel})`} value={districtRisk?.toUpperCase() ?? 'WAITING'} valueClassName="text-on-surface" valueTitle={districtRisk} sublabel={activeDate ? formatDisplayDate(activeDate) : 'Waiting for Sep frame'} accent="text-primary" />
      <KpiCard icon="calendar_month" label="Future risk window" value="01-14 SEP" sublabel="14 synchronized presentation frames" accent="text-amber-300" />
      <KpiCard icon="hub" label="Influencing verified cases" value={String(influencingCaseCount)} sublabel="Real coordinate anchors in Matara" accent="text-violet-300" />
      <KpiCard icon="medical_information" label="Mapped verified cases" value={String(verifiedClinicalCount)} sublabel="Fixed red markers" accent="text-rose-300" />
      <KpiCard icon="public" label="National situation" value={nationalValue} sublabel={nationalStatus === 'error' ? 'Layer unreachable' : `${diseaseShortLabel ?? ''} origins nationally`.trim()} accent="text-on-surface-variant" />
      {districtRisk && <span className="sr-only" style={{ color: riskColor(districtRisk) }}>{districtRisk} risk color</span>}
    </div>
  )
}
