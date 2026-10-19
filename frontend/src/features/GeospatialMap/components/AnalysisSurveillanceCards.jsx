import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
const COMPASS16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
const VERIFIED = '#e5383b'
const PENDING = '#8b8f99'

export function shortDay(key) {
  const [, m, d] = String(key ?? '').split('-')
  return key ? `${d} ${MONTHS[Number(m) - 1] ?? m}` : '—'
}
export function compass16(bearing) {
  return `${COMPASS16[Math.round((((bearing % 360) + 360) % 360) / 22.5) % 16]} ${Math.round(bearing)}°`
}

export function Card({ title, subtitle = null, right = null, children, label = undefined }) {
  return (
    <section className="rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" aria-label={label ?? title}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 pb-2 pt-3.5">
        <div className="min-w-0">
          <h3 className="text-[15px] font-bold text-on-surface">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[12px] text-on-surface-variant/65">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  )
}

export function KpiCard({ label, value, sub, loading = false, name }) {
  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-outline-variant/30 bg-surface-container/70 px-4 py-3.5 shadow-card-subtle" data-kpi={name}>
      <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-on-surface-variant/65">{label}</div>
      {loading
        ? <div className="mt-2 h-7 w-1/2 animate-pulse rounded bg-white/10" />
        : <div className="mt-1.5 truncate text-[26px] font-bold leading-tight text-on-surface" data-value={name}>{value}</div>}
      <div className="mt-1.5 text-[12px] leading-snug text-on-surface-variant/65">{loading ? 'Loading current surveillance data…' : sub}</div>
    </div>
  )
}

export function SegmentedControl({ options, value, onChange, label, size = 'md' }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-[11.5px]' : 'px-4 py-1.5 text-[13px]'
  return (
    <div className="inline-flex gap-1 rounded-lg border border-outline-variant/25 bg-surface-container-lowest/60 p-1" role="group" aria-label={label}>
      {options.map(([id, text]) => (
        <button key={id} type="button" aria-pressed={value === id} onClick={() => onChange(id)}
          className={`rounded-md font-bold transition ${pad} ${value === id ? 'bg-primary text-on-primary shadow' : 'text-on-surface-variant hover:text-on-surface'}`}>
          {text}
        </button>
      ))}
    </div>
  )
}

/** Stacked verified (red) + pending (grey) reports per day. */
export function ActivityChart({ days }) {
  const max = Math.max(4, ...days.map((d) => d.verified + d.pending))
  const step = Math.max(1, Math.ceil(max / 4))
  const top = Math.ceil(max / step) * step
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step)
  const every = Math.max(1, Math.ceil(days.length / 8))
  return (
    <div className="px-4 pb-3">
      <div className="relative flex h-[230px] pl-7" role="img" aria-label="Reported clinical cases per day, verified and pending">
        {ticks.map((t) => (
          <div key={t} className="pointer-events-none absolute left-7 right-0 flex items-center" style={{ bottom: `calc(22px + ${(t / top) * (230 - 30)}px)` }}>
            <span className="absolute -left-7 w-5 text-right font-mono text-[9.5px] text-on-surface-variant/55">{t}</span>
            <span className={`h-px w-full ${t === 0 ? 'bg-white/15' : 'bg-white/[0.05]'}`} />
          </div>
        ))}
        <div className="relative grid w-full items-end" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}>
          {days.map((d, i) => {
            const total = d.verified + d.pending
            const h = (v) => `${(v / top) * (230 - 30)}px`
            return (
              <div key={d.date} className="flex h-full flex-col items-center justify-end" data-day={d.date}>
                <div className="flex w-[56%] max-w-[26px] flex-col-reverse" title={`${formatDisplayDate(d.date)} · ${d.verified} verified · ${d.pending} pending`}>
                  {d.verified > 0 && <span className="block w-full rounded-[2px]" style={{ height: h(d.verified), backgroundColor: VERIFIED }} data-bar="verified" />}
                  {d.pending > 0 && <span className="block w-full rounded-[2px]" style={{ height: h(d.pending), backgroundColor: PENDING }} data-bar="pending" />}
                  {total === 0 && <span className="block h-0" />}
                </div>
                <span className="mt-1.5 h-[14px] whitespace-nowrap font-mono text-[9.5px] text-on-surface-variant/55">{i % every === 0 || i === days.length - 1 ? shortDay(d.date) : ''}</span>
              </div>
            )
          })}
        </div>
      </div>
      <div className="mt-2 flex gap-4 text-[12px] text-on-surface-variant/80">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: VERIFIED }} />Verified</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PENDING }} />Pending</span>
      </div>
    </div>
  )
}

const th = 'px-4 py-2.5 text-left font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-on-surface-variant/55'
const td = 'px-4 py-3 text-[13px] text-on-surface'

export function AffectedAreasTable({ rows, windowDays, emptyText }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse" aria-label="Most affected areas">
        <thead><tr className="border-b border-white/5">{['District', 'Records', 'Verified', 'Pending', 'Last observed', `vs previous ${windowDays} d`].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.length === 0 ? <tr><td colSpan={6} className="px-4 py-6 text-center text-[12px] text-on-surface-variant/60">{emptyText}</td></tr> : rows.map((r) => (
            <tr key={r.district} className={`border-t border-white/5 ${r.mine ? 'bg-primary/[0.04]' : ''}`} data-district={r.district}>
              <td className={td}>
                <span className="font-medium">{r.district}</span>
                {r.mine && <span className="ml-2 rounded border border-primary/50 px-1.5 py-0.5 font-mono text-[9.5px] font-bold text-primary">MY</span>}
                {Number.isFinite(r.nearestKm) && r.nearestKm > 0 && <span className="ml-2 text-[11px] text-on-surface-variant/55">{r.nearestKm.toFixed(0)} km away</span>}
              </td>
              <td className={`${td} font-bold text-primary`}>{r.records}</td>
              <td className={td}>{r.verified}</td>
              <td className={td}>{r.pending}</td>
              <td className={td}>{r.lastObserved ? formatDisplayDate(r.lastObserved) : '—'}</td>
              <td className={td} data-delta={r.delta}>
                <span style={{ color: r.delta > 0 ? '#fca5a5' : r.delta < 0 ? '#86efac' : undefined }} className={r.delta === 0 ? 'text-on-surface-variant/55' : ''}>
                  {r.delta > 0 ? `▲ ${r.delta}` : r.delta < 0 ? `▼ ${-r.delta}` : '—'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ClusterTable({ rows, emptyText }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse" aria-label="Space-time clusters">
        <thead><tr className="border-b border-white/5">{['Cluster', 'Cases', 'Districts', 'Radius', 'Drift', 'Direction'].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.length === 0 ? <tr><td colSpan={6} className="px-4 py-6 text-center text-[12px] text-on-surface-variant/60">{emptyText}</td></tr> : rows.map((c) => (
            <tr key={c.clusterId} className="border-t border-white/5" data-cluster={c.label}>
              <td className={`${td} font-mono font-bold text-[#2dd4bf]`} title={`${formatDisplayDate(c.startDate)} – ${formatDisplayDate(c.endDate)}`}>{c.label}</td>
              <td className={td}>{c.cases}{c.farms !== null && <span className="ml-1.5 text-[11px] text-on-surface-variant/55">({c.farms} farm{c.farms === 1 ? '' : 's'})</span>}</td>
              <td className={td}>{c.districts.length ? c.districts.join(', ') : '—'}</td>
              <td className={td}>{c.radiusKm !== null ? `${Math.round(c.radiusKm)} km` : '—'}</td>
              <td className={td}>{c.driftKm !== null ? `${Math.round(c.driftKm)} km` : '—'}</td>
              <td className={td}>{c.bearingDeg !== null ? compass16(c.bearingDeg) : <span className="text-on-surface-variant/55">Not supported</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
