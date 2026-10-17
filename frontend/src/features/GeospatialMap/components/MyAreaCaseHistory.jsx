import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'

const MAX_BAR_HEIGHT_PERCENT = 72

/**
 * Verified Cases mode chart: real reports per real date (Asia/Colombo
 * verification date for verified reports, report date for pending ones).
 * Observed history only -- no model dates, no forecast, no movement.
 */
export default function MyAreaCaseHistory({ areaLabel = 'My district', history = [], activeIndex = 0, onSelectIndex, diseaseShortLabel = '' }) {
  const max = Math.max(1, ...history.map((h) => h.verified + h.pending))
  return (
    <section className="rounded-xl border border-outline-variant/30 bg-surface-container/70 p-3 shadow-card-subtle" aria-labelledby="case-history-title">
      <div className="flex items-center justify-between gap-2">
        <div id="case-history-title" className="truncate text-sm font-semibold text-on-surface">Observed Case History — {areaLabel}</div>
        <div className="shrink-0 text-[10px] font-mono uppercase tracking-wide text-on-surface-variant/50">{history.length} report date{history.length === 1 ? '' : 's'}</div>
      </div>
      {history.length === 0 ? (
        <div className="mt-2 text-[11px] text-on-surface-variant">No {diseaseShortLabel} report with a usable date in this district.</div>
      ) : (
        <div className="mt-3 grid h-[130px] items-end gap-1.5" style={{ gridTemplateColumns: `repeat(${history.length}, minmax(0, 72px))` }} role="group" aria-label={`${areaLabel} reports by observed date`}>
          {history.map((h, index) => {
            const active = index === activeIndex
            const total = h.verified + h.pending
            const label = `${formatDisplayDate(h.date)} - ${h.verified} verified, ${h.pending} pending`
            return (
              <button key={h.date} type="button" aria-label={label} title={label} aria-current={active ? 'date' : undefined} onClick={() => onSelectIndex?.(index)}
                className={`flex h-full min-w-0 flex-col items-center justify-end gap-1 rounded-md border px-1 pb-1 ${active ? 'border-primary/70 bg-primary/[0.06]' : 'border-transparent hover:bg-white/[0.03]'} ${index > activeIndex ? 'opacity-40' : ''}`}>
                <span className="text-[9px] font-bold text-on-surface">{total}</span>
                <span className="flex h-[80px] w-full items-end overflow-hidden rounded-sm bg-surface-container-lowest/55">
                  <span className="flex w-full flex-col-reverse" style={{ height: `${(total / max) * MAX_BAR_HEIGHT_PERCENT + 8}%` }}>
                    {h.verified > 0 && <span className="block w-full bg-[#EF4444]" style={{ height: `${(h.verified / total) * 100}%` }} />}
                    {h.pending > 0 && <span className="block w-full border border-[#d97706] bg-[#d97706]/25" style={{ height: `${(h.pending / total) * 100}%` }} />}
                  </span>
                </span>
                <span className={`text-center text-[8px] font-semibold leading-tight ${active ? 'text-primary' : 'text-on-surface-variant/60'}`}>{formatDisplayDate(h.date)}</span>
              </button>
            )
          })}
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[9.5px] text-on-surface-variant/65">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-[#EF4444]" />Vet-verified report</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm border border-[#d97706]" />Pending verification</span>
        <span className="ml-auto">Real report dates only · selecting a date shows cases recorded up to it · cases never move</span>
      </div>
    </section>
  )
}
