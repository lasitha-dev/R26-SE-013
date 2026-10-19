import React from 'react'

import { CASE_AGE_COLOR, caseAgeText } from '../adapters/caseAge'
import { alertText } from '../context/useNewCaseAlerts'
import { formatDisplayDate } from '../adapters/forecastDate'
import { sriLankaDateKey } from '../adapters/verificationTime'
import { TIER_COLOR, TIER_DISPLAY } from '../adapters/spatialStory'

/**
 * Compact in-map chrome for the National Map: a stacked status line, the
 * risk-cell detail card and the "choose an analysis date" bar. Presentation only -- every value is passed
 * in from real backend/operational data by `OutbreakMapPage.jsx`.
 */

const CARD = 'pointer-events-auto rounded-xl border border-white/10 bg-[#0b1326]/90 shadow-[0_18px_40px_-18px_rgba(2,6,23,0.9)] backdrop-blur-md'

/** Non-overlapping status messages, one per line, never covering controls. */
export function MapStatusStack({ items }) {
  const visible = (items ?? []).filter(Boolean)
  if (visible.length === 0) return null
  return (
    <div className="pointer-events-none flex flex-col items-start gap-1.5">
      {visible.map((item) => (
        <div key={item.key} className={`${CARD} flex max-w-[22rem] items-center gap-2 px-2.5 py-1.5 text-[11px] leading-snug text-slate-300`} role="status" title={item.title}>
          {item.tone === 'loading' && <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-primary" />}
          {item.tone === 'ok' && <span aria-hidden="true" className="shrink-0 text-emerald-400">✓</span>}
          {item.tone === 'warn' && <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />}
          <span>{item.text}</span>
        </div>
      ))}
    </div>
  )
}

/** Detail card for a clicked 5 km risk cell (values from the backend cell). */
export function RiskCellCard({ cell, story, onClose }) {
  if (!cell) return null
  return (
    <div className={`${CARD} w-[17rem] px-3.5 py-3`} role="dialog" aria-label="Risk cell details">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[9.5px] font-extrabold uppercase tracking-[0.14em] text-slate-400">{cell.layerRole === 'SCORED_LAND_WITHIN_NOMINAL_REACH' ? 'Monitoring area · selected date' : 'Scientific cell · 5 km'}</div>
          <div className="mt-0.5 flex items-center gap-2 text-[14px] font-bold text-slate-100">
            <span aria-hidden="true" className="h-3 w-3 rounded-[2px]" style={{ backgroundColor: TIER_COLOR[cell.tier] }} />
            {cell.tierLabel} spatial score (within this snapshot)
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close cell details" className="text-slate-400 hover:text-slate-100">
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">close</span>
        </button>
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
        {cell.layerRole === 'SCORED_LAND_WITHIN_NOMINAL_REACH' ? <><dt className="text-slate-400">Scored land within reach</dt><dd className="text-right tabular-nums text-slate-100">{Number.isFinite(cell.areaKm2) ? `${cell.areaKm2.toFixed(1)} km²` : 'Unavailable'}</dd></> : <><dt className="text-slate-400">C0 score</dt><dd className="text-right tabular-nums text-slate-100">{Number.isFinite(cell.score) ? cell.score.toFixed(3) : '—'}</dd></>}
        <dt className="text-slate-400">Day</dt><dd className="text-right text-slate-100">Day {cell.day} · {formatDisplayDate(cell.date)}</dd>
        <dt className="text-slate-400">Within nominal reach</dt><dd className="text-right text-slate-100">{cell.inReach ? 'Yes' : cell.day === 0 ? 'Reach starts Day 1' : 'Not yet'}</dd>
        <dt className="text-slate-400">Score fixed as of</dt><dd className="text-right text-slate-100">{story?.asOf ? formatDisplayDate(story.asOf) : '—'}</dd>
      </dl>
      <p className="mt-2 text-[10px] leading-snug text-slate-400">
        Relative ranking of proximity to {story?.sources?.length ?? 'the'} source case{story?.sources?.length === 1 ? '' : 's'} (C0 kernel, 25 km). Not an infection probability, not a control zone.
      </p>
    </div>
  )
}

/** Bottom bar when no model output exists for the analysis date: a clear
 * path to a real date, never an inert animation. */
export function TimelineChooserDock({ title, body, options, currentId, onChoose }) {
  const choices = (options ?? []).filter((option) => option.id !== currentId)
  return (
    <div className={`${CARD} flex w-[min(980px,calc(100vw-2rem))] flex-wrap items-center gap-3 px-4 py-3`} role="group" aria-label="Spatial timeline unavailable for this analysis date">
      <span aria-hidden="true" className="material-symbols-outlined text-[22px] text-slate-400">timeline</span>
      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] font-bold text-slate-100">{title}</div>
        <div className="text-[11px] leading-snug text-slate-400">{body}</div>
      </div>
      {choices.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {choices.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => onChoose(option.id)}
              className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-[12px] font-semibold text-primary transition-colors hover:bg-primary/20"
              title={option.description}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/** Detail card for a clicked national case marker (privacy-reduced record). */
export function NationalCaseCard({ record, onClose, ageReferenceLabel = null }) {
  if (!record) return null
  const verified = record.verificationStatus === 'VERIFIED'
  const ageColor = CASE_AGE_COLOR[record.ageClass] ?? CASE_AGE_COLOR.DATE_UNKNOWN
  const date = (iso) => {
    const day = sriLankaDateKey(iso) // Asia/Colombo calendar date of the instant
    return day ? formatDisplayDate(day) : '—'
  }
  return (
    <div className={`${CARD} w-[17rem] px-3.5 py-3`} role="dialog" aria-label="Case details">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[9.5px] font-extrabold uppercase tracking-[0.14em] text-slate-400">Reported case · {record.disease}</div>
          <div className="mt-0.5 flex items-center gap-2 text-[14px] font-bold text-slate-100">
            <span aria-hidden="true" className={verified ? 'h-3 w-3 rounded-full border-2 border-white' : 'h-3 w-3 rounded-full border-2 border-amber-500'} style={{ backgroundColor: ageColor, opacity: verified ? 1 : 0.75 }} />
            {verified ? 'Vet-verified case' : 'Pending verification'}
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close case details" className="text-slate-400 hover:text-slate-100">
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">close</span>
        </button>
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
        <dt className="text-slate-400">Reported</dt><dd className="text-right text-slate-100">{date(record.reportedAt)}</dd>
        {record.recordKey && <><dt className="text-slate-400">Report key</dt><dd className="truncate text-right font-mono text-[10px] text-slate-100" title={record.recordKey}>{record.recordKey}</dd></>}
        <dt className="text-slate-400">Report age</dt><dd className="text-right text-slate-100">{record.ageClass ? caseAgeText({ ageClass: record.ageClass, ageDays: Number.isFinite(record.ageDays) ? record.ageDays : null }) : '—'}</dd>
        {Number(record.count) > 1 && <><dt className="text-slate-400">Reports here</dt><dd className="text-right tabular-nums text-slate-100">{record.count} (latest shown)</dd></>}
        <dt className="text-slate-400">Verified</dt><dd className="text-right text-slate-100">{verified ? date(record.verifiedAt) : 'Not yet'}</dd>
        <dt className="text-slate-400">District</dt><dd className="text-right text-slate-100">{record.district ?? '—'}</dd>
        <dt className="text-slate-400">Severity · stage</dt><dd className="text-right text-slate-100">{[record.severity, record.stage].filter(Boolean).join(' · ') || '—'}</dd>
        <dt className="text-slate-400">Diagnostic confidence</dt><dd className="text-right tabular-nums text-slate-100">{Number.isFinite(record.modelConfidence) ? `${Math.round(record.modelConfidence * 100)}%` : '—'}</dd>
        <dt className="text-slate-400">Location</dt><dd className="text-right text-slate-100">{record.locationQuality === 'FARM_GPS' ? 'Farm GPS' : 'Not available'}</dd>
        <dt className="text-slate-400">Source</dt><dd className="text-right text-slate-100">ADRS diagnostic case</dd>
      </dl>
      {ageReferenceLabel && <p className="mt-2 text-[10px] leading-snug text-slate-400">{ageReferenceLabel}. Colour = days since the case was reported; no onset date is recorded.</p>}
      {!verified && <p className="mt-2 text-[10px] leading-snug text-amber-200/90">Pending report; it has not been verified by a veterinarian.</p>}
    </div>
  )
}

/** Toasts for newly reported / newly verified cases (from the real national
 * case records; see context/useNewCaseAlerts.js). */
export function NewCaseToasts({ alerts = [], onView = null, onDismiss }) {
  if (!alerts.length) return null
  return (
    <div className="pointer-events-none flex w-[18rem] max-w-[calc(100vw-2rem)] flex-col gap-2" role="status" aria-live="polite" aria-label="New case alerts">
      {alerts.map((alert) => {
        const r = alert.record ?? {}
        const mappable = Number.isFinite(r.latitude) && Number.isFinite(r.longitude)
        const reported = sriLankaDateKey(r.reported_at)
        return (
          <div key={alert.id} className={`${CARD} pointer-events-auto flex items-start gap-2 px-3 py-2`}>
            <span aria-hidden="true" className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${alert.kind === 'NEW_CASE' ? 'animate-pulse bg-red-500' : 'bg-emerald-400'}`} />
            <div className="min-w-0 flex-1">
              <div className="text-[11.5px] font-bold text-slate-100">{alertText(alert)}</div>
              <div className="text-[10px] text-slate-400">{reported ? `Reported ${formatDisplayDate(reported)}` : 'Report date not recorded'}{mappable ? '' : ' · no farm GPS (not placed)'}</div>
            </div>
            {mappable && onView && <button type="button" onClick={() => onView(alert)} className="shrink-0 text-[11px] font-semibold text-emerald-300 hover:underline">View</button>}
            <button type="button" onClick={() => onDismiss(alert.id)} aria-label="Dismiss alert" className="shrink-0 text-slate-400 hover:text-slate-100">
              <span aria-hidden="true" className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
