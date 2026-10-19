import React from 'react'

function KpiCard({ icon, label, value, valueClassName = 'text-on-surface', valueTitle, sublabel, accent }) {
  return (
    <div className="flex h-[92px] min-w-0 flex-1 basis-[180px] flex-col gap-1 overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 p-2.5 shadow-card-subtle">
      <div className="flex items-start justify-between gap-2">
        <div className="truncate text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant/70" title={label}>{label}</div>
        <span aria-hidden="true" className={`material-symbols-outlined shrink-0 text-[16px] ${accent ?? 'text-on-surface-variant/50'}`}>{icon}</span>
      </div>
      <div className={`truncate text-base font-bold leading-tight ${valueClassName}`} title={valueTitle ?? String(value)}>{value}</div>
      {sublabel && <div className="mt-auto truncate text-[10px] leading-tight text-on-surface-variant/60" title={sublabel}>{sublabel}</div>}
    </div>
  )
}

/** Five compact KPI cards. The page builds them from the same state as the
 * map, chart and Area Intelligence (mode + selected frame / observed date). */
export default function MyAreaKpiCards({ cards = [] }) {
  return (
    <div className="flex flex-wrap gap-2.5" aria-label="My Area key figures">
      {cards.map((card) => <KpiCard key={card.id ?? card.label} {...card} />)}
    </div>
  )
}
